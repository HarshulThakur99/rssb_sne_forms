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

# --- Configuration ---
UPLOAD_FOLDER = 'uploads'
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

# new changes
# Define expected headers for the SNE sheet IN ORDER
SHEET_HEADERS = [
    "Submission Date", "Area", "Satsang Place", "First Name", "Last Name",
    "Father's/Husband's Name", "Gender", "Date of Birth", "Age", "Blood Group",
    "Aadhaar No", "Physically Challenged (Yes/No)", "Physically Challenged Details",
    "Help Required for Home Pickup (Yes/No)", "Help Pickup Reasons", "Handicap (Yes/No)",
    "Stretcher Required (Yes/No)", "Wheelchair Required (Yes/No)", "Ambulance Required (Yes/No)",
    "Pacemaker Operated (Yes/No)", "Chair Required for Sitting (Yes/No)",
    "Special Attendant Required (Yes/No)", "Hearing Loss (Yes/No)", "Mobile No",
    "Willing to Attend Satsangs (Yes/No)", "Satsang Pickup Help Details", "Other Special Requests",
    "Emergency Contact Name", "Emergency Contact Number", "Emergency Contact Relation",
    "Address", "State", "PIN Code", "Photo Filename", "Badge ID"
]

# Define expected headers for the Blood Camp sheet IN ORDER (User provided + Added back missing)
BLOOD_CAMP_SHEET_HEADERS = [
    "Token ID", "Submission Timestamp", "Area", # A, B, C
    "Name of Donor", "Father's/Husband's Name", # D, E
    "Date of Birth", "Gender", "Occupation", "House No.", "Sector", # F, G, H, I, J
    "City", "Mobile Number", # K, L <-- Mobile is 12th (index 11)
    "Blood Group", "Allow Call", "Donation Date", # M, N, O ("Donation Date" here likely means *Last* Donation Date)
    "Donation Location", # P (Likely *Last* Donation Location)
    "First Donation Date", "Total Donations", # Q, R <-- Added back
    "Status", "Reason for Rejection" # S, T
]


# Define Areas for Blood Camp
BLOOD_CAMP_AREAS = ['Chandigarh', 'Mullanpur Garibdass']


TEXT_ELEMENTS = {
    "badge_id": {"coords": (100, 1200), "size": 130, "color": (139, 0, 0), "is_bold": True},
    "name":     {"coords": (100, 1350), "size": 110, "color": "black", "is_bold": True},
    "gender":   {"coords": (100, 1500), "size": 110, "color": "black", "is_bold": True},
    "age":      {"coords": (100, 1650), "size": 110, "color": (139, 0, 0), "is_bold": True},
    "centre":   {"coords": (100, 1800), "size": 110, "color": "black", "is_bold": True},
    "area":     {"coords": (100, 1950), "size": 110, "color": "black", "is_bold": True},
    "address":  {"coords": (1750, 250), "size": 110, "color": "black", "is_bold": True}
}

