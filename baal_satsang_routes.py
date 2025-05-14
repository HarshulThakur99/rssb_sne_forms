# baal_satsang_routes.py (Updated for circular import fix and RBAC)
import datetime
import re
import logging
from io import BytesIO

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    send_file, current_app
)
from flask_login import login_required
# current_user is available globally via context_processor in app.py
from flask_login import current_user

# Import shared utilities and configuration
import utils
import config
# Import the decorator from the new decorators.py file
from decorators import permission_required

# --- Blueprint Definition ---
baal_satsang_bp = Blueprint('baal_satsang', __name__, url_prefix='/baal_satsang')
logger = logging.getLogger(__name__)

# --- Helper function to parse token IDs (range or CSV) ---
def parse_token_ids(id_string):
    """
    Parses a string that can be a range (e.g., "001-010") or comma-separated
    values (e.g., "001, 005, 008").
    Returns a list of formatted token IDs (e.g., ["001", "002", ...]).
    Returns None if input is invalid or results in an empty list.
    """
    ids = []
    id_string = id_string.strip()

    range_match = re.fullmatch(r'(\d+)\s*-\s*(\d+)', id_string)
    if range_match:
        try:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start > end:
                logger.warning(f"Invalid range: start ({start}) > end ({end})")
                return None

            # Determine padding length based on the 'end' number, minimum 3, max 6
            padding_len = max(3, len(str(end)))
            padding_len = min(padding_len, 6) # Cap padding at 6

            for i in range(start, end + 1):
                ids.append(str(i).zfill(padding_len))
            logger.info(f"Parsed ID range: {start}-{end} into {len(ids)} IDs with padding {padding_len}.")
        except ValueError:
            logger.error(f"Invalid number in range: {id_string}")
            return None
    else:
        # Handle comma-separated values
        raw_ids = id_string.split(',')
        for raw_id in raw_ids:
            cleaned_id = raw_id.strip()
            if cleaned_id.isdigit():
                # Determine padding based on the length of the individual ID, min 3, max 6
                padding_len = max(3, len(cleaned_id))
                padding_len = min(padding_len, 6) # Cap padding
                ids.append(cleaned_id.zfill(padding_len))
            elif cleaned_id: # If it's not empty and not a digit, it's invalid
                logger.warning(f"Invalid non-numeric ID found in CSV list: '{cleaned_id}'")
                # Optionally, you could decide to return None here to invalidate the whole list
                # For now, we'll just skip the invalid ID.
                continue # Skip this invalid ID and process others
        logger.info(f"Parsed CSV IDs: {id_string} into {len(ids)} IDs.")

    if not ids: # If after parsing, the list is empty (e.g., all were invalid or input was empty)
        return None
    return ids

# --- Baal Satsang Token Routes ---

@baal_satsang_bp.route('/printer')
@login_required
@permission_required('access_baal_satsang_printer')
def printer_page():
    """Displays the form to enter Baal Satsang Token IDs for printing."""
    current_year = datetime.date.today().year
    return render_template('baal_satsang_printer_form.html',
                           areas=config.AREAS,
                           token_types=config.BAAL_SATSANG_TOKEN_TYPES,
                           # current_user is available globally
                           current_year=current_year)

