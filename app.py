import os
import datetime
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    send_file, jsonify
)
from werkzeug.utils import secure_filename
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont, ImageOps # Added ImageDraw, ImageFont
from io import BytesIO
import re
import logging
import textwrap

# --- Configuration ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
GOOGLE_SHEET_ID = '1M9dHOwtVldpruZoBzH23vWIVdcvMlHTdf_fWJGWVmLM'
SERVICE_ACCOUNT_FILE = 'rssbsneform-57c1113348b0.json'
BADGE_TEMPLATE_PATH = 'static/images/sne_badge.png' # UPDATE if needed
# ---> NEW: Path to font file <---
FONT_PATH = 'static/fonts/arial.ttf' # UPDATE if using a different font/filename

# ---> CRITICAL: Adjust Photo Placement (Pixels) <---
PASTE_X_PX = 825
PASTE_Y_PX = 475
BOX_WIDTH_PX = 525 # UPDATE THIS - Max width for the photo
BOX_HEIGHT_PX = 700 # UPDATE THIS - Max height for the photo

# ---> CRITICAL: Adjust Text Placement, Size (Pixels), Color <---
# Color can be name (e.g., "black", "red") or RGB tuple (e.g., (0, 0, 0))
# Measure coords (top-left X, Y) from your template image!
TEXT_ELEMENTS = {
    "badge_id": {"coords": (100, 1250), "size": 130, "color": (139, 0, 0), "is_bold": True}, # Dark Red Example
    "name":     {"coords": (100, 1500), "size": 110, "color": "black"},
    "gender":   {"coords": (100, 1650), "size": 110, "color": "black"},
    "age":      {"coords": (100, 1800), "size": 110, "color": (139, 0, 0)}, # Dark Red Example
    "area":     {"coords": (100, 1950), "size": 110, "color": "black"},
    "address":  {"coords": (1750, 250), "size": 110, "color": "black", "is_bold": False} # EXAMPLE values - ADJUST!

    # Add/remove/adjust entries as needed based on sne_badge.png layout
}

# Badge Generation Configuration (Keep as needed)
BADGE_CONFIG = { # ... (keep existing config) ...
    "Chandigarh": {
        "CHD-IV (KAJHERI)": {"prefix": "SNE-AH-", "start": 91001, "zone": "ZONE-I"},
        "CHD-! (Sec 27)": {"prefix": "SNE-AH-", "start": 61001, "zone": "ZONE-I"},
    },
    "Mullanpur Garibdass": {
         "Zirakpur": {"prefix": "SNE-AX-", "start": 171001, "zone": "ZONE-III"},
    }
}
# Dropdown Data (Keep as needed)
AREAS = list(BADGE_CONFIG.keys()) # ... etc ...
CENTRES = sorted(list(set(centre for area_centres in BADGE_CONFIG.values() for centre in area_centres.keys())))
STATES = [ # ... keep list ...
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]
RELATIONS = ["Spouse", "Father", "Mother", "Brother", "Sister", "Neighbor", "In Laws", "Others"]

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'a_very_strong_combined_secret_key_change_it'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/images', exist_ok=True)
os.makedirs('static/fonts', exist_ok=True) # Ensure static/fonts exists

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s:%(funcName)s:%(lineno)d')