BADGE_CONFIG = { # SNE Badge Config remains the same
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

def get_sheet(sheet_id, service_account_path, read_only=False):
    """
    Authenticates and returns a specific Google Sheet worksheet object.
    Handles file not found and other common errors.
    """
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        if read_only:
            scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']

        if not os.path.exists(service_account_path):
             app.logger.error(f"Service account file not found: {service_account_path}")
             return None

        creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        return sheet
    except FileNotFoundError:
        app.logger.error(f"Service account file not found during credential loading: {service_account_path}")
        return None
    except gspread.exceptions.SpreadsheetNotFound:
        app.logger.error(f"Spreadsheet not found: {sheet_id}")
        return None
    except gspread.exceptions.APIError as e:
         app.logger.error(f"gspread API error accessing sheet (ID: {sheet_id}): {e}")
         return None
    except Exception as e:
        app.logger.error(f"Unexpected error accessing Google Sheet (ID: {sheet_id}): {e}", exc_info=True)
        return None

def get_all_sheet_data(sheet_id, service_account_path, include_headers=False):
    """Gets all data from the specified sheet."""
    sheet = get_sheet(sheet_id, service_account_path, read_only=True) # Use read-only for fetching data
    if not sheet:
        raise Exception(f"Could not connect to sheet {sheet_id} to get data.")
    try:
        if include_headers:
            data = sheet.get_all_values() # Returns list of lists including header row
        else:
            # Use include_empty=False to potentially skip fully empty rows if needed
            data = sheet.get_all_records(head=1, default_blank="") # Returns list of dictionaries
        app.logger.info(f"Fetched {len(data)} records from Google Sheet ID: {sheet_id}.")
        return data
    except Exception as e:
        app.logger.error(f"Could not get sheet data from {sheet_id}: {e}")
        raise Exception(f"Could not get sheet data from {sheet_id}: {e}")

def check_aadhaar_exists(sheet, aadhaar, area, exclude_badge_id=None):
    """
    Checks if Aadhaar already exists for the given Area in the SNE sheet,
    optionally excluding a specific Badge ID.
    Returns the existing Badge ID if found, otherwise None.
    """
    if not sheet:
        app.logger.error("SNE Sheet object is None in check_aadhaar_exists.")
        return False # Indicate error

    try:
        all_records = sheet.get_all_records(head=1, default_blank="") # Use headers from row 1
        aadhaar_col_header = 'Aadhaar No'
        area_col_header = 'Area'
        badge_id_col_header = 'Badge ID'

        # Clean the input Aadhaar number (remove spaces)
        cleaned_aadhaar_search = re.sub(r'\s+', '', str(aadhaar)).strip()
        if not cleaned_aadhaar_search: # Avoid searching for empty Aadhaar
             app.logger.warning("Attempted to check for empty Aadhaar number.")
             return None

        for record in all_records:
            # Check if record might be empty
            if not any(record.values()):
                continue # Skip potentially empty rows

            if exclude_badge_id and str(record.get(badge_id_col_header, '')).strip() == str(exclude_badge_id).strip():
                continue

            # Clean the Aadhaar number from the sheet
            record_aadhaar_raw = str(record.get(aadhaar_col_header, '')).strip()
            record_aadhaar_cleaned = re.sub(r'\s+', '', record_aadhaar_raw)

            record_area = str(record.get(area_col_header, '')).strip()
            record_badge_id = str(record.get(badge_id_col_header, '')).strip()

            # Compare cleaned Aadhaar numbers
            if record_aadhaar_cleaned == cleaned_aadhaar_search and record_area == str(area).strip():
                app.logger.info(f"SNE Aadhaar {cleaned_aadhaar_search} (Raw: {record_aadhaar_raw}) found in Area {area} with Badge ID {record_badge_id}.")
                return record_badge_id # Return the existing Badge ID

        return None # No matching record found
    except Exception as e:
        app.logger.error(f"Error checking SNE Aadhaar: {e}")
        return False # Indicate error

def get_next_badge_id(sheet, area, centre):
    """Generates the next sequential SNE Badge ID for the Area/Centre."""
    if not sheet:
        app.logger.error("SNE Sheet object is None in get_next_badge_id.")
        raise Exception("Could not connect to SNE sheet to generate Badge ID.")

    if area not in BADGE_CONFIG or centre not in BADGE_CONFIG[area]:
        raise ValueError("Invalid Area or Centre for SNE Badge ID.")
    config = BADGE_CONFIG[area][centre]
    prefix = config["prefix"]
    start_num = config["start"]
    try:
        badge_id_col_header = 'Badge ID'
        all_records = sheet.get_all_records(head=1, default_blank="") # Use headers from row 1
        max_num = start_num - 1
        for record in all_records:
             # Skip potentially empty rows
            if not any(record.values()):
                continue

            existing_id = str(record.get(badge_id_col_header, '')).strip()
            if existing_id.startswith(prefix):
                try:
                    # Ensure the part after prefix is numeric before converting
                    num_part_str = existing_id[len(prefix):]
                    if num_part_str.isdigit():
                        num_part = int(num_part_str)
                        max_num = max(max_num, num_part)
                    else:
                        app.logger.warning(f"Skipping non-numeric SNE Badge ID suffix: {existing_id}")
                except (ValueError, IndexError):
                    app.logger.warning(f"Could not parse SNE Badge ID suffix: {existing_id}")
                    continue
        next_num = max(start_num, max_num + 1)
        return f"{prefix}{next_num}"
    except Exception as e:
        app.logger.error(f"Error generating SNE Badge ID: {e}")
        raise Exception(f"Could not generate SNE Badge ID: {e}")

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

def find_row_index_by_value(sheet, column_header, value_to_find, headers_list):
    """
    Finds the 1-based row index for a given value in a specific column.
    Generic function usable for Badge ID (SNE) or Token ID (Blood Camp).
    Performs case-insensitive and stripped comparison.
    """
    if not sheet:
        app.logger.error(f"Sheet object is None when searching for '{value_to_find}' in column '{column_header}'.")
        return None

    try:
        # Find the 1-based column index from the provided header list
        try:
            col_index = headers_list.index(column_header) + 1
        except ValueError:
            app.logger.error(f"Header '{column_header}' not found in the provided headers list: {headers_list}")
            return None

        # Fetch all values from that specific column
        all_values_in_column = sheet.col_values(col_index)
        app.logger.info(f"Searching for '{value_to_find}' in column {col_index} ('{column_header}'). Found {len(all_values_in_column)} values.")


        # Prepare the search value (strip and uppercase)
        search_value_cleaned = str(value_to_find).strip().upper()
        if not search_value_cleaned: # Avoid matching empty strings
             app.logger.warning(f"Attempted to search for an empty value in column '{column_header}'.")
             return None

        # Iterate through the values to find a match
        for index, value in enumerate(all_values_in_column):
            # Skip header row (index 0)
            if index == 0:
                continue
            sheet_value_cleaned = str(value).strip().upper()
            # Log comparison for debugging
            # app.logger.debug(f"Row {index+1}: Comparing '{search_value_cleaned}' with sheet value '{sheet_value_cleaned}' (Raw: '{value}')")
            if sheet_value_cleaned == search_value_cleaned:
                app.logger.info(f"Found match for '{search_value_cleaned}' at row {index + 1}.")
                return index + 1 # Return 1-based row index

        app.logger.warning(f"Value '{search_value_cleaned}' not found in column '{column_header}'.")
        return None # Not found
    except gspread.exceptions.APIError as e:
         app.logger.error(f"gspread API error finding row for value '{value_to_find}' in column '{column_header}': {e}")
         if 'exceeds grid limits' in str(e):
             app.logger.error(f"Potential issue: '{column_header}' column index ({col_index}) might be incorrect or exceed sheet dimensions.")
         return None
    except Exception as e:
        app.logger.error(f"Error finding row index for value '{value_to_find}' in column '{column_header}': {e}")
        return None


def create_pdf_with_composite_badges(badge_data_list):
    """
    Generates PDF with SNE badges.
    (Code remains the same as provided in the previous version)
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

def find_donor_by_mobile(sheet, mobile_number):
    """
    Searches the Blood Camp sheet for a donor by mobile number in Column L (12th).
    Uses regex to clean and compare numbers (ignores non-digits).
    Returns the donor's record (dict) including Area if found, otherwise None.
    """
    if not sheet:
        app.logger.error("Blood Camp Sheet object is None in find_donor_by_mobile.")
        return None

    # --- Explicitly set column index for Mobile Number (Column L = 12) ---
    # Based on the latest BLOOD_CAMP_SHEET_HEADERS list provided by user
    mobile_col_index = 12
    expected_header = "Mobile Number" # Keep for verification

    try:
        # Optional: Verify header in Column L matches expectation
        header_row = sheet.row_values(1) # Get header row
        actual_header = header_row[mobile_col_index - 1] if len(header_row) >= mobile_col_index else None
        if actual_header != expected_header:
             app.logger.warning(f"Header mismatch in Column {mobile_col_index}: Expected '{expected_header}', Found '{actual_header}'. Proceeding anyway.")
             # If header mismatch is critical, you could return None here:
             # return None

        # Fetch all mobile numbers from the specific column (L)
        all_mobiles_raw = sheet.col_values(mobile_col_index)
        app.logger.info(f"Fetched {len(all_mobiles_raw)} values from Column {mobile_col_index} ('{actual_header or 'N/A'}') for mobile search.")


        # Clean the search mobile number (remove non-digits)
        cleaned_search_mobile = re.sub(r'\D', '', str(mobile_number))
        if not cleaned_search_mobile: # Handle empty search input
             app.logger.warning("Attempted search with empty or invalid mobile number.")
             return None

        # Iterate through the raw mobile numbers from the sheet (skip header row)
        for index, mobile_raw in enumerate(all_mobiles_raw):
            if index == 0: # Skip header row
                continue

            # Clean the sheet mobile number (remove non-digits)
            cleaned_sheet_mobile = re.sub(r'\D', '', str(mobile_raw))

            # Log the comparison (optional, can be verbose)
            # app.logger.debug(f"Comparing search '{cleaned_search_mobile}' with sheet row {index+1} '{cleaned_sheet_mobile}' (Raw: '{mobile_raw}')")

            # Compare cleaned numbers
            if cleaned_sheet_mobile == cleaned_search_mobile:
                # Found the mobile number, get the entire row
                row_index = index + 1
                donor_data_list = sheet.row_values(row_index)
                # Pad the list with empty strings if needed
                while len(donor_data_list) < len(BLOOD_CAMP_SHEET_HEADERS):
                    donor_data_list.append('')
                # Convert list to dictionary using headers
                donor_data_dict = dict(zip(BLOOD_CAMP_SHEET_HEADERS, donor_data_list))
                app.logger.info(f"Blood Camp Donor found by mobile {cleaned_search_mobile} (Raw sheet value: '{mobile_raw}') at row {row_index}.")
                return donor_data_dict

        app.logger.info(f"Blood Camp Donor not found with mobile {cleaned_search_mobile}.")
        return None # Not found
    except gspread.exceptions.APIError as e:
         app.logger.error(f"gspread API error finding Blood Camp donor by mobile {mobile_number} in Column {mobile_col_index}: {e}")
         return None # Indicate sheet API error
    except IndexError:
         app.logger.error(f"IndexError: Could not access expected header or value in column {mobile_col_index}. Check sheet structure.")
         return None
    except Exception as e:
        app.logger.error(f"Error searching Blood Camp donor by mobile {mobile_number}: {e}", exc_info=True)
        return None # Indicate general error

def generate_next_token_id(sheet, area):
    """
    Generates the next sequential Blood Camp Token ID based on the Area and last entry.
    Format: {Prefix}{YYYY}{MMM}{NNNN} (e.g., CHD2025APR0001 or MGD2025APR0001)
    """
    if not sheet:
        app.logger.error("Blood Camp Sheet object is None in generate_next_token_id.")
        return None

    # Determine prefix based on area
    if area == 'Chandigarh':
        area_prefix = 'CHD'
    elif area == 'Mullanpur Garibdass':
        area_prefix = 'MGD'
    else:
        app.logger.error(f"Invalid area '{area}' provided for Token ID generation.")
        return None # Or raise an error

    try:
        # Get all values in the Token ID column (col 1)
        token_col_values = sheet.col_values(1) # Column numbers are 1-based

        # Filter out potential empty strings or header row
        existing_tokens = [token for token in token_col_values if token and isinstance(token, str)]

        now = datetime.datetime.now()
        year_str = now.strftime("%Y")
        month_str = now.strftime("%b").upper() # e.g., APR
        # Full prefix including date part
        full_prefix = f"{area_prefix}{year_str}{month_str}"

        last_seq_num = 0
        if existing_tokens:
            # Find the highest sequence number *only for the current area and month prefix*
            current_area_month_tokens = [token for token in existing_tokens if token.startswith(full_prefix)]
            if current_area_month_tokens:
                 seq_numbers = []
                 for token in current_area_month_tokens:
                     try:
                         # Ensure the part after prefix is numeric before converting
                         num_part_str = token[len(full_prefix):]
                         if num_part_str.isdigit():
                             num_part = int(num_part_str)
                             seq_numbers.append(num_part)
                         else:
                            app.logger.warning(f"Skipping malformed token format: {token}")
                     except (ValueError, IndexError):
                         app.logger.warning(f"Could not parse sequence number from token: {token}")
                         continue
                 if seq_numbers:
                    last_seq_num = max(seq_numbers)

        next_seq_num = last_seq_num + 1
        new_token_id = f"{full_prefix}{next_seq_num:04d}" # Format sequence number

        app.logger.info(f"Generated next Blood Camp Token ID for Area '{area}': {new_token_id}")
        return new_token_id

    except gspread.exceptions.APIError as e:
         app.logger.error(f"gspread API error generating token ID for area {area}: {e}")
         return None
    except Exception as e:
        app.logger.error(f"Error generating Blood Camp Token ID for area {area}: {e}")
        return None


# --- Flask Routes ---

# --- NEW: Homepage Route ---
@app.route('/')
@login_required
def home():
    """Displays the main homepage."""
    # Pass current year for footer, and user object for potential display
    current_year = datetime.date.today().year
    return render_template('home.html', current_year=current_year, current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home')) # Redirect logged-in users to home
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
        # Redirect to intended page or default to home
        return redirect(next_page or url_for('home'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login')) # Redirect to login page after logout

# --- SNE Application Routes ---

# --- UPDATED Route for SNE Form ---
@app.route('/sne_form')
@login_required
def sne_form_page(): # Renamed function
    """Displays the SNE bio-data entry form."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('form.html',
                           today_date=today_date,
                           areas=AREAS, # SNE Areas
                           states=STATES,
                           relations=RELATIONS,
                           current_user=current_user,
                           current_year=current_year)

