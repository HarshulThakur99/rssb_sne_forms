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

# Import shared utilities and configuration
from app import utils
from app import config
from app import db_helpers
from app.models import db, Attendant
# Import the decorator from the new decorators.py file
from app.decorators import permission_required

# --- Blueprint Definition ---
attendant_bp = Blueprint('attendant', __name__, url_prefix='/attendant')
logger = logging.getLogger(__name__)

# --- Helper Functions Specific to Attendants (Copied from original) ---

def check_attendant_badge_id_exists(sheet, badge_id):
    """Checks if a specific Attendant Badge ID already exists. PostgreSQL version.
    Sheet parameter is ignored - kept for compatibility."""
    badge_id_to_check = str(badge_id).strip().upper()
    if not badge_id_to_check:
        return None  # No ID provided

    try:
        # Check PostgreSQL database
        exists = db_helpers.check_attendant_badge_id_exists_postgres(badge_id_to_check)
        if exists:
            logger.warning(f"Attendant Badge ID '{badge_id_to_check}' already exists.")
            return True  # ID Found
        return None  # ID Not Found
    except Exception as e:
        logger.error(f"Error checking attendant Badge ID '{badge_id_to_check}': {e}", exc_info=True)
        return False  # Indicate general error

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

    badge_id = form_data.get('badge_id').strip().upper()
    phone_number = utils.clean_phone_number(form_data.get('phone_number', ''))
    attendant_type = form_data.get('attendant_type', 'Family').strip()
    sne_id = form_data.get('sne_id', '').strip().upper()

    if len(phone_number) != 10:
         flash("Phone number must be 10 digits.", "error")
         return redirect(url_for('attendant.form_page'))

    # --- Check Existing ID (PostgreSQL version) ---
    id_exists = check_attendant_badge_id_exists(None, badge_id)
    if id_exists is True:
        flash(f"Error: Attendant Badge ID '{badge_id}' already exists.", "error")
        return redirect(url_for('attendant.form_page'))
    elif id_exists is False:  # Indicates an error during check
        flash("Error verifying Badge ID uniqueness. Please try again.", "error")
        return redirect(url_for('attendant.form_page'))

    # --- Handle Photo Upload ---
    s3_object_key = utils.handle_photo_upload(
        files.get('photo'),
        config.S3_BUCKET_NAME,
        s3_prefix='attendants',
        unique_id_part=badge_id
    )
    if s3_object_key == "Upload Error":
        flash("Photo upload failed. Please check logs.", "error")
        
    # --- Handle SNE Photo Upload ---
    sne_s3_object_key = "N/A"
    if attendant_type == 'Family' and 'sne_photo' in files and sne_id:
        sne_s3_object_key = utils.handle_photo_upload(
            files.get('sne_photo'),
            config.S3_BUCKET_NAME,
            s3_prefix='sne_members',
            unique_id_part=sne_id
        )
        if sne_s3_object_key == "Upload Error":
            flash("SNE Member photo upload failed. Please check logs.", "error")

    # --- Create Attendant Record in PostgreSQL ---
    try:
        # Parse submission date
        submission_date_str = form_data.get('submission_date', datetime.date.today().isoformat())
        try:
            from dateutil import parser as date_parser
            submission_date_obj = date_parser.parse(submission_date_str).date()
        except:
            submission_date_obj = datetime.date.today()
        
        # Create attendant record
        attendant_dict = {
            'submission_date': submission_date_obj,
            'area': selected_area,
            'centre': selected_centre,
            'name': form_data.get('name', ''),
            'phone_number': phone_number,
            'address': form_data.get('address', ''),
            'attendant_type': attendant_type,
            'photo_filename': s3_object_key,
            'sne_id': sne_id if sne_id else None,
            'sne_name': form_data.get('sne_name', ''),
            'sne_gender': form_data.get('sne_gender', ''),
            'sne_address': form_data.get('sne_address', ''),
            'sne_photo_filename': sne_s3_object_key
        }
        
        attendant, success = db_helpers.create_attendant(badge_id, **attendant_dict)
        if success:
            logger.info(f"Successfully added attendant data for Badge ID: {badge_id}")
            flash(f'Attendant data submitted successfully! Badge ID: {badge_id}', 'success')
            return redirect(url_for('attendant.form_page'))
        else:
            flash('Error submitting attendant data. Please try again.', 'error')
            # Clean up uploaded photos
            if s3_object_key not in ["N/A", "Upload Error", ""]:
                utils.delete_s3_object(config.S3_BUCKET_NAME, s3_object_key)
            if sne_s3_object_key not in ["N/A", "Upload Error", ""]:
                utils.delete_s3_object(config.S3_BUCKET_NAME, sne_s3_object_key)
            return redirect(url_for('attendant.form_page'))
    except Exception as e:
        logger.error(f"Error writing attendant data for {badge_id}: {e}", exc_info=True)
        flash(f'Error submitting attendant data: {e}.', 'error')
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
    """Searches attendant data by name or badge ID and returns JSON. PostgreSQL version."""
    search_name = request.args.get('name', '').strip().lower()
    search_badge_id = request.args.get('badge_id', '').strip().upper()

    if not search_name and not search_badge_id:
        return jsonify({"error": "Please provide a name or Badge ID to search."}), 400

    try:
        results = []
        
        if search_badge_id:
            attendant = db_helpers.get_attendant_by_badge_id(search_badge_id)
            if attendant:
                results.append({
                    'Badge ID': attendant.badge_id,
                    'Submission Date': attendant.submission_date.isoformat() if attendant.submission_date else '',
                    'Area': attendant.area,
                    'Centre': attendant.centre,
                    'Name': attendant.name,
                    'Phone Number': attendant.phone_number,
                    'Address': attendant.address or '',
                    'Attendant Type': attendant.attendant_type,
                    'Photo Filename': attendant.photo_filename or '',
                    'SNE ID': attendant.sne_id or '',
                    'SNE Name': attendant.sne_name or '',
                    'SNE Gender': attendant.sne_gender or '',
                    'SNE Address': attendant.sne_address or '',
                    'SNE Photo Filename': attendant.sne_photo_filename or ''
                })
        elif search_name:
            attendants = Attendant.query.filter(Attendant.name.ilike(f'%{search_name}%')).limit(50).all()
            for attendant in attendants:
                results.append({
                    'Badge ID': attendant.badge_id,
                    'Submission Date': attendant.submission_date.isoformat() if attendant.submission_date else '',
                    'Area': attendant.area,
                    'Centre': attendant.centre,
                    'Name': attendant.name,
                    'Phone Number': attendant.phone_number,
                    'Address': attendant.address or '',
                    'Attendant Type': attendant.attendant_type,
                    'Photo Filename': attendant.photo_filename or '',
                    'SNE ID': attendant.sne_id or '',
                    'SNE Name': attendant.sne_name or '',
                    'SNE Gender': attendant.sne_gender or '',
                    'SNE Address': attendant.sne_address or '',
                    'SNE Photo Filename': attendant.sne_photo_filename or ''
                })

        logger.info(f"Found {len(results)} attendant(s) matching query.")
        return jsonify(results[:50])

    except Exception as e:
        logger.error(f"Error searching attendant entries: {e}", exc_info=True)
        return jsonify({"error": f"Search failed due to server error: {e}"}), 500


