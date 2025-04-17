import os
import datetime
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    send_file, jsonify, logging # Added logging if not already present
)
from werkzeug.utils import secure_filename
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF # For PDF generation
from PIL import Image # For image handling
from io import BytesIO # To handle PDF in memory
import re # For parsing badge IDs
import logging # Import standard logging


# --- Configuration ---
# Ensure this path correctly points to the uploads folder relative to this script
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Google Sheet Configuration (MUST REPLACE with your actual details)
GOOGLE_SHEET_ID = ''
SERVICE_ACCOUNT_FILE = 'rssbsneform-57c1113348b0.json'

# Badge Generation Configuration (Consistent across functionalities)
BADGE_CONFIG = {
    "Chandigarh": {
        "CHD-IV (KAJHERI)": {"prefix": "SNE-AH-", "start": 91001, "zone": "ZONE-I"},
        "CHD-! (Sec 27)": {"prefix": "SNE-AH-", "start": 61001, "zone": "ZONE-I"},
    },
    "Mullanpur Garibdass": {
         "Zirakpur": {"prefix": "SNE-AX-", "start": 171001, "zone": "ZONE-III"},
    }
    # Add more areas/centres as needed
}

# Dropdown Data (Consistent across functionalities)
AREAS = list(BADGE_CONFIG.keys())
CENTRES = sorted(list(set(centre for area_centres in BADGE_CONFIG.values() for centre in area_centres.keys()))) # Unique, sorted list
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
] # Add more as needed
RELATIONS = ["Spouse", "Father", "Mother", "Brother", "Sister", "Neighbor", "In Laws", "Others"]


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'a_very_strong_combined_secret_key_change_it' # Change this!
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- Google Sheet Helper Functions ---

def get_sheet(read_only=False):
    """Authenticates and returns the Google Sheet worksheet object."""
    try:
        if read_only:
            scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        else:
            scopes = ['https://www.googleapis.com/auth/spreadsheets']

        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1 # Assuming data is in the first sheet
        return sheet
    except FileNotFoundError:
        app.logger.error(f"Service account file not found at {SERVICE_ACCOUNT_FILE}")
        raise Exception(f"Service account file not found at {SERVICE_ACCOUNT_FILE}")
    except gspread.exceptions.SpreadsheetNotFound:
        app.logger.error(f"Spreadsheet not found with ID: {GOOGLE_SHEET_ID}")
        raise Exception(f"Spreadsheet not found with ID: {GOOGLE_SHEET_ID}. Check ID and permissions.")
    except Exception as e:
        app.logger.error(f"Error accessing Google Sheet: {e}")
        raise Exception(f"Could not connect to Google Sheet: {e}")

def get_all_sheet_data():
    """Gets all data from the sheet as list of dictionaries."""
    try:
        sheet = get_sheet(read_only=True)
        data = sheet.get_all_records() # Assumes first row is header
        app.logger.info(f"Successfully fetched {len(data)} records from Google Sheet.")
        return data
    except Exception as e:
        # Logged in get_sheet
        raise Exception(f"Could not get sheet data: {e}")


def check_aadhaar_exists(sheet, aadhaar, area):
    """Checks if Aadhaar already exists for the given Area in the sheet."""
    # (Same implementation as before - using get_all_records now preferred)
    try:
        all_records = sheet.get_all_records() # Use passed sheet object
        aadhaar_col_header = 'Aadhaar No' # Check header name in your sheet
        area_col_header = 'Area'       # Check header name in your sheet
        for record in all_records:
            if str(record.get(aadhaar_col_header, '')).strip() == str(aadhaar).strip() and \
               record.get(area_col_header, '').strip() == area.strip():
                return True
        return False
    except Exception as e:
        app.logger.error(f"Error checking Aadhaar in Google Sheet: {e}")
        flash("Warning: Could not verify Aadhaar uniqueness due to sheet access error.", "warning")
        return False