# --- UPDATED Route for SNE Submission ---
@app.route('/submit_sne', methods=['POST']) # Changed route name slightly for clarity
@login_required
def submit_sne_form(): # Renamed function
    """Handles SNE bio-data form submission."""
    sheet = get_sheet(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to SNE data storage.", "error")
        return redirect(url_for('sne_form_page')) # Redirect back to SNE form

    try:
        form_data = request.form.to_dict()
        aadhaar_no = form_data.get('aadhaar_no', '').strip()
        selected_area = form_data.get('area', '').strip() # SNE Area
        selected_centre = form_data.get('satsang_place', '').strip() # SNE Centre
        dob_str = form_data.get('dob', '')

        mandatory_fields = ['area', 'satsang_place', 'first_name', 'last_name', 'father_husband_name', 'gender', 'dob', 'aadhaar_no', 'emergency_contact_name', 'emergency_contact_number', 'emergency_contact_relation', 'address', 'state']
        missing_fields = [field for field in mandatory_fields if not form_data.get(field)]
        if missing_fields:
            flash(f"Missing mandatory fields: {', '.join(missing_fields)}", "error")
            return redirect(url_for('sne_form_page')) # Redirect back to SNE form

        # Check Aadhaar uniqueness within the SNE sheet and selected SNE Area
        existing_badge_id = check_aadhaar_exists(sheet, aadhaar_no, selected_area)
        if existing_badge_id:
            flash(f"Error: Aadhaar number {aadhaar_no} already exists for SNE Area '{selected_area}' with Badge ID '{existing_badge_id}'.", "error")
            return redirect(url_for('sne_form_page')) # Redirect back to SNE form
        elif existing_badge_id is False:
             flash("Warning: Could not verify SNE Aadhaar uniqueness due to a database error.", "warning")

        photo_filename = "N/A"
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                original_filename = secure_filename(file.filename)
                extension = original_filename.rsplit('.', 1)[1].lower()
                # Clean Aadhaar for filename
                cleaned_aadhaar = re.sub(r'\s+', '', aadhaar_no) if aadhaar_no else ''
                unique_part = cleaned_aadhaar if cleaned_aadhaar else f"{form_data.get('first_name', 'user')}_{form_data.get('last_name', '')}"
                photo_filename = f"{unique_part}_{timestamp}.{extension}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
                try:
                    file.save(file_path)
                    app.logger.info(f"SNE Photo saved: {photo_filename}")
                except Exception as e:
                    app.logger.error(f"Error saving SNE photo {photo_filename}: {e}")
                    flash(f"Could not save SNE photo: {e}", "error")
                    photo_filename = "Upload Error"
            elif file and file.filename != '':
                flash(f"Invalid file type for SNE photo. Allowed: {', '.join(ALLOWED_EXTENSIONS)}. Photo not saved.", 'warning')

        try:
            # Generate SNE Badge ID
            new_badge_id = get_next_badge_id(sheet, selected_area, selected_centre)
        except ValueError as e:
            flash(f"SNE Configuration Error: {e}", "error"); return redirect(url_for('sne_form_page'))
        except Exception as e:
            flash(f"Error generating SNE Badge ID: {e}", "error"); return redirect(url_for('sne_form_page'))

        calculated_age = calculate_age_from_dob(dob_str)
        if calculated_age == '': app.logger.warning(f"Could not calculate age for DOB: {dob_str}. Saving empty age.")

        # Prepare data row according to SNE_SHEET_HEADERS
        data_row = []
        for header in SHEET_HEADERS:
            form_key = header.lower().replace(' ', '_').replace("'", "").replace('/', '_')
            if header == "Submission Date": value = form_data.get('submission_date', datetime.date.today().isoformat())
            elif header == "Area": value = selected_area # SNE Area
            elif header == "Satsang Place": value = selected_centre # SNE Centre
            elif header == "Age": value = calculated_age
            elif header == "Aadhaar No": value = aadhaar_no # Store original Aadhaar format
            elif header == "Photo Filename": value = photo_filename
            elif header == "Badge ID": value = new_badge_id # SNE Badge ID
            elif header in ["Physically Challenged", "Help Pickup", "Handicap", "Stretcher", "Wheelchair", "Ambulance", "Pacemaker", "Chair Sitting", "Special Attendant", "Hearing Loss", "Attend Satsang"]:
                 value = form_data.get(form_key, 'No')
            else: value = form_data.get(form_key, '')
            data_row.append(str(value))

        try:
            sheet.append_row(data_row)
            app.logger.info(f"SNE Data appended. Badge ID: {new_badge_id}")
            flash(f'SNE Data submitted successfully! Your Badge ID is: {new_badge_id}', 'success')
        except Exception as e:
            app.logger.error(f"Error writing SNE data to Google Sheet: {e}")
            if photo_filename not in ["N/A", "Upload Error"] and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)):
                try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)); app.logger.info(f"Removed SNE photo {photo_filename} due to sheet write error.")
                except OSError as rm_err: app.logger.error(f"Error removing SNE photo {photo_filename} after sheet error: {rm_err}")
            flash(f'Error submitting SNE data to Google Sheet: {e}. Please try again.', 'error')
            return redirect(url_for('sne_form_page')) # Redirect back to SNE form

        return redirect(url_for('sne_form_page')) # Redirect back to SNE form

    except Exception as e:
        app.logger.error(f"Unexpected error during SNE submission: {e}", exc_info=True)
        flash(f'An unexpected server error occurred during SNE submission: {e}', 'error')
        return redirect(url_for('sne_form_page')) # Redirect back to SNE form