@attendant_bp.route('/update/<original_badge_id>', methods=['POST'])
@login_required
@permission_required('update_attendant_entry')
def update_entry(original_badge_id):
    """Handles the submission of the edited attendant data. PostgreSQL version."""
    if not original_badge_id:
        flash("Error: No Attendant Badge ID provided for update.", "error")
        return redirect(url_for('attendant.edit_page'))

    original_badge_id = original_badge_id.strip().upper()

    try:
        # Fetch original attendant from PostgreSQL
        attendant = db_helpers.get_attendant_by_badge_id(original_badge_id)
        if not attendant:
            flash(f"Error: Attendant entry with Badge ID '{original_badge_id}' not found.", "error")
            return redirect(url_for('attendant.edit_page'))

        form_data = request.form.to_dict()
        files = request.files
        
        selected_area = form_data.get('area', form_data.get('area_select', '')).strip()
        selected_centre = form_data.get('centre', form_data.get('centre_select', '')).strip()
        attendant_type = form_data.get('attendant_type', 'Family').strip()
        sne_id = form_data.get('sne_id', '').strip().upper()

        # Get original photo keys
        old_s3_key = attendant.photo_filename or ''
        old_sne_s3_key = attendant.sne_photo_filename or ''
        logger.info(f"Fetched original record for attendant {original_badge_id}. Old photo key: {old_s3_key}")

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

        # Validate phone number
        phone_number = utils.clean_phone_number(form_data.get('phone_number', ''))
        if len(phone_number) != 10: 
            flash("Phone number must be 10 digits.", "error")
            return redirect(url_for('attendant.edit_page', search_badge_id=original_badge_id))

        # Prepare update data
        update_dict = {
            'area': selected_area if selected_area else attendant.area,
            'centre': selected_centre if selected_centre else attendant.centre,
            'name': form_data.get('name', attendant.name),
            'phone_number': phone_number,
            'address': form_data.get('address', attendant.address or ''),
            'attendant_type': attendant_type,
            'photo_filename': new_s3_key,
            'sne_id': sne_id if sne_id else None,
            'sne_name': form_data.get('sne_name', attendant.sne_name or ''),
            'sne_gender': form_data.get('sne_gender', attendant.sne_gender or ''),
            'sne_address': form_data.get('sne_address', attendant.sne_address or ''),
            'sne_photo_filename': new_sne_s3_key
        }

        try:
            # Update attendant in PostgreSQL
            success = db_helpers.update_attendant(original_badge_id, **update_dict)
            
            if success:
                logger.info(f"Successfully updated attendant data for Badge ID: {original_badge_id}")

                # Clean up old photos
                if delete_old_s3_object:
                    utils.delete_s3_object(config.S3_BUCKET_NAME, old_s3_key)
                if delete_old_sne_s3_object:
                    utils.delete_s3_object(config.S3_BUCKET_NAME, old_sne_s3_key)

                flash(f'Attendant Entry {original_badge_id} updated successfully!', 'success')
                return redirect(url_for('attendant.edit_page'))
            else:
                flash('Error updating attendant data. Please try again.', 'error')
                if uploaded_new_key_for_rollback: 
                    utils.delete_s3_object(config.S3_BUCKET_NAME, uploaded_new_key_for_rollback)
                if uploaded_new_sne_key_for_rollback:
                    utils.delete_s3_object(config.S3_BUCKET_NAME, uploaded_new_sne_key_for_rollback)
                return redirect(url_for('attendant.edit_page'))

        except Exception as e:
            logger.error(f"Error updating attendant {original_badge_id}: {e}", exc_info=True)
            flash(f'Error updating attendant: {e}.', 'error')
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
        # Fetch attendants from PostgreSQL
        all_attendants = db_helpers.get_all_attendants()
        
        # Convert to dict format for compatibility
        data_map = {}
        for att in all_attendants:
            data_map[att.badge_id] = {
                'Badge ID': att.badge_id,
                'Submission Date': att.submission_date.isoformat() if att.submission_date else '',
                'Area': att.area,
                'Centre': att.centre,
                'Name': att.name,
                'Phone Number': att.phone_number,
                'Address': att.address or '',
                'Attendant Type': att.attendant_type,
                'Photo Filename': att.photo_filename or '',
                'SNE ID': att.sne_id or '',
                'SNE Name': att.sne_name or '',
                'SNE Gender': att.sne_gender or '',
                'SNE Address': att.sne_address or '',
                'SNE Photo Filename': att.sne_photo_filename or ''
            }
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
            'badge_w_mm': 120, 'badge_h_mm': 80, 'margin_mm': 3, 'gap_mm': 0
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
