# sne_routes.py (Updated for circular import fix)
import datetime
import re
import logging
from io import BytesIO

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify,
    send_file, current_app
)
from flask_login import login_required
# current_user is available globally via context_processor in app.py,
# so direct import here might not be strictly necessary for templates,
# but good for explicitness if used in Python logic within this file.
from flask_login import current_user


# Import shared utilities and configuration
from app import utils
from app import config
# Import the decorator from the new decorators.py file
from app.decorators import permission_required

# --- Blueprint Definition ---
sne_bp = Blueprint('sne', __name__, url_prefix='/sne')
logger = logging.getLogger(__name__)

# --- Helper Functions Specific to SNE (Copied from original, ensure they are robust) ---
def check_sne_aadhaar_exists(sheet, aadhaar, area, exclude_badge_id=None):
    """Checks if SNE Aadhaar exists for the given Area, optionally excluding a Badge ID."""
    if not sheet:
        logger.error("SNE sheet object is None in check_sne_aadhaar_exists.")
        return False # Indicate error

    try:
        # Get column indices from config
        aadhaar_col_idx = config.SNE_SHEET_HEADERS.index('Aadhaar No')
        area_col_idx = config.SNE_SHEET_HEADERS.index('Area')
        badge_id_col_idx = config.SNE_SHEET_HEADERS.index('Badge ID')
    except ValueError as e:
        logger.error(f"SNE Header config error: {e}")
        return False # Indicate configuration error

    try:
        all_values = sheet.get_all_values()
        if len(all_values) <= 1: # Only header row or empty
            return None # Not found

        data_rows = all_values[1:]
        cleaned_aadhaar_search = utils.clean_aadhaar_number(aadhaar)
        if not cleaned_aadhaar_search: # Avoid searching for empty strings
            return None 

        for row in data_rows:
            # Ensure row has enough columns
            if len(row) <= max(aadhaar_col_idx, area_col_idx, badge_id_col_idx):
                continue

            record_badge_id = str(row[badge_id_col_idx]).strip().upper()
            # Skip the record being edited if exclude_badge_id is provided
            if exclude_badge_id and record_badge_id == str(exclude_badge_id).strip().upper():
                continue

            record_aadhaar_cleaned = utils.clean_aadhaar_number(row[aadhaar_col_idx])
            record_area = str(row[area_col_idx]).strip()

            if record_aadhaar_cleaned == cleaned_aadhaar_search and record_area == str(area).strip():
                logger.warning(f"SNE Aadhaar '{cleaned_aadhaar_search}' found in Area '{record_area}' with Badge ID '{record_badge_id}'.")
                return record_badge_id # Return the Badge ID of the existing record

        return None # Not found
    except Exception as e:
        logger.error(f"Error checking SNE Aadhaar: {e}", exc_info=True)
        return False # Indicate error during check

def get_next_sne_badge_id(sheet, area, centre):
    """Generates the next sequential SNE Badge ID specific to Area and Centre."""
    if not sheet:
        raise Exception("Could not connect to SNE sheet.")
    if area not in config.SNE_BADGE_CONFIG or centre not in config.SNE_BADGE_CONFIG[area]:
        raise ValueError("Invalid Area or Centre for SNE Badge ID generation.")

    centre_config = config.SNE_BADGE_CONFIG[area][centre]
    prefix = centre_config["prefix"]
    start_num = centre_config["start"]

    try:
        # Get column indices from config
        badge_id_col_idx = config.SNE_SHEET_HEADERS.index('Badge ID')
        satsang_place_col_idx = config.SNE_SHEET_HEADERS.index('Satsang Place')
    except ValueError as e:
        raise Exception(f"Missing required SNE headers in config: {e}")

    try:
        all_values = sheet.get_all_values()
        max_num = start_num - 1 # Initialize max_num correctly
        found_matching_centre = False

        if len(all_values) > 1: # Check if there are any data rows
            data_rows = all_values[1:]
            for row in data_rows:
                # Ensure row has enough columns
                if len(row) <= max(badge_id_col_idx, satsang_place_col_idx):
                    continue

                row_satsang_place = str(row[satsang_place_col_idx]).strip()
                existing_id = str(row[badge_id_col_idx]).strip().upper()

                # Check if the row belongs to the target centre and uses the correct prefix
                if row_satsang_place == centre and existing_id.startswith(prefix):
                    found_matching_centre = True
                    try:
                        # Extract the numeric part after the prefix
                        num_part_str = existing_id[len(prefix):]
                        if num_part_str.isdigit():
                            max_num = max(max_num, int(num_part_str))
                    except (ValueError, IndexError):
                        logger.warning(f"Could not parse number from existing SNE Badge ID: {existing_id}")
                        pass # Ignore IDs that don't parse correctly

        # If no entries found for this specific centre, max_num remains start_num - 1
        # So next_num will correctly become start_num
        if not found_matching_centre:
             # This ensures that if no entries for this center exist, it starts from the configured start_num
            max_num = start_num - 1


        # Calculate the next number
        next_num = max(start_num, max_num + 1) # Ensures it's at least start_num
        next_badge_id = f"{prefix}{next_num}" # Assumes prefix doesn't need zero padding for number
        logger.info(f"Generated next SNE Badge ID for {area}/{centre}: {next_badge_id}")
        return next_badge_id
    except Exception as e:
        logger.error(f"Error generating SNE Badge ID for {area}/{centre}: {e}", exc_info=True)
        raise # Re-raise the exception to be caught by the route

