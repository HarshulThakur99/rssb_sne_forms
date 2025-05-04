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
import re # Import re module for regex
import logging
import textwrap
import time
import boto3 # Import Boto3
from botocore.exceptions import ClientError # Import Boto3 exceptions
import collections
from dateutil import parser # Import parser for flexible date parsing

from attendant_routes import attendant_bp # Import the attendant blueprint
# --- Configuration ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
GOOGLE_SHEET_ID = '1M9dHOwtVldpruZoBzH23vWIVdcvMlHTdf_fWJGWVmLM' # SNE Sheet ID
SERVICE_ACCOUNT_FILE = 'rssbsneform-57c1113348b0.json' # SNE Service Account
BADGE_TEMPLATE_PATH = 'static/images/sne_badge.png'
FONT_PATH = 'static/fonts/times new roman.ttf'
FONT_BOLD_PATH = 'static/fonts/times new roman bold.ttf'
PASTE_X_PX = 825
PASTE_Y_PX = 475
BOX_WIDTH_PX = 525
BOX_HEIGHT_PX = 700

BLOOD_CAMP_SHEET_ID = '1fkswOZnDXymKblLsYi79c1_NROn3mMaSua7u5hEKO_E' # Blood Camp Sheet ID
BLOOD_CAMP_SERVICE_ACCOUNT_FILE = 'grand-nimbus-458116-f5-8295ebd9144b.json' # Blood Camp Service Account

# --- S3 Configuration ---
S3_BUCKET_NAME = 'rssbsne' # <<<--- REPLACE WITH YOUR ACTUAL BUCKET NAME
s3_client = boto3.client('s3')

# --- SNE Headers List ---
SHEET_HEADERS = [
    "Badge ID", "Submission Date", "Area", "Satsang Place", "First Name", "Last Name",
    "Father's/Husband's Name", "Gender", "Date of Birth", "Age", "Blood Group",
    "Aadhaar No", "Mobile No", "Physically Challenged (Yes/No)", "Physically Challenged Details",
    "Help Required for Home Pickup (Yes/No)", "Help Pickup Reasons", "Handicap (Yes/No)",
    "Stretcher Required (Yes/No)", "Wheelchair Required (Yes/No)", "Ambulance Required (Yes/No)",
    "Pacemaker Operated (Yes/No)", "Chair Required for Sitting (Yes/No)",
    "Special Attendant Required (Yes/No)", "Hearing Loss (Yes/No)",
    "Willing to Attend Satsangs (Yes/No)", "Satsang Pickup Help Details", "Other Special Requests",
    "Emergency Contact Name", "Emergency Contact Number", "Emergency Contact Relation",
    "Address", "State", "PIN Code", "Photo Filename"
]
    
# --- CORRECTED Blood Camp Headers List with persistent ID and history ---
BLOOD_CAMP_SHEET_HEADERS = [
    "Donor ID", "Submission Timestamp", "Area", # Renamed Token ID, kept Timestamp
    "Name of Donor", "Father's/Husband's Name", # Removed Area
    "Date of Birth", "Gender", "Occupation", "House No.", "Sector", "City", "Mobile Number",
    "Blood Group", "Allow Call", "Donation Date", "Donation Location",
    "First Donation Date", "Total Donations", # Added History Columns
    "Status", "Reason for Rejection"
]

# Define Areas for Blood Camp (Still needed for SNE part)
BLOOD_CAMP_AREAS = ['Chandigarh', 'Mullanpur Garibdass']

