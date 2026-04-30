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
from app import db_helpers
from app.models import db
# Import the decorator from the new decorators.py file
from app.decorators import permission_required

# --- Blueprint Definition ---
sne_bp = Blueprint('sne', __name__, url_prefix='/sne')
logger = logging.getLogger(__name__)

# --- Helper Functions Specific to SNE (Copied from original, ensure they are robust) ---
def check_sne_aadhaar_exists(sheet, aadhaar, area, exclude_badge_id=None):
    """Checks if SNE Aadhaar exists for the given Area (PostgreSQL version)."""
    # PostgreSQL version - sheet parameter ignored
    cleaned_aadhaar = utils.clean_aadhaar_number(aadhaar)
    if not cleaned_aadhaar:
        return None
    
    return db_helpers.check_sne_aadhaar_exists_postgres(cleaned_aadhaar, area, exclude_badge_id)

def get_next_sne_badge_id(sheet, area, centre):
    """Generates the next sequential SNE Badge ID (PostgreSQL version)."""
    # PostgreSQL version - sheet parameter ignored
    if area not in config.SNE_BADGE_CONFIG or centre not in config.SNE_BADGE_CONFIG[area]:
        raise ValueError("Invalid Area or Centre for SNE Badge ID generation.")

    centre_config = config.SNE_BADGE_CONFIG[area][centre]
    prefix = centre_config["prefix"]
    start_num = centre_config["start"]
    
    return db_helpers.get_next_sne_badge_id_postgres(area, centre, prefix, start_num)

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
    """Handles the submission of the new SNE form (PostgreSQL version)."""
    # PostgreSQL version - no sheet connection needed
    sheet = None  # Keep for compatibility with helper functions

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

        # Try to generate badge ID and insert with retry logic (max 3 attempts)
        max_retries = 3
        retry_count = 0
        new_badge_id = None
        
        while retry_count < max_retries:
            try:
                new_badge_id = get_next_sne_badge_id(sheet, selected_area, selected_centre)
                break
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"Failed to generate badge ID after {max_retries} attempts: {e}")
                    flash(f"Error generating SNE Badge ID: {e}", "error")
                    if s3_object_key not in ["N/A", "Upload Error", ""]: # Check if a file was actually uploaded
                        utils.delete_s3_object(config.S3_BUCKET_NAME, s3_object_key)
                    return redirect(url_for('sne.form_page'))
                logger.warning(f"Badge ID generation attempt {retry_count} failed, retrying...")

        calculated_age = utils.calculate_age_from_dob(dob_str)
        # Save to PostgreSQL
        try:
            submission_date_str = form_data.get('submission_date', datetime.date.today().isoformat())
            submission_date = datetime.datetime.strptime(submission_date_str, '%Y-%m-%d').date() if isinstance(submission_date_str, str) else submission_date_str
            
            dob = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
            
            sne_data = {
                'father_husband_name': form_data.get('father_husband_name', ''),
                'gender': form_data.get('gender', ''),
                'date_of_birth': dob,
                'age': calculated_age,
                'blood_group': form_data.get('blood_group', ''),
                'aadhaar_no': utils.clean_aadhaar_number(aadhaar_no),
                'mobile_no': form_data.get('mobile_no', ''),
                'physically_challenged': form_data.get('physically_challenged', 'No'),
                'physically_challenged_details': form_data.get('physically_challenged_details', ''),
                'help_required_home_pickup': form_data.get('help_required_home_pickup', 'No'),
                'help_pickup_reasons': form_data.get('help_pickup_reasons', ''),
                'handicap': form_data.get('handicap', 'No'),
                'stretcher_required': form_data.get('stretcher_required', 'No'),
                'wheelchair_required': form_data.get('wheelchair_required', 'No'),
                'ambulance_required': form_data.get('ambulance_required', 'No'),
                'pacemaker_operated': form_data.get('pacemaker_operated', 'No'),
                'chair_required_sitting': form_data.get('chair_required_sitting', 'No'),
                'special_attendant_required': form_data.get('special_attendant_required', 'No'),
                'hearing_loss': form_data.get('hearing_loss', 'No'),
                'willing_attend_satsangs': form_data.get('willing_attend_satsangs', 'No'),
                'satsang_pickup_help_details': form_data.get('satsang_pickup_help_details', ''),
                'other_special_requests': form_data.get('other_special_requests', ''),
                'emergency_contact_name': form_data.get('emergency_contact_name', ''),
                'emergency_contact_number': form_data.get('emergency_contact_number', ''),
                'emergency_contact_relation': form_data.get('emergency_contact_relation', ''),
                'address': form_data.get('address', ''),
                'state': form_data.get('state', ''),
                'pin_code': form_data.get('pin_code', ''),
                'photo_filename': s3_object_key
            }
            
            # Attempt to insert with retry logic for duplicate badge_id
            max_insert_retries = 3
            insert_retry_count = 0
            
            while insert_retry_count < max_insert_retries:
                sne_form, success, error_msg = db_helpers.create_sne_form(
                    badge_id=new_badge_id,
                    submission_date=submission_date,
                    area=selected_area,
                    satsang_place=selected_centre,
                    first_name=form_data.get('first_name', ''),
                    last_name=form_data.get('last_name', ''),
                    **sne_data
                )
                
                if success:
                    logger.info(f"Successfully added SNE data to PostgreSQL for Badge ID: {new_badge_id}")
                    flash(f'SNE Data submitted successfully! Badge ID: {new_badge_id}', 'success')
                    return redirect(url_for('sne.form_page'))
                elif error_msg == "DUPLICATE_BADGE_ID":
                    # Race condition detected - generate new badge ID and retry
                    insert_retry_count += 1
                    if insert_retry_count >= max_insert_retries:
                        raise Exception(f"Failed to insert after {max_insert_retries} attempts due to duplicate badge IDs. Please try again.")
                    
                    logger.warning(f"Duplicate badge_id {new_badge_id} detected (attempt {insert_retry_count}), generating new ID...")
                    try:
                        new_badge_id = get_next_sne_badge_id(sheet, selected_area, selected_centre)
                    except Exception as badge_e:
                        raise Exception(f"Failed to generate new badge ID after duplicate: {badge_e}")
                else:
                    # Other error - don't retry
                    raise Exception(f"Database insert failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error writing SNE data to PostgreSQL for {new_badge_id}: {e}", exc_info=True)
            flash(f'Error submitting SNE data: {e}.', 'error')
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
        # Fetch from PostgreSQL
        from app.models import SNEForm
        sne_forms = SNEForm.query.filter(SNEForm.badge_id.in_(badge_ids_to_print)).all()
        
        data_map = {}
        for sne in sne_forms:
            data_map[sne.badge_id] = {
                'Badge ID': sne.badge_id,
                'First Name': sne.first_name or '',
                'Last Name': sne.last_name or '',
                'Gender': sne.gender or '',
                'Age': str(sne.age) if sne.age else '',
                'Satsang Place': sne.satsang_place or '',
                'Area': sne.area or '',
                'Address': sne.address or '',
                'Photo Filename': sne.photo_filename or '',
                'Date of Birth': sne.date_of_birth.isoformat() if sne.date_of_birth else ''
            }
    except Exception as e:
        logger.error(f"Error fetching SNE data from PostgreSQL for PDF generation: {e}", exc_info=True)
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
    """Searches SNE entries by name or badge ID (PostgreSQL version)."""
    search_name = request.args.get('name', '').strip().lower()
    search_badge_id = request.args.get('badge_id', '').strip().upper()

    if not search_name and not search_badge_id:
        return jsonify({"error": "Please provide a name or Badge ID to search."}), 400
    
    try:
        # Search in PostgreSQL
        results = db_helpers.search_sne_forms(search_name, search_badge_id)
        logger.info(f"Found {len(results)} SNE entries in PostgreSQL matching query")
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error searching SNE entries in PostgreSQL: {e}", exc_info=True)
        return jsonify({"error": f"Search failed due to server error: {e}"}), 500

