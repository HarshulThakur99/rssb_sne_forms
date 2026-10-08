# nominal_roll_routes.py
import datetime
import logging

from flask import Blueprint, render_template
from flask_login import login_required

from app import config
from app.decorators import permission_required

# --- Blueprint Definition ---
nominal_roll_bp = Blueprint('nominal_roll', __name__, url_prefix='/nominal_roll')
logger = logging.getLogger(__name__)


@nominal_roll_bp.route('/form')
@login_required
@permission_required('access_nominal_roll_form')
def form_page():
    """Displays the fillable/printable Nominal Roll - Sewa Jatha form."""
    current_year = datetime.date.today().year
    return render_template('nominal_roll_form.html',
                           areas=config.AREAS,
                           default_area=config.AREAS[0],
                           default_centre='CHD-I (Sec 27)',
                           default_zone='III',
                           default_area_secy='GURDAS BANSAL - 9872111336',
                           default_area_jathedar='PARAMJEET - 9988194860',
                           current_year=current_year)