# --- SNE Text Elements & Config (Keep as is) ---
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
        "Kurari": {"prefix": "SNE-AX-", "start": 111001, "zone": "ZONE-III"},
        "Lalru": {"prefix": "SNE-AX-", "start": 121001, "zone": "ZONE-III"},
        "Malikpur Jaula": {"prefix": "SNE-AX-", "start": 131001, "zone": "ZONE-III"},
        "Mullanpur Garibdass": {"prefix": "SNE-AX-", "start": 141001, "zone": "ZONE-III"},
        "Samgoli": {"prefix": "SNE-AX-", "start": 151001, "zone": "ZONE-III"},
        "Tewar": {"prefix": "SNE-AX-", "start": 161001, "zone": "ZONE-III"},
        "Zirakpur": {"prefix": "SNE-AX-", "start": 171001, "zone": "ZONE-III"},
    }
}
AREAS = list(BADGE_CONFIG.keys()) # SNE Areas
CENTRES = sorted(list(set(centre for area_centres in BADGE_CONFIG.values() for centre in area_centres.keys()))) # SNE Centres
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]
RELATIONS = ["Spouse", "Father", "Mother", "Son", "Daughter", "Brother", "Sister", "Neighbor", "In Laws", "Others"]

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_strong_combined_secret_key_change_it_for_production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs('static/images', exist_ok=True)
os.makedirs('static/fonts', exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s:%(funcName)s:%(lineno)d')

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

app.register_blueprint(attendant_bp) # Register the attendant blueprint

users_db = { # Simple in-memory user store
    'admin': { 'password_hash': generate_password_hash('password123'), 'id': 'admin' }
}
class User(UserMixin):
    def __init__(self, id, password_hash): self.id = id; self.password_hash = password_hash
    @staticmethod
    def get(user_id):
        user_data = users_db.get(user_id)
        return User(id=user_data['id'], password_hash=user_data['password_hash']) if user_data else None
@login_manager.user_loader
def load_user(user_id): return User.get(user_id)

# --- Helper Functions ---

def get_sheet(sheet_id, service_account_path, read_only=False):
    """Authenticates and returns a specific Google Sheet worksheet object."""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        if read_only: scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        if not os.path.exists(service_account_path):
             app.logger.error(f"Service account file not found: {service_account_path}"); return None
        creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        return sheet
    except Exception as e:
        app.logger.error(f"Error accessing Google Sheet (ID: {sheet_id}): {e}", exc_info=True); return None

def get_all_sheet_data(sheet_id, service_account_path, headers_list):
    """Gets all data from the sheet and constructs a list of dictionaries."""
    sheet = get_sheet(sheet_id, service_account_path, read_only=True)
    if not sheet: raise Exception(f"Could not connect to sheet {sheet_id} to get data.")
    try:
        all_values = sheet.get_all_values()
        if not all_values or len(all_values) < 1: return []
        header_row = headers_list
        data_rows = all_values[1:]
        list_of_dicts = []
        num_headers = len(header_row)
        for row_index, row in enumerate(data_rows):
            padded_row = row + [''] * (num_headers - len(row))
            truncated_row = padded_row[:num_headers]
            try:
                record_dict = dict(zip(header_row, truncated_row))
                if any(val for val in record_dict.values()): list_of_dicts.append(record_dict)
            except Exception as zip_err: app.logger.error(f"Error creating dict for row {row_index + 2} in sheet {sheet_id}: {zip_err} - Row: {row}")
        return list_of_dicts
    except Exception as e:
        app.logger.error(f"Could not get/process sheet data from {sheet_id}: {e}", exc_info=True)
        raise Exception(f"Could not get/process sheet data from {sheet_id}: {e}")

def check_aadhaar_exists(sheet, aadhaar, area, exclude_badge_id=None):
    """Checks if SNE Aadhaar exists for the given Area, optionally excluding a Badge ID."""
    if not sheet: return False # Indicate error
    try:
        try:
            aadhaar_col_idx = SHEET_HEADERS.index('Aadhaar No')
            area_col_idx = SHEET_HEADERS.index('Area')
            badge_id_col_idx = SHEET_HEADERS.index('Badge ID')
        except ValueError as e: app.logger.error(f"Header config error: {e}"); return False
        all_values = sheet.get_all_values()
        if len(all_values) <= 1: return None
        data_rows = all_values[1:]
        cleaned_aadhaar_search = re.sub(r'\s+', '', str(aadhaar)).strip()
        if not cleaned_aadhaar_search: return None
        for row in data_rows:
            if len(row) <= max(aadhaar_col_idx, area_col_idx, badge_id_col_idx): continue
            record_badge_id = str(row[badge_id_col_idx]).strip()
            if exclude_badge_id and record_badge_id == str(exclude_badge_id).strip(): continue
            record_aadhaar_cleaned = re.sub(r'\s+', '', str(row[aadhaar_col_idx]).strip())
            record_area = str(row[area_col_idx]).strip()
            if record_aadhaar_cleaned == cleaned_aadhaar_search and record_area == str(area).strip():
                return record_badge_id
        return None
    except Exception as e: app.logger.error(f"Error checking SNE Aadhaar: {e}", exc_info=True); return False

def get_next_badge_id(sheet, area, centre):
    """Generates the next sequential SNE Badge ID specific to Area and Centre."""
    if not sheet: raise Exception("Could not connect to SNE sheet.")
    if area not in BADGE_CONFIG or centre not in BADGE_CONFIG[area]: raise ValueError("Invalid Area or Centre for SNE.")
    config = BADGE_CONFIG[area][centre]; prefix = config["prefix"]; start_num = config["start"]
    try:
        try:
            badge_id_col_idx = SHEET_HEADERS.index('Badge ID')
            satsang_place_col_idx = SHEET_HEADERS.index('Satsang Place')
        except ValueError as e: raise Exception(f"Missing SNE headers: {e}")
        all_values = sheet.get_all_values(); max_num = start_num - 1
        if len(all_values) > 1:
            data_rows = all_values[1:]; found_matching_centre = False
            for row in data_rows:
                if len(row) <= max(badge_id_col_idx, satsang_place_col_idx): continue
                row_satsang_place = str(row[satsang_place_col_idx]).strip()
                existing_id = str(row[badge_id_col_idx]).strip()
                if row_satsang_place == centre and existing_id.startswith(prefix):
                    found_matching_centre = True
                    try:
                        num_part_str = existing_id[len(prefix):]
                        if num_part_str.isdigit(): max_num = max(max_num, int(num_part_str))
                    except (ValueError, IndexError): pass # Ignore parsing errors
            if not found_matching_centre: max_num = start_num - 1
        next_num = max(start_num, max_num + 1)
        return f"{prefix}{next_num}"
    except Exception as e: app.logger.error(f"Error generating SNE Badge ID: {e}", exc_info=True); raise

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_age_from_dob(dob_str):
    """Calculates age in years from a DOB string."""
    if not dob_str: return None
    try:
        birth_date = parser.parse(dob_str).date(); today = datetime.date.today()
        if birth_date > today: return None
        return relativedelta(today, birth_date).years
    except Exception: return None

def find_row_index_by_value(sheet, column_header, value_to_find, headers_list):
    """Finds the 1-based row index for a value in a column."""
    if not sheet: return None
    try:
        try: col_index = headers_list.index(column_header) + 1
        except ValueError: app.logger.error(f"Header '{column_header}' not found."); return None
        all_values_in_column = sheet.col_values(col_index)
        search_value_cleaned = str(value_to_find).strip().upper()
        if not search_value_cleaned: return None
        for index, value in enumerate(all_values_in_column):
            if index == 0: continue
            if str(value).strip().upper() == search_value_cleaned: return index + 1
        return None
    except Exception as e: app.logger.error(f"Error finding row index for '{value_to_find}': {e}"); return None

def create_pdf_with_composite_badges(badge_data_list):
    """Generates PDF with SNE badges, downloading photos from S3."""
    PAGE_WIDTH_MM = 297; PAGE_HEIGHT_MM = 210; BADGE_WIDTH_MM = 125; BADGE_HEIGHT_MM = 80
    MARGIN_MM = 15; gap_mm = 0; effective_badge_width = BADGE_WIDTH_MM + gap_mm
    effective_badge_height = BADGE_HEIGHT_MM + gap_mm
    badges_per_row = int((PAGE_WIDTH_MM - 2 * MARGIN_MM + gap_mm) / effective_badge_width) if effective_badge_width > 0 else 1
    badges_per_col = int((PAGE_HEIGHT_MM - 2 * MARGIN_MM + gap_mm) / effective_badge_height) if effective_badge_height > 0 else 1
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False, margin=MARGIN_MM)
    pdf.add_page(); col_num = 0; row_num = 0
    try: base_template = Image.open(BADGE_TEMPLATE_PATH).convert("RGBA")
    except Exception as e: raise Exception(f"Error loading template: {e}")
    loaded_fonts = {}; loaded_fonts_bold = {}; bold_load_failed_sizes = set()
    for element, config in TEXT_ELEMENTS.items(): # Pre-load fonts
        size = config['size']; is_bold = config.get('is_bold', False)
        if size not in loaded_fonts:
            try: loaded_fonts[size] = ImageFont.truetype(FONT_PATH, size)
            except Exception as e: raise Exception(f"CRITICAL: Error loading regular font: {e}")
        if is_bold and size not in loaded_fonts_bold and size not in bold_load_failed_sizes:
            try: loaded_fonts_bold[size] = ImageFont.truetype(FONT_BOLD_PATH, size)
            except Exception as e: loaded_fonts_bold[size] = loaded_fonts.get(size); bold_load_failed_sizes.add(size)
    for data in badge_data_list:
        badge_image = None
        try:
            badge_image = base_template.copy(); draw = ImageDraw.Draw(badge_image)
            s3_object_key = data.get('Photo Filename', '')
            if s3_object_key and s3_object_key not in ['N/A', 'Upload Error', '']:
                try:
                    s3_response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_object_key)
                    with Image.open(BytesIO(s3_response['Body'].read())).convert("RGBA") as holder_photo:
                        with holder_photo.resize((BOX_WIDTH_PX, BOX_HEIGHT_PX), Image.Resampling.LANCZOS) as resized_photo:
                            badge_image.paste(resized_photo, (PASTE_X_PX, PASTE_Y_PX), resized_photo)
                except Exception as e: app.logger.error(f"Badge Gen: Error processing S3 photo '{s3_object_key}': {e}")
            display_age = data.get('Age', '') or (calculate_age_from_dob(data.get('Date of Birth')) or '')
            details = {
                "badge_id": str(data.get('Badge ID', 'N/A')), "name": f"{str(data.get('First Name', '')).upper()} {str(data.get('Last Name', '')).upper()}".strip(),
                "gender": str(data.get('Gender', '')).upper(), "age": f"AGE: {display_age} YEARS" if display_age else "",
                "centre": str(data.get('Satsang Place', '')).upper(), "area": str(data.get('Area', '')).upper(), "address": str(data.get('Address', ''))
            }
            for key, text in details.items():
                if key in TEXT_ELEMENTS and text:
                    config = TEXT_ELEMENTS[key]; font_size = config['size']; is_bold = config.get('is_bold', False)
                    font = loaded_fonts_bold.get(font_size) if is_bold else loaded_fonts.get(font_size)
                    if not font and is_bold: font = loaded_fonts.get(font_size) # Fallback
                    if not font: continue
                    if key == "address":
                        wrapped = "\n".join(textwrap.wrap(text, width=20)); bbox = draw.multiline_textbbox(config['coords'], wrapped, font=font, spacing=10)
                        box_coords = [bbox[0] - 17, bbox[1] - 17, bbox[2] + 17, bbox[3] + 17]
                        draw.rectangle(box_coords, outline="black", width=0)
                        draw.multiline_text(config['coords'], wrapped, fill=config['color'], font=font, spacing=10)
                    else: draw.text(config['coords'], text, fill=config['color'], font=font)
            if col_num >= badges_per_row: col_num = 0; row_num += 1
            if row_num >= badges_per_col: row_num = 0; pdf.add_page()
            x_pos = MARGIN_MM + col_num * effective_badge_width; y_pos = MARGIN_MM + row_num * effective_badge_height
            with BytesIO() as temp_img_buffer:
                badge_image.save(temp_img_buffer, format="PNG"); temp_img_buffer.seek(0)
                pdf.image(temp_img_buffer, x=x_pos, y=y_pos, w=BADGE_WIDTH_MM, h=BADGE_HEIGHT_MM, type='PNG')
            col_num += 1
        except Exception as e: app.logger.error(f"Badge composition failed for ID {data.get('Badge ID', 'N/A')}: {e}")
        finally:
             if badge_image and badge_image != base_template: badge_image.close()
    base_template.close()
    try: return BytesIO(pdf.output())
    except TypeError: return BytesIO(pdf.output(dest='S').encode('latin-1'))