@baal_satsang_bp.route('/generate_tokens_pdf', methods=['POST'])
@login_required
@permission_required('generate_baal_satsang_tokens_pdf')
def generate_tokens_pdf():
    """Generates a PDF of badges for the specified Baal Satsang Token IDs."""
    token_ids_raw = request.form.get('token_ids', '')
    selected_token_type_key = request.form.get('token_type', '').strip().lower()
    selected_area = request.form.get('area', '').strip()
    selected_centre = request.form.get('centre', '').strip()

    # --- Validation ---
    if not selected_area:
        flash("Please select an Area.", "error")
        return redirect(url_for('baal_satsang.printer_page'))
    if not selected_centre:
        flash("Please select a Centre.", "error")
        return redirect(url_for('baal_satsang.printer_page'))
    if not token_ids_raw:
        flash("Please enter Token IDs.", "error")
        return redirect(url_for('baal_satsang.printer_page'))
    if not selected_token_type_key or selected_token_type_key not in config.BAAL_SATSANG_TOKEN_TYPES:
        flash("Please select a valid Token Type.", "error")
        return redirect(url_for('baal_satsang.printer_page'))

    token_ids_to_print = parse_token_ids(token_ids_raw)

    if token_ids_to_print is None or not token_ids_to_print:
        flash("Invalid Token ID input. Please use a range (e.g., 001-010) or comma-separated numbers (e.g., 001, 005, 008). Ensure IDs are numeric.", "error")
        return redirect(url_for('baal_satsang.printer_page'))

    logger.info(f"Request to generate PDF for Baal Satsang Tokens: Area='{selected_area}', Centre='{selected_centre}', Type='{selected_token_type_key}', IDs='{token_ids_to_print}'")

    # --- Determine the correct template path, text elements, and PDF layout ---
    template_path_map = {
        "sangat": config.BAAL_SATSANG_SANGAT_TOKEN_TEMPLATE_PATH,
        "visitor": config.BAAL_SATSANG_VISITOR_TOKEN_TEMPLATE_PATH,
        "sibling_parent": config.BAAL_SATSANG_SIBLING_PARENT_TOKEN_TEMPLATE_PATH,
        "single_child_parent": config.BAAL_SATSANG_SINGLE_CHILD_PARENT_TOKEN_TEMPLATE_PATH,
    }
    text_elements_map = {
        "sangat": config.BAAL_SATSANG_TOKEN_TEXT_ELEMENTS,
        "visitor": config.BAAL_SATSANG_VISITOR_TEXT_ELEMENTS,
        "sibling_parent": config.BAAL_SATSANG_SIBLING_PARENT_TEXT_ELEMENTS,
        "single_child_parent": config.BAAL_SATSANG_SINGLE_CHILD_PARENT_TEXT_ELEMENTS,
    }
    pdf_layout_map = config.BAAL_SATSANG_PDF_LAYOUTS

    badge_template_image_path = template_path_map.get(selected_token_type_key, config.BAAL_SATSANG_SANGAT_TOKEN_TEMPLATE_PATH) # Fallback
    current_text_elements = text_elements_map.get(selected_token_type_key, config.BAAL_SATSANG_TOKEN_TEXT_ELEMENTS) # Fallback
    current_pdf_layout = pdf_layout_map.get(selected_token_type_key, pdf_layout_map.get("default")) # Fallback to default layout

    tokens_data_for_pdf = []
    for token_id_val in token_ids_to_print:
        tokens_data_for_pdf.append({
            "token_id": token_id_val,
            "area_display": selected_area, # Text to display for area
            "centre_display": selected_centre, # Text to display for centre
            # "attendant_type" is not needed here as template is chosen by selected_token_type_key
        })

    token_layout_config = {
        "template_path": badge_template_image_path,
        "text_elements": current_text_elements,
        "photo_config": {}, # No photos for Baal Satsang tokens
        "pdf_layout": current_pdf_layout,
        "font_path": config.FONT_PATH,
        "font_bold_path": config.FONT_BOLD_PATH,
        "s3_bucket": config.S3_BUCKET_NAME, # Not used for Baal Satsang but part of generic config
        # "wrap_config": {} # No text wrapping expected for these tokens by default
    }

    try:
        logger.info(f"Generating PDF for {len(tokens_data_for_pdf)} Baal Satsang tokens of type '{selected_token_type_key}' for Area '{selected_area}', Centre '{selected_centre}'.")
        pdf_buffer = utils.generate_badge_pdf(tokens_data_for_pdf, token_layout_config)

        if pdf_buffer is None:
             raise Exception("Baal Satsang Token PDF generation failed (returned None). Check logs.")

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        # Sanitize area and centre names for filename
        area_short = "".join(filter(str.isalnum, selected_area))[:10]
        centre_short = "".join(filter(str.isalnum, selected_centre))[:15]
        token_type_name = config.BAAL_SATSANG_TOKEN_TYPES.get(selected_token_type_key, "Token")
        token_type_short = "".join(filter(str.isalnum, token_type_name)).replace("BaalSatsangToken", "")[:20]

        filename = f"BaalSatsang_{area_short}_{centre_short}_{token_type_short}_{timestamp}.pdf"

        logger.info(f"Sending generated Baal Satsang Token PDF: {filename}")
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error generating Baal Satsang Token PDF: {e}", exc_info=True)
        flash(f"Error generating PDF: {e}", "error")
        return redirect(url_for('baal_satsang.printer_page'))