def get_next_badge_id(sheet, area, centre):
    """Generates the next sequential Badge ID for the Area/Centre."""
    # (Same implementation as before - using passed sheet object)
    if area not in BADGE_CONFIG or centre not in BADGE_CONFIG[area]:
        raise ValueError("Invalid Area or Centre selected for Badge ID generation.")

    config = BADGE_CONFIG[area][centre]
    prefix = config["prefix"]
    start_num = config["start"]

    try:
        badge_id_col_header = 'Badge ID' # IMPORTANT: Check header name in your sheet
        all_records = sheet.get_all_records()
        max_num = start_num - 1

        for record in all_records:
            existing_id = str(record.get(badge_id_col_header, '')).strip()
            if existing_id.startswith(prefix):
                try:
                    num_part = int(existing_id[len(prefix):])
                    if num_part > max_num:
                        max_num = num_part
                except ValueError:
                    continue # Ignore malformed IDs

        next_num = max(start_num, max_num + 1)
        return f"{prefix}{next_num}"

    except Exception as e:
        app.logger.error(f"Error generating next Badge ID from Google Sheet: {e}")
        raise Exception(f"Could not generate Badge ID due to sheet access error: {e}")


# --- File Upload Helper ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --- PDF Generation Class & Function ---
# Badge Layout Constants (Approximate - Adjust as needed)
BADGE_WIDTH_MM = 85
BADGE_HEIGHT_MM = 54 # Standard credit card size (approx)
PAGE_WIDTH_MM = 210 # A4 width
PAGE_HEIGHT_MM = 297 # A4 height
MARGIN_MM = 10
PHOTO_X = 28
PHOTO_Y = 17
PHOTO_W = 25
PHOTO_H = 25 # Assuming square photo area

class PDF(FPDF):
    # (Same implementation as in app_printer.py)
    def header(self):
        pass
    def footer(self):
        pass
    def add_badge(self, data):
        # --- Get required data with fallbacks ---
        badge_id = str(data.get('Badge ID', 'N/A'))
        first_name = str(data.get('First Name', '')).upper()
        last_name = str(data.get('Last Name', '')).upper()
        full_name = f"{first_name} {last_name}".strip()
        gender = str(data.get('Gender', '')).upper()
        age = str(data.get('Age', ''))
        age_display = f"AGE: {age} YEARS" if age else ""
        # Assuming Centre name maps to Satsang Place
        centre = str(data.get('Satsang Place / Centre', ''))
        area = str(data.get('Area', '')).upper()
        photo_filename = data.get('Photo Filename', '')
        # address = str(data.get('Address', '')) # For potential back side
        # mobile = str(data.get('Mobile No', '')) # For potential back side

        # Attempt to get Zone from config
        zone = "ZONE" # Default
        for area_key, centres_dict in BADGE_CONFIG.items():
             if area_key == data.get('Area'):
                 if centre in centres_dict and "zone" in centres_dict[centre]:
                     zone = centres_dict[centre]["zone"]
                     break

        # --- Draw Badge Elements ---
        start_x = self.get_x()
        start_y = self.get_y()
        self.set_line_width(0.3)
        self.set_draw_color(0, 0, 0) # Black
        self.rect(start_x, start_y, BADGE_WIDTH_MM, BADGE_HEIGHT_MM)

        self.set_font('Arial', 'B', 8)
        self.set_xy(start_x + 5, start_y + 3)
        self.cell(BADGE_WIDTH_MM - 10, 3, 'RADHA SOAMI SATSANG BEAS', align='C')
        self.set_xy(start_x + 5, start_y + 6)
        self.cell(BADGE_WIDTH_MM - 10, 3, zone, align='C')

        self.set_font('Arial', 'B', 7)
        self.set_fill_color(220, 220, 220)
        self.set_xy(start_x + 2, start_y + 10)
        self.cell(BADGE_WIDTH_MM - 4, 4, 'SPECIAL NEEDS ENCLOSURE', border=1, align='C', fill=True)

        photo_path = os.path.join(UPLOAD_FOLDER, photo_filename) if photo_filename and photo_filename not in ['N/A', 'Upload Error', ''] else None
        placeholder_x = start_x + PHOTO_X
        placeholder_y = start_y + PHOTO_Y
        if photo_path and os.path.exists(photo_path):
            try:
                # self.image(photo_path, placeholder_x, placeholder_y, PHOTO_W, PHOTO_H) # Simple placement
                 # Preserve aspect ratio within bounds
                with Image.open(photo_path) as img:
                    img.thumbnail((PHOTO_W * 3, PHOTO_H * 3)) # Use higher res factor
                    width_ratio = PHOTO_W / img.width
                    height_ratio = PHOTO_H / img.height
                    scale_ratio = min(width_ratio, height_ratio)
                    new_width = img.width * scale_ratio
                    new_height = img.height * scale_ratio
                    # Center the image within the placeholder bounds
                    img_x = placeholder_x + (PHOTO_W - new_width) / 2
                    img_y = placeholder_y + (PHOTO_H - new_height) / 2
                    self.image(photo_path, img_x, img_y, new_width, new_height)

            except Exception as e:
                app.logger.warning(f"Could not process image {photo_filename}: {e}")
                self.set_fill_color(200, 200, 200); self.rect(placeholder_x, placeholder_y, PHOTO_W, PHOTO_H, 'FD') # Placeholder
        else:
             self.set_fill_color(200, 200, 200); self.rect(placeholder_x, placeholder_y, PHOTO_W, PHOTO_H, 'FD') # Placeholder
             self.set_font('Arial', 'I', 6); self.set_text_color(100,100,100)
             self.set_xy(placeholder_x, placeholder_y + PHOTO_H/2 -1); self.cell(PHOTO_W, 3, "No Photo", align='C'); self.set_text_color(0,0,0)

        current_x = start_x + 3
        current_y = start_y + PHOTO_Y + PHOTO_H + 3

        self.set_font('Arial', 'B', 8); self.set_xy(current_x, current_y); self.cell(40, 4, badge_id); current_y += 4
        self.set_font('Arial', '', 7); self.set_xy(current_x, current_y); self.cell(40, 3.5, full_name); current_y += 3.5
        self.set_xy(current_x, current_y); self.cell(40, 3.5, gender); current_y += 3.5
        self.set_xy(current_x, current_y); self.cell(40, 3.5, age_display); current_y += 3.5
        self.set_xy(current_x, current_y); self.cell(40, 3.5, area); current_y += 3.5

        self.set_line_width(0.1)
        sig_y = start_y + BADGE_HEIGHT_MM - 5
        self.line(start_x + 5, sig_y, start_x + BADGE_WIDTH_MM - 5, sig_y)
        self.set_font('Arial', 'I', 6)
        self.set_xy(start_x + 5, sig_y + 0.5)
        self.cell(BADGE_WIDTH_MM - 10, 3, 'Area Secretary', align='C')