def find_donor_by_mobile(sheet, mobile_number):
    """Finds the LATEST Blood Camp donor entry by mobile number."""
    if not sheet: return None
    try:
        mobile_header = "Mobile Number"; timestamp_header = "Submission Timestamp"
        mobile_col_index = BLOOD_CAMP_SHEET_HEADERS.index(mobile_header) + 1
        timestamp_col_index = BLOOD_CAMP_SHEET_HEADERS.index(timestamp_header) + 1
    except ValueError: app.logger.error(f"Headers missing in BLOOD_CAMP_SHEET_HEADERS."); return None
    try:
        all_data = sheet.get_all_values(); matching_entries = []
        if len(all_data) <= 1: return None
        cleaned_search_mobile = re.sub(r'\D', '', str(mobile_number))
        if not cleaned_search_mobile: return None
        header_row = BLOOD_CAMP_SHEET_HEADERS; num_headers = len(header_row)
        for i, row in enumerate(all_data[1:], start=2):
            padded_row = row + [''] * (num_headers - len(row)); current_row = padded_row[:num_headers]
            sheet_mobile_raw = str(current_row[mobile_col_index - 1]).strip()
            cleaned_sheet_mobile = re.sub(r'\D', '', sheet_mobile_raw)
            if cleaned_sheet_mobile == cleaned_search_mobile:
                timestamp_str = str(current_row[timestamp_col_index - 1]).strip(); row_timestamp = datetime.datetime.min
                try:
                    if timestamp_str: row_timestamp = parser.parse(timestamp_str)
                except parser.ParserError: pass # Use min date if unparsable
                matching_entries.append({"data": dict(zip(header_row, current_row)), "timestamp": row_timestamp, "row_index": i})
        if not matching_entries: return None
        latest_entry = max(matching_entries, key=lambda x: x["timestamp"])
        return latest_entry["data"]
    except Exception as e: app.logger.error(f"Error searching donor by mobile {mobile_number}: {e}", exc_info=True); return None