@app.route('/printer')
@login_required
def printer():
    """Displays the form to enter SNE badge IDs for printing."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('printer_form.html',
                           centres=CENTRES, # SNE Centres
                           current_user=current_user,
                           current_year=current_year)

@app.route('/generate_pdf', methods=['POST'])
@login_required
def generate_pdf():
    """Fetches SNE data and generates the PDF with composite badge images."""
    badge_ids_raw = request.form.get('badge_ids', '')
    badge_ids = [bid.strip().upper() for bid in badge_ids_raw.split(',') if bid.strip()]

    if not badge_ids:
        flash("Please enter at least one SNE Badge ID.", "error")
        return redirect(url_for('printer'))

    try:
        # Fetch data specifically from the SNE sheet
        all_sheet_data = get_all_sheet_data(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE)
        data_map = {str(row.get('Badge ID', '')).strip().upper(): row for row in all_sheet_data if row.get('Badge ID')}
    except Exception as e:
        flash(f"Error fetching SNE data from Google Sheet: {e}", "error")
        return redirect(url_for('printer'))

    badges_to_print = []
    not_found_ids = []
    for bid in badge_ids:
        if bid in data_map:
            badges_to_print.append(data_map[bid])
        else:
            not_found_ids.append(bid)

    if not badges_to_print:
        flash("No valid SNE Badge IDs found in the sheet.", "error")
        if not_found_ids: flash(f"IDs not found: {', '.join(not_found_ids)}", "warning")
        return redirect(url_for('printer'))

    if not_found_ids:
        flash(f"Warning: The following SNE Badge IDs were not found: {', '.join(not_found_ids)}", "warning")

    try:
        pdf_buffer = create_pdf_with_composite_badges(badges_to_print)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SNE_Composite_Badges_{timestamp}.pdf"
        return send_file(
            pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf'
        )
    except Exception as e:
        app.logger.error(f"Error generating SNE composite badge PDF: {e}", exc_info=True)
        flash(f"An error occurred while generating the SNE badge PDF: {e}", "error")
        return redirect(url_for('printer'))

# --- Route to get SNE centres for dynamic dropdown ---
@app.route('/get_centres/<area>')
@login_required
def get_centres(area):
    """Returns a JSON list of SNE centres for the given SNE area."""
    if area in BADGE_CONFIG: # Use SNE BADGE_CONFIG
        centres_for_area = sorted(list(BADGE_CONFIG[area].keys()))
        return jsonify(centres_for_area)
    else:
        return jsonify([])

# --- SNE Edit Form Routes ---

@app.route('/edit')
@login_required
def edit_form_page():
    """Displays the SNE search/edit form page."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('edit_form.html',
                           areas=AREAS, # SNE Areas
                           states=STATES,
                           relations=RELATIONS,
                           current_user=current_user,
                           current_year=current_year)

