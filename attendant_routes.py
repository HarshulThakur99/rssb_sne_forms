# attendant_routes.py (Refactored with RBAC and circular import fix)
import datetime
import re
import logging
from io import BytesIO

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify,
    send_file, current_app
)
from flask_login import login_required
# current_user is available globally via context_processor in app.py
from flask_login import current_user
import gspread # Keep for Cell object if needed

# Import shared utilities, configuration
import utils
import config
# Import the decorator from the new decorators.py file
from decorators import permission_required

# --- Blueprint Definition ---
attendant_bp = Blueprint('attendant', __name__, url_prefix='/attendant')
logger = logging.getLogger(__name__)

# --- Helper Functions Specific to Attendants (Copied from original) ---

def check_attendant_badge_id_exists(sheet, badge_id):
    """Checks if a specific Attendant Badge ID already exists in the sheet."""
    if not sheet:
        logger.error("Attendant sheet object is None in check_attendant_badge_id_exists.")
        return False # Indicate error

    badge_id_to_check = str(badge_id).strip().upper()
    if not badge_id_to_check:
        return None # No ID provided

    try:
        # Find the column index for "Badge ID" using config
        badge_id_col_index = config.ATTENDANT_SHEET_HEADERS.index('Badge ID') + 1
    except ValueError:
        logger.error("Header 'Badge ID' not found in ATTENDANT_SHEET_HEADERS config.")
        return False # Indicate configuration error

    try:
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

# --- Attendant Routes ---

@attendant_bp.route('/form')
@login_required
@permission_required('access_attendant_form')
def form_page():
    """Displays the form for adding a new SNE Sewadar Attendant."""
    today_date = datetime.date.today()
    current_year = today_date.year
    # Use AREAS from the main config
    return render_template('attendant_form.html',
                           today_date=today_date,
                           areas=config.AREAS,
                           # current_user is available globally
                           current_year=current_year)