def generate_next_donor_id(sheet):
    """Generates the next sequential persistent Donor ID (BDXXXXX format)."""
    if not sheet: return None
    prefix = "BD"; start_num = 1
    try:
        try: donor_id_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
        except ValueError: app.logger.error("Header 'Donor ID' not found."); return None
        all_donor_ids = sheet.col_values(donor_id_col_index); max_num = 0
        for existing_id in all_donor_ids[1:]:
            if isinstance(existing_id, str) and existing_id.startswith(prefix):
                try:
                    num_part_str = existing_id[len(prefix):]
                    if num_part_str.isdigit(): max_num = max(max_num, int(num_part_str))
                except (ValueError, IndexError): pass
        next_num = max(start_num, max_num + 1)
        return f"{prefix}{next_num:05d}"
    except Exception as e: app.logger.error(f"Error generating Donor ID: {e}", exc_info=True); return None

# --- Flask Routes ---

@app.route('/')
@login_required
def home():
    current_year = datetime.date.today().year
    return render_template('home.html', current_year=current_year, current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))
        user_data = users_db.get(username)
        if not user_data or not check_password_hash(user_data['password_hash'], password):
            flash('Invalid username or password.', 'error'); return redirect(url_for('login'))
        user_obj = User.get(username)
        login_user(user_obj, remember=remember)
        flash('Logged in successfully!', 'success')
        return redirect(request.args.get('next') or url_for('home'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); flash('You have been logged out.', 'info'); return redirect(url_for('login'))

# --- SNE Application Routes ---
@app.route('/sne_form')
@login_required
def sne_form_page():
    today_date = datetime.date.today(); current_year = today_date.year
    return render_template('form.html', today_date=today_date, areas=AREAS, states=STATES, relations=RELATIONS, current_user=current_user, current_year=current_year)

@app.route('/submit_sne', methods=['POST'])
@login_required
def submit_sne_form():
    sheet = get_sheet(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet: flash("Error connecting to SNE data storage.", "error"); return redirect(url_for('sne_form_page'))
    try:
        form_data = request.form.to_dict()
        aadhaar_no = form_data.get('aadhaar_no', '').strip()
        selected_area = form_data.get('area', '').strip()
        selected_centre = form_data.get('satsang_place', '').strip()
        dob_str = form_data.get('dob', '')
        mandatory_fields = ['area', 'satsang_place', 'first_name', 'last_name', 'father_husband_name', 'gender', 'dob', 'aadhaar_no', 'emergency_contact_name', 'emergency_contact_number', 'emergency_contact_relation', 'address', 'state']
        if any(not form_data.get(field) for field in mandatory_fields):
            flash(f"Missing mandatory SNE fields.", "error"); return redirect(url_for('sne_form_page'))
        existing_badge_id = check_aadhaar_exists(sheet, aadhaar_no, selected_area)
        if existing_badge_id: flash(f"Error: SNE Aadhaar {aadhaar_no} exists for Area '{selected_area}' (Badge ID '{existing_badge_id}').", "error"); return redirect(url_for('sne_form_page'))
        elif existing_badge_id is False: flash("Error verifying SNE Aadhaar uniqueness.", "error"); return redirect(url_for('sne_form_page'))
        s3_object_key = "N/A"
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                cleaned_aadhaar = re.sub(r'\s+', '', aadhaar_no) if aadhaar_no else ''
                unique_part = cleaned_aadhaar if cleaned_aadhaar else f"{form_data.get('first_name', 'user')}_{form_data.get('last_name', '')}"
                s3_object_key = f"{unique_part}_{timestamp}.{secure_filename(file.filename).rsplit('.', 1)[1].lower()}"
                try: s3_client.upload_fileobj(file, S3_BUCKET_NAME, s3_object_key)
                except Exception as e: app.logger.error(f"S3 UPLOAD FAILED! Key: {s3_object_key}, Error: {e}"); flash(f"Photo upload failed: {e}", "error"); s3_object_key = "Upload Error"
            elif file and file.filename != '': flash(f"Invalid SNE photo type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}.", 'warning'); s3_object_key = "N/A"
        try: new_badge_id = get_next_badge_id(sheet, selected_area, selected_centre)
        except Exception as e: flash(f"Error generating SNE Badge ID: {e}", "error"); return redirect(url_for('sne_form_page'))
        calculated_age = calculate_age_from_dob(dob_str)
        data_row = []
        for header in SHEET_HEADERS:
            form_key = header.lower().replace(' ', '_').replace("'", "").replace('/', '_').replace('(yes/no)', '').replace('(','').replace(')','').strip('_')
            if header == "Submission Date": value = form_data.get('submission_date', datetime.date.today().isoformat())
            elif header == "Area": value = selected_area
            elif header == "Satsang Place": value = selected_centre
            elif header == "Age": value = calculated_age if calculated_age is not None else ''
            elif header == "Aadhaar No": value = aadhaar_no
            elif header == "Photo Filename": value = s3_object_key
            elif header == "Badge ID": value = new_badge_id
            elif header.endswith('(Yes/No)'): value = form_data.get(header.replace(' (Yes/No)', '').lower().replace(' ', '_').replace("'", "").replace('/', '_'), 'No')
            else: value = form_data.get(form_key, '')
            data_row.append(str(value))
        try: sheet.append_row(data_row); flash(f'SNE Data submitted! Badge ID: {new_badge_id}', 'success')
        except Exception as e:
            app.logger.error(f"Error writing SNE data to Sheet: {e}")
            if s3_object_key not in ["N/A", "Upload Error"]:
                try: s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_object_key); app.logger.info(f"Deleted S3 object '{s3_object_key}' after sheet error.")
                except Exception as s3_del_err: app.logger.error(f"FAILED to delete S3 object '{s3_object_key}' after sheet error: {s3_del_err}")
            flash(f'Error submitting SNE data to Sheet: {e}.', 'error')
        return redirect(url_for('sne_form_page'))
    except Exception as e: app.logger.error(f"Unexpected error during SNE submission: {e}", exc_info=True); flash(f'Unexpected error: {e}', 'error'); return redirect(url_for('sne_form_page'))

@app.route('/printer')
@login_required
def printer():
    current_year = datetime.date.today().year
    return render_template('printer_form.html', centres=CENTRES, current_user=current_user, current_year=current_year)

@app.route('/generate_pdf', methods=['POST'])
@login_required
def generate_pdf():
    badge_ids_raw = request.form.get('badge_ids', '')
    badge_ids = [bid.strip().upper() for bid in badge_ids_raw.split(',') if bid.strip()]
    if not badge_ids: flash("Please enter at least one SNE Badge ID.", "error"); return redirect(url_for('printer'))
    try:
        all_sheet_data = get_all_sheet_data(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE, SHEET_HEADERS)
        data_map = {str(row.get('Badge ID', '')).strip().upper(): row for row in all_sheet_data if row.get('Badge ID')}
    except Exception as e: flash(f"Error fetching SNE data: {e}", "error"); return redirect(url_for('printer'))
    badges_to_print = []; not_found_ids = []
    for bid in badge_ids:
        if bid in data_map: badges_to_print.append(data_map[bid])
        else: not_found_ids.append(bid)
    if not badges_to_print: flash("No valid SNE Badge IDs found.", "error"); return redirect(url_for('printer'))
    if not_found_ids: flash(f"Warning: SNE IDs not found: {', '.join(not_found_ids)}", "warning")
    try:
        pdf_buffer = create_pdf_with_composite_badges(badges_to_print)
        filename = f"SNE_Composite_Badges_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')
    except Exception as e: app.logger.error(f"Error generating SNE PDF: {e}", exc_info=True); flash(f"Error generating PDF: {e}", "error"); return redirect(url_for('printer'))

@app.route('/get_centres/<area>')
@login_required
def get_centres(area):
    if area in BADGE_CONFIG: return jsonify(sorted(list(BADGE_CONFIG[area].keys())))
    else: return jsonify([])

@app.route('/edit')
@login_required
def edit_form_page():
    current_year = datetime.date.today().year
    return render_template('edit_form.html', areas=AREAS, states=STATES, relations=RELATIONS, current_user=current_user, current_year=current_year)

@app.route('/search_entries', methods=['GET'])
@login_required
def search_entries():
    search_name = request.args.get('name', '').strip().lower()
    search_badge_id = request.args.get('badge_id', '').strip().upper()
    try:
        all_data = get_all_sheet_data(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE, SHEET_HEADERS)
        results = []
        if search_badge_id:
             for entry in all_data:
                 if str(entry.get('Badge ID', '')).strip().upper() == search_badge_id: results.append(entry); break
        elif search_name:
            for entry in all_data:
                first = str(entry.get('First Name', '')).strip().lower()
                last = str(entry.get('Last Name', '')).strip().lower()
                if search_name in first or search_name in last or search_name in f"{first} {last}": results.append(entry)
        return jsonify(results[:50])
    except Exception as e: app.logger.error(f"Error searching SNE entries: {e}", exc_info=True); return jsonify({"error": f"SNE Search failed: {e}"}), 500

@app.route('/update_entry/<original_badge_id>', methods=['POST'])
@login_required
def update_entry(original_badge_id):
    if not original_badge_id: flash("Error: No SNE Badge ID for update.", "error"); return redirect(url_for('edit_form_page'))
    sheet = get_sheet(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet: flash("Error connecting to SNE data storage.", "error"); return redirect(url_for('edit_form_page'))
    try:
        row_index = find_row_index_by_value(sheet, 'Badge ID', original_badge_id, SHEET_HEADERS)
        if not row_index: flash(f"Error: SNE entry {original_badge_id} not found.", "error"); return redirect(url_for('edit_form_page'))
        form_data = request.form.to_dict()
        try:
            original_record_list = sheet.row_values(row_index)
            while len(original_record_list) < len(SHEET_HEADERS): original_record_list.append('')
            original_record = dict(zip(SHEET_HEADERS, original_record_list))
            aadhaar_no = original_record.get('Aadhaar No', '').strip()
            old_s3_key = original_record.get('Photo Filename', '')
        except Exception as fetch_err: app.logger.error(f"Could not fetch original SNE record {original_badge_id}: {fetch_err}"); flash(f"Error fetching SNE data.", "error"); return redirect(url_for('edit_form_page'))
        new_s3_key = old_s3_key; delete_old_s3_object = False; uploaded_new_key = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                cleaned_aadhaar = re.sub(r'\s+', '', aadhaar_no) if aadhaar_no else ''
                unique_part = cleaned_aadhaar if cleaned_aadhaar else f"{form_data.get('first_name', 'user')}_{form_data.get('last_name', '')}"
                temp_new_key = f"{unique_part}_{timestamp}.{secure_filename(file.filename).rsplit('.', 1)[1].lower()}"
                try:
                    s3_client.upload_fileobj(file, S3_BUCKET_NAME, temp_new_key)
                    new_s3_key = temp_new_key; uploaded_new_key = temp_new_key
                    if old_s3_key and old_s3_key not in ["N/A", "Upload Error", ""] and old_s3_key != new_s3_key: delete_old_s3_object = True
                except Exception as e: app.logger.error(f"S3 UPLOAD FAILED! Key: {temp_new_key}, Error: {e}"); flash(f"Photo upload failed: {e}", "error")
            elif file and file.filename != '': flash(f"Invalid SNE photo type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}.", 'warning')
        dob_str = form_data.get('dob', '')
        calculated_age = calculate_age_from_dob(dob_str)
        updated_data_row = []
        for header in SHEET_HEADERS:
            form_key = header.lower().replace(' ', '_').replace("'", "").replace('/', '_').replace('(yes/no)', '').replace('(','').replace(')','').strip('_')
            if header == "Badge ID": value = original_badge_id
            elif header == "Aadhaar No": value = aadhaar_no
            elif header == "Age": value = calculated_age if calculated_age is not None else ''
            elif header == "Photo Filename": value = new_s3_key
            elif header == "Submission Date": value = original_record.get('Submission Date', '')
            elif header.endswith('(Yes/No)'): value = form_data.get(header.replace(' (Yes/No)', '').lower().replace(' ', '_').replace("'", "").replace('/', '_'), 'No')
            else: value = form_data.get(form_key, '')
            updated_data_row.append(str(value))
        try:
            end_column_letter = gspread.utils.rowcol_to_a1(1, len(SHEET_HEADERS)).split('1')[0]
            sheet.update(f'A{row_index}:{end_column_letter}{row_index}', [updated_data_row])
            if delete_old_s3_object:
                try: s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=old_s3_key); app.logger.info(f"Deleted old S3 object: {old_s3_key}")
                except Exception as s3_del_err: app.logger.error(f"FAILED to delete old S3 object '{old_s3_key}': {s3_del_err}"); flash(f"Updated, but failed to delete old photo.", "warning")
            flash(f'SNE Entry {original_badge_id} updated!', 'success'); return redirect(url_for('edit_form_page'))
        except Exception as e:
            app.logger.error(f"Error updating SNE Sheet {original_badge_id}: {e}")
            if uploaded_new_key:
                try: s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=uploaded_new_key); app.logger.info(f"Deleted new S3 object '{uploaded_new_key}' after sheet error.")
                except Exception as s3_del_err: app.logger.error(f"FAILED to delete new S3 object '{uploaded_new_key}' after sheet error: {s3_del_err}")
            flash(f'Error updating SNE Sheet: {e}.', 'error'); return redirect(url_for('edit_form_page'))
    except Exception as e: app.logger.error(f"Unexpected error during SNE update {original_badge_id}: {e}", exc_info=True); flash(f'Unexpected error: {e}', 'error'); return redirect(url_for('edit_form_page'))

