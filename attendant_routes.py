# attendant_routes.py

import os
import datetime
import re
import logging
from io import BytesIO

# Flask imports
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify,
    send_file, current_app # Use current_app to access app config/context if needed
)
# Login manager (assuming configured in main app.py)
from flask_login import login_required, current_user

# Google Sheets (assuming gspread is installed)
import gspread
from google.oauth2.service_account import Credentials

# S3 (assuming boto3 is installed)
import boto3
from botocore.exceptions import ClientError

# PDF Generation (assuming fpdf, Pillow are installed)
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont, ImageOps
import textwrap # For text wrapping on badge

from werkzeug.utils import secure_filename
# --- Configuration Placeholders & Constants ---

# !!! IMPORTANT: Replace these placeholders with your actual values !!!
ATTENDANT_SHEET_ID = '13kSQ28X8Gyyba3z3uVJfOqXCYM6ruaw2sIp-nRnqcrM'
ATTENDANT_SERVICE_ACCOUNT_FILE = 'grand-nimbus-458116-f5-8295ebd9144b.json'
# You can reuse the SNE S3 bucket or use a separate one
ATTENDANT_S3_BUCKET_NAME = 'rssbsne' # Or 'your-attendant-s3-bucket-name'

# Define the expected headers for the Attendant Google Sheet
# Ensure this matches the actual columns in your sheet
ATTENDANT_SHEET_HEADERS = [
    "Badge ID",         # Manually entered ID (e.g., ATT-AH-01)
    "Submission Date",
    "Area",
    "Centre",
    "Name",             # Full Name
    "Phone Number",
    "Address",
    "Photo Filename"    # Key for the photo stored in S3
]

# --- Constants (Potentially shared with app.py or defined in a config file) ---
# These might be imported from your main app or a config file
# If defined here, ensure they match your main app's config

# Allowed image extensions (reuse from app.py)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Badge generation constants (ADAPT THESE FOR ATTENDANT BADGE LAYOUT)
# Assuming reuse of SNE template and fonts for now, but likely needs changes
BADGE_TEMPLATE_PATH = 'static/images/sne_           badge.png' # Use attendant template if different
FONT_PATH = 'static/fonts/times new roman.ttf'
FONT_BOLD_PATH = 'static/fonts/times new roman bold.ttf'

# Photo placement on badge (pixels from top-left of template) - ADJUST AS NEEDED
PHOTO_PASTE_X_PX = 825
PHOTO_PASTE_Y_PX = 475
PHOTO_BOX_WIDTH_PX = 525
PHOTO_BOX_HEIGHT_PX = 700

# Text element positions, sizes, colors on the badge - ADJUST FOR ATTENDANT LAYOUT
# Example - Adapt keys and values for attendant details
ATTENDANT_TEXT_ELEMENTS = {
    "badge_id": {"coords": (100, 1200), "size": 130, "color": (0, 0, 139), "is_bold": True}, # Dark Blue ID
    "name":     {"coords": (100, 1350), "size": 110, "color": "black", "is_bold": True},
    "phone":    {"coords": (100, 1500), "size": 110, "color": "black", "is_bold": False}, # Example: Phone
    "centre":   {"coords": (100, 1800), "size": 110, "color": "black", "is_bold": True},
    "area":     {"coords": (100, 1950), "size": 110, "color": "black", "is_bold": True},
    # Add/remove/modify elements as needed for the attendant badge layout
    # "address":  {"coords": (1750, 250), "size": 110, "color": "black", "is_bold": True} # Example address
}

# Areas and Centres Configuration (Assuming reuse from app.py's BADGE_CONFIG)
# This blueprint needs access to this structure for the /get_centres route.
# It's best practice to have this defined globally or passed via app config.
# Example: Import from main app: from app import BADGE_CONFIG, AREAS, STATES, RELATIONS
# For now, assume BADGE_CONFIG is accessible.
# If not, you might need to pass it during blueprint registration in app.py
# or duplicate the /get_centres route in app.py.

# --- Blueprint Definition ---
# Creates a Blueprint named 'attendant'.
# The first argument 'attendant' is the endpoint prefix (e.g., url_for('attendant.form_page')).
# url_prefix can be added here if desired (e.g., url_prefix='/attendant')
attendant_bp = Blueprint('attendant', __name__,
                         template_folder='templates', # Assumes templates are in the main 'templates' folder
                         static_folder='static'      # Assumes static files are in the main 'static' folder
                        )

# --- S3 Client (Assuming configured globally in app.py) ---
# It's better to initialize boto3 client once in your main app.py
# and potentially make it accessible via app context or importing.
# Example: from app import s3_client
# For demonstration, we might initialize it here if needed, but it's not ideal.
# s3_client = boto3.client('s3') # Avoid doing this here if possible

# --- Logging Setup (Use Flask's app logger) ---
# Example: logger = current_app.logger (inside routes) or logging directly
logger = logging.getLogger(__name__) # Get logger for this module

# --- Helper Functions (Adapted for Attendants) ---

