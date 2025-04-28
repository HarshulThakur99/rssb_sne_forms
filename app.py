import os
import datetime
from dateutil.relativedelta import relativedelta
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    send_file, jsonify, session
)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO
import re
import logging
import textwrap
import time

# --- Configuration ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
GOOGLE_SHEET_ID = '1M9dHOwtVldpruZoBzH23vWIVdcvMlHTdf_fWJGWVmLM' # Replace with your Sheet ID
SERVICE_ACCOUNT_FILE = 'rssbsneform-57c1113348b0.json' # Replace with your service account file
BADGE_TEMPLATE_PATH = 'static/images/sne_badge.png'
FONT_PATH = 'static/fonts/times new roman.ttf'
FONT_BOLD_PATH = 'static/fonts/times new roman bold.ttf'
PASTE_X_PX = 825
PASTE_Y_PX = 475
BOX_WIDTH_PX = 525
BOX_HEIGHT_PX = 700

BLOOD_CAMP_SHEET_ID = '1fkswOZnDXymKblLsYi79c1_NROn3mMaSua7u5hEKO_E'
BLOOD_CAMP_SERVICE_ACCOUNT_FILE = 'grand-nimbus-458116-f5-8295ebd9144b.json'

# Define expected headers for the Blood Camp sheet IN ORDER
BLOOD_CAMP_SHEET_HEADERS = [
    "Token ID", "Submission Timestamp", "Name of Donor", "Father's/Husband's Name",
    "Date of Birth", "Gender", "Occupation", "House No.", "Sector", "City",
    "Mobile Number", "Blood Group", "Allow Call", "Last Donation Date",
    "Last Donation Location", "First Donation Date", "Total Donations" # Example tracking fields
]

TEXT_ELEMENTS = {
    "badge_id": {"coords": (100, 1200), "size": 130, "color": (139, 0, 0), "is_bold": True},
    "name":     {"coords": (100, 1350), "size": 110, "color": "black", "is_bold": True},
    "gender":   {"coords": (100, 1500), "size": 110, "color": "black", "is_bold": True},
    "age":      {"coords": (100, 1650), "size": 110, "color": (139, 0, 0), "is_bold": True},
    "centre":   {"coords": (100, 1800), "size": 110, "color": "black", "is_bold": True},
    "area":     {"coords": (100, 1950), "size": 110, "color": "black", "is_bold": True},
    "address":  {"coords": (1750, 250), "size": 110, "color": "black", "is_bold": True}
}

BADGE_CONFIG = {
    "Chandigarh": {
        "CHD-I (Sec 27)": {"prefix": "SNE-AH-0", "start": 61001, "zone": "ZONE-I"},
        "CHD-II (Maloya)": {"prefix": "SNE-AH-0", "start": 71001, "zone": "ZONE-I"},
        "CHD-III (Khuda Alisher)": {"prefix": "SNE-AH-0", "start": 81001, "zone": "ZONE-I"},
        "CHD-IV (KAJHERI)": {"prefix": "SNE-AH-0", "start": 91001, "zone": "ZONE-I"},
    },
    "Mullanpur Garibdass": {
        "Baltana": {"prefix": "SNE-AX-0", "start": 11001, "zone": "ZONE-III"},
        "Banur": {"prefix": "SNE-AX-0", "start": 21002, "zone": "ZONE-III"},
        "Basma": {"prefix": "SNE-AX-0", "start": 31001, "zone": "ZONE-III"},
        "Barauli": {"prefix": "SNE-AX-0", "start": 41001, "zone": "ZONE-III"},
        "Dhakoran Kalan": {"prefix": "SNE-AX-0", "start": 51001, "zone": "ZONE-III"},
        "Gholu Majra": {"prefix": "SNE-AX-0", "start": 61001, "zone": "ZONE-III"},
        "Hamayunpur Tisambly": {"prefix": "SNE-AX-0", "start": 71001, "zone": "ZONE-III"},
        "Haripur Hinduan": {"prefix": "SNE-AX-0", "start": 81001, "zone": "ZONE-III"},
        "Jarout": {"prefix": "SNE-AX-0", "start": 91001, "zone": "ZONE-III"},
        "Khizrabad": {"prefix": "SNE-AX-", "start": 101001, "zone": "ZONE-III"},
        "KURARI": {"prefix": "SNE-AX-", "start": 111001, "zone": "ZONE-III"},
        "Lalru": {"prefix": "SNE-AX-", "start": 121001, "zone": "ZONE-III"},
        "Malikpur Jaula": {"prefix": "SNE-AX-", "start": 131001, "zone": "ZONE-III"},
        "Mullanpur Garibdass": {"prefix": "SNE-AX-", "start": 141001, "zone": "ZONE-III"},
        "Samgoli": {"prefix": "SNE-AX-", "start": 151001, "zone": "ZONE-III"},
        "Tewar": {"prefix": "SNE-AX-", "start": 161001, "zone": "ZONE-III"},
        "Zirakpur": {"prefix": "SNE-AX-", "start": 171001, "zone": "ZONE-III"},
    }
}

AREAS = list(BADGE_CONFIG.keys())
CENTRES = sorted(list(set(centre for area_centres in BADGE_CONFIG.values() for centre in area_centres.keys())))

STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]
# --- UPDATED RELATIONS LIST ---
RELATIONS = ["Spouse", "Father", "Mother", "Son", "Daughter", "Brother", "Sister", "Neighbor", "In Laws", "Others"]

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_strong_combined_secret_key_change_it_for_production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- Ensure Folders Exist ---
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/images', exist_ok=True)
os.makedirs('static/fonts', exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s:%(funcName)s:%(lineno)d')

# --- Initialize Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

# --- User Model ---
users_db = {
    'admin': {
        'password_hash': generate_password_hash('password123'), # Replace with your actual generated hash
        'id': 'admin'
    },
    # Add more users if needed
}

class User(UserMixin):
    def __init__(self, id, password_hash):
        self.id = id
        self.password_hash = password_hash

    @staticmethod
    def get(user_id):
        user_data = users_db.get(user_id)
        if not user_data:
            return None
        return User(id=user_data['id'], password_hash=user_data['password_hash'])

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# --- Google Sheet & Other Helper Functions ---

# Define expected headers in the correct order they appear in the sheet
# **IMPORTANT**: Update this list to exactly match your Google Sheet headers!
SHEET_HEADERS = [
    "Submission Date", "Area", "Satsang Place", "First Name", "Last Name",
    "Father's/Husband's Name", "Gender", "Date of Birth", "Age", "Blood Group",
    "Aadhaar No", "Physically Challenged", "Physically Challenged Details",
    "Help Pickup", "Help Pickup Reasons", "Handicap", "Stretcher", "Wheelchair",
    "Ambulance", "Pacemaker", "Chair Sitting", "Special Attendant", "Hearing Loss",
    "Mobile No", "Attend Satsang", "Satsang Pickup Help", "Other Requests",
    "Emergency Contact Name", "Emergency Contact Number", "Emergency Contact Relation",
    "Address", "State", "PIN Code", "Photo Filename", "Badge ID"
]

def get_sheet(read_only=False):
    """Authenticates and returns the Google Sheet worksheet object."""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        if read_only:
            scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        return sheet
    except FileNotFoundError:
        app.logger.error(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
        raise Exception(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
    except gspread.exceptions.SpreadsheetNotFound:
        app.logger.error(f"Spreadsheet not found: {GOOGLE_SHEET_ID}")
        raise Exception(f"Spreadsheet not found. Check ID/permissions: {GOOGLE_SHEET_ID}")
    except Exception as e:
        app.logger.error(f"Error accessing Google Sheet: {e}")
        raise Exception(f"Could not connect to Google Sheet: {e}")

def get_all_sheet_data(include_headers=False):
    """Gets all data from the sheet as list of dictionaries or list of lists."""
    try:
        sheet = get_sheet(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE, read_only=False)
        if include_headers:
            data = sheet.get_all_values() # Returns list of lists including header row
        else:
            data = sheet.get_all_records() # Returns list of dictionaries (headers as keys)
        app.logger.info(f"Fetched {len(data)} records from Google Sheet.")
        return data
    except Exception as e:
        app.logger.error(f"Could not get sheet data: {e}")
        raise Exception(f"Could not get sheet data: {e}")

def check_aadhaar_exists(sheet, aadhaar, area, exclude_badge_id=None):
    """
    Checks if Aadhaar already exists for the given Area, optionally excluding a specific Badge ID.
    Returns the existing Badge ID if found, otherwise None.
    """
    try:
        all_records = sheet.get_all_records()
        aadhaar_col_header = 'Aadhaar No'
        area_col_header = 'Area'
        badge_id_col_header = 'Badge ID'

        for record in all_records:
            if exclude_badge_id and str(record.get(badge_id_col_header, '')).strip() == str(exclude_badge_id).strip():
                continue

            record_aadhaar = str(record.get(aadhaar_col_header, '')).strip()
            record_area = str(record.get(area_col_header, '')).strip()
            record_badge_id = str(record.get(badge_id_col_header, '')).strip()

            if record_aadhaar == str(aadhaar).strip() and record_area == str(area).strip():
                app.logger.info(f"Aadhaar {aadhaar} found in Area {area} with Badge ID {record_badge_id}.")
                return record_badge_id # Return the existing Badge ID

        return None # No matching record found
    except Exception as e:
        app.logger.error(f"Error checking Aadhaar: {e}")
        return None

def get_next_badge_id(sheet, area, centre):
    """Generates the next sequential Badge ID for the Area/Centre."""
    if area not in BADGE_CONFIG or centre not in BADGE_CONFIG[area]:
        raise ValueError("Invalid Area or Centre for Badge ID.")
    config = BADGE_CONFIG[area][centre]
    prefix = config["prefix"]
    start_num = config["start"]
    try:
        badge_id_col_header = 'Badge ID'
        all_records = sheet.get_all_records()
        max_num = start_num - 1
        for record in all_records:
            existing_id = str(record.get(badge_id_col_header, '')).strip()
            if existing_id.startswith(prefix):
                try:
                    num_part = int(existing_id[len(prefix):])
                    max_num = max(max_num, num_part)
                except ValueError:
                    continue
        next_num = max(start_num, max_num + 1)
        return f"{prefix}{next_num}"
    except Exception as e:
        app.logger.error(f"Error generating Badge ID: {e}")
        raise Exception(f"Could not generate Badge ID: {e}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_age_from_dob(dob_str):
    """Calculates age in years from a DOB string (YYYY-MM-DD)."""
    if not dob_str: return ''
    try:
        birth_date = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date()
        today = datetime.date.today()
        age = relativedelta(today, birth_date).years
        return age
    except (ValueError, TypeError):
        app.logger.warning(f"Invalid date format received for DOB: {dob_str}")
        return ''
    except Exception as e:
        app.logger.error(f"Error calculating age from DOB {dob_str}: {e}")
        return ''

def find_row_index_by_badge_id(sheet, badge_id_to_find):
    """Finds the 1-based row index for a given Badge ID."""
    try:
        badge_id_col_header = 'Badge ID'
        badge_id_column_index = len(SHEET_HEADERS)
        all_badge_ids = sheet.col_values(badge_id_column_index)
        for index, badge_id in enumerate(all_badge_ids):
            if str(badge_id).strip() == str(badge_id_to_find).strip():
                return index + 1
        return None
    except gspread.exceptions.APIError as e:
         app.logger.error(f"gspread API error finding row for {badge_id_to_find}: {e}")
         if 'exceeds grid limits' in str(e):
             app.logger.error(f"Potential issue: 'Badge ID' column index ({badge_id_column_index}) might be incorrect or exceed sheet dimensions.")
         raise Exception(f"API error finding row: {e}")
    except Exception as e:
        app.logger.error(f"Error finding row index for Badge ID {badge_id_to_find}: {e}")
        raise Exception(f"Could not find row index: {e}")

def create_pdf_with_composite_badges(badge_data_list):
    """
    Generates PDF with badges created by pasting photos AND drawing text
    onto a base template image. Adds a box around the address.
    (Code is the same as provided in the previous version)
    """
    PAGE_WIDTH_MM = 297; PAGE_HEIGHT_MM = 210; BADGE_WIDTH_MM = 125; BADGE_HEIGHT_MM = 80
    MARGIN_MM = 15; gap_mm = 0; effective_badge_width = BADGE_WIDTH_MM + gap_mm
    effective_badge_height = BADGE_HEIGHT_MM + gap_mm
    badges_per_row = int((PAGE_WIDTH_MM - 2 * MARGIN_MM + gap_mm) / effective_badge_width) if effective_badge_width > 0 else 1
    badges_per_col = int((PAGE_HEIGHT_MM - 2 * MARGIN_MM + gap_mm) / effective_badge_height) if effective_badge_height > 0 else 1
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False, margin=MARGIN_MM)
    pdf.add_page(); col_num = 0; row_num = 0

    try: base_template = Image.open(BADGE_TEMPLATE_PATH).convert("RGBA")
    except FileNotFoundError: app.logger.error(f"Template not found: {BADGE_TEMPLATE_PATH}"); raise Exception(f"Template missing: {BADGE_TEMPLATE_PATH}")
    except Exception as e: app.logger.error(f"Error loading template: {e}"); raise Exception(f"Error loading template: {e}")

    loaded_fonts = {}; loaded_fonts_bold = {}; bold_load_failed_sizes = set()
    for element, config in TEXT_ELEMENTS.items():
        size = config['size']; is_bold = config.get('is_bold', False)
        if size not in loaded_fonts:
            try: loaded_fonts[size] = ImageFont.truetype(FONT_PATH, size); app.logger.info(f"Loaded REGULAR font {FONT_PATH} size {size}")
            except IOError: app.logger.error(f"CRITICAL: REGULAR font file not found: {FONT_PATH}"); raise Exception(f"CRITICAL: Regular font missing: {FONT_PATH}")
            except Exception as e: app.logger.error(f"CRITICAL: Error loading REGULAR font {FONT_PATH} size {size}: {e}"); raise Exception(f"CRITICAL: Error loading regular font: {e}")
        if is_bold and size not in loaded_fonts_bold and size not in bold_load_failed_sizes:
            try: loaded_fonts_bold[size] = ImageFont.truetype(FONT_BOLD_PATH, size); app.logger.info(f"Loaded BOLD font {FONT_BOLD_PATH} size {size}")
            except IOError: app.logger.warning(f"BOLD font file not found: {FONT_BOLD_PATH}. Falling back for size {size}."); loaded_fonts_bold[size] = loaded_fonts.get(size); bold_load_failed_sizes.add(size)
            except Exception as e: app.logger.warning(f"Error loading BOLD font {FONT_BOLD_PATH} size {size}: {e}. Falling back."); loaded_fonts_bold[size] = loaded_fonts.get(size); bold_load_failed_sizes.add(size)

    for data in badge_data_list:
        badge_image = None
        try:
            badge_image = base_template.copy(); draw = ImageDraw.Draw(badge_image)
            photo_filename = data.get('Photo Filename', ''); photo_path = os.path.join(UPLOAD_FOLDER, photo_filename) if photo_filename and photo_filename not in ['N/A', 'Upload Error', ''] else None
            photo_processed = False
            if photo_path and os.path.exists(photo_path):
                holder_photo = None; resized_photo = None
                try:
                    holder_photo = Image.open(photo_path).convert("RGBA"); resized_photo = holder_photo.resize((BOX_WIDTH_PX, BOX_HEIGHT_PX), Image.Resampling.LANCZOS)
                    badge_image.paste(resized_photo, (PASTE_X_PX, PASTE_Y_PX), resized_photo); photo_processed = True
                except Exception as e: app.logger.warning(f"Could not process/paste photo {photo_filename} for {data.get('Badge ID', 'N/A')}: {e}")
                finally:
                    if holder_photo: holder_photo.close()
                    if resized_photo: resized_photo.close()
            if not photo_processed: app.logger.warning(f"Photo not found/processed for {data.get('Badge ID', 'N/A')}")

            display_age = data.get('Age', '')
            if not display_age and data.get('Date of Birth'):
                try: dob_obj = datetime.datetime.strptime(str(data['Date of Birth']), '%Y-%m-%d').date(); display_age = relativedelta(datetime.date.today(), dob_obj).years
                except (ValueError, TypeError): app.logger.warning(f"Could not parse DOB '{data.get('Date of Birth')}' for badge ID {data.get('Badge ID', 'N/A')}"); display_age = ''

            details_to_draw = {
                "badge_id": str(data.get('Badge ID', 'N/A')), "name": f"{str(data.get('First Name', '')).upper()} {str(data.get('Last Name', '')).upper()}".strip(),
                "gender": str(data.get('Gender', '')).upper(), "age": f"AGE: {display_age} YEARS" if display_age != '' else "",
                "centre": str(data.get('Satsang Place', '')).upper(), "area": str(data.get('Area', '')).upper(), "address": str(data.get('Address', ''))
            }
            for key, text_to_write in details_to_draw.items():
                if key in TEXT_ELEMENTS and text_to_write:
                    config = TEXT_ELEMENTS[key]; coords = config['coords']; font_size = config['size']; color = config['color']; is_bold = config.get('is_bold', False)
                    active_font = loaded_fonts_bold.get(font_size) if is_bold else loaded_fonts.get(font_size)
                    if not active_font and is_bold: active_font = loaded_fonts.get(font_size) # Fallback if bold failed
                    if not active_font: app.logger.error(f"CRITICAL: Font object None for size {font_size}! Cannot draw '{key}'."); continue
                    try:
                        if key == "address":
                            max_chars = 20; line_space = 10; pad = 17; box_color = "black"; box_width = 0
                            wrapped = textwrap.wrap(text_to_write, width=max_chars); wrapped_addr = "\n".join(wrapped)
                            bbox = draw.multiline_textbbox(coords, wrapped_addr, font=active_font, spacing=line_space)
                            box_coords = [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad]
                            draw.rectangle(box_coords, outline=box_color, width=box_width)
                            draw.multiline_text(coords, wrapped_addr, fill=color, font=active_font, spacing=line_space)
                        else: draw.text(coords, text_to_write, fill=color, font=active_font)
                    except Exception as e: app.logger.error(f"Error drawing text '{key}' for {data.get('Badge ID', 'N/A')}: {e}")

            if col_num >= badges_per_row: col_num = 0; row_num += 1
            if row_num >= badges_per_col: row_num = 0; pdf.add_page()
            x_pos = MARGIN_MM + col_num * effective_badge_width; y_pos = MARGIN_MM + row_num * effective_badge_height
            temp_img_buffer = BytesIO(); badge_image.save(temp_img_buffer, format="PNG"); temp_img_buffer.seek(0)
            pdf.image(temp_img_buffer, x=x_pos, y=y_pos, w=BADGE_WIDTH_MM, h=BADGE_HEIGHT_MM, type='PNG'); temp_img_buffer.close()
            col_num += 1
        except Exception as e: app.logger.error(f"Failed badge composition for ID {data.get('Badge ID', 'N/A')}: {e}")
        finally:
             if badge_image and badge_image != base_template: badge_image.close()

    base_template.close()
    try: pdf_bytes_output = pdf.output(); pdf_buffer = BytesIO(pdf_bytes_output); return pdf_buffer
    except TypeError: pdf_bytes_output = pdf.output(dest='S').encode('latin-1'); pdf_buffer = BytesIO(pdf_bytes_output); return pdf_buffer
# --- End PDF Generation ---


# --- Flask Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('form'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        user_data = users_db.get(username)
        if not user_data or not check_password_hash(user_data['password_hash'], password):
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))
        user_obj = User.get(username)
        login_user(user_obj, remember=remember)
        flash('Logged in successfully!', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('form'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- Main Application Routes ---

@app.route('/')
@login_required
def form():
    """Displays the bio-data entry form."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('form.html',
                           today_date=today_date,
                           areas=AREAS,
                           states=STATES,
                           relations=RELATIONS, # Pass the updated list
                           current_user=current_user,
                           current_year=current_year)

@app.route('/submit', methods=['POST'])
@login_required
def submit_form():
    """Handles bio-data form submission."""
    try:
        sheet = get_sheet(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE, read_only=False)
    except Exception as e:
        flash(f"Error connecting to data storage: {e}", "error")
        return redirect(url_for('form'))

    try:
        form_data = request.form.to_dict()
        aadhaar_no = form_data.get('aadhaar_no', '').strip()
        selected_area = form_data.get('area', '').strip()
        selected_centre = form_data.get('satsang_place', '').strip()
        dob_str = form_data.get('dob', '')

        mandatory_fields = ['area', 'satsang_place', 'first_name', 'last_name', 'father_husband_name', 'gender', 'dob', 'aadhaar_no', 'emergency_contact_name', 'emergency_contact_number', 'emergency_contact_relation', 'address', 'state']
        missing_fields = [field for field in mandatory_fields if not form_data.get(field)]
        if missing_fields:
            flash(f"Missing mandatory fields: {', '.join(missing_fields)}", "error")
            return redirect(url_for('form'))

        existing_badge_id = check_aadhaar_exists(sheet, aadhaar_no, selected_area)
        if existing_badge_id:
            flash(f"Error: Aadhaar number {aadhaar_no} already exists for Area '{selected_area}' with Badge ID '{existing_badge_id}'.", "error")
            return redirect(url_for('form'))
        elif existing_badge_id is False:
             flash("Warning: Could not verify Aadhaar uniqueness due to an error.", "warning")

        photo_filename = "N/A"
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                original_filename = secure_filename(file.filename)
                extension = original_filename.rsplit('.', 1)[1].lower()
                unique_part = aadhaar_no if aadhaar_no else f"{form_data.get('first_name', 'user')}_{form_data.get('last_name', '')}"
                photo_filename = f"{unique_part}_{timestamp}.{extension}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
                try:
                    file.save(file_path)
                    app.logger.info(f"Photo saved: {photo_filename}")
                except Exception as e:
                    app.logger.error(f"Error saving photo {photo_filename}: {e}")
                    flash(f"Could not save photo: {e}", "error")
                    photo_filename = "Upload Error"
            elif file and file.filename != '':
                flash(f"Invalid file type for photo. Allowed: {', '.join(ALLOWED_EXTENSIONS)}. Photo not saved.", 'warning')

        try:
            new_badge_id = get_next_badge_id(sheet, selected_area, selected_centre)
        except ValueError as e:
            flash(f"Configuration Error: {e}", "error"); return redirect(url_for('form'))
        except Exception as e:
            flash(f"Error generating Badge ID: {e}", "error"); return redirect(url_for('form'))

        calculated_age = calculate_age_from_dob(dob_str)
        if calculated_age == '': app.logger.warning(f"Could not calculate age for DOB: {dob_str}. Saving empty age.")

        data_row = []
        for header in SHEET_HEADERS:
            form_key = header.lower().replace(' ', '_').replace("'", "").replace('/', '_')
            if header == "Submission Date": value = form_data.get('submission_date', datetime.date.today().isoformat())
            elif header == "Satsang Place": value = selected_centre
            elif header == "Age": value = calculated_age
            elif header == "Aadhaar No": value = aadhaar_no
            elif header == "Photo Filename": value = photo_filename
            elif header == "Badge ID": value = new_badge_id
            elif header in ["Physically Challenged", "Help Pickup", "Handicap", "Stretcher", "Wheelchair", "Ambulance", "Pacemaker", "Chair Sitting", "Special Attendant", "Hearing Loss", "Attend Satsang"]:
                 value = form_data.get(form_key, 'No')
            else: value = form_data.get(form_key, '')
            data_row.append(str(value))

        try:
            sheet.append_row(data_row)
            app.logger.info(f"Data appended. Badge ID: {new_badge_id}")
            flash(f'Data submitted successfully! Your Badge ID is: {new_badge_id}', 'success')
        except Exception as e:
            app.logger.error(f"Error writing to Google Sheet: {e}")
            if photo_filename not in ["N/A", "Upload Error"] and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)):
                try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)); app.logger.info(f"Removed photo {photo_filename} due to sheet write error.")
                except OSError as rm_err: app.logger.error(f"Error removing photo {photo_filename} after sheet error: {rm_err}")
            flash(f'Error submitting data to Google Sheet: {e}. Please try again.', 'error')
            return redirect(url_for('form'))

        return redirect(url_for('form'))

    except Exception as e:
        app.logger.error(f"Unexpected error during submission: {e}", exc_info=True)
        flash(f'An unexpected server error occurred: {e}', 'error')
        return redirect(url_for('form'))


@app.route('/printer')
@login_required
def printer():
    """Displays the form to enter badge IDs for printing."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('printer_form.html',
                           centres=CENTRES,
                           current_user=current_user,
                           current_year=current_year)

@app.route('/generate_pdf', methods=['POST'])
@login_required
def generate_pdf():
    """Fetches data and generates the PDF with composite badge images."""
    badge_ids_raw = request.form.get('badge_ids', '')
    badge_ids = [bid.strip().upper() for bid in badge_ids_raw.split(',') if bid.strip()]

    if not badge_ids:
        flash("Please enter at least one Badge ID.", "error")
        return redirect(url_for('printer'))

    try:
        all_sheet_data = get_all_sheet_data()
        data_map = {str(row.get('Badge ID', '')).strip().upper(): row for row in all_sheet_data if row.get('Badge ID')}
    except Exception as e:
        flash(f"Error fetching data from Google Sheet: {e}", "error")
        return redirect(url_for('printer'))

    badges_to_print = []
    not_found_ids = []
    for bid in badge_ids:
        if bid in data_map:
            badges_to_print.append(data_map[bid])
        else:
            not_found_ids.append(bid)

    if not badges_to_print:
        flash("No valid Badge IDs found in the sheet.", "error")
        if not_found_ids: flash(f"IDs not found: {', '.join(not_found_ids)}", "warning")
        return redirect(url_for('printer'))

    if not_found_ids:
        flash(f"Warning: The following Badge IDs were not found: {', '.join(not_found_ids)}", "warning")

    try:
        pdf_buffer = create_pdf_with_composite_badges(badges_to_print)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Composite_Badges_{timestamp}.pdf"
        return send_file(
            pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf'
        )
    except Exception as e:
        app.logger.error(f"Error generating composite badge PDF: {e}", exc_info=True)
        flash(f"An error occurred while generating the badge PDF: {e}", "error")
        return redirect(url_for('printer'))

# --- Route to get centres for dynamic dropdown ---
@app.route('/get_centres/<area>')
@login_required
def get_centres(area):
    """Returns a JSON list of centres for the given area."""
    if area in BADGE_CONFIG:
        centres_for_area = sorted(list(BADGE_CONFIG[area].keys()))
        return jsonify(centres_for_area)
    else:
        return jsonify([])

# --- Edit Form Routes ---

@app.route('/edit')
@login_required
def edit_form_page():
    """Displays the search/edit form page."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('edit_form.html',
                           areas=AREAS,
                           states=STATES,
                           relations=RELATIONS, # Pass the updated list
                           current_user=current_user,
                           current_year=current_year)

@app.route('/search_entries', methods=['GET'])
@login_required
def search_entries():
    """Handles AJAX search requests for entries."""
    search_name = request.args.get('name', '').strip().lower()
    search_badge_id = request.args.get('badge_id', '').strip().upper()

    try:
        all_data = get_all_sheet_data()
        results = []

        if search_badge_id:
            for entry in all_data:
                if str(entry.get('Badge ID', '')).strip().upper() == search_badge_id:
                    results.append(entry); break
        elif search_name:
            for entry in all_data:
                first_name = str(entry.get('First Name', '')).strip().lower()
                last_name = str(entry.get('Last Name', '')).strip().lower()
                if search_name in first_name or search_name in last_name:
                    results.append(entry)

        MAX_RESULTS = 50
        return jsonify(results[:MAX_RESULTS])

    except Exception as e:
        app.logger.error(f"Error searching entries: {e}")
        return jsonify({"error": f"Search failed: {e}"}), 500


@app.route('/update_entry/<original_badge_id>', methods=['POST'])
@login_required
def update_entry(original_badge_id):
    """Handles submission of the edited form data."""
    if not original_badge_id:
        flash("Error: No Badge ID specified for update.", "error")
        return redirect(url_for('edit_form_page'))

    try:
        sheet = get_sheet(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE, read_only=False)
    except Exception as e:
        flash(f"Error connecting to data storage: {e}", "error")
        return redirect(url_for('edit_form_page'))

    try:
        row_index = find_row_index_by_badge_id(sheet, original_badge_id)
        if not row_index:
            flash(f"Error: Could not find entry with Badge ID {original_badge_id} to update.", "error")
            return redirect(url_for('edit_form_page'))

        form_data = request.form.to_dict()
        try:
            original_record_list = sheet.row_values(row_index)
            original_record = dict(zip(SHEET_HEADERS, original_record_list))
            aadhaar_no = original_record.get('Aadhaar No', '').strip()
            if not aadhaar_no: aadhaar_no = form_data.get('aadhaar_no', '').strip()
            app.logger.info(f"Updating record for Badge ID: {original_badge_id} at row {row_index} with Aadhaar: {aadhaar_no}")
        except Exception as fetch_err:
             app.logger.error(f"Could not fetch original record for {original_badge_id} at row {row_index}: {fetch_err}")
             flash(f"Error fetching original data before update.", "error")
             return redirect(url_for('edit_form_page'))

        new_photo_filename = original_record.get('Photo Filename', 'N/A')
        delete_old_photo = False
        old_photo_filename = original_record.get('Photo Filename', '')

        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                original_filename = secure_filename(file.filename)
                extension = original_filename.rsplit('.', 1)[1].lower()
                unique_part = aadhaar_no if aadhaar_no else f"{form_data.get('first_name', 'user')}_{form_data.get('last_name', '')}"
                temp_new_filename = f"{unique_part}_{timestamp}.{extension}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_new_filename)
                try:
                    file.save(file_path)
                    app.logger.info(f"New photo saved for update: {temp_new_filename}")
                    new_photo_filename = temp_new_filename
                    delete_old_photo = True
                except Exception as e:
                    app.logger.error(f"Error saving new photo {temp_new_filename}: {e}")
                    flash(f"Could not save new photo: {e}. Keeping existing photo.", "error")
            elif file and file.filename != '':
                flash(f"Invalid file type for new photo. Allowed: {', '.join(ALLOWED_EXTENSIONS)}. Photo not updated.", 'warning')

        dob_str = form_data.get('dob', '')
        calculated_age = calculate_age_from_dob(dob_str)
        if calculated_age == '': app.logger.warning(f"Could not calculate age for DOB: {dob_str} during update.")

        updated_data_row = []
        for header in SHEET_HEADERS:
            form_key = header.lower().replace(' ', '_').replace("'", "").replace('/', '_')
            if header == "Badge ID": value = original_badge_id
            elif header == "Aadhaar No": value = aadhaar_no
            elif header == "Age": value = calculated_age
            elif header == "Photo Filename": value = new_photo_filename
            elif header == "Submission Date": value = form_data.get('submission_date', original_record.get('Submission Date', ''))
            elif header in ["Physically Challenged", "Help Pickup", "Handicap", "Stretcher", "Wheelchair", "Ambulance", "Pacemaker", "Chair Sitting", "Special Attendant", "Hearing Loss", "Attend Satsang"]:
                 value = form_data.get(form_key, 'No')
            else: value = form_data.get(form_key, '')
            updated_data_row.append(str(value))

        try:
            end_column_letter = gspread.utils.rowcol_to_a1(1, len(SHEET_HEADERS)).split('1')[0]
            update_range = f'A{row_index}:{end_column_letter}{row_index}'
            sheet.update(update_range, [updated_data_row])

            app.logger.info(f"Data updated for Badge ID: {original_badge_id} at row {row_index}")

            if delete_old_photo and old_photo_filename and old_photo_filename not in ["N/A", "Upload Error", ""]:
                 old_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], old_photo_filename)
                 if os.path.exists(old_photo_path):
                     try: os.remove(old_photo_path); app.logger.info(f"Successfully deleted old photo: {old_photo_filename}")
                     except OSError as e: app.logger.error(f"Error deleting old photo {old_photo_filename}: {e}"); flash(f"Entry updated, but failed to delete old photo: {old_photo_filename}", "warning")

            flash(f'Entry for Badge ID {original_badge_id} updated successfully!', 'success')
            return redirect(url_for('edit_form_page'))

        except Exception as e:
            app.logger.error(f"Error updating Google Sheet for Badge ID {original_badge_id}: {e}")
            if delete_old_photo:
                 new_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], new_photo_filename)
                 if os.path.exists(new_photo_path):
                     try: os.remove(new_photo_path); app.logger.info(f"Removed newly uploaded photo {new_photo_filename} due to sheet update error.")
                     except OSError as rm_err: app.logger.error(f"Error removing new photo {new_photo_filename} after sheet update error: {rm_err}")
            flash(f'Error updating data in Google Sheet: {e}. Please try again.', 'error')
            return redirect(url_for('edit_form_page'))

    except Exception as e:
        app.logger.error(f"Unexpected error during update for Badge ID {original_badge_id}: {e}", exc_info=True)
        flash(f'An unexpected server error occurred during update: {e}', 'error')
        return redirect(url_for('edit_form_page'))


def get_sheet(sheet_id, service_account_path, read_only=False):
    """
    Authenticates and returns a specific Google Sheet worksheet object.
    MODIFIED to accept sheet_id and service_account_path.
    """
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        if read_only:
            scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']

        # Check if the service account file exists
        if not os.path.exists(service_account_path):
             app.logger.error(f"Service account file not found: {service_account_path}")
             # Return None or raise a specific error to be caught by the route
             # Returning None here to allow routes to handle specific messages
             return None

        creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        return sheet
    except FileNotFoundError:
        # This case is handled above, but kept for robustness
        app.logger.error(f"Service account file not found during credential loading: {service_account_path}")
        return None
    except gspread.exceptions.SpreadsheetNotFound:
        app.logger.error(f"Spreadsheet not found: {sheet_id}")
        return None # Allow route to handle
    except Exception as e:
        app.logger.error(f"Error accessing Google Sheet (ID: {sheet_id}): {e}")
        return None # Allow route to handle

# --- Existing get_all_sheet_data, check_aadhaar_exists etc. remain ---
# --- You might adapt get_all_sheet_data if needed for blood camp ---

# === NEW: Blood Camp Helper Functions ===

def find_donor_by_mobile(sheet, mobile_number):
    """
    Searches the Blood Camp sheet for a donor by mobile number.
    Returns the donor's record (dict) if found, otherwise None.
    Assumes 'Mobile Number' is a header in BLOOD_CAMP_SHEET_HEADERS.
    """
    if not sheet:
        app.logger.error("Sheet object is None in find_donor_by_mobile.")
        return None # Indicate sheet connection issue

    try:
        # Find the column index for Mobile Number (adjust if header changes)
        mobile_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Mobile Number") + 1
        # Fetch all mobile numbers from the specific column
        all_mobiles = sheet.col_values(mobile_col_index)

        # Iterate through the mobile numbers to find a match
        for index, mobile in enumerate(all_mobiles):
            if str(mobile).strip() == str(mobile_number).strip():
                # Found the mobile number, get the entire row (index is 0-based, row is 1-based)
                row_index = index + 1
                donor_data_list = sheet.row_values(row_index)
                # Convert list to dictionary using headers
                donor_data_dict = dict(zip(BLOOD_CAMP_SHEET_HEADERS, donor_data_list))
                app.logger.info(f"Donor found by mobile {mobile_number} at row {row_index}.")
                return donor_data_dict
        app.logger.info(f"Donor not found with mobile {mobile_number}.")
        return None # Not found
    except ValueError:
        app.logger.error(f"Header 'Mobile Number' not found in BLOOD_CAMP_SHEET_HEADERS.")
        return None # Indicate configuration error
    except gspread.exceptions.APIError as e:
         app.logger.error(f"gspread API error finding donor by mobile {mobile_number}: {e}")
         return None # Indicate sheet API error
    except Exception as e:
        app.logger.error(f"Error searching donor by mobile {mobile_number}: {e}")
        return None # Indicate general error

def generate_next_token_id(sheet):
    """
    Generates the next sequential Token ID based on the last entry.
    Format: CHD{YYYY}{MMM}{NNNN} (e.g., CHD2025APR0001)
    Assumes 'Token ID' is the first header in BLOOD_CAMP_SHEET_HEADERS.
    """
    if not sheet:
        app.logger.error("Sheet object is None in generate_next_token_id.")
        return None # Indicate sheet connection issue

    try:
        # Get the last token ID from the sheet (assuming Token ID is in the first column)
        # Get all values in the Token ID column (col 1)
        token_col_values = sheet.col_values(1) # Column numbers are 1-based

        # Filter out potential empty strings or header row if present
        existing_tokens = [token for token in token_col_values if token and token.startswith('CHD')]

        now = datetime.datetime.now()
        year_str = now.strftime("%Y")
        month_str = now.strftime("%b").upper() # e.g., APR
        prefix = f"CHD{year_str}{month_str}"

        last_seq_num = 0
        if existing_tokens:
            # Find the highest sequence number for the current prefix
            current_month_tokens = [token for token in existing_tokens if token.startswith(prefix)]
            if current_month_tokens:
                 # Extract numbers, handle potential errors
                 seq_numbers = []
                 for token in current_month_tokens:
                     try:
                         num_part = int(token[len(prefix):])
                         seq_numbers.append(num_part)
                     except (ValueError, IndexError):
                         app.logger.warning(f"Could not parse sequence number from token: {token}")
                         continue # Skip malformed tokens
                 if seq_numbers:
                    last_seq_num = max(seq_numbers)

        next_seq_num = last_seq_num + 1
        new_token_id = f"{prefix}{next_seq_num:04d}" # Format sequence number with leading zeros

        app.logger.info(f"Generated next Token ID: {new_token_id}")
        return new_token_id

    except gspread.exceptions.APIError as e:
         app.logger.error(f"gspread API error generating token ID: {e}")
         return None
    except Exception as e:
        app.logger.error(f"Error generating Token ID: {e}")
        return None

def find_row_index_by_token_id(sheet, token_id_to_find):
    """Finds the 1-based row index for a given Token ID in the Blood Camp sheet."""
    if not sheet: return None
    try:
        token_id_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Token ID") + 1
        all_token_ids = sheet.col_values(token_id_col_index)
        for index, token_id in enumerate(all_token_ids):
            if str(token_id).strip() == str(token_id_to_find).strip():
                return index + 1 # 1-based index
        return None
    except ValueError:
         app.logger.error(f"Header 'Token ID' not found in BLOOD_CAMP_SHEET_HEADERS.")
         return None
    except gspread.exceptions.APIError as e:
         app.logger.error(f"gspread API error finding row for Token ID {token_id_to_find}: {e}")
         return None
    except Exception as e:
        app.logger.error(f"Error finding row index for Token ID {token_id_to_find}: {e}")
        return None

# === END NEW: Blood Camp Helper Functions ===


# --- Flask Routes ---

# ... (Existing /login, /logout, /form, /submit, /printer, /generate_pdf, /get_centres, /edit, /search_entries, /update_entry routes) ...

# === NEW: Blood Camp Routes ===

@app.route('/blood_camp')
@login_required
def blood_camp_form_page():
    """Displays the blood camp donor form."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('blood_camp_form.html',
                           today_date=today_date,
                           current_year=current_year,
                           current_user=current_user)

@app.route('/search_donor', methods=['GET'])
@login_required
def search_donor():
    """Handles AJAX search requests for blood camp donors by mobile."""
    mobile_number = request.args.get('mobile', '').strip()

    if not mobile_number or not mobile_number.isdigit() or len(mobile_number) != 10:
        return jsonify({"error": "Invalid mobile number format."}), 400

    # Get the specific sheet for blood camp data (read-only)
    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)

    if not sheet:
         # Error message if sheet connection failed
         return jsonify({"error": "Could not connect to donor database."}), 500

    donor_record = find_donor_by_mobile(sheet, mobile_number)

    if donor_record is None:
         # Check if the error was sheet connection or just not found
         # Re-check sheet object status if needed, or assume 'not found' if no specific error logged in find_donor_by_mobile
         # For simplicity, assume 'not found' if donor_record is None after a successful sheet connection check
         if get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True): # Quick re-check
              app.logger.info(f"Search: Donor not found for mobile {mobile_number}")
              return jsonify({"found": False})
         else:
             # If sheet connection failed even on re-check
             app.logger.error(f"Search: Sheet connection failed for mobile {mobile_number}")
             return jsonify({"error": "Database connection error during search."}), 500

    elif isinstance(donor_record, dict):
        app.logger.info(f"Search: Donor found for mobile {mobile_number}")
        return jsonify({"found": True, "donor": donor_record})
    else:
        # Handle potential unexpected return values from find_donor_by_mobile if applicable
        app.logger.error(f"Search: Unexpected result for mobile {mobile_number}")
        return jsonify({"error": "An unexpected error occurred during search."}), 500