@app.route('/search_entries', methods=['GET'])
@login_required
def search_entries():
    """Handles AJAX search requests for SNE entries."""
    search_name = request.args.get('name', '').strip().lower()
    search_badge_id = request.args.get('badge_id', '').strip().upper()

    try:
        # Fetch data specifically from the SNE sheet
        all_data = get_all_sheet_data(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE)
        results = []

        if search_badge_id:
            # Use the generic function for exact match on Badge ID
             badge_id_header = "Badge ID"
             for entry in all_data:
                 if str(entry.get(badge_id_header, '')).strip().upper() == search_badge_id:
                     results.append(entry)
                     break # Found exact match
        elif search_name:
            # Perform name search (case-insensitive)
            for entry in all_data:
                 # Skip potentially empty rows
                if not any(entry.values()):
                    continue
                first_name = str(entry.get('First Name', '')).strip().lower()
                last_name = str(entry.get('Last Name', '')).strip().lower()
                full_name = f"{first_name} {last_name}"
                # Check if search term is in first, last, or full name
                if search_name in first_name or search_name in last_name or search_name in full_name:
                    results.append(entry)

        MAX_RESULTS = 50
        return jsonify(results[:MAX_RESULTS])

    except Exception as e:
        app.logger.error(f"Error searching SNE entries: {e}")
        return jsonify({"error": f"SNE Search failed: {e}"}), 500