def create_badge_pdf(badge_data_list):
    """Generates a PDF document with multiple badges."""
    # (Same implementation as in app_printer.py)
    pdf = PDF(orientation='P', unit='mm', format='A4') # Portrait A4
    pdf.set_auto_page_break(auto=False, margin=MARGIN_MM)
    pdf.add_page()

    # Calculate how many badges fit per page
    # Adjust spacing if needed (e.g., add a small gap between badges)
    gap_mm = 2 # Small gap between badges
    effective_badge_width = BADGE_WIDTH_MM + gap_mm
    effective_badge_height = BADGE_HEIGHT_MM + gap_mm
    badges_per_row = int((PAGE_WIDTH_MM - 2 * MARGIN_MM + gap_mm) / effective_badge_width)
    badges_per_col = int((PAGE_HEIGHT_MM - 2 * MARGIN_MM + gap_mm) / effective_badge_height)

    col_num = 0
    row_num = 0

    for data in badge_data_list:
        if col_num >= badges_per_row:
            col_num = 0
            row_num += 1
            if row_num >= badges_per_col:
                row_num = 0
                pdf.add_page()

        x_pos = MARGIN_MM + col_num * effective_badge_width
        y_pos = MARGIN_MM + row_num * effective_badge_height

        pdf.set_xy(x_pos, y_pos)
        pdf.add_badge(data)

        col_num += 1

    pdf_bytes = pdf.output(dest='S') # pdf.output(dest='S') already returns bytes
    return BytesIO(pdf_bytes)


# --- Flask Routes ---