# --- Blood Camp Routes ---

@app.route('/blood_camp')
@login_required
def blood_camp_form_page():
    today_date = datetime.date.today(); current_year = today_date.year
    # Removed BLOOD_CAMP_AREAS pass
    return render_template('blood_camp_form.html', today_date=today_date, current_year=current_year, current_user=current_user)

@app.route('/search_donor', methods=['GET'])
@login_required
def search_donor():
    mobile_number = request.args.get('mobile', '').strip()
    if not mobile_number or not re.fullmatch(r'\d{10}', mobile_number):
        return jsonify({"error": "Invalid mobile number format (must be 10 digits)."}), 400
    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet: return jsonify({"error": "Could not connect to donor database."}), 500
    donor_record = find_donor_by_mobile(sheet, mobile_number) # Finds latest entry
    if donor_record: return jsonify({"found": True, "donor": donor_record})
    else: return jsonify({"found": False})

# CORRECTED submit_blood_camp route (Only ONE definition)
@app.route('/submit_blood_camp', methods=['POST'])
@login_required
def submit_blood_camp():
    """Handles blood camp form submission with persistent Donor ID and history."""
    form_data = request.form.to_dict()
    mobile_number = form_data.get('mobile_no', '').strip()

    # --- Basic Validation ---
    if not mobile_number: flash("Mobile number is required.", "error"); return redirect(url_for('blood_camp_form_page'))
    cleaned_mobile_number = re.sub(r'\D', '', mobile_number)
    if len(cleaned_mobile_number) != 10: flash("Mobile number must be 10 digits.", "error"); return redirect(url_for('blood_camp_form_page'))

    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet: flash("Error connecting to the donor database.", "error"); return redirect(url_for('blood_camp_form_page'))

    try:
        existing_donor_data = find_donor_by_mobile(sheet, cleaned_mobile_number)
        current_donation_date = form_data.get('donation_date', datetime.date.today().isoformat())

        if existing_donor_data:
            # --- Update Existing Donor's Donation Record ---
            donor_id = existing_donor_data.get("Donor ID")
            if not donor_id:
                 app.logger.error(f"Inconsistency: Donor found by mobile {cleaned_mobile_number} but no Donor ID: {existing_donor_data}")
                 flash("Data inconsistency found. Contact support.", "error"); return redirect(url_for('blood_camp_form_page'))
            first_donation_date = existing_donor_data.get("First Donation Date", current_donation_date)
            try: total_donations = int(existing_donor_data.get("Total Donations", 0)) + 1
            except (ValueError, TypeError): total_donations = 1
            data_row = []
            for header in BLOOD_CAMP_SHEET_HEADERS:
                form_key = header.lower().replace("'", "").replace('/', '_').replace(' ', '_')
                if header == "Donor ID": value = donor_id
                elif header == "Submission Timestamp": value = datetime.datetime.now().isoformat()
                elif header == "Mobile Number": value = cleaned_mobile_number
                elif header == "Donation Date": value = current_donation_date
                elif header == "Donation Location": value = form_data.get('donation_location', '')
                elif header == "First Donation Date": value = first_donation_date
                elif header == "Total Donations": value = total_donations
                elif header in ["Status", "Reason for Rejection"]: value = '' # Reset status
                else: value = form_data.get(form_key, existing_donor_data.get(header, '')) # Allow updating other fields
                data_row.append(str(value))
            sheet.append_row(data_row)
            flash(f'Donation recorded for Donor ID: {donor_id} (Total: {total_donations})', 'success')
        else:
            # --- Add New Donor ---
            new_donor_id = generate_next_donor_id(sheet)
            if not new_donor_id: flash("Error generating Donor ID.", "error"); return redirect(url_for('blood_camp_form_page'))
            first_donation_date = current_donation_date; total_donations = 1
            data_row = []
            for header in BLOOD_CAMP_SHEET_HEADERS:
                form_key = header.lower().replace("'", "").replace('/', '_').replace(' ', '_')
                if header == "Donor ID": value = new_donor_id
                elif header == "Submission Timestamp": value = datetime.datetime.now().isoformat()
                elif header == "Mobile Number": value = cleaned_mobile_number
                elif header == "Donation Date": value = current_donation_date
                elif header == "First Donation Date": value = first_donation_date
                elif header == "Total Donations": value = total_donations
                elif header in ["Status", "Reason for Rejection"]: value = ''
                else: value = form_data.get(form_key, '')
                data_row.append(str(value))
            sheet.append_row(data_row)
            flash(f'New donor registered! Donor ID: {new_donor_id}', 'success')
        return redirect(url_for('blood_camp_form_page'))
    except Exception as e:
        app.logger.error(f"Error during blood camp submission: {e}", exc_info=True)
        flash(f"Server error during submission: {e}", "error")
        return redirect(url_for('blood_camp_form_page'))