# --- Google Sheet Helper Functions ---
# (get_sheet, get_all_sheet_data, check_aadhaar_exists, get_next_badge_id - Unchanged)
def get_sheet(read_only=False):
    """Authenticates and returns the Google Sheet worksheet object."""
    try:
        if read_only: scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        else: scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1 # Assuming data is in the first sheet
        return sheet
    except FileNotFoundError: app.logger.error(f"Service account file not found: {SERVICE_ACCOUNT_FILE}"); raise Exception(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
    except gspread.exceptions.SpreadsheetNotFound: app.logger.error(f"Spreadsheet not found: {GOOGLE_SHEET_ID}"); raise Exception(f"Spreadsheet not found. Check ID/permissions: {GOOGLE_SHEET_ID}")
    except Exception as e: app.logger.error(f"Error accessing Google Sheet: {e}"); raise Exception(f"Could not connect to Google Sheet: {e}")

def get_all_sheet_data():
    """Gets all data from the sheet as list of dictionaries."""
    try:
        sheet = get_sheet(read_only=True); data = sheet.get_all_records()
        app.logger.info(f"Fetched {len(data)} records from Google Sheet.")
        return data
    except Exception as e: raise Exception(f"Could not get sheet data: {e}")

def check_aadhaar_exists(sheet, aadhaar, area):
    """Checks if Aadhaar already exists for the given Area in the sheet."""
    try:
        all_records = sheet.get_all_records(); aadhaar_col_header = 'Aadhaar No'; area_col_header = 'Area'
        for record in all_records:
            if str(record.get(aadhaar_col_header, '')).strip() == str(aadhaar).strip() and record.get(area_col_header, '').strip() == area.strip(): return True
        return False
    except Exception as e: app.logger.error(f"Error checking Aadhaar: {e}"); flash("Warning: Could not verify Aadhaar uniqueness.", "warning"); return False

def get_next_badge_id(sheet, area, centre):
    """Generates the next sequential Badge ID for the Area/Centre."""
    if area not in BADGE_CONFIG or centre not in BADGE_CONFIG[area]: raise ValueError("Invalid Area or Centre for Badge ID.")
    config = BADGE_CONFIG[area][centre]; prefix = config["prefix"]; start_num = config["start"]
    try:
        badge_id_col_header = 'Badge ID'; all_records = sheet.get_all_records(); max_num = start_num - 1
        for record in all_records:
            existing_id = str(record.get(badge_id_col_header, '')).strip()
            if existing_id.startswith(prefix):
                try: num_part = int(existing_id[len(prefix):]); max_num = max(max_num, num_part)
                except ValueError: continue
        next_num = max(start_num, max_num + 1); return f"{prefix}{next_num}"
    except Exception as e: app.logger.error(f"Error generating Badge ID: {e}"); raise Exception(f"Could not generate Badge ID: {e}")

# --- File Upload Helper ---
def allowed_file(filename):
    # (Unchanged)
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Badge Generation Function (REVISED for Text Drawing and Address Box) ---

def create_pdf_with_composite_badges(badge_data_list):
    """
    Generates PDF with badges created by pasting photos AND drawing text
    onto a base template image. Adds a box around the address.
    """
    # Layout constants for placing badges on A4 page
    PAGE_WIDTH_MM = 215; PAGE_HEIGHT_MM = 297; BADGE_WIDTH_MM = 70; BADGE_HEIGHT_MM = 50
    MARGIN_MM = 0; gap_mm = 0; effective_badge_width = BADGE_WIDTH_MM + gap_mm
    effective_badge_height = BADGE_HEIGHT_MM + gap_mm
    badges_per_row = int((PAGE_WIDTH_MM - 2 * MARGIN_MM + gap_mm) / effective_badge_width) if effective_badge_width > 0 else 1
    badges_per_col = int((PAGE_HEIGHT_MM - 2 * MARGIN_MM + gap_mm) / effective_badge_height) if effective_badge_height > 0 else 1

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False, margin=MARGIN_MM)
    pdf.add_page()
    col_num = 0
    row_num = 0

    # Load base template image ONCE
    try:
        base_template = Image.open(BADGE_TEMPLATE_PATH).convert("RGBA")
    except FileNotFoundError: app.logger.error(f"Template not found: {BADGE_TEMPLATE_PATH}"); raise Exception(f"Template missing: {BADGE_TEMPLATE_PATH}")
    except Exception as e: app.logger.error(f"Error loading template: {e}"); raise Exception(f"Error loading template: {e}")

    # Load fonts ONCE
    loaded_fonts = {}
    for element, config in TEXT_ELEMENTS.items():
        size = config['size']
        if size not in loaded_fonts:
            try:
                loaded_fonts[size] = ImageFont.truetype(FONT_PATH, size)
            except IOError: app.logger.error(f"Font file not found or cannot be read: {FONT_PATH}"); raise Exception(f"Font file missing or invalid: {FONT_PATH}")
            except Exception as e: app.logger.error(f"Error loading font {FONT_PATH}: {e}"); raise Exception(f"Error loading font: {e}")

    for data in badge_data_list:
        badge_image = None # Ensure variable exists
        try:
            # Create a fresh copy for manipulation
            badge_image = base_template.copy()
            draw = ImageDraw.Draw(badge_image)

            # --- 1. Process and Paste Photo ---
            photo_filename = data.get('Photo Filename', '')
            photo_path = os.path.join(UPLOAD_FOLDER, photo_filename) if photo_filename and photo_filename not in ['N/A', 'Upload Error', ''] else None
            photo_processed_successfully = False

            if photo_path and os.path.exists(photo_path):
                holder_photo = None
                resized_photo = None
                try:
                    holder_photo = Image.open(photo_path).convert("RGBA")
                    resized_photo = holder_photo.resize((BOX_WIDTH_PX, BOX_HEIGHT_PX), Image.Resampling.LANCZOS)
                    paste_pos = (PASTE_X_PX, PASTE_Y_PX)
                    badge_image.paste(resized_photo, paste_pos, resized_photo)
                    photo_processed_successfully = True

                except Exception as e:
                    app.logger.warning(f"Could not process/paste photo {photo_filename} for {data.get('Badge ID', 'N/A')}: {e}")
                finally:
                    if holder_photo: holder_photo.close()
                    if resized_photo: resized_photo.close()

            if not photo_processed_successfully:
                 app.logger.warning(f"Photo not found or processed for {data.get('Badge ID', 'N/A')}")
                 # Optional: Draw a placeholder box if photo fails/missing
                 # draw = ImageDraw.Draw(badge_image)
                 # placeholder_color = (220, 220, 220, 255) # Light grey solid
                 # draw.rectangle([PASTE_X_PX, PASTE_Y_PX, PASTE_X_PX + BOX_WIDTH_PX, PASTE_Y_PX + BOX_HEIGHT_PX], fill=placeholder_color)

            # --- 2. Draw Text Details ---
            details_to_draw = {
                "badge_id": str(data.get('Badge ID', 'N/A')),
                "name": f"{str(data.get('First Name', '')).upper()} {str(data.get('Last Name', '')).upper()}".strip(),
                "gender": str(data.get('Gender', '')).upper(),
                "age": f"AGE: {data.get('Age', '')} YEARS" if data.get('Age') else "",
                "area": str(data.get('Area', '')).upper(),
                "address": str(data.get('Address', ''))
                # Add other fields if needed, map to TEXT_ELEMENTS keys
            }

            for key, text_to_write in details_to_draw.items():
                if key in TEXT_ELEMENTS and text_to_write:
                    config = TEXT_ELEMENTS[key]
                    coords = config['coords']
                    font_size = config['size']
                    color = config['color']
                    font = loaded_fonts.get(font_size)

                    if not font:
                        app.logger.error(f"CRITICAL: Font object is None for size {font_size}! Cannot draw '{key}'. Check FONT_PATH and font file.")
                        continue # Skip drawing if font is invalid

                    try:
                        # ---> MODIFICATION FOR ADDRESS BOX <---
                        if key == "address":
                            # --- ADJUST THESE VALUES AS NEEDED ---
                            max_chars_per_line = 20 # Example: Max characters before wrapping
                            line_spacing = 10      # Example: Pixels between lines
                            box_padding_px = 17    # Example: Pixels padding around text inside box
                            box_outline_color = "black" # Color of the box border
                            box_outline_width = 0     # Width of the box border in pixels
                            # --- END OF ADJUSTABLE VALUES ---

                            wrapped_lines = textwrap.wrap(text_to_write, width=max_chars_per_line)
                            wrapped_address = "\n".join(wrapped_lines)

                            # Calculate the bounding box needed for the text
                            # text_bbox = (left, top, right, bottom) relative to anchor point (coords)
                            text_bbox = draw.multiline_textbbox(coords, wrapped_address, font=font, spacing=line_spacing)

                            # Calculate the box coordinates including padding
                            box_left = text_bbox[0] - box_padding_px
                            box_top = text_bbox[1] - box_padding_px
                            box_right = text_bbox[2] + box_padding_px
                            box_bottom = text_bbox[3] + box_padding_px
                            box_coords = [box_left, box_top, box_right, box_bottom]

                            # Draw the rectangle (the box)
                            print(f"Drawing BOX for '{key}' at {box_coords}")
                            draw.rectangle(box_coords, outline=box_outline_color, width=box_outline_width)

                            # Draw the wrapped text INSIDE the box (using original coords as anchor)
                            print(f"Drawing MULTILINE text for '{key}': '{wrapped_address}' at {coords} with size {font_size}")
                            draw.multiline_text(coords, wrapped_address, fill=color, font=font, spacing=line_spacing)

                        else:
                            # Draw other elements as single lines (unchanged)
                            # Determine if bold font is needed (assuming non-bold if not specified)
                            is_bold = config.get('is_bold', False)
                            # NOTE: Pillow doesn't directly support bold variations from a single .ttf easily.
                            # If you need actual bold, you'd typically load a separate bold font file (e.g., arialbd.ttf)
                            # and select it here based on the is_bold flag.
                            # For simplicity, this example uses the same font for bold/non-bold.
                            # You might need to adjust FONT_PATH loading if true bold is required.
                            active_font = font # Use the loaded font

                            print(f"Drawing text for '{key}': '{text_to_write}' at {coords} with size {font_size}, bold={is_bold}")
                            draw.text(coords, text_to_write, fill=color, font=active_font)
                        # ---> END OF MODIFICATION <---

                    except Exception as e:
                        app.logger.error(f"Error drawing text '{key}' for {data.get('Badge ID', 'N/A')}: {e}")

            # --- 3. Place final image onto PDF ---
            if col_num >= badges_per_row:
                col_num = 0; row_num += 1
                if row_num >= badges_per_col: row_num = 0; pdf.add_page()

            x_pos = MARGIN_MM + col_num * effective_badge_width
            y_pos = MARGIN_MM + row_num * effective_badge_height

            temp_img_buffer = BytesIO()
            badge_image.save(temp_img_buffer, format="PNG") # Save as PNG
            temp_img_buffer.seek(0)
            pdf.image(temp_img_buffer, x=x_pos, y=y_pos, w=BADGE_WIDTH_MM, h=BADGE_HEIGHT_MM, type='PNG')
            temp_img_buffer.close()
            col_num += 1

        except Exception as e:
            app.logger.error(f"Failed badge composition for ID {data.get('Badge ID', 'N/A')}: {e}")
        finally:
             if badge_image and badge_image != base_template:
                badge_image.close()

    # Close base template file
    base_template.close()

    # Save PDF to memory
    try:
        pdf_bytes_output = pdf.output()
        pdf_buffer = BytesIO(pdf_bytes_output)
        return pdf_buffer
    except TypeError: # Handle older PyFPDF versions
        pdf_bytes_output = pdf.output(dest='S').encode('latin-1')
        pdf_buffer = BytesIO(pdf_bytes_output)
        return pdf_buffer


