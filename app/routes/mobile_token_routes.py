# mobile_token_routes.py
import logging
from flask import (
    Blueprint, render_template, request, flash, redirect, url_for, make_response
)
from flask_login import login_required
# Import shared utilities and configuration
from app import utils
from app import config
# Import the decorator from the new decorators.py file
from app.decorators import permission_required

# --- Blueprint Definition ---
mobile_token_bp = Blueprint('mobile_token', __name__, url_prefix='/mobile_token')
logger = logging.getLogger(__name__)

# --- Mobile Token Routes ---

@mobile_token_bp.route('/printer')
@login_required
@permission_required('access_mobile_token_printer')
def printer_page():
    """Displays the Mobile Token printer form."""
    current_year = utils.get_current_year()
    areas = list(config.SNE_BADGE_CONFIG.keys())
    return render_template('mobile_token_printer_form.html',
                           current_year=current_year,
                           areas=areas)

@mobile_token_bp.route('/generate_pdf', methods=['POST'])
@login_required
@permission_required('access_mobile_token_printer')
def generate_tokens_pdf():
    """Generates a PDF of mobile tokens based on form submission."""
    area = request.form.get('area')
    centre = request.form.get('centre')
    token_ids_str = request.form.get('token_ids', '')

    if not all([area, centre, token_ids_str]):
        flash("Area, Centre, and Token IDs are required.", "error")
        return redirect(url_for('mobile_token.printer_page'))

    try:
        # Use the new 7-digit padding for mobile tokens
        token_ids = utils.parse_token_ids(token_ids_str, padding=4)
        if not token_ids:
            flash("Invalid Token ID format. Please use ranges (e.g., 1-10) or commas (e.g., 1,5,8).", "error")
            return redirect(url_for('mobile_token.printer_page'))

        # Prepare the list of data dictionaries for the PDF generator
        badge_data_list = []
        for token_id in token_ids:
            badge_data_list.append({
                "token_id": token_id,
                "area_display": f"{area}",
                "centre_display": f"{centre}"
            })

        if not badge_data_list:
            flash("Could not generate any token data. Please check your input.", "error")
            return redirect(url_for('mobile_token.printer_page'))

        # Use the comprehensive layout config from config.py
        layout_config = config.MOBILE_TOKEN_LAYOUT_CONFIG
        
        # Call the correct utility function that generates the full PDF
        pdf_buffer = utils.generate_badge_pdf(badge_data_list, layout_config)

        if not pdf_buffer:
            flash("Failed to generate PDF. Please check the application logs.", "error")
            return redirect(url_for('mobile_token.printer_page'))

        # Create and return the PDF response
        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=mobile_tokens_{area}_{centre}.pdf'
        return response

    except Exception as e:
        logger.error(f"Error generating mobile token PDF: {e}", exc_info=True)
        flash(f"An unexpected error occurred: {e}", "error")
        return redirect(url_for('mobile_token.printer_page'))