@app.route('/blood_donor_status')
@login_required
def blood_donor_status_page():
    today_date = datetime.date.today(); current_year = today_date.year
    return render_template('blood_donor_status.html', today_date=today_date, current_year=current_year, current_user=current_user)

@app.route('/get_donor_details/<donor_id>', methods=['GET'])
@login_required
def get_donor_details(donor_id):
    if not donor_id: return jsonify({"error": "Donor ID is required."}), 400
    if not re.fullmatch(r'BD\d{5}', donor_id): return jsonify({"error": "Invalid Donor ID format."}), 400
    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet: return jsonify({"error": "Could not connect to donor database."}), 500
    try:
        # Find LATEST entry for this Donor ID to get current status
        all_data = sheet.get_all_values()
        matching_rows = []
        try:
            donor_id_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
            timestamp_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Submission Timestamp") + 1
            name_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Name of Donor") + 1
            status_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Status") + 1
            reason_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Reason for Rejection") + 1
        except ValueError as e: app.logger.error(f"Header config error: {e}"); return jsonify({"error": "Server config error."}), 500

        for i, row in enumerate(all_data[1:], start=2):
             padded_row = row + [''] * (len(BLOOD_CAMP_SHEET_HEADERS) - len(row))
             if len(padded_row) >= donor_id_col_index and str(padded_row[donor_id_col_index - 1]).strip() == donor_id:
                 timestamp_str = str(padded_row[timestamp_col_index - 1]).strip(); row_timestamp = datetime.datetime.min
                 try:
                     if timestamp_str: row_timestamp = parser.parse(timestamp_str)
                 except parser.ParserError: pass
                 matching_rows.append({
                     "index": i, "timestamp": row_timestamp,
                     "name": str(padded_row[name_col_index - 1]),
                     "status": str(padded_row[status_col_index - 1]),
                     "reason": str(padded_row[reason_col_index - 1])
                 })

        if not matching_rows: return jsonify({"found": False, "error": "Donor not found."}), 404

        latest_row_info = max(matching_rows, key=lambda x: x["timestamp"])
        return jsonify({"found": True, "name": latest_row_info["name"], "status": latest_row_info["status"], "reason": latest_row_info["reason"]})
    except Exception as e: app.logger.error(f"Error fetching donor details {donor_id}: {e}", exc_info=True); return jsonify({"error": "Server error."}), 500