@sne_bp.route('/update/<original_badge_id>', methods=['POST'])
@login_required
@permission_required('update_sne_entry')
def update_entry(original_badge_id):
    """Handles the submission of the edited SNE data (PostgreSQL version)."""
    if not original_badge_id:
        flash("Error: No SNE Badge ID provided for update.", "error")
        return redirect(url_for('sne.edit_page'))

    original_badge_id = original_badge_id.strip().upper()
    
    try:
        # Fetch existing record from PostgreSQL
        sne_record = db_helpers.get_sne_by_badge_id(original_badge_id)
        if not sne_record:
            flash(f"Error: SNE entry with Badge ID '{original_badge_id}' not found for update.", "error")
            return redirect(url_for('sne.edit_page'))

        form_data = request.form.to_dict()
        files = request.files
        
        # Get original data
        aadhaar_no = sne_record.aadhaar_no  # Aadhaar should not change
        old_s3_key = sne_record.photo_filename or ''
        logger.info(f"Fetched original record for SNE {original_badge_id}. Old photo key: {old_s3_key}, Aadhaar: {aadhaar_no}")

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
        
        # Update PostgreSQL
        try:
            dob = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
            
            update_data = {
                'area': form_data.get('area'),
                'satsang_place': form_data.get('satsang_place'),
                'first_name': form_data.get('first_name'),
                'last_name': form_data.get('last_name'),
                'father_husband_name': form_data.get('father_husband_name'),
                'gender': form_data.get('gender'),
                'date_of_birth': dob,
                'age': calculated_age,
                'blood_group': form_data.get('blood_group'),
                'mobile_no': form_data.get('mobile_no'),
                'physically_challenged': form_data.get('physically_challenged', 'No'),
                'physically_challenged_details': form_data.get('physically_challenged_details'),
                'help_required_home_pickup': form_data.get('help_required_home_pickup', 'No'),
                'help_pickup_reasons': form_data.get('help_pickup_reasons'),
                'handicap': form_data.get('handicap', 'No'),
                'stretcher_required': form_data.get('stretcher_required', 'No'),
                'wheelchair_required': form_data.get('wheelchair_required', 'No'),
                'ambulance_required': form_data.get('ambulance_required', 'No'),
                'pacemaker_operated': form_data.get('pacemaker_operated', 'No'),
                'chair_required_sitting': form_data.get('chair_required_sitting', 'No'),
                'special_attendant_required': form_data.get('special_attendant_required', 'No'),
                'hearing_loss': form_data.get('hearing_loss', 'No'),
                'willing_attend_satsangs': form_data.get('willing_attend_satsangs', 'No'),
                'satsang_pickup_help_details': form_data.get('satsang_pickup_help_details'),
                'other_special_requests': form_data.get('other_special_requests'),
                'emergency_contact_name': form_data.get('emergency_contact_name'),
                'emergency_contact_number': form_data.get('emergency_contact_number'),
                'emergency_contact_relation': form_data.get('emergency_contact_relation'),
                'address': form_data.get('address'),
                'state': form_data.get('state'),
                'pin_code': form_data.get('pin_code'),
                'photo_filename': new_s3_key
            }
            
            success = db_helpers.update_sne_form(original_badge_id, **update_data)
            
            if success:
                logger.info(f"Successfully updated SNE data in PostgreSQL for Badge ID: {original_badge_id}")
                if delete_old_s3_object:
                    utils.delete_s3_object(config.S3_BUCKET_NAME, old_s3_key)
                flash(f'SNE Entry {original_badge_id} updated successfully!', 'success')
                return redirect(url_for('sne.edit_page'))
            else:
                raise Exception("Database update failed")
                
        except Exception as e:
            logger.error(f"Error updating SNE data in PostgreSQL for {original_badge_id}: {e}", exc_info=True)
            flash(f'Error updating SNE data: {e}.', 'error')
            if uploaded_new_key_for_rollback:
                utils.delete_s3_object(config.S3_BUCKET_NAME, uploaded_new_key_for_rollback)
            return redirect(url_for('sne.edit_page'))
    except Exception as e:
        logger.error(f"Unexpected error during SNE update for {original_badge_id}: {e}", exc_info=True)
        flash(f'An unexpected error occurred: {e}', 'error')
        return redirect(url_for('sne.edit_page'))