@app.route('/update_entry/<original_badge_id>', methods=['POST'])
@login_required
def update_entry(original_badge_id):
    """Handles submission of the edited SNE form data."""
    if not original_badge_id:
        flash("Error: No SNE Badge ID specified for update.", "error")
        return redirect(url_for('edit_form_page'))

    # Get SNE sheet for update
    sheet = get_sheet(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to SNE data storage for update.", "error")
        return redirect(url_for('edit_form_page'))

    try:
        # Find row using the generic function with SNE headers
        row_index = find_row_index_by_value(sheet, 'Badge ID', original_badge_id, SHEET_HEADERS)
        if not row_index:
            flash(f"Error: Could not find SNE entry with Badge ID {original_badge_id} to update.", "error")
            return redirect(url_for('edit_form_page'))

        form_data = request.form.to_dict()
        try:
            original_record_list = sheet.row_values(row_index)
            # Pad if necessary
            while len(original_record_list) < len(SHEET_HEADERS):
                original_record_list.append('')
            original_record = dict(zip(SHEET_HEADERS, original_record_list))

            # Aadhaar should not be changed, fetch from original record
            aadhaar_no = original_record.get('Aadhaar No', '').strip()
            if not aadhaar_no:
                app.logger.warning(f"Original SNE Aadhaar number missing for Badge ID {original_badge_id} during update.")
                # Fallback to form data ONLY if absolutely necessary and intended
                # aadhaar_no = form_data.get('aadhaar_no', '').strip()

            app.logger.info(f"Updating SNE record for Badge ID: {original_badge_id} at row {row_index} with Aadhaar: {aadhaar_no}")
        except Exception as fetch_err:
             app.logger.error(f"Could not fetch original SNE record for {original_badge_id} at row {row_index}: {fetch_err}")
             flash(f"Error fetching original SNE data before update.", "error")
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
                # Use clean Aadhaar if available for filename uniqueness
                cleaned_aadhaar = re.sub(r'\s+', '', aadhaar_no) if aadhaar_no else ''
                unique_part = cleaned_aadhaar if cleaned_aadhaar else f"{form_data.get('first_name', 'user')}_{form_data.get('last_name', '')}"
                temp_new_filename = f"{unique_part}_{timestamp}.{extension}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_new_filename)
                try:
                    file.save(file_path)
                    app.logger.info(f"New photo saved for SNE update: {temp_new_filename}")
                    new_photo_filename = temp_new_filename
                    delete_old_photo = True
                except Exception as e:
                    app.logger.error(f"Error saving new SNE photo {temp_new_filename}: {e}")
                    flash(f"Could not save new SNE photo: {e}. Keeping existing photo.", "error")
            elif file and file.filename != '':
                flash(f"Invalid file type for new SNE photo. Allowed: {', '.join(ALLOWED_EXTENSIONS)}. Photo not updated.", 'warning')

        dob_str = form_data.get('dob', '')
        calculated_age = calculate_age_from_dob(dob_str)
        if calculated_age == '': app.logger.warning(f"Could not calculate age for DOB: {dob_str} during SNE update.")

        # Prepare updated row according to SNE_SHEET_HEADERS
        updated_data_row = []
        for header in SHEET_HEADERS:
            form_key = header.lower().replace(' ', '_').replace("'", "").replace('/', '_')
            if header == "Badge ID": value = original_badge_id # Keep original Badge ID
            elif header == "Aadhaar No": value = aadhaar_no # Keep original Aadhaar format
            elif header == "Age": value = calculated_age
            elif header == "Photo Filename": value = new_photo_filename
            elif header == "Submission Date": value = original_record.get('Submission Date', '') # Keep original submission date
            elif header in ["Physically Challenged", "Help Pickup", "Handicap", "Stretcher", "Wheelchair", "Ambulance", "Pacemaker", "Chair Sitting", "Special Attendant", "Hearing Loss", "Attend Satsang"]:
                 value = form_data.get(form_key, 'No') # Get updated value or default to 'No'
            else: value = form_data.get(form_key, '') # Get updated value for other fields
            updated_data_row.append(str(value))

        try:
            end_column_letter = gspread.utils.rowcol_to_a1(1, len(SHEET_HEADERS)).split('1')[0]
            update_range = f'A{row_index}:{end_column_letter}{row_index}'
            sheet.update(update_range, [updated_data_row])

            app.logger.info(f"SNE Data updated for Badge ID: {original_badge_id} at row {row_index}")

            if delete_old_photo and old_photo_filename and old_photo_filename not in ["N/A", "Upload Error", ""]:
                 old_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], old_photo_filename)
                 if os.path.exists(old_photo_path):
                     try: os.remove(old_photo_path); app.logger.info(f"Successfully deleted old SNE photo: {old_photo_filename}")
                     except OSError as e: app.logger.error(f"Error deleting old SNE photo {old_photo_filename}: {e}"); flash(f"SNE Entry updated, but failed to delete old photo: {old_photo_filename}", "warning")

            flash(f'SNE Entry for Badge ID {original_badge_id} updated successfully!', 'success')
            return redirect(url_for('edit_form_page'))

        except Exception as e:
            app.logger.error(f"Error updating SNE Google Sheet for Badge ID {original_badge_id}: {e}")
            # Rollback photo if sheet update failed
            if delete_old_photo:
                 new_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], new_photo_filename)
                 if os.path.exists(new_photo_path):
                     try: os.remove(new_photo_path); app.logger.info(f"Removed newly uploaded SNE photo {new_photo_filename} due to sheet update error.")
                     except OSError as rm_err: app.logger.error(f"Error removing new SNE photo {new_photo_filename} after sheet update error: {rm_err}")
            flash(f'Error updating SNE data in Google Sheet: {e}. Please try again.', 'error')
            return redirect(url_for('edit_form_page'))

    except Exception as e:
        app.logger.error(f"Unexpected error during SNE update for Badge ID {original_badge_id}: {e}", exc_info=True)
        flash(f'An unexpected server error occurred during SNE update: {e}', 'error')
        return redirect(url_for('edit_form_page'))


# === Blood Camp Routes ===

