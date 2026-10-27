# nominal_roll_routes.py
import datetime
import logging

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

from app import config
from app.decorators import permission_required
from app.models import Sewadar
from app.db_helpers import case_insensitive_like

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


@nominal_roll_bp.route('/search_sewadars')
@login_required
@permission_required('access_nominal_roll_form')
def search_sewadars():
    """Looks up sewadars by (partial) name for the nominal roll's type-ahead search."""
    query_text = request.args.get('q', '').strip()
    if len(query_text) < 2:
        return jsonify([])

    results = Sewadar.query.filter(
        case_insensitive_like(Sewadar.sewadar_name, f'%{query_text}%')
    ).order_by(Sewadar.sewadar_name.asc()).limit(15).all()

    return jsonify([{
        'id': s.id,
        'badge_number': s.badge_number or '',
        'sewadar_name': s.sewadar_name,
        'relation': s.relation or '',
        'father_husband_name': s.father_husband_name or '',
        'gender': s.gender or '',
        'age': s.age or '',
        'address': s.address or '',
        'centre': s.centre or '',
        'department': s.department or ''
    } for s in results])
