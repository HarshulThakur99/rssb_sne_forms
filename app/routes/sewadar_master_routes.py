# sewadar_master_routes.py
import datetime
import logging

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import config
from app.decorators import permission_required
from app.models import db, Sewadar
from app.db_helpers import case_insensitive_like

sewadar_master_bp = Blueprint('sewadar_master', __name__, url_prefix='/sewadar_master')
logger = logging.getLogger(__name__)


@sewadar_master_bp.route('/')
@login_required
@permission_required('access_sewadar_master')
def list_page():
    """Lists sewadar master records with optional name/badge/mobile search and centre filter."""
    search_query = request.args.get('q', '').strip()
    filter_centre = request.args.get('centre', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 50

    query = Sewadar.query
    if search_query:
        pattern = f'%{search_query}%'
        query = query.filter(
            case_insensitive_like(Sewadar.sewadar_name, pattern) |
            case_insensitive_like(Sewadar.badge_number, pattern) |
            case_insensitive_like(Sewadar.contact_no, pattern)
        )
    if filter_centre:
        query = query.filter(Sewadar.centre == filter_centre)

    query = query.order_by(Sewadar.sewadar_name.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    centres = [c[0] for c in db.session.query(Sewadar.centre).distinct().order_by(Sewadar.centre).all() if c[0]]

    return render_template('sewadar_master_list.html',
                           sewadars=pagination.items,
                           pagination=pagination,
                           centres=centres,
                           search_query=search_query,
                           filter_centre=filter_centre)


@sewadar_master_bp.route('/add', methods=['GET', 'POST'])
@login_required
@permission_required('access_sewadar_master')
def add_sewadar():
    """Adds a new sewadar to the master list."""
    if request.method == 'POST':
        sewadar = Sewadar()
        error = _populate_sewadar_from_form(sewadar, request.form)
        if error:
            flash(error, 'error')
            return render_template('sewadar_master_form.html', sewadar=request.form.to_dict(), is_new=True, states=config.STATES, centres=config.CENTRES)
        db.session.add(sewadar)
        db.session.commit()
        logger.info(f"Added sewadar '{sewadar.sewadar_name}' to master list by {current_user.id}")
        flash('Sewadar added to master list.', 'success')
        return redirect(url_for('sewadar_master.list_page'))

    return render_template('sewadar_master_form.html', sewadar=None, is_new=True, states=config.STATES, centres=config.CENTRES)


@sewadar_master_bp.route('/edit/<int:sewadar_id>', methods=['GET', 'POST'])
@login_required
@permission_required('access_sewadar_master')
def edit_sewadar(sewadar_id):
    """Edits an existing sewadar master record."""
    sewadar = Sewadar.query.get_or_404(sewadar_id)

    if request.method == 'POST':
        error = _populate_sewadar_from_form(sewadar, request.form, editing_id=sewadar_id)
        if error:
            flash(error, 'error')
            return render_template('sewadar_master_form.html', sewadar=request.form.to_dict(), is_new=False, sewadar_id=sewadar_id, states=config.STATES, centres=config.CENTRES)
        db.session.commit()
        logger.info(f"Updated sewadar {sewadar_id} by {current_user.id}")
        flash('Sewadar updated.', 'success')
        return redirect(url_for('sewadar_master.list_page'))

    return render_template('sewadar_master_form.html', sewadar=_sewadar_to_dict(sewadar), is_new=False, sewadar_id=sewadar_id, states=config.STATES, centres=config.CENTRES)


@sewadar_master_bp.route('/delete/<int:sewadar_id>', methods=['POST'])
@login_required
@permission_required('access_sewadar_master')
def delete_sewadar(sewadar_id):
    """Deletes a sewadar master record."""
    sewadar = Sewadar.query.get_or_404(sewadar_id)
    name = sewadar.sewadar_name
    db.session.delete(sewadar)
    db.session.commit()
    logger.info(f"Deleted sewadar {sewadar_id} ({name}) by {current_user.id}")
    flash('Sewadar deleted.', 'success')
    return redirect(url_for('sewadar_master.list_page'))


def _sewadar_to_dict(sewadar):
    """Flattens a Sewadar model instance into a plain dict for form pre-fill (dates as YYYY-MM-DD strings)."""
    return {
        'badge_number': sewadar.badge_number or '',
        'old_badge_number': sewadar.old_badge_number or '',
        'sewadar_name': sewadar.sewadar_name or '',
        'relation': sewadar.relation or '',
        'father_husband_name': sewadar.father_husband_name or '',
        'dob': sewadar.dob.isoformat() if sewadar.dob else '',
        'doe': sewadar.doe.isoformat() if sewadar.doe else '',
        'gender': sewadar.gender or '',
        'blood_group': sewadar.blood_group or '',
        'age': sewadar.age if sewadar.age is not None else '',
        'year_of_birth': sewadar.year_of_birth if sewadar.year_of_birth is not None else '',
        'centre': sewadar.centre or '',
        'department': sewadar.department or '',
        'address': sewadar.address or '',
        'contact_no': sewadar.contact_no or '',
        'city': sewadar.city or '',
        'state': sewadar.state or ''
    }


def _populate_sewadar_from_form(sewadar, form, editing_id=None):
    """Fills a Sewadar instance from submitted form data. Returns an error string, or None on success."""
    name = (form.get('sewadar_name') or '').strip()
    centre = (form.get('centre') or '').strip()
    if not name:
        return 'Sewadar Name is required.'
    if not centre:
        return 'Centre is required.'

    badge_number = (form.get('badge_number') or '').strip() or None
    if badge_number:
        existing = Sewadar.query.filter(Sewadar.badge_number == badge_number).first()
        if existing and existing.id != editing_id:
            return f'Badge number {badge_number} is already assigned to {existing.sewadar_name}.'

    def parse_date(value):
        value = (value or '').strip()
        if not value:
            return None
        try:
            return datetime.datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return None

    def parse_int(value):
        value = (value or '').strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    sewadar.badge_number = badge_number
    sewadar.old_badge_number = (form.get('old_badge_number') or '').strip() or None
    sewadar.sewadar_name = name
    sewadar.relation = (form.get('relation') or '').strip() or None
    sewadar.father_husband_name = (form.get('father_husband_name') or '').strip() or None
    sewadar.dob = parse_date(form.get('dob'))
    sewadar.doe = parse_date(form.get('doe'))
    sewadar.gender = (form.get('gender') or '').strip() or None
    sewadar.blood_group = (form.get('blood_group') or '').strip() or None
    sewadar.age = parse_int(form.get('age'))
    sewadar.year_of_birth = parse_int(form.get('year_of_birth'))
    sewadar.centre = centre
    sewadar.department = (form.get('department') or '').strip() or None
    sewadar.address = (form.get('address') or '').strip() or None
    sewadar.contact_no = (form.get('contact_no') or '').strip() or None
    sewadar.city = (form.get('city') or '').strip() or None
    sewadar.state = (form.get('state') or '').strip() or None
    return None