# --- Flask Routes ---
# (/ , /submit, /printer routes remain unchanged)
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
    try: sheet = get_sheet(read_only=False)
    except Exception as e: flash(f"Error connecting to data storage: {e}", "error"); return redirect(url_for('form'))
    try:
        form_data = request.form.to_dict(); aadhaar_no = form_data.get('aadhaar_no', '').strip(); selected_area = form_data.get('area', '').strip(); selected_centre = form_data.get('satsang_place', '').strip()
        mandatory_fields = ['area', 'satsang_place', 'first_name', 'last_name', 'father_husband_name', 'gender', 'dob', 'aadhaar_no', 'emergency_contact_name', 'emergency_contact_number', 'emergency_contact_relation', 'address', 'state']
        missing_fields = [field for field in mandatory_fields if not form_data.get(field)]
        if missing_fields: flash(f"Missing mandatory fields: {', '.join(missing_fields)}", "error"); return redirect(url_for('form'))
        if check_aadhaar_exists(sheet, aadhaar_no, selected_area): flash(f"Error: Aadhaar number {aadhaar_no} already exists for Area '{selected_area}'.", "error"); return redirect(url_for('form'))
        photo_filename = "N/A"
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S"); original_filename = secure_filename(file.filename); extension = original_filename.rsplit('.', 1)[1].lower()
                photo_filename = f"{form_data.get('first_name', 'user')}_{form_data.get('last_name', '')}_{timestamp}.{extension}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
                try: file.save(file_path); app.logger.info(f"Photo saved: {photo_filename}")
                except Exception as e: app.logger.error(f"Error saving photo {photo_filename}: {e}"); flash(f"Could not save photo: {e}", "error"); photo_filename = "Upload Error"
            elif file and file.filename != '': flash(f"Invalid file type for photo. Allowed: {', '.join(ALLOWED_EXTENSIONS)}. Photo not saved.", 'warning')
        try: new_badge_id = get_next_badge_id(sheet, selected_area, selected_centre)
        except ValueError as e: flash(f"Error generating Badge ID: {e}", "error"); return redirect(url_for('form'))
        except Exception as e: flash(f"Error generating Badge ID: {e}", "error"); return redirect(url_for('form'))
        # Check your sheet column order - this must match EXACTLY
        data_row = [ form_data.get('submission_date', datetime.date.today().isoformat()), selected_area, selected_centre, form_data.get('first_name', ''), form_data.get('last_name', ''), form_data.get('father_husband_name', ''), form_data.get('gender', ''), form_data.get('dob', ''), form_data.get('age', ''), form_data.get('blood_group',''), aadhaar_no, form_data.get('physically_challenged', 'No'), form_data.get('physically_challenged_details', ''), form_data.get('help_pickup', 'No'), form_data.get('help_pickup_reasons', ''), form_data.get('handicap', 'No'), form_data.get('stretcher', 'No'), form_data.get('wheelchair', 'No'), form_data.get('ambulance', 'No'), form_data.get('pacemaker', 'No'), form_data.get('chair_sitting', 'No'), form_data.get('special_attendant', 'No'), form_data.get('hearing_loss', 'No'), form_data.get('mobile_no', ''), form_data.get('attend_satsang', 'No'), form_data.get('satsang_pickup_help', ''), form_data.get('other_requests', ''), form_data.get('emergency_contact_name', ''), form_data.get('emergency_contact_number', ''), form_data.get('emergency_contact_relation', ''), form_data.get('address', ''), form_data.get('state', ''), form_data.get('pin_code', ''), photo_filename, new_badge_id ]
        try: sheet.append_row(data_row); app.logger.info(f"Data appended. Badge ID: {new_badge_id}"); flash(f'Data submitted successfully! Your Badge ID is: {new_badge_id}', 'success')
        except Exception as e: app.logger.error(f"Error writing to Google Sheet: {e}"); flash(f'Error submitting data to Google Sheet: {e}. Please try again.', 'error'); return redirect(url_for('form'))
        return redirect(url_for('form'))
    except Exception as e: app.logger.error(f"Unexpected error during submission: {e}", exc_info=True); flash(f'An unexpected server error occurred: {e}', 'error'); return redirect(url_for('form'))