# == Data Entry Routes ==
@app.route('/')
def form():
    """Displays the bio-data entry form."""
    today_date = datetime.date.today()
    return render_template('form.html',
                           today_date=today_date,
                           areas=AREAS,
                           centres=CENTRES,
                           states=STATES,
                           relations=RELATIONS)

@app.route('/submit', methods=['POST'])
def submit_form():
    """Handles bio-data form submission."""
    # (Same implementation as the updated app.py from previous steps)
    # Ensures it uses the shared get_sheet(), check_aadhaar_exists(), get_next_badge_id()
    try:
        sheet = get_sheet(read_only=False) # Need write access
    except Exception as e:
        flash(f"Error connecting to data storage: {e}", "error")
        return redirect(url_for('form')) # Redirect back to data entry form

    try:
        form_data = request.form.to_dict()
        aadhaar_no = form_data.get('aadhaar_no', '').strip()
        selected_area = form_data.get('area', '').strip()
        selected_centre = form_data.get('satsang_place', '').strip()

        # --- Mandatory Field Check ---
        mandatory_fields = ['area', 'satsang_place', 'first_name', 'last_name', 'father_husband_name',
                            'gender', 'dob', 'aadhaar_no', 'emergency_contact_name',
                            'emergency_contact_number', 'emergency_contact_relation', 'address', 'state']
        missing_fields = [field for field in mandatory_fields if not form_data.get(field)]
        if missing_fields:
            flash(f"Missing mandatory fields: {', '.join(missing_fields)}", "error")
            return redirect(url_for('form'))

        # --- Aadhaar Check ---
        if check_aadhaar_exists(sheet, aadhaar_no, selected_area):
            flash(f"Error: Aadhaar number {aadhaar_no} already exists for the Area '{selected_area}'.", "error")
            return redirect(url_for('form'))

        # --- Optional File Upload ---
        photo_filename = "N/A"
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                original_filename = secure_filename(file.filename)
                extension = original_filename.rsplit('.', 1)[1].lower()
                photo_filename = f"{form_data.get('first_name', 'user')}_{form_data.get('last_name', '')}_{timestamp}.{extension}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
                try:
                    file.save(file_path); app.logger.info(f"Photo saved: {photo_filename}")
                except Exception as e:
                    app.logger.error(f"Error saving photo {photo_filename}: {e}"); flash(f"Could not save photo: {e}", "error"); photo_filename = "Upload Error"
            elif file and file.filename != '':
                 flash(f"Invalid file type for photo. Allowed: {', '.join(ALLOWED_EXTENSIONS)}. Photo not saved.", 'warning')

        # --- Generate Badge ID ---
        try:
            new_badge_id = get_next_badge_id(sheet, selected_area, selected_centre)
        except ValueError as e:
             flash(f"Error generating Badge ID: {e}", "error"); return redirect(url_for('form'))
        except Exception as e:
             flash(f"Error generating Badge ID: {e}", "error"); return redirect(url_for('form'))

        # --- Prepare Data Row ---
        # Check your sheet column order - this must match EXACTLY
        data_row = [
            form_data.get('submission_date', datetime.date.today().isoformat()), # 1
            selected_area,                 # 2 Area
            selected_centre,               # 3 Satsang Place/Centre
            form_data.get('first_name', ''), # 4
            form_data.get('last_name', ''),  # 5
            form_data.get('father_husband_name', ''), # 6
            form_data.get('gender', ''),     # 7
            form_data.get('dob', ''),        # 8
            form_data.get('age', ''),        # 9 - Optional
            form_data.get('blood_group', ''),# 10 - Optional
            aadhaar_no,                    # 11 Aadhaar No
            form_data.get('physically_challenged', 'No'), # 12 Default No if not present
            form_data.get('physically_challenged_details', ''), # 13
            form_data.get('help_pickup', 'No'), # 14 Default No
            form_data.get('help_pickup_reasons', ''), # 15
            form_data.get('handicap', 'No'),   # 16 Default No
            form_data.get('stretcher', 'No'),  # 17 Default No
            form_data.get('wheelchair', 'No'), # 18 Default No
            form_data.get('ambulance', 'No'),  # 19 Default No
            form_data.get('pacemaker', 'No'),  # 20 Default No
            form_data.get('chair_sitting', 'No'),# 21 Default No
            form_data.get('special_attendant', 'No'),# 22 Default No
            form_data.get('hearing_loss', 'No'), # 23 Default No
            form_data.get('mobile_no', ''),  # 24 - Optional
            form_data.get('attend_satsang', 'No'), # 25 Default No
            form_data.get('satsang_pickup_help', ''), # 26
            form_data.get('other_requests', ''), # 27
            form_data.get('emergency_contact_name', ''), # 28
            form_data.get('emergency_contact_number', ''), # 29
            form_data.get('emergency_contact_relation', ''), # 30
            form_data.get('address', ''),    # 31
            form_data.get('state', ''),      # 32 State
            form_data.get('pin_code', ''),   # 33 - Optional
            photo_filename,                  # 34 Photo Filename
            new_badge_id                     # 35 Badge ID
        ]

        # --- Append Data to Google Sheet ---
        try:
            sheet.append_row(data_row)
            app.logger.info(f"Data appended successfully. Badge ID: {new_badge_id}")
            flash(f'Data submitted successfully! Your Badge ID is: {new_badge_id}', 'success')
        except Exception as e:
            app.logger.error(f"Error writing to Google Sheet: {e}")
            flash(f'Error submitting data to Google Sheet: {e}. Please try again.', 'error')
            return redirect(url_for('form')) # Redirect back on sheet error

        return redirect(url_for('form')) # Redirect back to entry form after success

    except Exception as e:
        app.logger.error(f"An unexpected error occurred during submission: {e}", exc_info=True)
        flash(f'An unexpected server error occurred: {e}', 'error')
        return redirect(url_for('form'))