# --- SNE Routes ---
@sne_bp.route('/form')
@login_required
@permission_required('access_sne_form')
def form_page():
    """Displays the SNE data entry form."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('form.html',
                           today_date=today_date,
                           areas=config.AREAS,
                           states=config.STATES,
                           relations=config.RELATIONS,
                           # current_user is available globally via context_processor
                           current_year=current_year)

@sne_bp.route('/submit', methods=['POST'])
@login_required
@permission_required('submit_sne_form')
def submit_form():
    """Handles the submission of the new SNE form."""
    sheet = utils.get_sheet(config.SNE_SHEET_ID, config.SNE_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to SNE data storage.", "error")
        return redirect(url_for('sne.form_page'))

    try:
        form_data = request.form.to_dict()
        files = request.files
        aadhaar_no = form_data.get('aadhaar_no', '').strip()
        selected_area = form_data.get('area', '').strip()
        selected_centre = form_data.get('satsang_place', '').strip()
        dob_str = form_data.get('dob', '')

        mandatory_fields = ['area', 'satsang_place', 'first_name', 'father_husband_name',
                            'gender', 'dob', 'aadhaar_no', 'emergency_contact_name',
                            'emergency_contact_number', 'emergency_contact_relation', 'address', 'state']
        missing_fields = [field for field in mandatory_fields if not form_data.get(field)]
        if missing_fields:
            flash(f"Missing mandatory SNE fields: {', '.join(missing_fields)}", "error")
            return redirect(url_for('sne.form_page'))

        existing_badge_id = check_sne_aadhaar_exists(sheet, aadhaar_no, selected_area)
        if existing_badge_id: # True if exists
            flash(f"Error: SNE Aadhaar {aadhaar_no} already exists for Area '{selected_area}' (Badge ID '{existing_badge_id}').", "error")
            return redirect(url_for('sne.form_page'))
        elif existing_badge_id is False: # False indicates an error during the check
            flash("Error verifying SNE Aadhaar uniqueness. Please try again.", "error")
            return redirect(url_for('sne.form_page'))

        cleaned_aadhaar = utils.clean_aadhaar_number(aadhaar_no)
        unique_part = cleaned_aadhaar if cleaned_aadhaar else f"{form_data.get('first_name', 'user')}_{form_data.get('last_name', '')}"
        s3_object_key = utils.handle_photo_upload(
            files.get('photo'),
            config.S3_BUCKET_NAME,
            s3_prefix='sne_photos',
            unique_id_part=unique_part
        )
        if s3_object_key == "Upload Error":
            flash("Photo upload failed. Please check logs.", "error")
            # Continue submission but mark photo as failed

        try:
            new_badge_id = get_next_sne_badge_id(sheet, selected_area, selected_centre)
        except Exception as e:
            flash(f"Error generating SNE Badge ID: {e}", "error")
            if s3_object_key not in ["N/A", "Upload Error", ""]: # Check if a file was actually uploaded
                utils.delete_s3_object(config.S3_BUCKET_NAME, s3_object_key)
            return redirect(url_for('sne.form_page'))

        calculated_age = utils.calculate_age_from_dob(dob_str)
        data_row = []
        for header in config.SNE_SHEET_HEADERS:
            # Standardize form key generation
            form_key = header.lower().replace(' ', '_').replace("'", "").replace('/', '_').replace('(yes/no)', '').replace('(','').replace(')','').strip('_')

            if header == "Submission Date": value = form_data.get('submission_date', datetime.date.today().isoformat())
            elif header == "Area": value = selected_area
            elif header == "Satsang Place": value = selected_centre
            elif header == "Age": value = calculated_age if calculated_age is not None else ''
            elif header == "Aadhaar No": value = aadhaar_no # Use original form value
            elif header == "Photo Filename": value = s3_object_key
            elif header == "Badge ID": value = new_badge_id
            elif header.endswith('(Yes/No)'):
                # Construct the likely form key for Yes/No fields
                base_key = header.replace(' (Yes/No)', '').lower().replace(' ', '_').replace("'", "").replace('/', '_')
                value = form_data.get(base_key, 'No') # Default to 'No' if not found
            else:
                value = form_data.get(form_key, '') # Get value from form or default to empty
            data_row.append(str(value))
        try:
            sheet.append_row(data_row, value_input_option='USER_ENTERED')
            logger.info(f"Successfully added SNE data for Badge ID: {new_badge_id}")
            flash(f'SNE Data submitted successfully! Badge ID: {new_badge_id}', 'success')
            return redirect(url_for('sne.form_page'))
        except Exception as e:
            logger.error(f"Error writing SNE data to Sheet for {new_badge_id}: {e}", exc_info=True)
            flash(f'Error submitting SNE data to Sheet: {e}.', 'error')
            if s3_object_key not in ["N/A", "Upload Error", ""]:
                utils.delete_s3_object(config.S3_BUCKET_NAME, s3_object_key)
            return redirect(url_for('sne.form_page'))
    except Exception as e:
        logger.error(f"Unexpected error during SNE submission: {e}", exc_info=True)
        flash(f'An unexpected error occurred: {e}', 'error')
        return redirect(url_for('sne.form_page'))

@sne_bp.route('/printer')
@login_required
@permission_required('access_sne_printer')
def printer_page():
    """Displays the SNE badge printing form."""
    current_year = datetime.date.today().year
    return render_template('printer_form.html',
                           centres=config.CENTRES, # Kept for consistency if needed later
                           current_year=current_year)

@sne_bp.route('/generate_pdf', methods=['POST'])
@login_required
@permission_required('generate_sne_pdf')
def generate_pdf():
    """Generates a PDF of badges for the specified SNE Badge IDs."""
    badge_ids_raw = request.form.get('badge_ids', '')
    badge_ids_to_print = [bid.strip().upper() for bid in badge_ids_raw.split(',') if bid.strip()]

    if not badge_ids_to_print:
        flash("Please enter at least one SNE Badge ID.", "error")
        return redirect(url_for('sne.printer_page'))
    logger.info(f"Request to generate PDF for SNE Badge IDs: {badge_ids_to_print}")
    try:
        all_sne_sheet_data = utils.get_all_sheet_data(
            config.SNE_SHEET_ID,
            config.SNE_SERVICE_ACCOUNT_FILE,
            config.SNE_SHEET_HEADERS
        )
        data_map = {str(row.get('Badge ID', '')).strip().upper(): row
                    for row in all_sne_sheet_data if row.get('Badge ID')}
    except Exception as e:
        logger.error(f"Error fetching SNE data for PDF generation: {e}", exc_info=True)
        flash(f"Error fetching SNE data: {e}", "error")
        return redirect(url_for('sne.printer_page'))

    badges_data_for_pdf = []
    not_found_ids = []
    for bid in badge_ids_to_print:
        if bid in data_map:
            if not data_map[bid].get('Age'): # Calculate age if missing
                 dob = data_map[bid].get('Date of Birth')
                 age = utils.calculate_age_from_dob(dob)
                 if age is not None:
                     data_map[bid]['Age'] = age
            badges_data_for_pdf.append(data_map[bid])
        else:
            not_found_ids.append(bid)
            logger.warning(f"SNE Badge ID '{bid}' requested for PDF not found in sheet data.")
    if not badges_data_for_pdf:
        flash("No valid SNE Badge IDs found in the provided list.", "error")
        return redirect(url_for('sne.printer_page'))
    if not_found_ids:
        flash(f"Warning: The following SNE IDs were not found: {', '.join(not_found_ids)}", "warning")

    sne_layout_config = {
        "template_path": config.SNE_BADGE_TEMPLATE_PATH,
        "text_elements": config.SNE_TEXT_ELEMENTS,
        "photo_config": {
            'paste_x': config.SNE_PHOTO_PASTE_X_PX,
            'paste_y': config.SNE_PHOTO_PASTE_Y_PX,
            'box_w': config.SNE_PHOTO_BOX_WIDTH_PX,
            'box_h': config.SNE_PHOTO_BOX_HEIGHT_PX,
            's3_key_field': 'Photo Filename'
        },
        "pdf_layout": {
            'orientation': 'L', 'unit': 'mm', 'format': 'A4',
            'badge_w_mm': 125, 'badge_h_mm': 80, 'margin_mm': 15, 'gap_mm': 0
        },
        "font_path": config.FONT_PATH,
        "font_bold_path": config.FONT_BOLD_PATH,
        "s3_bucket": config.S3_BUCKET_NAME,
         "wrap_config": {'field_key': 'address', 'width': 20, 'spacing': 10}
    }
    pdf_ready_data = []
    for row_data in badges_data_for_pdf:
        mapped_data = {
            "badge_id": row_data.get('Badge ID', 'N/A'),
            "name": f"{str(row_data.get('First Name', '')).strip()} {str(row_data.get('Last Name', '')).strip()}".strip(),
            "gender": row_data.get('Gender', ''),
            "age": f"AGE: {row_data.get('Age', '')} YEARS" if row_data.get('Age') else "",
            "centre": row_data.get('Satsang Place', ''),
            "area": row_data.get('Area', ''),
            "address": row_data.get('Address', ''),
            "Photo Filename": row_data.get('Photo Filename', '')
        }
        pdf_ready_data.append(mapped_data)
    try:
        logger.info(f"Generating PDF for {len(pdf_ready_data)} SNE badges.")
        pdf_buffer = utils.generate_badge_pdf(pdf_ready_data, sne_layout_config)
        if pdf_buffer is None:
             raise Exception("PDF generation failed (returned None). Check logs.")
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"SNE_Badges_{timestamp}.pdf"
        logger.info(f"Sending generated SNE PDF: {filename}")
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error generating SNE PDF: {e}", exc_info=True)
        flash(f"Error generating PDF: {e}", "error")
        return redirect(url_for('sne.printer_page'))

@sne_bp.route('/edit')
@login_required
@permission_required('access_sne_edit')
def edit_page():
    """Displays the SNE edit form."""
    current_year = datetime.date.today().year
    return render_template('edit_form.html',
                           areas=config.AREAS,
                           states=config.STATES,
                           relations=config.RELATIONS,
                           current_year=current_year)

@sne_bp.route('/search', methods=['GET'])
@login_required
@permission_required('search_sne_entries')
def search_entries():
    """Searches SNE entries by name or badge ID."""
    search_name = request.args.get('name', '').strip().lower()
    search_badge_id = request.args.get('badge_id', '').strip().upper()

    if not search_name and not search_badge_id:
        return jsonify({"error": "Please provide a name or Badge ID to search."}), 400
    try:
        all_data = utils.get_all_sheet_data(
            config.SNE_SHEET_ID,
            config.SNE_SERVICE_ACCOUNT_FILE,
            config.SNE_SHEET_HEADERS
        )
        results = []
        if search_badge_id:
            for entry in all_data:
                if str(entry.get('Badge ID', '')).strip().upper() == search_badge_id:
                    results.append(entry)
                    break
        elif search_name:
            for entry in all_data:
                first = str(entry.get('First Name', '')).strip().lower()
                last = str(entry.get('Last Name', '')).strip().lower()
                if search_name in first or search_name in last or search_name in f"{first} {last}":
                    results.append(entry)
        limit = 50
        logger.info(f"Found {len(results)} SNE entries matching query. Returning up to {limit}.")
        return jsonify(results[:limit])
    except Exception as e:
        logger.error(f"Error searching SNE entries: {e}", exc_info=True)
        return jsonify({"error": f"Search failed due to server error: {e}"}), 500

@sne_bp.route('/update/<original_badge_id>', methods=['POST'])
@login_required
@permission_required('update_sne_entry')
def update_entry(original_badge_id):
    """Handles the submission of the edited SNE data."""
    if not original_badge_id:
        flash("Error: No SNE Badge ID provided for update.", "error")
        return redirect(url_for('sne.edit_page'))

    original_badge_id = original_badge_id.strip().upper()
    sheet = utils.get_sheet(config.SNE_SHEET_ID, config.SNE_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to SNE data storage.", "error")
        return redirect(url_for('sne.edit_page'))
    try:
        row_index = utils.find_row_index_by_value(sheet, 'Badge ID', original_badge_id, config.SNE_SHEET_HEADERS)
        if not row_index:
            flash(f"Error: SNE entry with Badge ID '{original_badge_id}' not found for update.", "error")
            return redirect(url_for('sne.edit_page'))

        form_data = request.form.to_dict()
        files = request.files
        try:
            original_record_list = sheet.row_values(row_index)
            while len(original_record_list) < len(config.SNE_SHEET_HEADERS):
                original_record_list.append('')
            original_record = dict(zip(config.SNE_SHEET_HEADERS, original_record_list))
            aadhaar_no = original_record.get('Aadhaar No', '').strip() # Aadhaar should not change
            old_s3_key = original_record.get('Photo Filename', '')
            logger.info(f"Fetched original record for SNE {original_badge_id}. Old photo key: {old_s3_key}, Aadhaar: {aadhaar_no}")
        except Exception as fetch_err:
            logger.error(f"Could not fetch original SNE record {original_badge_id}: {fetch_err}", exc_info=True)
            flash(f"Error fetching original SNE data.", "error")
            return redirect(url_for('sne.edit_page'))

        new_s3_key = old_s3_key
        delete_old_s3_object = False
        uploaded_new_key_for_rollback = None
        if 'photo' in files:
            photo_file = files['photo']
            if photo_file and photo_file.filename != '':
                # Use Aadhaar for unique part of filename if available, else name
                cleaned_aadhaar = utils.clean_aadhaar_number(aadhaar_no)
                unique_part = cleaned_aadhaar if cleaned_aadhaar else f"{form_data.get('first_name', 'user')}_{form_data.get('last_name', '')}"
                upload_result = utils.handle_photo_upload(
                    photo_file, config.S3_BUCKET_NAME, s3_prefix='sne_photos', unique_id_part=unique_part
                )
                if upload_result == "Upload Error": flash("New photo upload failed. Keeping old photo if available.", "error")
                elif upload_result == "N/A": flash(f"Invalid new photo file type. Allowed: {', '.join(config.ALLOWED_EXTENSIONS)}. No photo updated.", 'warning')
                else:
                    new_s3_key = upload_result
                    uploaded_new_key_for_rollback = new_s3_key
                    if old_s3_key and old_s3_key not in ["N/A", "Upload Error", ""] and old_s3_key != new_s3_key:
                        delete_old_s3_object = True
                        logger.info(f"Marking old SNE photo '{old_s3_key}' for deletion.")
        dob_str = form_data.get('dob', '')
        calculated_age = utils.calculate_age_from_dob(dob_str)
        updated_data_row = []
        for header in config.SNE_SHEET_HEADERS:
            form_key = header.lower().replace(' ', '_').replace("'", "").replace('/', '_').replace('(yes/no)', '').replace('(','').replace(')','').strip('_')
            if header == "Badge ID": value = original_badge_id
            elif header == "Aadhaar No": value = aadhaar_no # Keep original Aadhaar
            elif header == "Age": value = calculated_age if calculated_age is not None else ''
            elif header == "Photo Filename": value = new_s3_key
            elif header == "Submission Date": value = original_record.get('Submission Date', '') # Keep original
            elif header.endswith('(Yes/No)'):
                base_key = header.replace(' (Yes/No)', '').lower().replace(' ', '_').replace("'", "").replace('/', '_')
                value = form_data.get(base_key, 'No')
            else: value = form_data.get(form_key, original_record.get(header, '')) # Fallback to original if not in form
            updated_data_row.append(str(value))
        try:
            import gspread # Import gspread for utils.rowcol_to_a1
            end_column_letter = gspread.utils.rowcol_to_a1(1, len(config.SNE_SHEET_HEADERS)).split('1')[0]
            update_range = f'A{row_index}:{end_column_letter}{row_index}'
            sheet.update(update_range, [updated_data_row], value_input_option='USER_ENTERED')
            logger.info(f"Successfully updated SNE data in sheet for Badge ID: {original_badge_id}")
            if delete_old_s3_object:
                utils.delete_s3_object(config.S3_BUCKET_NAME, old_s3_key)
            flash(f'SNE Entry {original_badge_id} updated successfully!', 'success')
            return redirect(url_for('sne.edit_page'))
        except Exception as e:
            logger.error(f"Error updating SNE Sheet row {row_index} for {original_badge_id}: {e}", exc_info=True)
            flash(f'Error updating SNE Sheet: {e}.', 'error')
            if uploaded_new_key_for_rollback:
                utils.delete_s3_object(config.S3_BUCKET_NAME, uploaded_new_key_for_rollback)
            return redirect(url_for('sne.edit_page'))
    except Exception as e:
        logger.error(f"Unexpected error during SNE update for {original_badge_id}: {e}", exc_info=True)
        flash(f'An unexpected error occurred: {e}', 'error')
        return redirect(url_for('sne.edit_page'))