def get_attendant_sheet(read_only=False):
    """Authenticates and returns the Attendant Google Sheet worksheet object."""
    # This function assumes ATTENDANT_SERVICE_ACCOUNT_FILE is correctly set
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        if read_only:
            scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']

        service_account_path = ATTENDANT_SERVICE_ACCOUNT_FILE
        if not os.path.exists(service_account_path):
             logger.error(f"Attendant Service account file not found: {service_account_path}")
             return None

        creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
        client = gspread.authorize(creds)
        # Assumes the attendant data is on the first sheet (sheet1)
        sheet = client.open_by_key(ATTENDANT_SHEET_ID).sheet1
        logger.info(f"Successfully accessed Attendant Google Sheet (ID: {ATTENDANT_SHEET_ID}). ReadOnly={read_only}")
        return sheet
    except gspread.exceptions.APIError as e:
        logger.error(f"gspread API Error accessing Attendant Sheet (ID: {ATTENDANT_SHEET_ID}): {e}", exc_info=True)
        if e.response.status_code == 403:
             logger.error("Permission denied. Check sheet sharing settings and service account permissions.")
        elif e.response.status_code == 404:
             logger.error("Sheet not found. Verify ATTENDANT_SHEET_ID.")
        return None
    except Exception as e:
        logger.error(f"Error accessing Attendant Google Sheet (ID: {ATTENDANT_SHEET_ID}): {e}", exc_info=True)
        return None

def get_all_attendant_data():
    """Gets all data from the attendant sheet and returns a list of dictionaries."""
    sheet = get_attendant_sheet(read_only=True)
    if not sheet:
        raise Exception(f"Could not connect to attendant sheet {ATTENDANT_SHEET_ID} to get data.")
    try:
        all_values = sheet.get_all_values()
        if not all_values or len(all_values) < 1: # Check if sheet is empty or just header
            return []

        # Use the defined headers
        header_row = ATTENDANT_SHEET_HEADERS
        # Assume first row is header if sheet is not empty
        data_rows = all_values[1:] if len(all_values) > 1 else []

        list_of_dicts = []
        num_headers = len(header_row)
        for row_index, row in enumerate(data_rows):
            # Pad row with empty strings if it's shorter than headers
            padded_row = row + [''] * (num_headers - len(row))
            # Truncate row if it's longer than headers
            truncated_row = padded_row[:num_headers]
            try:
                # Create dict, skipping rows that are entirely empty
                record_dict = dict(zip(header_row, truncated_row))
                if any(val for val in record_dict.values()): # Check if dict has any non-empty values
                    list_of_dicts.append(record_dict)
            except Exception as zip_err:
                logger.error(f"Error creating dict for attendant row {row_index + 2}: {zip_err} - Row: {row}")

        logger.info(f"Fetched {len(list_of_dicts)} attendant records.")
        return list_of_dicts
    except Exception as e:
        logger.error(f"Could not get/process attendant sheet data: {e}", exc_info=True)
        raise Exception(f"Could not get/process attendant sheet data: {e}")

def check_attendant_badge_id_exists(sheet, badge_id):
    """Checks if a specific Attendant Badge ID already exists in the sheet."""
    if not sheet:
        logger.error("Attendant sheet object is None in check_attendant_badge_id_exists.")
        return False # Indicate error or inability to check

    badge_id_to_check = str(badge_id).strip().upper()
    if not badge_id_to_check:
        return None # No ID provided

    try:
        # Find the column index for "Badge ID" (1-based for gspread)
        try:
            badge_id_col_index = ATTENDANT_SHEET_HEADERS.index('Badge ID') + 1
        except ValueError:
            logger.error("Header 'Badge ID' not found in ATTENDANT_SHEET_HEADERS.")
            return False # Indicate configuration error

        # Fetch all values from the Badge ID column
        all_badge_ids_in_sheet = sheet.col_values(badge_id_col_index)

        # Check if the badge_id exists (case-insensitive comparison after stripping whitespace)
        # Skip header row (index 0)
        for existing_id in all_badge_ids_in_sheet[1:]:
            if str(existing_id).strip().upper() == badge_id_to_check:
                logger.warning(f"Attendant Badge ID '{badge_id_to_check}' already exists.")
                return True # ID Found

        return None # ID Not Found
    except gspread.exceptions.APIError as e:
         logger.error(f"gspread API Error checking attendant Badge ID '{badge_id_to_check}': {e}", exc_info=True)
         return False # Indicate error during check
    except Exception as e:
        logger.error(f"Error checking attendant Badge ID '{badge_id_to_check}': {e}", exc_info=True)
        return False # Indicate general error

def find_attendant_row_index_by_badge_id(sheet, badge_id):
    """Finds the 1-based row index for an attendant Badge ID."""
    if not sheet:
        logger.error("Attendant sheet object is None in find_attendant_row_index_by_badge_id.")
        return None
    badge_id_to_find = str(badge_id).strip().upper()
    if not badge_id_to_find:
        return None
    try:
        try:
            badge_id_col_index = ATTENDANT_SHEET_HEADERS.index('Badge ID') + 1
        except ValueError:
            logger.error("Header 'Badge ID' not found in ATTENDANT_SHEET_HEADERS.")
            return None

        # Find the cell matching the Badge ID
        cell = sheet.find(badge_id_to_find, in_column=badge_id_col_index)
        if cell:
            logger.info(f"Found attendant Badge ID '{badge_id_to_find}' at row {cell.row}.")
            return cell.row # Return the 1-based row index
        else:
            logger.warning(f"Attendant Badge ID '{badge_id_to_find}' not found in sheet.")
            return None
    except gspread.exceptions.APIError as e:
         logger.error(f"gspread API Error finding attendant Badge ID '{badge_id_to_find}': {e}", exc_info=True)
         return None
    except Exception as e:
        logger.error(f"Error finding attendant row index for '{badge_id_to_find}': {e}", exc_info=True)
        return None