# == Badge Printer Routes ==
@app.route('/printer')
def printer():
    """Displays the form to enter badge IDs for printing."""
    return render_template('printer_form.html', centres=CENTRES)


@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    """Fetches data and generates the PDF for selected badges."""
    # (Same implementation as in app_printer.py)
    selected_centre = request.form.get('centre') # Keep centre selection for user clarity/batching
    badge_ids_raw = request.form.get('badge_ids', '')
    badge_ids = [bid.strip() for bid in badge_ids_raw.split(',') if bid.strip()]

    if not badge_ids: flash("Please enter at least one Badge ID.", "error"); return redirect(url_for('printer'))
    # Centre selection optional now for filtering?
    # if not selected_centre: flash("Please select a Centre.", "error"); return redirect(url_for('printer'))

    try:
        all_sheet_data = get_all_sheet_data()
        data_map = {str(row.get('Badge ID', '')): row for row in all_sheet_data if row.get('Badge ID')}
    except Exception as e:
        flash(f"Error fetching data from Google Sheet: {e}", "error"); return redirect(url_for('printer'))

    badges_to_print = []
    not_found_ids = []

    for bid in badge_ids:
        if bid in data_map:
            record = data_map[bid]
            # Optionally add filtering by selected_centre here if needed
            # record_centre = record.get('Satsang Place / Centre', '')
            # if selected_centre and record_centre != selected_centre:
            #     continue # Skip if centre doesn't match selection
            badges_to_print.append(record)
        else:
            not_found_ids.append(bid)

    if not badges_to_print:
        flash("No valid Badge IDs found.", "error")
        if not_found_ids: flash(f"IDs not found: {', '.join(not_found_ids)}", "warning")
        return redirect(url_for('printer'))

    if not_found_ids: flash(f"Warning: The following Badge IDs were not found: {', '.join(not_found_ids)}", "warning")

    try:
        pdf_buffer = create_badge_pdf(badges_to_print)
        pdf_buffer.seek(0)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Badges_{timestamp}.pdf" # Simpler filename

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        app.logger.error(f"Error generating PDF: {e}", exc_info=True)
        flash(f"An error occurred while generating the PDF: {e}", "error")
        return redirect(url_for('printer'))


if __name__ == '__main__':
     logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s:%(funcName)s:%(lineno)d')
     # Ensure debug=False for production deployment
     app.run(debug=True, port=5000) # Run on standard port 5000