@app.route('/submit_blood_camp', methods=['POST'])
@login_required
def submit_blood_camp():
    """Handles blood camp form submission (new donors and updates)."""
    form_data = request.form.to_dict()
    is_update = form_data.get('is_update', 'false').lower() == 'true'
    token_id = form_data.get('token_id', '').strip()
    mobile_number = form_data.get('mobile_no', '').strip()

    # Basic validation (add more as needed)
    if not mobile_number:
         flash("Mobile number is required.", "error")
         return redirect(url_for('blood_camp_form_page'))
    if is_update and not token_id:
         flash("Token ID missing for update.", "error")
         return redirect(url_for('blood_camp_form_page'))

    # Get the specific sheet for blood camp data (read-write)
    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=False)

    if not sheet:
        flash("Error connecting to the donor database. Please try again.", "error")
        return redirect(url_for('blood_camp_form_page'))

    try:
        if is_update:
            # --- Update Existing Donor ---
            row_index = find_row_index_by_token_id(sheet, token_id)
            if not row_index:
                flash(f"Error: Could not find donor with Token ID {token_id} to update.", "error")
                return redirect(url_for('blood_camp_form_page'))

            # Fetch the existing row to preserve some data and update specific fields
            existing_data_list = sheet.row_values(row_index)
            existing_data = dict(zip(BLOOD_CAMP_SHEET_HEADERS, existing_data_list))

            # Prepare updated row data - primarily update donation date/location and count
            updated_row = []
            total_donations = int(existing_data.get('Total Donations', 0)) + 1
            for header in BLOOD_CAMP_SHEET_HEADERS:
                if header == "Last Donation Date":
                    value = form_data.get('donation_date', datetime.date.today().isoformat())
                elif header == "Last Donation Location":
                    value = form_data.get('donation_location', '')
                elif header == "Total Donations":
                    value = total_donations
                elif header == "Submission Timestamp": # Update timestamp on modification
                     value = datetime.datetime.now().isoformat()
                # Keep other fields from the existing record unless explicitly changed in the form
                # (Current form only focuses on donation date/location for updates)
                else:
                    # Use existing value if not directly editable/updated in this flow
                    value = existing_data.get(header, '')
                updated_row.append(str(value))

            # Update the row in the sheet
            sheet.update(f'A{row_index}:{gspread.utils.rowcol_to_a1(1, len(BLOOD_CAMP_SHEET_HEADERS)).split("1")[0]}{row_index}', [updated_row])
            flash(f'Donation details updated successfully for Token ID: {token_id}', 'success')
            app.logger.info(f"Updated donation for Token ID: {token_id} at row {row_index}")

        else:
            # --- Add New Donor ---
            # Check if mobile number already exists (should ideally be prevented by search, but double-check)
            existing_donor = find_donor_by_mobile(sheet, mobile_number)
            if existing_donor:
                 flash(f"Error: Mobile number {mobile_number} already exists with Token ID {existing_donor.get('Token ID', 'N/A')}. Please use the search function.", "error")
                 return redirect(url_for('blood_camp_form_page'))

            # Generate new Token ID
            new_token_id = generate_next_token_id(sheet)
            if not new_token_id:
                 flash("Error generating a unique Token ID. Please try again.", "error")
                 return redirect(url_for('blood_camp_form_page'))

            # Prepare data row based on BLOOD_CAMP_SHEET_HEADERS
            data_row = []
            donation_date = form_data.get('donation_date', datetime.date.today().isoformat())
            for header in BLOOD_CAMP_SHEET_HEADERS:
                form_key = header.lower().replace("'", "").replace('/', '_').replace(' ', '_') # Simple key conversion
                if header == "Token ID": value = new_token_id
                elif header == "Submission Timestamp": value = datetime.datetime.now().isoformat()
                elif header == "Name of Donor": value = form_data.get('donor_name', '')
                elif header == "Father's/Husband's Name": value = form_data.get('father_husband_name', '')
                elif header == "Date of Birth": value = form_data.get('dob', '')
                elif header == "Gender": value = form_data.get('gender', '')
                elif header == "Occupation": value = form_data.get('occupation', '')
                elif header == "House No.": value = form_data.get('house_no', '')
                elif header == "Sector": value = form_data.get('sector', '')
                elif header == "City": value = form_data.get('city', '')
                elif header == "Mobile Number": value = mobile_number # Already validated
                elif header == "Blood Group": value = form_data.get('blood_group', '')
                elif header == "Allow Call": value = form_data.get('allow_call', 'No')
                elif header == "Last Donation Date": value = donation_date
                elif header == "Last Donation Location": value = form_data.get('donation_location', '')
                elif header == "First Donation Date": value = donation_date # First time donating
                elif header == "Total Donations": value = 1 # First donation
                else: value = form_data.get(form_key, '') # Default mapping
                data_row.append(str(value))

            # Append the new row to the sheet
            sheet.append_row(data_row)
            flash(f'New donor registered successfully! Token ID: {new_token_id}', 'success')
            app.logger.info(f"Appended new donor. Token ID: {new_token_id}")

        return redirect(url_for('blood_camp_form_page')) # Redirect back to the form

    except gspread.exceptions.APIError as e:
        app.logger.error(f"Google Sheet API error during blood camp submission: {e}")
        flash(f"Database error: {e}. Please try again.", "error")
        return redirect(url_for('blood_camp_form_page'))
    except Exception as e:
        app.logger.error(f"Unexpected error during blood camp submission: {e}", exc_info=True)
        flash(f"An unexpected server error occurred: {e}", "error")
        return redirect(url_for('blood_camp_form_page'))
    

# --- Main Execution ---
if __name__ == '__main__':
    # Set debug=False for production
    # Use host='0.0.0.0' to be accessible on the network
    # app.run(debug=True, port=5000) # Development
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) # Production/Deployment