@app.route('/blood_camp')
@login_required
def blood_camp_form_page():
    """Displays the blood camp donor form."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('blood_camp_form.html',
                           today_date=today_date,
                           current_year=current_year,
                           current_user=current_user,
                           blood_camp_areas=BLOOD_CAMP_AREAS) # Pass areas to template

@app.route('/search_donor', methods=['GET'])
@login_required
def search_donor():
    """Handles AJAX search requests for blood camp donors by mobile."""
    mobile_number = request.args.get('mobile', '').strip()

    # Validate input format (10 digits)
    if not mobile_number or not re.fullmatch(r'\d{10}', mobile_number):
        return jsonify({"error": "Invalid mobile number format (must be 10 digits)."}), 400

    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
         app.logger.error(f"Search Donor: Could not connect to Blood Camp sheet for mobile {mobile_number}")
         return jsonify({"error": "Could not connect to donor database."}), 500

    # Use the updated find_donor_by_mobile function
    donor_record = find_donor_by_mobile(sheet, mobile_number)

    if donor_record is None:
         # Check sheet connection status again for clarity
         if get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True):
              app.logger.info(f"Search: Blood Camp Donor not found for mobile {mobile_number}")
              return jsonify({"found": False})
         else:
             app.logger.error(f"Search: Blood Camp Sheet connection failed on re-check for mobile {mobile_number}")
             return jsonify({"error": "Database connection error during search."}), 500

    elif isinstance(donor_record, dict):
        app.logger.info(f"Search: Blood Camp Donor found for mobile {mobile_number}")
        # Return the full record, which now includes 'Area' if the header exists and was populated
        return jsonify({"found": True, "donor": donor_record})
    else:
        # This case should ideally not happen if find_donor_by_mobile returns dict or None
        app.logger.error(f"Search: Unexpected result type '{type(donor_record)}' for mobile {mobile_number}")
        return jsonify({"error": "An unexpected error occurred during search."}), 500


@app.route('/submit_blood_camp', methods=['POST'])
@login_required
def submit_blood_camp():
    """Handles blood camp form submission (new donors and updates)."""
    form_data = request.form.to_dict()
    is_update = form_data.get('is_update', 'false').lower() == 'true'
    token_id = form_data.get('token_id', '').strip()
    mobile_number = form_data.get('mobile_no', '').strip()
    area = form_data.get('area', '').strip() # Get selected area

    # Basic validation
    if not mobile_number:
         flash("Mobile number is required.", "error")
         return redirect(url_for('blood_camp_form_page'))
    # Clean mobile number for storage/comparison consistency
    cleaned_mobile_number = re.sub(r'\D', '', mobile_number)
    if len(cleaned_mobile_number) != 10:
         flash("Mobile number must be 10 digits.", "error")
         return redirect(url_for('blood_camp_form_page'))

    if not area: # Area is now mandatory
         flash("Area is required.", "error")
         return redirect(url_for('blood_camp_form_page'))
    if is_update and not token_id:
         flash("Token ID missing for update.", "error")
         return redirect(url_for('blood_camp_form_page'))

    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to the donor database. Please try again.", "error")
        return redirect(url_for('blood_camp_form_page'))

    try:
        if is_update:
            # --- Update Existing Donor ---
            row_index = find_row_index_by_value(sheet, 'Token ID', token_id, BLOOD_CAMP_SHEET_HEADERS)
            if not row_index:
                flash(f"Error: Could not find donor with Token ID {token_id} to update.", "error")
                return redirect(url_for('blood_camp_form_page'))

            existing_data_list = sheet.row_values(row_index)
            while len(existing_data_list) < len(BLOOD_CAMP_SHEET_HEADERS):
                existing_data_list.append('')
            existing_data = dict(zip(BLOOD_CAMP_SHEET_HEADERS, existing_data_list))

            # Prepare updated row data
            updated_row = []
            total_donations = 0
            try:
                # Use the correct header name from the list
                total_donations = int(existing_data.get('Total Donations', 0)) + 1
            except (ValueError, TypeError): # Catch TypeError if value is not convertible
                app.logger.warning(f"Could not parse existing 'Total Donations' ('{existing_data.get('Total Donations')}') for Token ID {token_id}. Resetting to 1.")
                total_donations = 1

            # Use the header names from BLOOD_CAMP_SHEET_HEADERS
            last_donation_date_header = "Donation Date" # As per user's list
            last_donation_location_header = "Donation Location" # As per user's list

            for header in BLOOD_CAMP_SHEET_HEADERS:
                form_key = header.lower().replace("'", "").replace('/', '_').replace(' ', '_')
                if header == last_donation_date_header:
                    value = form_data.get('donation_date', datetime.date.today().isoformat())
                elif header == last_donation_location_header:
                    value = form_data.get('donation_location', '')
                elif header == "Total Donations":
                    value = total_donations
                elif header == "Submission Timestamp": # Update timestamp on modification
                     value = datetime.datetime.now().isoformat()
                # Keep most other fields from the existing record
                elif header == "Area":
                    # Keep existing area, don't allow changing via this update flow
                    value = existing_data.get(header, '')
                elif header == "Mobile Number":
                     # Keep existing mobile number (cleaned format if possible), don't allow changing via this update flow
                     existing_mobile_cleaned = re.sub(r'\D', '', existing_data.get(header, ''))
                     value = existing_mobile_cleaned if existing_mobile_cleaned else '' # Store cleaned version
                elif header in ["Status", "Reason for Rejection"]:
                    value = existing_data.get(header, '') # Keep existing status/reason
                else:
                    # Use existing value unless explicitly changed in form (e.g., Name, DOB etc if form allowed it)
                    # Prioritize existing data for fields not directly updated in this flow
                    value = existing_data.get(header, form_data.get(form_key, ''))
                updated_row.append(str(value))

            # Update the row in the sheet
            end_column_letter = gspread.utils.rowcol_to_a1(1, len(BLOOD_CAMP_SHEET_HEADERS)).split("1")[0]
            sheet.update(f'A{row_index}:{end_column_letter}{row_index}', [updated_row])
            flash(f'Donation details updated successfully for Token ID: {token_id}', 'success')
            app.logger.info(f"Updated Blood Camp donation for Token ID: {token_id} at row {row_index}")

        else:
            # --- Add New Donor ---
            # Check if CLEANED mobile number already exists using the robust function
            existing_donor_check = find_donor_by_mobile(sheet, cleaned_mobile_number)
            if existing_donor_check:
                 flash(f"Error: Mobile number {cleaned_mobile_number} already exists with Token ID {existing_donor_check.get('Token ID', 'N/A')}. Please use the search function.", "error")
                 return redirect(url_for('blood_camp_form_page'))

            # Generate new Token ID using the selected area
            new_token_id = generate_next_token_id(sheet, area)
            if not new_token_id:
                 flash(f"Error generating a unique Token ID for Area '{area}'. Please try again or check configuration.", "error")
                 return redirect(url_for('blood_camp_form_page'))

            # Prepare data row based on BLOOD_CAMP_SHEET_HEADERS
            data_row = []
            # Use the new header names from BLOOD_CAMP_SHEET_HEADERS
            last_donation_date_header = "Donation Date" # As per user's list
            last_donation_location_header = "Donation Location" # As per user's list

            current_donation_date = form_data.get('donation_date', datetime.date.today().isoformat())

            for header in BLOOD_CAMP_SHEET_HEADERS:
                form_key = header.lower().replace("'", "").replace('/', '_').replace(' ', '_')
                if header == "Token ID": value = new_token_id
                elif header == "Submission Timestamp": value = datetime.datetime.now().isoformat()
                elif header == "Area": value = area # Save the selected Area
                elif header == "Name of Donor": value = form_data.get('donor_name', '')
                elif header == "Father's/Husband's Name": value = form_data.get('father_husband_name', '')
                elif header == "Date of Birth": value = form_data.get('dob', '')
                elif header == "Gender": value = form_data.get('gender', '')
                elif header == "Occupation": value = form_data.get('occupation', '')
                elif header == "House No.": value = form_data.get('house_no', '')
                elif header == "Sector": value = form_data.get('sector', '')
                elif header == "Mobile Number": value = cleaned_mobile_number # Store cleaned number
                elif header == "City": value = form_data.get('city', '') # Get City from form
                elif header == "Blood Group": value = form_data.get('blood_group', '')
                elif header == "Allow Call": value = form_data.get('allow_call', 'No')
                elif header == last_donation_date_header: value = current_donation_date # Current donation date
                elif header == last_donation_location_header: value = form_data.get('donation_location', '') # Current location
                elif header == "First Donation Date": value = current_donation_date # First time donating, use current date
                elif header == "Total Donations": value = 1 # First donation
                elif header in ["Status", "Reason for Rejection"]: value = '' # Leave blank for new donors
                else: value = form_data.get(form_key, '') # Default mapping
                data_row.append(str(value))

            # Append the new row to the sheet
            sheet.append_row(data_row)
            flash(f'New donor registered successfully! Token ID: {new_token_id}', 'success')
            app.logger.info(f"Appended new Blood Camp donor. Area: {area}, Token ID: {new_token_id}")

        return redirect(url_for('blood_camp_form_page')) # Redirect back to the form

    except gspread.exceptions.APIError as e:
        app.logger.error(f"Google Sheet API error during blood camp submission: {e}")
        flash(f"Database error during submission: {e}. Please try again.", "error")
        return redirect(url_for('blood_camp_form_page'))
    except Exception as e:
        app.logger.error(f"Unexpected error during blood camp submission: {e}", exc_info=True)
        flash(f"An unexpected server error occurred during submission: {e}", "error")
        return redirect(url_for('blood_camp_form_page'))


# === Blood Donor Status Update Routes ===

@app.route('/blood_donor_status')
@login_required
def blood_donor_status_page():
    """Displays the blood donor status update form."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('blood_donor_status.html',
                           today_date=today_date,
                           current_year=current_year,
                           current_user=current_user)