def allowed_file(filename):
    """Checks if the filename has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_attendant_pdf_with_badges(badge_data_list):
    """
    Generates a PDF document containing badges for the provided attendant data.
    Downloads photos from S3 if available.
    ADAPT LAYOUT AND CONTENT FOR ATTENDANT BADGES.
    """
    # --- PDF Page and Badge Layout ---
    # A4 Landscape: 297mm wide, 210mm high
    PAGE_WIDTH_MM = 297
    PAGE_HEIGHT_MM = 210
    # Define badge dimensions in mm (adjust as needed)
    BADGE_WIDTH_MM = 100 # Example size
    BADGE_HEIGHT_MM = 60  # Example size
    MARGIN_MM = 10        # Margin around the page edges
    GAP_MM = 5            # Gap between badges

    effective_badge_width = BADGE_WIDTH_MM + GAP_MM
    effective_badge_height = BADGE_HEIGHT_MM + GAP_MM

    # Calculate how many badges fit per row/column
    badges_per_row = int((PAGE_WIDTH_MM - 2 * MARGIN_MM + GAP_MM) / effective_badge_width) if effective_badge_width > 0 else 1
    badges_per_col = int((PAGE_HEIGHT_MM - 2 * MARGIN_MM + GAP_MM) / effective_badge_height) if effective_badge_height > 0 else 1
    if badges_per_row <= 0: badges_per_row = 1
    if badges_per_col <= 0: badges_per_col = 1

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False, margin=MARGIN_MM)
    pdf.add_page()
    col_num = 0
    row_num = 0

    # --- Load Badge Template and Fonts ---
    try:
        # Ensure the BADGE_TEMPLATE_PATH points to the correct template for attendants
        base_template = Image.open(BADGE_TEMPLATE_PATH).convert("RGBA")
        logger.info(f"Loaded badge template: {BADGE_TEMPLATE_PATH}")
    except Exception as e:
        logger.error(f"CRITICAL: Error loading badge template '{BADGE_TEMPLATE_PATH}': {e}", exc_info=True)
        raise Exception(f"Error loading badge template: {e}")

    # Pre-load fonts to avoid loading them repeatedly inside the loop
    loaded_fonts = {}
    loaded_fonts_bold = {}
    bold_load_failed_sizes = set() # Track sizes where bold font failed to load

    font_elements_to_load = ATTENDANT_TEXT_ELEMENTS # Use attendant layout config
    for element, config in font_elements_to_load.items():
        size = config['size']
        is_bold = config.get('is_bold', False)

        # Load regular font if not already loaded
        if size not in loaded_fonts:
            try:
                loaded_fonts[size] = ImageFont.truetype(FONT_PATH, size)
            except Exception as e:
                logger.error(f"CRITICAL: Error loading regular font '{FONT_PATH}' size {size}: {e}")
                # If base font fails, we cannot proceed reliably
                raise Exception(f"CRITICAL: Error loading regular font: {e}")

        # Load bold font if needed and not already loaded/failed
        if is_bold and size not in loaded_fonts_bold and size not in bold_load_failed_sizes:
            try:
                loaded_fonts_bold[size] = ImageFont.truetype(FONT_BOLD_PATH, size)
            except Exception as e:
                logger.warning(f"Could not load bold font '{FONT_BOLD_PATH}' size {size}: {e}. Falling back to regular.")
                # Store regular font as fallback and mark size as failed for bold
                loaded_fonts_bold[size] = loaded_fonts.get(size)
                bold_load_failed_sizes.add(size)
        elif is_bold and size in bold_load_failed_sizes:
             # Ensure fallback is set if bold failed previously
             loaded_fonts_bold[size] = loaded_fonts.get(size)


    # --- S3 Client (Ensure it's initialized) ---
    # Assuming s3_client is available globally or via current_app context
    # Example: s3_client = current_app.s3_client
    # If not, initialize it here (less ideal):
    try:
        s3_client = boto3.client('s3')
        logger.info("S3 client initialized for PDF generation.")
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}", exc_info=True)
        s3_client = None # Mark as unavailable

    # --- Generate Badges ---
    for data in badge_data_list:
        badge_image = None # Ensure badge_image is reset or defined in each iteration
        try:
            # Create a fresh copy of the template for each badge
            badge_image = base_template.copy()
            draw = ImageDraw.Draw(badge_image)

            # --- Add Photo from S3 (if available) ---
            s3_object_key = data.get('Photo Filename', '')
            if s3_client and s3_object_key and s3_object_key not in ['N/A', 'Upload Error', '']:
                try:
                    logger.info(f"Attempting to download photo from S3: Bucket='{ATTENDANT_S3_BUCKET_NAME}', Key='{s3_object_key}'")
                    s3_response = s3_client.get_object(Bucket=ATTENDANT_S3_BUCKET_NAME, Key=s3_object_key)
                    # Open image directly from S3 stream
                    with Image.open(BytesIO(s3_response['Body'].read())).convert("RGBA") as holder_photo:
                        # Resize photo to fit the designated box on the template
                        # Using LANCZOS for high-quality downscaling
                        with holder_photo.resize((PHOTO_BOX_WIDTH_PX, PHOTO_BOX_HEIGHT_PX), Image.Resampling.LANCZOS) as resized_photo:
                            # Paste the resized photo onto the badge template
                            # The third argument (mask) ensures transparency is handled correctly
                            badge_image.paste(resized_photo, (PHOTO_PASTE_X_PX, PHOTO_PASTE_Y_PX), resized_photo)
                    logger.info(f"Successfully added photo '{s3_object_key}' to badge.")
                except ClientError as e:
                     if e.response['Error']['Code'] == 'NoSuchKey':
                         logger.warning(f"S3 photo not found: Key='{s3_object_key}', Bucket='{ATTENDANT_S3_BUCKET_NAME}'")
                     else:
                         logger.error(f"S3 ClientError downloading photo '{s3_object_key}': {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error processing S3 photo '{s3_object_key}': {e}", exc_info=True)
            elif not s3_client and s3_object_key and s3_object_key not in ['N/A', 'Upload Error', '']:
                 logger.warning(f"S3 client not available, cannot download photo: {s3_object_key}")


            # --- Prepare Text Details for Badge ---
            # Adapt these details based on ATTENDANT_SHEET_HEADERS and desired badge content
            details = {
                "badge_id": str(data.get('Badge ID', 'N/A')).upper(),
                "name": str(data.get('Name', '')).upper(), # Example: Use 'Name' field
                "phone": f"Ph: {str(data.get('Phone Number', ''))}", # Example: Add phone
                "centre": str(data.get('Centre', '')).upper(), # Example: Use 'Centre' field
                "area": str(data.get('Area', '')).upper(), # Example: Use 'Area' field
                # Add other fields as needed based on ATTENDANT_TEXT_ELEMENTS
            }

            # --- Draw Text onto Badge ---
            for key, text in details.items():
                if key in ATTENDANT_TEXT_ELEMENTS and text: # Check if key exists in layout config and text is not empty
                    config = ATTENDANT_TEXT_ELEMENTS[key]
                    font_size = config['size']
                    is_bold = config.get('is_bold', False)

                    # Select the pre-loaded font (regular or bold fallback)
                    font = loaded_fonts_bold.get(font_size) if is_bold else loaded_fonts.get(font_size)
                    # Final fallback if bold failed and regular somehow missing (should not happen after pre-loading)
                    if not font:
                         font = loaded_fonts.get(min(loaded_fonts.keys())) # Get smallest available font as last resort
                         logger.warning(f"Font size {font_size} (bold={is_bold}) not loaded for '{key}', using fallback.")
                         if not font: continue # Skip if no fonts loaded at all

                    # Handle text wrapping for specific fields if needed (e.g., address)
                    if key == "address": # Example for address wrapping
                        # Adjust width based on badge layout
                        wrapped_text = "\n".join(textwrap.wrap(text, width=20))
                        # Optional: Draw a background box for wrapped text
                        # bbox = draw.multiline_textbbox(config['coords'], wrapped_text, font=font, spacing=10)
                        # box_coords = [bbox[0] - 10, bbox[1] - 10, bbox[2] + 10, bbox[3] + 10] # Add padding
                        # draw.rectangle(box_coords, outline="black", width=1)
                        draw.multiline_text(config['coords'], wrapped_text, fill=config['color'], font=font, spacing=10)
                    else:
                        # Draw single line text
                        draw.text(config['coords'], text, fill=config['color'], font=font)

            # --- Place Badge onto PDF Page ---
            if col_num >= badges_per_row:
                col_num = 0
                row_num += 1

            if row_num >= badges_per_col:
                row_num = 0
                col_num = 0 # Reset column as well
                pdf.add_page()

            # Calculate top-left position for the current badge
            x_pos = MARGIN_MM + col_num * effective_badge_width
            y_pos = MARGIN_MM + row_num * effective_badge_height

            # Save the composite badge image to a temporary buffer
            with BytesIO() as temp_img_buffer:
                badge_image.save(temp_img_buffer, format="PNG")
                temp_img_buffer.seek(0)
                # Add the image from buffer to the PDF
                pdf.image(temp_img_buffer, x=x_pos, y=y_pos, w=BADGE_WIDTH_MM, h=BADGE_HEIGHT_MM, type='PNG')

            col_num += 1

        except Exception as e:
            logger.error(f"Badge composition failed for ID {data.get('Badge ID', 'N/A')}: {e}", exc_info=True)
            # Optionally add a placeholder or skip the badge on error
        finally:
            # Clean up the copied image object to free memory
            if badge_image and badge_image != base_template:
                try:
                    badge_image.close()
                except Exception as close_err:
                    logger.warning(f"Error closing badge image object: {close_err}")

    # Clean up the base template image object
    try:
        base_template.close()
    except Exception as close_err:
        logger.warning(f"Error closing base template image object: {close_err}")

    # --- Output PDF to Buffer ---
    try:
        # Use BytesIO to output PDF to memory
        pdf_buffer = BytesIO(pdf.output(dest='S')) # Output as byte string and encode
        pdf_buffer.seek(0) # Rewind buffer to the beginning
        logger.info(f"Successfully generated PDF with {len(badge_data_list)} attendant badges.")
        return pdf_buffer
    except Exception as pdf_err:
         logger.error(f"Error generating final PDF output: {pdf_err}", exc_info=True)
         raise Exception(f"Error generating final PDF output: {pdf_err}")


# --- Attendant Routes ---

@attendant_bp.route('/attendant_form')
@login_required
def attendant_form_page():
    """Displays the form for adding a new SNE Sewadar Attendant."""
    today_date = datetime.date.today()
    current_year = today_date.year
    # Assume AREAS is available from main app context or imported
    # Example: from app import AREAS
    try:
        # You might need to explicitly fetch AREAS from your config source here
        # For now, assume it's passed correctly in render_template context in app.py
        # or available via import. Let's simulate fetching it if needed.
        from app import AREAS # Example: Importing from app.py
    except ImportError:
        logger.warning("Could not import AREAS from app.py for attendant_form_page. Using empty list.")
        AREAS = [] # Fallback

    return render_template('attendant_form.html',
                           today_date=today_date,
                           areas=AREAS, # Pass areas for the dropdown
                           current_user=current_user,
                           current_year=current_year)

@attendant_bp.route('/submit_attendant_form', methods=['POST'])
@login_required
def submit_attendant_form():
    """Handles the submission of the new attendant form."""
    form_data = request.form.to_dict()
    files = request.files

    # --- Basic Validation ---
    required_fields = ['badge_id', 'name', 'area', 'centre', 'phone_number', 'address']
    missing_fields = [field for field in required_fields if not form_data.get(field)]
    if missing_fields:
        flash(f"Missing required fields: {', '.join(missing_fields)}", "error")
        # Re-render form with existing data? Or just redirect? Redirecting is simpler.
        return redirect(url_for('attendant.attendant_form_page'))

    badge_id = form_data.get('badge_id').strip().upper()
    phone_number = re.sub(r'\D', '', form_data.get('phone_number', '')) # Clean phone number

    if len(phone_number) != 10:
         flash("Phone number must be 10 digits.", "error")
         return redirect(url_for('attendant.attendant_form_page'))

    # --- Connect to Sheet and Check Existing ID ---
    sheet = get_attendant_sheet(read_only=False) # Need write access
    if not sheet:
        flash("Error connecting to attendant data storage.", "error")
        return redirect(url_for('attendant.attendant_form_page'))

    id_exists = check_attendant_badge_id_exists(sheet, badge_id)
    if id_exists is True:
        flash(f"Error: Attendant Badge ID '{badge_id}' already exists.", "error")
        return redirect(url_for('attendant.attendant_form_page'))
    elif id_exists is False:
        # False indicates an error occurred during the check
        flash("Error verifying Badge ID uniqueness. Please try again.", "error")
        return redirect(url_for('attendant.attendant_form_page'))

    # --- Handle Photo Upload to S3 (Optional) ---
    s3_object_key = "N/A" # Default if no photo or error
    uploaded_key_for_rollback = None # Track if upload succeeds but sheet write fails

    if 'photo' in files:
        file = files['photo']
        if file and file.filename != '' and allowed_file(file.filename):
            # Create a unique filename (e.g., using Badge ID + timestamp)
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            # Secure filename processing
            base_filename = secure_filename(file.filename)
            extension = base_filename.rsplit('.', 1)[1].lower()
            # Use Badge ID in the key for easier identification
            s3_object_key = f"attendants/{badge_id}_{timestamp}.{extension}"

            try:
                # Assuming s3_client is available
                s3_client = boto3.client('s3') # Initialize if not global
                s3_client.upload_fileobj(
                    file,
                    ATTENDANT_S3_BUCKET_NAME,
                    s3_object_key,
                    ExtraArgs={'ContentType': file.content_type} # Optional: Set content type
                )
                uploaded_key_for_rollback = s3_object_key # Mark successful upload
                logger.info(f"Successfully uploaded attendant photo to S3: {s3_object_key}")
            except ClientError as e:
                 logger.error(f"S3 ClientError uploading attendant photo: {e}", exc_info=True)
                 flash(f"Photo upload failed: {e}", "error")
                 s3_object_key = "Upload Error" # Mark as failed in sheet
            except Exception as e:
                logger.error(f"S3 upload failed for attendant photo: {e}", exc_info=True)
                flash(f"Photo upload failed: {e}", "error")
                s3_object_key = "Upload Error" # Mark as failed in sheet

        elif file and file.filename != '':
            # File provided but type is not allowed
            flash(f"Invalid photo file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}.", 'warning')
            s3_object_key = "N/A" # Treat as if no file was uploaded

    # --- Prepare Data Row for Google Sheet ---
    # Ensure the order matches ATTENDANT_SHEET_HEADERS
    data_row = []
    for header in ATTENDANT_SHEET_HEADERS:
        if header == "Badge ID":
            value = badge_id
        elif header == "Submission Date":
            value = form_data.get('submission_date', datetime.date.today().isoformat())
        elif header == "Area":
            value = form_data.get('area', '')
        elif header == "Centre":
            value = form_data.get('centre', '')
        elif header == "Name":
            value = form_data.get('name', '')
        elif header == "Phone Number":
            value = phone_number # Use cleaned number
        elif header == "Address":
            value = form_data.get('address', '')
        elif header == "Photo Filename":
            value = s3_object_key # Use the S3 key or N/A/Upload Error
        else:
            # Fallback for any unexpected headers
            form_key = header.lower().replace(' ', '_')
            value = form_data.get(form_key, '')
        data_row.append(str(value)) # Ensure all values are strings for gspread

    # --- Append Row to Google Sheet ---
    try:
        sheet.append_row(data_row, value_input_option='USER_ENTERED')
        logger.info(f"Successfully added attendant data for Badge ID: {badge_id}")
        flash(f'Attendant data submitted successfully! Badge ID: {badge_id}', 'success')
        return redirect(url_for('attendant.attendant_form_page')) # Redirect after success
    except gspread.exceptions.APIError as e:
         logger.error(f"gspread API Error appending attendant row for {badge_id}: {e}", exc_info=True)
         flash(f'Error submitting data to Sheet: API Error. Please try again.', 'error')
    except Exception as e:
        logger.error(f"Error writing attendant data to Sheet for {badge_id}: {e}", exc_info=True)
        flash(f'Error submitting data to Sheet: {e}.', 'error')

        # --- Rollback S3 Upload if Sheet Write Fails ---
        if uploaded_key_for_rollback:
            logger.warning(f"Rolling back S3 upload due to sheet error for Badge ID {badge_id}. Deleting key: {uploaded_key_for_rollback}")
            try:
                s3_client = boto3.client('s3') # Re-initialize if needed
                s3_client.delete_object(Bucket=ATTENDANT_S3_BUCKET_NAME, Key=uploaded_key_for_rollback)
                logger.info(f"Successfully deleted S3 object '{uploaded_key_for_rollback}' after sheet error.")
            except ClientError as s3_del_err:
                 logger.error(f"S3 ClientError FAILED to delete S3 object '{uploaded_key_for_rollback}' after sheet error: {s3_del_err}", exc_info=True)
            except Exception as s3_del_err:
                logger.error(f"FAILED to delete S3 object '{uploaded_key_for_rollback}' after sheet error: {s3_del_err}", exc_info=True)

        return redirect(url_for('attendant.attendant_form_page')) # Redirect even on error


@attendant_bp.route('/attendant_edit')
@login_required
def attendant_edit_page():
    """Displays the page for searching and editing attendant entries."""
    current_year = datetime.date.today().year
    # Assume AREAS is available from main app context or imported
    # Example: from app import AREAS
    try:
        from app import AREAS # Example import
    except ImportError:
        AREAS = []

    return render_template('attendant_edit_form.html',
                           areas=AREAS, # Pass areas for the dropdown in the edit form
                           current_user=current_user,
                           current_year=current_year)

@attendant_bp.route('/search_attendant_entries', methods=['GET'])
@login_required
def search_attendant_entries():
    """Searches attendant sheet data by name or badge ID and returns JSON."""
    search_name = request.args.get('name', '').strip().lower()
    search_badge_id = request.args.get('badge_id', '').strip().upper()

    if not search_name and not search_badge_id:
        return jsonify({"error": "Please provide a name or Badge ID to search."}), 400

    try:
        all_data = get_all_attendant_data() # Fetch all attendant data
        results = []

        if search_badge_id:
            # Exact match for Badge ID
            for entry in all_data:
                if str(entry.get('Badge ID', '')).strip().upper() == search_badge_id:
                    results.append(entry)
                    break # Found exact match, no need to search further
        elif search_name:
            # Partial match for Name
            for entry in all_data:
                # Assuming 'Name' is the key for the full name in your sheet data
                full_name = str(entry.get('Name', '')).strip().lower()
                if search_name in full_name:
                    results.append(entry)

        # Limit results to avoid overwhelming the browser (e.g., first 50 matches)
        logger.info(f"Found {len(results)} attendant(s) matching query. Returning up to 50.")
        return jsonify(results[:50])

    except Exception as e:
        logger.error(f"Error searching attendant entries: {e}", exc_info=True)
        return jsonify({"error": f"Search failed due to server error: {e}"}), 500


@attendant_bp.route('/update_attendant_entry/<original_badge_id>', methods=['POST'])
@login_required
def update_attendant_entry(original_badge_id):
    """Handles the submission of the edited attendant data."""
    if not original_badge_id:
        flash("Error: No Attendant Badge ID provided for update.", "error")
        return redirect(url_for('attendant.attendant_edit_page'))

    original_badge_id = original_badge_id.strip().upper()
    form_data = request.form.to_dict()
    files = request.files

    # --- Connect to Sheet and Find Row ---
    sheet = get_attendant_sheet(read_only=False) # Need write access
    if not sheet:
        flash("Error connecting to attendant data storage.", "error")
        return redirect(url_for('attendant.attendant_edit_page'))

    row_index = find_attendant_row_index_by_badge_id(sheet, original_badge_id)
    if not row_index:
        flash(f"Error: Attendant entry with Badge ID '{original_badge_id}' not found.", "error")
        return redirect(url_for('attendant.attendant_edit_page'))

    # --- Get Original Record Data (for photo filename) ---
    try:
        original_record_list = sheet.row_values(row_index)
        # Pad if the fetched row is shorter than expected headers
        while len(original_record_list) < len(ATTENDANT_SHEET_HEADERS):
            original_record_list.append('')
        original_record = dict(zip(ATTENDANT_SHEET_HEADERS, original_record_list))
        old_s3_key = original_record.get('Photo Filename', '')
        logger.info(f"Fetched original record for attendant {original_badge_id}. Old photo key: {old_s3_key}")
    except Exception as fetch_err:
        logger.error(f"Could not fetch original attendant record {original_badge_id}: {fetch_err}", exc_info=True)
        flash(f"Error fetching original attendant data.", "error")
        return redirect(url_for('attendant.attendant_edit_page'))

    # --- Handle Photo Update/Replacement ---
    new_s3_key = old_s3_key # Start with the old key
    delete_old_s3_object = False
    uploaded_new_key_for_rollback = None # Track new upload for potential rollback

    if 'photo' in files:
        file = files['photo']
        if file and file.filename != '' and allowed_file(file.filename):
            # New photo uploaded, generate new key and upload
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            base_filename = secure_filename(file.filename)
            extension = base_filename.rsplit('.', 1)[1].lower()
            temp_new_key = f"attendants/{original_badge_id}_{timestamp}.{extension}" # Use original_badge_id

            try:
                s3_client = boto3.client('s3') # Initialize if not global
                s3_client.upload_fileobj(
                    file,
                    ATTENDANT_S3_BUCKET_NAME,
                    temp_new_key,
                     ExtraArgs={'ContentType': file.content_type}
                )
                new_s3_key = temp_new_key # Update to the new key
                uploaded_new_key_for_rollback = new_s3_key # Track for rollback
                logger.info(f"Successfully uploaded NEW attendant photo to S3: {new_s3_key}")

                # Mark old photo for deletion if it existed and is different
                if old_s3_key and old_s3_key not in ["N/A", "Upload Error", ""] and old_s3_key != new_s3_key:
                    delete_old_s3_object = True
                    logger.info(f"Marking old photo '{old_s3_key}' for deletion.")

            except ClientError as e:
                 logger.error(f"S3 ClientError uploading NEW attendant photo: {e}", exc_info=True)
                 flash(f"New photo upload failed: {e}. Keeping old photo if available.", "error")
                 new_s3_key = old_s3_key # Revert to old key on upload failure
            except Exception as e:
                logger.error(f"S3 upload failed for NEW attendant photo: {e}", exc_info=True)
                flash(f"New photo upload failed: {e}. Keeping old photo if available.", "error")
                new_s3_key = old_s3_key # Revert to old key on upload failure

        elif file and file.filename != '':
            # File provided but type is not allowed
            flash(f"Invalid new photo file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}. No photo updated.", 'warning')
            # Keep the old key, don't change new_s3_key

    # --- Prepare Updated Data Row ---
    updated_data_row = []
    phone_number = re.sub(r'\D', '', form_data.get('phone_number', '')) # Clean phone number

    if len(phone_number) != 10:
         flash("Phone number must be 10 digits.", "error")
         return redirect(url_for('attendant.attendant_edit_page')) # Consider redirecting back with error

    for header in ATTENDANT_SHEET_HEADERS:
        if header == "Badge ID":
            value = original_badge_id # Keep original Badge ID
        elif header == "Submission Date":
             # Keep original submission date unless you want to update it
             value = original_record.get('Submission Date', datetime.date.today().isoformat())
        elif header == "Area":
            value = form_data.get('area', '')
        elif header == "Centre":
            value = form_data.get('centre', '')
        elif header == "Name":
            value = form_data.get('name', '')
        elif header == "Phone Number":
            value = phone_number # Use cleaned number
        elif header == "Address":
            value = form_data.get('address', '')
        elif header == "Photo Filename":
            value = new_s3_key # Use the determined S3 key (new or old)
        else:
            # Fallback for any unexpected headers
            form_key = header.lower().replace(' ', '_')
            value = form_data.get(form_key, '') # Get from form or default to empty
        updated_data_row.append(str(value))

    # --- Update Row in Google Sheet ---
    try:
        # Define the cell range to update (e.g., A<row_index>:H<row_index>)
        end_column_letter = gspread.utils.rowcol_to_a1(1, len(ATTENDANT_SHEET_HEADERS)).split('1')[0]
        update_range = f'A{row_index}:{end_column_letter}{row_index}'

        sheet.update(update_range, [updated_data_row], value_input_option='USER_ENTERED')
        logger.info(f"Successfully updated attendant data in sheet for Badge ID: {original_badge_id}")

        # --- Delete Old S3 Object After Successful Sheet Update ---
        if delete_old_s3_object:
            logger.info(f"Attempting to delete old S3 object: {old_s3_key}")
            try:
                s3_client = boto3.client('s3') # Re-initialize if needed
                s3_client.delete_object(Bucket=ATTENDANT_S3_BUCKET_NAME, Key=old_s3_key)
                logger.info(f"Successfully deleted old S3 object: {old_s3_key}")
            except ClientError as s3_del_err:
                 logger.error(f"S3 ClientError FAILED to delete old S3 object '{old_s3_key}': {s3_del_err}", exc_info=True)
                 flash(f"Attendant data updated, but failed to delete the old photo from storage.", "warning") # Non-critical error
            except Exception as s3_del_err:
                logger.error(f"FAILED to delete old S3 object '{old_s3_key}': {s3_del_err}", exc_info=True)
                flash(f"Attendant data updated, but failed to delete the old photo from storage.", "warning") # Non-critical error

        flash(f'Attendant Entry {original_badge_id} updated successfully!', 'success')
        return redirect(url_for('attendant.attendant_edit_page')) # Redirect after success

    except gspread.exceptions.APIError as e:
         logger.error(f"gspread API Error updating attendant row {row_index} for {original_badge_id}: {e}", exc_info=True)
         flash(f'Error updating Sheet: API Error. Please try again.', 'error')
    except Exception as e:
        logger.error(f"Error updating attendant Sheet row {row_index} for {original_badge_id}: {e}", exc_info=True)
        flash(f'Error updating Sheet: {e}.', 'error')

        # --- Rollback New S3 Upload if Sheet Update Fails ---
        if uploaded_new_key_for_rollback:
            logger.warning(f"Rolling back S3 upload due to sheet update error for {original_badge_id}. Deleting key: {uploaded_new_key_for_rollback}")
            try:
                s3_client = boto3.client('s3') # Re-initialize if needed
                s3_client.delete_object(Bucket=ATTENDANT_S3_BUCKET_NAME, Key=uploaded_new_key_for_rollback)
                logger.info(f"Successfully deleted NEW S3 object '{uploaded_new_key_for_rollback}' after sheet update error.")
            except ClientError as s3_del_err:
                 logger.error(f"S3 ClientError FAILED to delete NEW S3 object '{uploaded_new_key_for_rollback}' after sheet update error: {s3_del_err}", exc_info=True)
            except Exception as s3_del_err:
                logger.error(f"FAILED to delete NEW S3 object '{uploaded_new_key_for_rollback}' after sheet update error: {s3_del_err}", exc_info=True)

        return redirect(url_for('attendant.attendant_edit_page')) # Redirect on error


@attendant_bp.route('/attendant_printer')
@login_required
def attendant_printer_page():
    """Displays the form to enter attendant Badge IDs for printing."""
    current_year = datetime.date.today().year
    return render_template('attendant_printer_form.html',
                           current_user=current_user,
                           current_year=current_year)

@attendant_bp.route('/generate_attendant_pdf', methods=['POST'])
@login_required
def generate_attendant_pdf():
    """Generates a PDF of badges for the specified attendant Badge IDs."""
    badge_ids_raw = request.form.get('badge_ids', '')
    # Process input: split by comma, trim whitespace, convert to uppercase, filter empty strings
    badge_ids_to_print = [bid.strip().upper() for bid in badge_ids_raw.split(',') if bid.strip()]

    if not badge_ids_to_print:
        flash("Please enter at least one Attendant Badge ID.", "error")
        return redirect(url_for('attendant.attendant_printer_page'))

    logger.info(f"Request to generate PDF for Attendant Badge IDs: {badge_ids_to_print}")

    try:
        # Fetch all attendant data from the sheet
        all_attendant_sheet_data = get_all_attendant_data()
        # Create a dictionary for quick lookup by Badge ID
        data_map = {str(row.get('Badge ID', '')).strip().upper(): row
                    for row in all_attendant_sheet_data if row.get('Badge ID')}
    except Exception as e:
        logger.error(f"Error fetching attendant data for PDF generation: {e}", exc_info=True)
        flash(f"Error fetching attendant data: {e}", "error")
        return redirect(url_for('attendant.attendant_printer_page'))

    # Filter the data to include only the requested Badge IDs
    badges_data_for_pdf = []
    not_found_ids = []
    for bid in badge_ids_to_print:
        if bid in data_map:
            badges_data_for_pdf.append(data_map[bid])
        else:
            not_found_ids.append(bid)
            logger.warning(f"Attendant Badge ID '{bid}' requested for PDF not found in sheet data.")

    # Check if any valid IDs were found
    if not badges_data_for_pdf:
        flash("No valid Attendant Badge IDs found in the provided list.", "error")
        return redirect(url_for('attendant.attendant_printer_page'))

    # Optionally flash a warning if some IDs were not found
    if not_found_ids:
        flash(f"Warning: The following Attendant IDs were not found: {', '.join(not_found_ids)}", "warning")

    # --- Generate the PDF ---
    try:
        logger.info(f"Generating PDF for {len(badges_data_for_pdf)} attendant badges.")
        # Call the helper function to create the PDF in memory
        pdf_buffer = create_attendant_pdf_with_badges(badges_data_for_pdf)

        # Create a dynamic filename for the download
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Attendant_Badges_{timestamp}.pdf"

        logger.info(f"Sending generated PDF: {filename}")
        # Send the PDF buffer as a file download
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error generating attendant PDF: {e}", exc_info=True)
        flash(f"Error generating PDF: {e}", "error")
        return redirect(url_for('attendant.attendant_printer_page'))


# --- Route for Dynamic Centre Loading (If needed within Blueprint) ---
# This depends on how BADGE_CONFIG is accessed. If it's global or passed
# via app config, this can work here. Otherwise, keep it in app.py.
@attendant_bp.route('/get_centres/<area>')
@login_required
def get_centres_for_attendant(area):
    """Returns a JSON list of centres for a given area."""
    # Assumes BADGE_CONFIG is accessible (e.g., imported from app or config)
    try:
        from app import BADGE_CONFIG # Example import
        if area in BADGE_CONFIG:
            centres = sorted(list(BADGE_CONFIG[area].keys()))
            return jsonify(centres)
        else:
            return jsonify([]) # Return empty list if area not found
    except ImportError:
         logger.error("BADGE_CONFIG could not be imported for /get_centres route in attendant_routes.")
         return jsonify({"error": "Server configuration error"}), 500
    except Exception as e:
        logger.error(f"Error in get_centres_for_attendant for area '{area}': {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve centres"}), 500

