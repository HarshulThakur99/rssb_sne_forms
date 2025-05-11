# utils.py
import os
import datetime
import re
import logging
from io import BytesIO
import textwrap

import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont, ImageOps # Ensure ImageOps is imported if used for something like fit
from dateutil.relativedelta import relativedelta
from dateutil import parser as date_parser
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError

# Import configuration constants
import config

# Initialize S3 client globally (or pass it around if preferred)
s3_client = boto3.client('s3')
logger = logging.getLogger(__name__) # Use a logger instance

# --- Google Sheet Utilities ---

def get_sheet(sheet_id, service_account_path, read_only=False):
    """Authenticates and returns a specific Google Sheet worksheet object."""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        if read_only:
            scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']

        if not os.path.exists(service_account_path):
            logger.error(f"Service account file not found: {service_account_path}")
            return None

        creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        logger.info(f"Successfully accessed Google Sheet (ID: {sheet_id}). ReadOnly={read_only}")
        return sheet
    except gspread.exceptions.APIError as e:
        logger.error(f"gspread API Error accessing Sheet (ID: {sheet_id}): {e}", exc_info=True)
        if hasattr(e, 'response'):
            if e.response.status_code == 403:
                 logger.error("Permission denied. Check sheet sharing settings and service account permissions.")
            elif e.response.status_code == 404:
                 logger.error("Sheet not found. Verify SHEET_ID.")
        return None
    except Exception as e:
        logger.error(f"Error accessing Google Sheet (ID: {sheet_id}): {e}", exc_info=True)
        return None

def get_all_sheet_data(sheet_id, service_account_path, headers_list):
    """Gets all data from the sheet and returns a list of dictionaries."""
    sheet = get_sheet(sheet_id, service_account_path, read_only=True)
    if not sheet:
        raise Exception(f"Could not connect to sheet {sheet_id} to get data.")
    try:
        all_values = sheet.get_all_values()
        if not all_values or len(all_values) < 1: 
            return []

        header_row = headers_list
        data_rows = all_values[1:] if len(all_values) > 1 else []

        list_of_dicts = []
        num_headers = len(header_row)
        for row_index, row in enumerate(data_rows):
            padded_row = row + [''] * (num_headers - len(row))
            truncated_row = padded_row[:num_headers]
            try:
                record_dict = dict(zip(header_row, truncated_row))
                if any(val for val in record_dict.values()): 
                    list_of_dicts.append(record_dict)
            except Exception as zip_err:
                logger.error(f"Error creating dict for row {row_index + 2} in sheet {sheet_id}: {zip_err} - Row: {row}")

        logger.info(f"Fetched {len(list_of_dicts)} records from sheet {sheet_id}.")
        return list_of_dicts
    except Exception as e:
        logger.error(f"Could not get/process sheet data from {sheet_id}: {e}", exc_info=True)
        raise Exception(f"Could not get/process sheet data from {sheet_id}: {e}")

def find_row_index_by_value(sheet, column_header, value_to_find, headers_list):
    """Finds the 1-based row index for a value in a specific column."""
    if not sheet:
        logger.error("Sheet object is None in find_row_index_by_value.")
        return None
    try:
        col_index = headers_list.index(column_header) + 1
    except ValueError:
        logger.error(f"Header '{column_header}' not found in provided headers list.")
        return None

    value_to_find_cleaned = str(value_to_find).strip().upper()
    if not value_to_find_cleaned:
        return None 

    try:
        cell = sheet.find(value_to_find_cleaned, in_column=col_index)
        if cell:
            logger.info(f"Found '{value_to_find_cleaned}' in column '{column_header}' at row {cell.row}.")
            return cell.row 
        else:
            logger.warning(f"Value '{value_to_find_cleaned}' not found in column '{column_header}'.")
            return None
    except gspread.exceptions.APIError as e:
         logger.error(f"gspread API Error finding value '{value_to_find_cleaned}' in column '{column_header}': {e}", exc_info=True)
         return None 
    except Exception as e:
        logger.error(f"Error finding row index for '{value_to_find_cleaned}' in column '{column_header}': {e}", exc_info=True)
        return None 

# --- File & Data Utilities ---