@app.route('/update_donor_status', methods=['POST'])
@login_required
def update_donor_status():
    donor_id = request.form.get('donor_id', '').strip()
    status = request.form.get('status', '').strip()
    reason = request.form.get('reason', '').strip()
    if not donor_id or not re.fullmatch(r'BD\d{5}', donor_id): flash("Valid Donor ID required.", "error"); return redirect(url_for('blood_donor_status_page'))
    if not status: flash("Status required.", "error"); return redirect(url_for('blood_donor_status_page'))
    if status == 'Rejected' and not reason: flash("Reason required for rejection.", "error"); return redirect(url_for('blood_donor_status_page'))
    if status == 'Accepted': reason = ''
    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet: flash("Error connecting to database.", "error"); return redirect(url_for('blood_donor_status_page'))
    try:
        try:
            donor_id_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
            timestamp_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Submission Timestamp") + 1
            status_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Status") + 1
            reason_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Reason for Rejection") + 1
        except ValueError as e: app.logger.error(f"Header config error: {e}"); flash("Server config error.", "error"); return redirect(url_for('blood_donor_status_page'))
        all_data = sheet.get_all_values(); matching_rows = []
        for i, row in enumerate(all_data[1:], start=2):
             padded_row = row + [''] * (len(BLOOD_CAMP_SHEET_HEADERS) - len(row))
             if len(padded_row) >= donor_id_col_index and str(padded_row[donor_id_col_index - 1]).strip() == donor_id:
                 timestamp_str = str(padded_row[timestamp_col_index - 1]).strip(); row_timestamp = datetime.datetime.min
                 try:
                     if timestamp_str: row_timestamp = parser.parse(timestamp_str)
                 except parser.ParserError: pass
                 matching_rows.append({"index": i, "timestamp": row_timestamp})
        if not matching_rows: flash(f"Donor ID '{donor_id}' not found.", "error"); return redirect(url_for('blood_donor_status_page'))
        latest_row_info = max(matching_rows, key=lambda x: x["timestamp"])
        row_index_to_update = latest_row_info["index"]
        updates = [gspread.Cell(row=row_index_to_update, col=status_col_index, value=status), gspread.Cell(row=row_index_to_update, col=reason_col_index, value=reason)]
        sheet.update_cells(updates)
        flash(f"Status updated for Donor ID: {donor_id}", "success")
        return redirect(url_for('blood_donor_status_page'))
    except Exception as e: app.logger.error(f"Error updating status for {donor_id}: {e}", exc_info=True); flash(f"Error updating status: {e}", "error"); return redirect(url_for('blood_donor_status_page'))

@app.route('/dashboard')
@login_required
def dashboard():
    app.logger.info("Dashboard route accessed")
    current_year = datetime.date.today().year
    return render_template('dashboard.html', current_year=current_year, current_user=current_user)