@app.route('/printer')
def printer():
    """Displays the form to enter badge IDs for printing."""
    return render_template('printer_form.html', centres=CENTRES)

# (/generate_pdf route remains unchanged - it calls the updated function)
@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    """Fetches data and generates the PDF with composite badge images."""
    selected_centre = request.form.get('centre')
    badge_ids_raw = request.form.get('badge_ids', '')
    badge_ids = [bid.strip() for bid in badge_ids_raw.split(',') if bid.strip()]

    if not badge_ids: flash("Please enter at least one Badge ID.", "error"); return redirect(url_for('printer'))

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
            badges_to_print.append(record)
        else:
            not_found_ids.append(bid)

    if not badges_to_print:
        flash("No valid Badge IDs found.", "error")
        if not_found_ids: flash(f"IDs not found: {', '.join(not_found_ids)}", "warning")
        return redirect(url_for('printer'))

    if not_found_ids: flash(f"Warning: The following Badge IDs were not found: {', '.join(not_found_ids)}", "warning")

    try:
        # Calls the updated function which now draws text AND the box
        pdf_buffer = create_pdf_with_composite_badges(badges_to_print)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Composite_Badges_{timestamp}.pdf"

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        app.logger.error(f"Error generating composite badge PDF: {e}", exc_info=True)
        flash(f"An error occurred while generating the badge PDF: {e}", "error")
        return redirect(url_for('printer'))


if __name__ == '__main__':
     app.run(debug=True, port=5000)