@app.route('/get_donor_details/<token_id>', methods=['GET'])
@login_required
def get_donor_details(token_id):
    """Fetches donor name and current status for the status update form."""
    if not token_id:
        return jsonify({"error": "Token ID is required."}), 400

    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
        return jsonify({"error": "Could not connect to donor database."}), 500

    try:
        row_index = find_row_index_by_value(sheet, 'Token ID', token_id, BLOOD_CAMP_SHEET_HEADERS)
        if not row_index:
            # Return found: False consistently
            return jsonify({"found": False, "error": "Donor not found with this Token ID."}), 404

        # Fetch specific columns: Name, Status, Reason using the correct headers list
        try:
            name_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Name of Donor") + 1
            status_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Status") + 1
            reason_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Reason for Rejection") + 1
        except ValueError as e:
             app.logger.error(f"Header configuration error fetching donor details: {e} - Headers: {BLOOD_CAMP_SHEET_HEADERS}")
             return jsonify({"error": "Server configuration error."}), 500

        row_data = sheet.row_values(row_index)
        while len(row_data) < len(BLOOD_CAMP_SHEET_HEADERS):
             row_data.append('')

        donor_name = row_data[name_col_index - 1] if len(row_data) >= name_col_index else "N/A"
        current_status = row_data[status_col_index - 1] if len(row_data) >= status_col_index else ""
        current_reason = row_data[reason_col_index - 1] if len(row_data) >= reason_col_index else ""

        return jsonify({
            "found": True,
            "name": donor_name,
            "status": current_status,
            "reason": current_reason
        })

    except gspread.exceptions.APIError as e:
        app.logger.error(f"gspread API error fetching donor details for {token_id}: {e}")
        return jsonify({"error": "Database error fetching details."}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error fetching donor details for {token_id}: {e}", exc_info=True)
        return jsonify({"error": "Server error fetching details."}), 500


@app.route('/update_donor_status', methods=['POST'])
@login_required
def update_donor_status():
    """Handles the submission of the donor status update form."""
    token_id = request.form.get('token_id', '').strip()
    status = request.form.get('status', '').strip()
    reason = request.form.get('reason', '').strip()

    # Validation
    if not token_id:
        flash("Token ID is required.", "error")
        return redirect(url_for('blood_donor_status_page'))
    if not status:
        flash("Status (Accepted/Rejected) is required.", "error")
        return redirect(url_for('blood_donor_status_page'))
    if status == 'Rejected' and not reason:
        flash("Reason for rejection is required when status is 'Rejected'.", "error")
        return redirect(url_for('blood_donor_status_page'))

    if status == 'Accepted':
        reason = '' # Clear reason if accepted

    sheet = get_sheet(BLOOD_CAMP_SHEET_ID, BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to the donor database. Please try again.", "error")
        return redirect(url_for('blood_donor_status_page'))

    try:
        row_index = find_row_index_by_value(sheet, 'Token ID', token_id, BLOOD_CAMP_SHEET_HEADERS)
        if not row_index:
            flash(f"Error: Donor with Token ID '{token_id}' not found.", "error")
            return redirect(url_for('blood_donor_status_page'))

        # Use the correct headers list to find indices
        try:
            status_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Status") + 1
            reason_col_index = BLOOD_CAMP_SHEET_HEADERS.index("Reason for Rejection") + 1
        except ValueError as e:
             app.logger.error(f"Header configuration error updating status: {e} - Headers: {BLOOD_CAMP_SHEET_HEADERS}")
             flash("Server configuration error preventing status update.", "error")
             return redirect(url_for('blood_donor_status_page'))

        updates = [
            gspread.Cell(row=row_index, col=status_col_index, value=status),
            gspread.Cell(row=row_index, col=reason_col_index, value=reason)
        ]
        sheet.update_cells(updates)

        flash(f"Status updated successfully for Donor Token ID: {token_id}", "success")
        app.logger.info(f"Updated status ({status}) for Token ID: {token_id} at row {row_index}")
        return redirect(url_for('blood_donor_status_page'))

    except gspread.exceptions.APIError as e:
        app.logger.error(f"Google Sheet API error updating status for {token_id}: {e}")
        flash(f"Database error updating status: {e}. Please try again.", "error")
        return redirect(url_for('blood_donor_status_page'))
    except Exception as e:
        app.logger.error(f"Unexpected error updating status for {token_id}: {e}", exc_info=True)
        flash(f"An unexpected server error occurred during status update: {e}", "error")
        return redirect(url_for('blood_donor_status_page'))


# --- Main Execution ---
if __name__ == '__main__':
    # Set debug=False for production
    # Use host='0.0.0.0' to be accessible on the network
    # app.run(debug=True, port=5000) # Development
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) # Production/Deployment