@app.route('/dashboard_data')
@login_required
def dashboard_data():
    """Provides data for the updated blood camp dashboard charts."""
    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet: return jsonify({"error": "Could not connect to data source."}), 500
    try:
        all_values = sheet.get_all_values()
        if not all_values or len(all_values) < 2:
            return jsonify({ # Return default structure with zeros
                "kpis": {"registrations_today": 0, "accepted_total": 0, "rejected_total": 0, "acceptance_rate": 0.0},
                "blood_group_distribution": {}, "gender_distribution": {}, "age_group_distribution": {},
                "status_counts": {"Accepted": 0, "Rejected": 0, "Other/Pending": 0},
                "rejection_reasons": {}, "donor_types": {"First-Time": 0, "Repeat": 0},
                "communication_opt_in": {}
            })
        header_row = BLOOD_CAMP_SHEET_HEADERS; data_rows = all_values[1:]
        today_str = datetime.date.today().isoformat()
        try: # Get column indices
            donor_id_col = header_row.index("Donor ID"); timestamp_col = header_row.index("Submission Timestamp")
            dob_col = header_row.index("Date of Birth"); gender_col = header_row.index("Gender")
            blood_group_col = header_row.index("Blood Group"); allow_call_col = header_row.index("Allow Call")
            total_donations_col = header_row.index("Total Donations"); status_col = header_row.index("Status")
            reason_col = header_row.index("Reason for Rejection")
        except ValueError as e: app.logger.error(f"Dashboard Data: Missing header: {e}"); return jsonify({"error": f"Missing column config: {e}"}), 500

        latest_donor_entries = {}; num_headers = len(header_row)
        for row_index, row in enumerate(data_rows): # Find latest entry per Donor ID
            padded_row = row + [''] * (num_headers - len(row)); current_row = padded_row[:num_headers]
            donor_id = str(current_row[donor_id_col]).strip()
            if not donor_id: continue
            timestamp_str = str(current_row[timestamp_col]).strip(); row_timestamp = datetime.datetime.min
            try:
                if timestamp_str: row_timestamp = parser.parse(timestamp_str)
            except parser.ParserError: pass
            if donor_id not in latest_donor_entries or row_timestamp > latest_donor_entries[donor_id].get("timestamp", datetime.datetime.min):
                 latest_donor_entries[donor_id] = {"data": current_row, "timestamp": row_timestamp}

        registrations_today = 0; accepted_count = 0; rejected_count = 0
        blood_groups = []; genders = []; ages = []; statuses = []
        rejection_reasons = []; donor_types_list = []; allow_calls = []

        for donor_id, entry in latest_donor_entries.items(): # Process latest entries
            row_data = entry["data"]; row_timestamp = entry["timestamp"]
            if row_timestamp and row_timestamp.date().isoformat() == today_str: registrations_today += 1
            stat = str(row_data[status_col]).strip().capitalize()
            if stat == "Accepted": accepted_count += 1; statuses.append("Accepted")
            elif stat == "Rejected":
                rejected_count += 1; statuses.append("Rejected")
                reason_text = str(row_data[reason_col]).strip()
                if reason_text: rejection_reasons.append(reason_text)
            else: statuses.append("Other/Pending")
            bg = str(row_data[blood_group_col]).strip(); blood_groups.append(bg if bg else "Unknown")
            gen = str(row_data[gender_col]).strip(); genders.append(gen if gen else "Unknown")
            age = calculate_age_from_dob(str(row_data[dob_col]).strip());
            if age is not None: ages.append(age)
            donations_str = str(row_data[total_donations_col]).strip()
            try:
                num_donations = int(donations_str)
                if num_donations > 1: donor_types_list.append("Repeat")
                else: donor_types_list.append("First-Time") # Includes 1, 0, negative
            except (ValueError, TypeError): donor_types_list.append("First-Time")
            call_pref = str(row_data[allow_call_col]).strip().capitalize(); allow_calls.append(call_pref if call_pref in ["Yes", "No"] else "Unknown")

        total_decided = accepted_count + rejected_count
        acceptance_rate = (accepted_count / total_decided * 100) if total_decided > 0 else 0.0
        age_bins = [(18, 25), (26, 35), (36, 45), (46, 55), (56, 65), (66, 120)]
        age_group_counts = collections.defaultdict(int)
        for age in ages:
            binned = False
            for min_age, max_age in age_bins:
                if min_age <= age <= max_age: age_group_counts[f"{min_age}-{max_age}"] += 1; binned = True; break
            if not binned: age_group_counts["> 65" if age > 65 else "< 18"] += 1
        try: sorted_age_group_keys = sorted(age_group_counts.keys(), key=lambda x: int(re.search(r'\d+', x.replace('<','').replace('>','')).group()))
        except: sorted_age_group_keys = sorted(age_group_counts.keys())
        sorted_age_group_counts = {k: age_group_counts[k] for k in sorted_age_group_keys}
        blood_group_counts = collections.Counter(blood_groups); gender_counts = collections.Counter(genders)
        status_counts = collections.Counter(statuses); rejection_reason_counts = collections.Counter(rejection_reasons)
        donor_type_counts = collections.Counter(donor_types_list); communication_counts = collections.Counter(allow_calls)
        final_status_counts = {"Accepted": status_counts.get("Accepted", 0), "Rejected": status_counts.get("Rejected", 0), "Other/Pending": status_counts.get("Other/Pending", 0)}
        final_donor_type_counts = {"First-Time": donor_type_counts.get("First-Time", 0), "Repeat": donor_type_counts.get("Repeat", 0)}
        final_communication_counts = {"Yes": communication_counts.get("Yes", 0), "No": communication_counts.get("No", 0), "Unknown": communication_counts.get("Unknown", 0)}

        return jsonify({
            "kpis": {"registrations_today": registrations_today, "accepted_total": accepted_count, "rejected_total": rejected_count, "acceptance_rate": round(acceptance_rate, 1)},
            "blood_group_distribution": dict(blood_group_counts), "gender_distribution": dict(gender_counts),
            "age_group_distribution": sorted_age_group_counts, "status_counts": final_status_counts,
            "rejection_reasons": dict(rejection_reason_counts.most_common(10)), "donor_types": final_donor_type_counts,
            "communication_opt_in": final_communication_counts
        })
    except Exception as e: app.logger.error(f"Dashboard Data: Error processing: {e}", exc_info=True); return jsonify({"error": f"Server error: {e}"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    # Use host='0.0.0.0' for deployment, debug=False for production
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False) # Example for deployment
    # app.run(debug=True, port=5000) # For local development