@attendant_bp.route('/submit', methods=['POST'])
@login_required
@permission_required('submit_attendant_form')
def submit_form():
    """Handles the submission of the new attendant form."""
    form_data = request.form.to_dict()
    files = request.files

    # --- Basic Validation ---
    # Corrected field names for area and centre to match HTML form
    required_fields = ['badge_id', 'name', 'area_select', 'centre_select', 'phone_number', 'address', 'attendant_type']
    missing_fields = [field for field in required_fields if not form_data.get(field)]
    if missing_fields:
        # Adjust message if needed, though current message is generic enough
        flash(f"Missing required fields: {', '.join(missing_fields).replace('_select', '')}", "error")
        return redirect(url_for('attendant.form_page'))

    # Retrieve area and centre using the correct form names
    selected_area = form_data.get('area_select', '').strip()
    selected_centre = form_data.get('centre_select', '').strip()

    badge_id = form_data.get('badge_id').strip().upper() # This comes from the hidden 'badge_id_full' input
    phone_number = utils.clean_phone_number(form_data.get('phone_number', ''))
    attendant_type = form_data.get('attendant_type', 'Family').strip()
    sne_id = form_data.get('sne_id', '').strip().upper()


    if len(phone_number) != 10:
         flash("Phone number must be 10 digits.", "error")
         return redirect(url_for('attendant.form_page'))

    # --- Connect to Sheet and Check Existing ID ---
    sheet = utils.get_sheet(config.ATTENDANT_SHEET_ID, config.ATTENDANT_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to attendant data storage.", "error")
        return redirect(url_for('attendant.form_page'))

    id_exists = check_attendant_badge_id_exists(sheet, badge_id)
    if id_exists is True:
        flash(f"Error: Attendant Badge ID '{badge_id}' already exists.", "error")
        return redirect(url_for('attendant.form_page'))
    elif id_exists is False: # Indicates an error during check
        flash("Error verifying Badge ID uniqueness. Please try again.", "error")
        return redirect(url_for('attendant.form_page'))

    # --- Handle Photo Upload ---
    s3_object_key = utils.handle_photo_upload(
        files.get('photo'),
        config.S3_BUCKET_NAME,
        s3_prefix='attendants',
        unique_id_part=badge_id # Use the full badge_id from the hidden field
    )
    if s3_object_key == "Upload Error":
        flash("Photo upload failed. Please check logs.", "error")
        # Continue submission but mark photo as failed
        
    # --- Handle SNE Photo Upload ---
    sne_s3_object_key = "N/A"
    if attendant_type == 'Family' and 'sne_photo' in files and sne_id:
        sne_s3_object_key = utils.handle_photo_upload(
            files.get('sne_photo'),
            config.S3_BUCKET_NAME,
            s3_prefix='sne_members', # A different prefix for SNE photos
            unique_id_part=sne_id
        )
        if sne_s3_object_key == "Upload Error":
            flash("SNE Member photo upload failed. Please check logs.", "error")


    # --- Prepare Data Row for Google Sheet ---
    data_row = []
    for header in config.ATTENDANT_SHEET_HEADERS:
        # Map sheet headers to form data keys
        if header == "Badge ID": value = badge_id
        elif header == "Submission Date": value = form_data.get('submission_date', datetime.date.today().isoformat())
        elif header == "Area": value = selected_area # Use the retrieved selected_area
        elif header == "Centre": value = selected_centre # Use the retrieved selected_centre
        elif header == "Name": value = form_data.get('name', '')
        elif header == "Phone Number": value = phone_number
        elif header == "Address": value = form_data.get('address', '')
        elif header == "Attendant Type": value = attendant_type
        elif header == "Photo Filename": value = s3_object_key
        elif header == "SNE ID": value = sne_id
        elif header == "SNE Name": value = form_data.get('sne_name', '')
        elif header == "SNE Gender": value = form_data.get('sne_gender', '')
        elif header == "SNE Address": value = form_data.get('sne_address', '')
        elif header == "SNE Photo Filename": value = sne_s3_object_key
        else:
            # Fallback for any other headers, trying to match a form key
            form_key = header.lower().replace(' ', '_')
            value = form_data.get(form_key, '')
        data_row.append(str(value))

    # --- Append Row to Google Sheet ---
    try:
        sheet.append_row(data_row, value_input_option='USER_ENTERED')
        logger.info(f"Successfully added attendant data for Badge ID: {badge_id}")
        flash(f'Attendant data submitted successfully! Badge ID: {badge_id}', 'success')
        return redirect(url_for('attendant.form_page'))
    except Exception as e:
        logger.error(f"Error writing attendant data to Sheet for {badge_id}: {e}", exc_info=True)
        flash(f'Error submitting attendant data to Sheet: {e}.', 'error')
        if s3_object_key not in ["N/A", "Upload Error", ""]:
            utils.delete_s3_object(config.S3_BUCKET_NAME, s3_object_key)
        if sne_s3_object_key not in ["N/A", "Upload Error", ""]:
            utils.delete_s3_object(config.S3_BUCKET_NAME, sne_s3_object_key)
        return redirect(url_for('attendant.form_page'))


@attendant_bp.route('/edit')
@login_required
@permission_required('access_attendant_edit')
def edit_page():
    """Displays the page for searching and editing attendant entries."""
    current_year = datetime.date.today().year
    return render_template('attendant_edit_form.html',
                           areas=config.AREAS,
                           current_year=current_year)

@attendant_bp.route('/search', methods=['GET'])
@login_required
@permission_required('search_attendant_entries')
def search_entries():
    """Searches attendant sheet data by name or badge ID and returns JSON."""
    search_name = request.args.get('name', '').strip().lower()
    search_badge_id = request.args.get('badge_id', '').strip().upper()

    if not search_name and not search_badge_id:
        return jsonify({"error": "Please provide a name or Badge ID to search."}), 400

    try:
        all_data = utils.get_all_sheet_data(
            config.ATTENDANT_SHEET_ID,
            config.ATTENDANT_SERVICE_ACCOUNT_FILE,
            config.ATTENDANT_SHEET_HEADERS
        )
        results = []

        if search_badge_id:
            for entry in all_data:
                if str(entry.get('Badge ID', '')).strip().upper() == search_badge_id:
                    results.append(entry)
                    break
        elif search_name:
            for entry in all_data:
                full_name = str(entry.get('Name', '')).strip().lower()
                if search_name in full_name:
                    results.append(entry)

        limit = 50
        logger.info(f"Found {len(results)} attendant(s) matching query. Returning up to {limit}.")
        return jsonify(results[:limit])

    except Exception as e:
        logger.error(f"Error searching attendant entries: {e}", exc_info=True)
        return jsonify({"error": f"Search failed due to server error: {e}"}), 500


@attendant_bp.route('/update/<original_badge_id>', methods=['POST'])
@login_required
@permission_required('update_attendant_entry')
def update_entry(original_badge_id):
    """Handles the submission of the edited attendant data."""
    if not original_badge_id:
        flash("Error: No Attendant Badge ID provided for update.", "error")
        return redirect(url_for('attendant.edit_page'))

    original_badge_id = original_badge_id.strip().upper()
    sheet = utils.get_sheet(config.ATTENDANT_SHEET_ID, config.ATTENDANT_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to attendant data storage.", "error")
        return redirect(url_for('attendant.edit_page'))

    try:
        row_index = utils.find_row_index_by_value(sheet, 'Badge ID', original_badge_id, config.ATTENDANT_SHEET_HEADERS)
        if not row_index:
            flash(f"Error: Attendant entry with Badge ID '{original_badge_id}' not found.", "error")
            return redirect(url_for('attendant.edit_page'))

        form_data = request.form.to_dict()
        files = request.files
        
        selected_area = form_data.get('area', form_data.get('area_select', '')).strip()
        selected_centre = form_data.get('centre', form_data.get('centre_select', '')).strip()
        attendant_type = form_data.get('attendant_type', 'Family').strip()
        sne_id = form_data.get('sne_id', '').strip().upper()


        try:
            original_record_list = sheet.row_values(row_index)
            while len(original_record_list) < len(config.ATTENDANT_SHEET_HEADERS):
                original_record_list.append('')
            original_record = dict(zip(config.ATTENDANT_SHEET_HEADERS, original_record_list))
            old_s3_key = original_record.get('Photo Filename', '')
            old_sne_s3_key = original_record.get('SNE Photo Filename', '')
            logger.info(f"Fetched original record for attendant {original_badge_id}. Old photo key: {old_s3_key}")
        except Exception as fetch_err:
            logger.error(f"Could not fetch original attendant record {original_badge_id}: {fetch_err}", exc_info=True)
            flash(f"Error fetching original attendant data.", "error")
            return redirect(url_for('attendant.edit_page'))

        new_s3_key = old_s3_key
        delete_old_s3_object = False
        uploaded_new_key_for_rollback = None

        if 'photo' in files:
            photo_file = files['photo']
            if photo_file and photo_file.filename != '':
                upload_result = utils.handle_photo_upload(
                    photo_file,
                    config.S3_BUCKET_NAME,
                    s3_prefix='attendants',
                    unique_id_part=original_badge_id
                )
                if upload_result == "Upload Error":
                    flash("New photo upload failed. Keeping old photo if available.", "error")
                elif upload_result != "N/A":
                    new_s3_key = upload_result
                    uploaded_new_key_for_rollback = new_s3_key
                    if old_s3_key and old_s3_key not in ["N/A", "Upload Error", ""] and old_s3_key != new_s3_key:
                        delete_old_s3_object = True
                        logger.info(f"Marking old attendant photo '{old_s3_key}' for deletion.")

        new_sne_s3_key = old_sne_s3_key
        delete_old_sne_s3_object = False
        uploaded_new_sne_key_for_rollback = None

        if 'sne_photo' in files and sne_id:
            sne_photo_file = files['sne_photo']
            if sne_photo_file and sne_photo_file.filename != '':
                sne_upload_result = utils.handle_photo_upload(
                    sne_photo_file,
                    config.S3_BUCKET_NAME,
                    s3_prefix='sne_members',
                    unique_id_part=sne_id
                )
                if sne_upload_result == "Upload Error":
                    flash("New SNE photo upload failed. Keeping old photo if available.", "error")
                elif sne_upload_result != "N/A":
                    new_sne_s3_key = sne_upload_result
                    uploaded_new_sne_key_for_rollback = new_sne_s3_key
                    if old_sne_s3_key and old_sne_s3_key not in ["N/A", "Upload Error", ""] and old_sne_s3_key != new_sne_s3_key:
                        delete_old_sne_s3_object = True
                        logger.info(f"Marking old SNE photo '{old_sne_s3_key}' for deletion.")

        updated_data_row = []
        phone_number = utils.clean_phone_number(form_data.get('phone_number', ''))
        if len(phone_number) != 10: 
            flash("Phone number must be 10 digits.", "error")
            return redirect(url_for('attendant.edit_page', search_badge_id=original_badge_id))


        for header in config.ATTENDANT_SHEET_HEADERS:
            if header == "Badge ID": value = original_badge_id
            elif header == "Submission Date": value = original_record.get('Submission Date', '') 
            elif header == "Area": value = selected_area if selected_area else original_record.get('Area', '')
            elif header == "Centre": value = selected_centre if selected_centre else original_record.get('Centre', '')
            elif header == "Name": value = form_data.get('name', original_record.get('Name', ''))
            elif header == "Phone Number": value = phone_number
            elif header == "Address": value = form_data.get('address', original_record.get('Address', ''))
            elif header == "Attendant Type": value = attendant_type
            elif header == "Photo Filename": value = new_s3_key
            elif header == "SNE ID": value = sne_id
            elif header == "SNE Name": value = form_data.get('sne_name', original_record.get('SNE Name', ''))
            elif header == "SNE Gender": value = form_data.get('sne_gender', original_record.get('SNE Gender', ''))
            elif header == "SNE Address": value = form_data.get('sne_address', original_record.get('SNE Address', ''))
            elif header == "SNE Photo Filename": value = new_sne_s3_key
            else:
                form_key = header.lower().replace(' ', '_')
                value = form_data.get(form_key, original_record.get(header, ''))
            updated_data_row.append(str(value))

        try:
            end_column_letter = gspread.utils.rowcol_to_a1(1, len(config.ATTENDANT_SHEET_HEADERS)).split('1')[0]
            update_range = f'A{row_index}:{end_column_letter}{row_index}'
            sheet.update(update_range, [updated_data_row], value_input_option='USER_ENTERED')
            logger.info(f"Successfully updated attendant data in sheet for Badge ID: {original_badge_id}")

            if delete_old_s3_object:
                utils.delete_s3_object(config.S3_BUCKET_NAME, old_s3_key)
            if delete_old_sne_s3_object:
                utils.delete_s3_object(config.S3_BUCKET_NAME, old_sne_s3_key)


            flash(f'Attendant Entry {original_badge_id} updated successfully!', 'success')
            return redirect(url_for('attendant.edit_page'))

        except Exception as e:
            logger.error(f"Error updating attendant Sheet row {row_index} for {original_badge_id}: {e}", exc_info=True)
            flash(f'Error updating Sheet: {e}.', 'error')
            if uploaded_new_key_for_rollback: 
                utils.delete_s3_object(config.S3_BUCKET_NAME, uploaded_new_key_for_rollback)
            if uploaded_new_sne_key_for_rollback:
                utils.delete_s3_object(config.S3_BUCKET_NAME, uploaded_new_sne_key_for_rollback)
            return redirect(url_for('attendant.edit_page'))

    except Exception as e:
        logger.error(f"Unexpected error during attendant update for {original_badge_id}: {e}", exc_info=True)
        flash(f'An unexpected error occurred: {e}', 'error')
        return redirect(url_for('attendant.edit_page'))


@attendant_bp.route('/printer')
@login_required
@permission_required('access_attendant_printer')
def printer_page():
    """Displays the form to enter attendant Badge IDs for printing."""
    current_year = datetime.date.today().year
    return render_template('attendant_printer_form.html',
                           current_year=current_year)

@attendant_bp.route('/generate_pdf', methods=['POST'])
@login_required
@permission_required('generate_attendant_pdf')
def generate_pdf():
    """Generates a PDF of badges for the specified attendant Badge IDs."""
    badge_ids_raw = request.form.get('badge_ids', '')
    badge_ids_to_print = [bid.strip().upper() for bid in badge_ids_raw.split(',') if bid.strip()]

    if not badge_ids_to_print:
        flash("Please enter at least one Attendant Badge ID.", "error")
        return redirect(url_for('attendant.printer_page'))

    logger.info(f"Request to generate PDF for Attendant Badge IDs: {badge_ids_to_print}")

    try:
        all_attendant_data = utils.get_all_sheet_data(
            config.ATTENDANT_SHEET_ID,
            config.ATTENDANT_SERVICE_ACCOUNT_FILE,
            config.ATTENDANT_SHEET_HEADERS
        )
        data_map = {str(row.get('Badge ID', '')).strip().upper(): row
                    for row in all_attendant_data if row.get('Badge ID')}
    except Exception as e:
        logger.error(f"Error fetching attendant data for PDF generation: {e}", exc_info=True)
        flash(f"Error fetching attendant data: {e}", "error")
        return redirect(url_for('attendant.printer_page'))

    badges_data_for_pdf = []
    not_found_ids = []
    for bid in badge_ids_to_print:
        if bid in data_map:
            badges_data_for_pdf.append(data_map[bid])
        else:
            not_found_ids.append(bid)
            logger.warning(f"Attendant Badge ID '{bid}' requested for PDF not found.")

    if not badges_data_for_pdf:
        flash("No valid Attendant Badge IDs found in the provided list.", "error")
        return redirect(url_for('attendant.printer_page'))
    if not_found_ids:
        flash(f"Warning: The following Attendant IDs were not found: {', '.join(not_found_ids)}", "warning")

    attendant_layout_config = {
        "templates_by_type": { 
            "sewadar": config.ATTENDANT_BADGE_SEWADAR_TEMPLATE_PATH,
            "family": config.ATTENDANT_BADGE_FAMILY_TEMPLATE_PATH,
            "default": config.ATTENDANT_BADGE_FAMILY_TEMPLATE_PATH 
        },
        "text_elements": config.ATTENDANT_TEXT_ELEMENTS,
        "photo_config": {
            'paste_x': config.ATTENDANT_PHOTO_PASTE_X_PX,
            'paste_y': config.ATTENDANT_PHOTO_PASTE_Y_PX,
            'box_w': config.ATTENDANT_PHOTO_BOX_WIDTH_PX,
            'box_h': config.ATTENDANT_PHOTO_BOX_HEIGHT_PX,
            's3_key_field': 'Photo Filename'
        },
        "sne_photo_config": {
            'paste_x': config.ATTENDANT_SNE_PHOTO_PASTE_X_PX,
            'paste_y': config.ATTENDANT_SNE_PHOTO_PASTE_Y_PX,
            'box_w': config.ATTENDANT_SNE_PHOTO_BOX_WIDTH_PX,
            'box_h': config.ATTENDANT_SNE_PHOTO_BOX_HEIGHT_PX,
            's3_key_field': 'SNE Photo Filename'
        },
        "pdf_layout": {
            'orientation': 'L', 'unit': 'mm', 'format': 'A4',
            'badge_w_mm': 135, 'badge_h_mm': 100, 'margin_mm': 3, 'gap_mm': 0
        },
        "font_path": config.FONT_PATH,
        "font_bold_path": config.FONT_BOLD_PATH,
        "s3_bucket": config.S3_BUCKET_NAME,
        "wrap_config": {'field_key': 'address', 'width': 20, 'spacing': 4}
    }

    pdf_ready_data = []
    for row_data in badges_data_for_pdf:
        mapped_data = {
            "badge_id": row_data.get('Badge ID', 'N/A'),
            "name": row_data.get('Name', ''),
            "phone": f"Ph: {row_data.get('Phone Number', '')}", 
            "centre": row_data.get('Centre', ''),
            "area": row_data.get('Area', ''),
            "address": row_data.get('Address', ''),
            "attendant_type": row_data.get('Attendant Type', 'family').strip().lower(), 
            "Photo Filename": row_data.get('Photo Filename', ''),
            "SNE Photo Filename": row_data.get('SNE Photo Filename', '')
        }
        
        if mapped_data["attendant_type"] == "family":
            sne_name = row_data.get('SNE Name', '').strip()
            sne_id = row_data.get('SNE ID', '').strip()
            sne_gender = row_data.get('SNE Gender', '').strip()

            if sne_name:
                mapped_data["sne_details_line1"] = f"{sne_name}"
            
            details_line2_parts = []
            if sne_id:
                details_line2_parts.append(sne_id)
            if sne_gender:
                details_line2_parts.append(sne_gender)
            
            if details_line2_parts:
                mapped_data["sne_details_line2"] = " / ".join(details_line2_parts)

        pdf_ready_data.append(mapped_data)

    try:
        logger.info(f"Generating PDF for {len(pdf_ready_data)} attendant badges.")
        pdf_buffer = utils.generate_badge_pdf(pdf_ready_data, attendant_layout_config)

        if pdf_buffer is None:
             raise Exception("Attendant PDF generation failed (returned None). Check logs.")

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Attendant_Badges_{timestamp}.pdf"

        logger.info(f"Sending generated Attendant PDF: {filename}")
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error generating attendant PDF: {e}", exc_info=True)
        flash(f"Error generating PDF: {e}", "error")
        return redirect(url_for('attendant.printer_page'))