def allowed_file(filename):
    """Checks if the filename has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

def calculate_age_from_dob(dob_str):
    """Calculates age in years from a DOB string (YYYY-MM-DD). Returns None on error."""
    if not dob_str:
        return None
    try:
        birth_date = date_parser.parse(dob_str).date()
        today = datetime.date.today()
        if birth_date > today:
             logger.warning(f"DOB {dob_str} is in the future.")
             return None 
        age = relativedelta(today, birth_date).years
        return age
    except Exception as e:
        logger.error(f"Error calculating age from DOB '{dob_str}': {e}")
        return None

def clean_phone_number(phone_str):
    """Removes non-digit characters from a phone number string."""
    return re.sub(r'\D', '', str(phone_str))

def clean_aadhaar_number(aadhaar_str):
    """Removes spaces from an Aadhaar number string."""
    return re.sub(r'\s+', '', str(aadhaar_str)).strip()

# --- S3 Utilities ---

def handle_photo_upload(file_storage, bucket_name, s3_prefix, unique_id_part):
    """Handles photo upload to S3."""
    if not file_storage or file_storage.filename == '':
        return "N/A" 

    if not allowed_file(file_storage.filename):
        logger.warning(f"Invalid file type uploaded: {file_storage.filename}")
        return "N/A" 

    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        base_filename = secure_filename(file_storage.filename)
        extension = base_filename.rsplit('.', 1)[1].lower()
        s3_object_key = f"{s3_prefix.strip('/')}/{unique_id_part}_{timestamp}.{extension}"

        s3_client.upload_fileobj(
            file_storage,
            bucket_name,
            s3_object_key,
            ExtraArgs={'ContentType': file_storage.content_type} 
        )
        logger.info(f"Successfully uploaded photo to S3: {s3_object_key}")
        return s3_object_key
    except ClientError as e:
         logger.error(f"S3 ClientError uploading photo: {e}", exc_info=True)
         return "Upload Error"
    except Exception as e:
        logger.error(f"S3 upload failed for photo: {e}", exc_info=True)
        return "Upload Error"

def delete_s3_object(bucket_name, s3_key):
    """Deletes an object from S3, logging errors."""
    if not s3_key or s3_key in ["N/A", "Upload Error", ""]:
        logger.debug(f"Skipping S3 deletion for invalid key: {s3_key}")
        return False 

    try:
        logger.info(f"Attempting to delete S3 object: Bucket='{bucket_name}', Key='{s3_key}'")
        s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
        logger.info(f"Successfully deleted S3 object: {s3_key}")
        return True
    except ClientError as e:
         logger.error(f"S3 ClientError FAILED to delete S3 object '{s3_key}': {e}", exc_info=True)
         return False
    except Exception as e:
        logger.error(f"FAILED to delete S3 object '{s3_key}': {e}", exc_info=True)
        return False

# --- PDF Generation Utility ---

def generate_badge_pdf(badge_data_list, layout_config):
    """
    Generates a PDF document containing badges based on provided data and layout config.
    Dynamically selects badge template based on 'attendant_type' in badge_data.
    """
    pdf_layout = layout_config['pdf_layout']
    photo_config = layout_config['photo_config']
    text_elements = layout_config['text_elements']
    wrap_config = layout_config.get('wrap_config', {})

    PAGE_WIDTH_MM = 297 if pdf_layout['format'] == 'A4' and pdf_layout['orientation'] == 'L' else 210
    PAGE_HEIGHT_MM = 210 if pdf_layout['format'] == 'A4' and pdf_layout['orientation'] == 'L' else 297
    BADGE_WIDTH_MM = pdf_layout['badge_w_mm']
    BADGE_HEIGHT_MM = pdf_layout['badge_h_mm']
    MARGIN_MM = pdf_layout['margin_mm']
    GAP_MM = pdf_layout.get('gap_mm', 0)

    effective_badge_width = BADGE_WIDTH_MM + GAP_MM
    effective_badge_height = BADGE_HEIGHT_MM + GAP_MM

    badges_per_row = int((PAGE_WIDTH_MM - 2 * MARGIN_MM + GAP_MM) / effective_badge_width) if effective_badge_width > 0 else 1
    badges_per_col = int((PAGE_HEIGHT_MM - 2 * MARGIN_MM + GAP_MM) / effective_badge_height) if effective_badge_height > 0 else 1
    if badges_per_row <= 0: badges_per_row = 1
    if badges_per_col <= 0: badges_per_col = 1

    pdf = FPDF(orientation=pdf_layout['orientation'], unit=pdf_layout['unit'], format=pdf_layout['format'])
    pdf.set_auto_page_break(auto=False, margin=MARGIN_MM)
    pdf.add_page()
    col_num = 0
    row_num = 0

    # --- Pre-load Badge Templates based on type ---
    templates_by_type_paths = layout_config.get('templates_by_type', {})
    loaded_templates = {}
    if not templates_by_type_paths:
        logger.error("CRITICAL: 'templates_by_type' is missing in layout_config.")
        return None

    for type_key, path in templates_by_type_paths.items():
        try:
            if not os.path.exists(path):
                logger.error(f"CRITICAL: Badge template file not found for type '{type_key}': {path}")
                # If default template is missing, it's a critical failure
                if type_key == "default": return None 
                continue # Skip this template if not default and not found
            loaded_templates[type_key] = Image.open(path).convert("RGBA")
            logger.info(f"Loaded badge template for type '{type_key}': {path}")
        except Exception as e:
            logger.error(f"CRITICAL: Error loading badge template for type '{type_key}' path '{path}': {e}", exc_info=True)
            if type_key == "default": return None # Critical if default fails
            # For other types, we can try to fall back to default later if this specific one fails

    if not loaded_templates.get("default"):
        logger.error("CRITICAL: Default badge template ('default') not loaded or path not specified.")
        return None
        
    # --- Pre-load Fonts ---
    loaded_fonts = {}
    loaded_fonts_bold = {}
    bold_load_failed_sizes = set()
    font_path = layout_config['font_path']
    font_bold_path = layout_config['font_bold_path']

    unique_font_sizes = set(config['size'] for config in text_elements.values())
    needs_bold = any(config.get('is_bold', False) for config in text_elements.values())

    for size in unique_font_sizes:
        if size not in loaded_fonts:
            try:
                if not os.path.exists(font_path):
                     logger.error(f"CRITICAL: Font file not found: {font_path}")
                     return None # Cannot proceed without base font
                loaded_fonts[size] = ImageFont.truetype(font_path, size)
            except Exception as e:
                logger.error(f"CRITICAL: Error loading regular font '{font_path}' size {size}: {e}")
                return None

        if needs_bold and size not in loaded_fonts_bold and size not in bold_load_failed_sizes:
            try:
                if not os.path.exists(font_bold_path):
                    logger.warning(f"Bold font file not found: {font_bold_path}. Falling back to regular for size {size}.")
                    loaded_fonts_bold[size] = loaded_fonts.get(size) # Fallback
                    bold_load_failed_sizes.add(size)
                else:
                    loaded_fonts_bold[size] = ImageFont.truetype(font_bold_path, size)
            except Exception as e:
                logger.warning(f"Could not load bold font '{font_bold_path}' size {size}: {e}. Falling back to regular.")
                loaded_fonts_bold[size] = loaded_fonts.get(size) 
                bold_load_failed_sizes.add(size)
        elif needs_bold and size in bold_load_failed_sizes:
            loaded_fonts_bold[size] = loaded_fonts.get(size) 
        elif needs_bold and not loaded_fonts_bold.get(size): # Ensure bold font is set if needed
             loaded_fonts_bold[size] = loaded_fonts.get(size)


    # --- Generate Badges ---
    for data in badge_data_list:
        badge_image_composite = None 
        try:
            # --- Determine and select the correct template for the current badge ---
            attendant_type = str(data.get('attendant_type', 'default')).lower() # Get type from data, default to 'default'
            
            current_template_image = loaded_templates.get(attendant_type)
            if not current_template_image:
                logger.warning(f"Template for type '{attendant_type}' not found or failed to load. Using default template.")
                current_template_image = loaded_templates.get("default")
            
            if not current_template_image:
                logger.error(f"CRITICAL: Default template also not available. Skipping badge for {data.get('badge_id', data.get('name', 'N/A'))}.")
                continue # Skip this badge if no template can be found

            # Create a fresh copy of the selected template for this badge
            badge_image_composite = current_template_image.copy()
            draw = ImageDraw.Draw(badge_image_composite)

            # --- Add Photo from S3 (if configured and available) ---
            s3_key_field = photo_config.get('s3_key_field')
            s3_object_key = data.get(s3_key_field, '') if s3_key_field else ''

            if s3_object_key and s3_object_key not in ['N/A', 'Upload Error', '']:
                try:
                    logger.info(f"Attempting to download photo from S3: Bucket='{layout_config['s3_bucket']}', Key='{s3_object_key}'")
                    s3_response = s3_client.get_object(Bucket=layout_config['s3_bucket'], Key=s3_object_key)
                    with Image.open(BytesIO(s3_response['Body'].read())).convert("RGBA") as holder_photo:
                        # Resize photo using LANCZOS (high quality)
                        with holder_photo.resize((photo_config['box_w'], photo_config['box_h']), Image.Resampling.LANCZOS) as resized_photo:
                            badge_image_composite.paste(resized_photo, (photo_config['paste_x'], photo_config['paste_y']), resized_photo)
                    logger.info(f"Successfully added photo '{s3_object_key}' to badge.")
                except ClientError as e:
                     if e.response['Error']['Code'] == 'NoSuchKey':
                         logger.warning(f"S3 photo not found: Key='{s3_object_key}', Bucket='{layout_config['s3_bucket']}'")
                     else:
                         logger.error(f"S3 ClientError downloading photo '{s3_object_key}': {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error processing S3 photo '{s3_object_key}': {e}", exc_info=True)
            elif s3_object_key and s3_object_key not in ['N/A', 'Upload Error', '']: # Log if key exists but client might be issue
                 logger.warning(f"S3 client not available or config missing, cannot download photo: {s3_object_key}")


            # --- Draw Text onto Badge ---
            for key, text_config in text_elements.items():
                text = str(data.get(key, '')).upper() 
                if text: 
                    font_size = text_config['size']
                    is_bold = text_config.get('is_bold', False)
                    color = text_config.get('color', 'black') 

                    font_to_use = loaded_fonts_bold.get(font_size) if is_bold else loaded_fonts.get(font_size)
                    if not font_to_use and is_bold: # Fallback if bold font for that size failed to load
                        font_to_use = loaded_fonts.get(font_size)
                    
                    if not font_to_use:
                        logger.warning(f"Font size {font_size} (bold={is_bold}) not loaded for '{key}', skipping text draw.")
                        continue

                    if wrap_config and key == wrap_config.get('field_key'):
                        wrapped_text = "\n".join(textwrap.wrap(text, width=wrap_config.get('width', 20)))
                        draw.multiline_text(text_config['coords'], wrapped_text, fill=color, font=font_to_use, spacing=wrap_config.get('spacing', 4))
                    else:
                        draw.text(text_config['coords'], text, fill=color, font=font_to_use)

            # --- Place Badge onto PDF Page ---
            if col_num >= badges_per_row:
                col_num = 0
                row_num += 1

            if row_num >= badges_per_col:
                row_num = 0
                col_num = 0 
                pdf.add_page()

            x_pos = MARGIN_MM + col_num * effective_badge_width
            y_pos = MARGIN_MM + row_num * effective_badge_height

            with BytesIO() as temp_img_buffer:
                badge_image_composite.save(temp_img_buffer, format="PNG")
                temp_img_buffer.seek(0)
                pdf.image(temp_img_buffer, x=x_pos, y=y_pos, w=BADGE_WIDTH_MM, h=BADGE_HEIGHT_MM, type='PNG')

            col_num += 1

        except Exception as e:
            logger.error(f"Badge composition failed for data: {data.get('Badge ID', data.get('Donor ID', 'N/A'))}: {e}", exc_info=True)
        finally:
            if badge_image_composite:
                try:
                    badge_image_composite.close()
                except Exception as close_err:
                    logger.warning(f"Error closing badge composite image object: {close_err}")

    # --- Clean up pre-loaded templates ---
    for template_img in loaded_templates.values():
        if template_img: # Check if it was successfully loaded
            try:
                template_img.close()
            except Exception as close_err:
                logger.warning(f"Error closing pre-loaded template image: {close_err}")

    # --- Output PDF to Buffer ---
    try:
        try:
            pdf_output = pdf.output(dest='S')
            pdf_buffer = BytesIO(pdf_output)
        except TypeError: 
            pdf_output = pdf.output(dest='S').encode('latin-1') # Ensure correct encoding for BytesIO
            pdf_buffer = BytesIO(pdf_output)

        pdf_buffer.seek(0) 
        logger.info(f"Successfully generated PDF with {len(badge_data_list)} badges.")
        return pdf_buffer
    except Exception as pdf_err:
         logger.error(f"Error generating final PDF output: {pdf_err}", exc_info=True)
         return None
