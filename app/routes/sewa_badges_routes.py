# sewa_badges_routes.py
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
sewa_badges_bp = Blueprint('sewa_badges', __name__, url_prefix='/sewa_badges')
logger = logging.getLogger(__name__)

# --- Sewa Badges Routes ---

@sewa_badges_bp.route('/printer')
@login_required
@permission_required('access_sewa_badges_printer')
def printer_page():
    """Displays the Sewa Badges printer form."""
    current_year = utils.get_current_year()
    areas = list(config.SNE_BADGE_CONFIG.keys())
    sewa_types = config.SEWA_TYPES
    return render_template('sewa_badges_printer_form.html',
                           current_year=current_year,
                           areas=areas,
                           sewa_types=sewa_types)

@sewa_badges_bp.route('/generate_pdf', methods=['POST'])
@login_required
@permission_required('access_sewa_badges_printer')
def generate_badges_pdf():
    """Generates a PDF of sewa badges based on form submission."""
    sewa_type = request.form.get('sewa_type')
    area = request.form.get('area')
    centre = request.form.get('centre')
    badge_ids_str = request.form.get('badge_ids', '')

    if not all([sewa_type, area, centre, badge_ids_str]):
        flash("Sewa Type, Area, Centre, and Badge IDs are required.", "error")
        return redirect(url_for('sewa_badges.printer_page'))

    try:
        # Use 4-digit padding for sewa badges
        badge_ids = utils.parse_token_ids(badge_ids_str, padding=4)
        if not badge_ids:
            flash("Invalid Badge ID format. Please use ranges (e.g., 1-10) or commas (e.g., 1,5,8).", "error")
            return redirect(url_for('sewa_badges.printer_page'))

        # Prepare the list of data dictionaries for the PDF generator
        badge_data_list = []
        for badge_id in badge_ids:
            badge_data_list.append({
                "badge_id": badge_id,
                "sewa_type": sewa_type,
                "area_display": f"{area}",
                "centre_display": f"{centre}"
            })

        if not badge_data_list:
            flash("Could not generate any badge data. Please check your input.", "error")
            return redirect(url_for('sewa_badges.printer_page'))

        # Use the comprehensive layout config from config.py
        layout_config = config.SEWA_BADGE_LAYOUT_CONFIG
        
        # Call the correct utility function that generates the full PDF
        pdf_buffer = utils.generate_badge_pdf(badge_data_list, layout_config)

        if not pdf_buffer:
            flash("Failed to generate PDF. Please check the application logs.", "error")
            return redirect(url_for('sewa_badges.printer_page'))

        # Create and return the PDF response
        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=sewa_badges_{sewa_type}_{area}_{centre}.pdf'
        return response

    except Exception as e:
        logger.error(f"Error generating sewa badge PDF: {e}", exc_info=True)
        flash(f"An unexpected error occurred: {e}", "error")
        return redirect(url_for('sewa_badges.printer_page'))
