# nominal_roll_routes.py
import datetime
import logging
from io import BytesIO

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from openpyxl import Workbook
from openpyxl.styles import Font

from app import config
from app.decorators import permission_required
from app.models import db, Sewadar, NominalRoll, NominalRollSewadar
from app.db_helpers import case_insensitive_like

# --- Blueprint Definition ---
nominal_roll_bp = Blueprint('nominal_roll', __name__, url_prefix='/nominal_roll')
logger = logging.getLogger(__name__)


def _roll_to_dict(roll):
    return {
        'id': roll.id,
        'nominal_roll_id': roll.nominal_roll_id or '',
        'area': roll.area,
        'centre': roll.centre,
        'zone': roll.zone or '',
        'area_jathedar': roll.area_jathedar or '',
        'vehicle_type': roll.vehicle_type or '',
        'vehicle_no': roll.vehicle_no or '',
        'driver': roll.driver or '',
        'place_of_sewa': roll.place_of_sewa or '',
        'sewa_start_date': roll.sewa_start_date.isoformat() if roll.sewa_start_date else '',
        'sewa_end_date': roll.sewa_end_date.isoformat() if roll.sewa_end_date else '',
        'jathedar_sign_date': roll.jathedar_sign_date or '',
        'jathedar_contact_no': roll.jathedar_contact_no or '',
        'functionary_sign_date': roll.functionary_sign_date or '',
        'functionary_contact_no': roll.functionary_contact_no or '',
        'rows': [{
            'sewadar_name': r.sewadar_name or '',
            'relation': r.relation or '',
            'father_husband_name': r.father_husband_name or '',
            'gender': r.gender or '',
            'age': r.age if r.age is not None else '',
            'address': r.address or '',
            'mobile_no': r.mobile_no or '',
            'badge_number': r.badge_number or '',
            'jatha': r.jatha or '',
            'helpline': r.helpline or '',
            'calling_status': r.calling_status or ''
        } for r in roll.sewadars]
    }


@nominal_roll_bp.route('/form')
@login_required
@permission_required('access_nominal_roll_form')
def form_page():
    """Displays the fillable/printable Nominal Roll - Sewa Jatha form.
    Pass ?id=<roll_id> to load a previously saved roll for viewing/editing."""
    roll_id = request.args.get('id', type=int)
    roll_data = None
    read_only = False

    if roll_id:
        roll = NominalRoll.query.get(roll_id)
        if not roll:
            flash('Nominal roll not found.', 'error')
            return redirect(url_for('nominal_roll.list_page'))
        read_only = roll.sewa_end_date < datetime.date.today()
        roll_data = _roll_to_dict(roll)

    current_year = datetime.date.today().year
    return render_template('nominal_roll_form.html',
                           areas=config.AREAS,
                           default_area=config.AREAS[0],
                           default_centre='CHD-I (Sec 27)',
                           default_zone='III',
                           default_area_jathedar='PARAMJEET - 9988194860',
                           current_year=current_year,
                           roll_data=roll_data,
                           read_only=read_only)


@nominal_roll_bp.route('/list')
@login_required
@permission_required('access_nominal_roll_form')
def list_page():
    """Lists saved nominal rolls. Also lazily purges rolls more than 7 days past their sewa end date."""
    cutoff = datetime.date.today() - datetime.timedelta(days=7)
    deleted = NominalRoll.query.filter(NominalRoll.sewa_end_date < cutoff).delete(synchronize_session=False)
    if deleted:
        db.session.commit()
        logger.info(f"Auto-deleted {deleted} nominal roll(s) past their 7-day retention window.")

    today = datetime.date.today()
    rolls = NominalRoll.query.order_by(NominalRoll.sewa_end_date.desc(), NominalRoll.id.desc()).all()
    rolls_data = [{
        'id': r.id,
        'nominal_roll_id': r.nominal_roll_id or '',
        'area': r.area,
        'centre': r.centre,
        'sewa_start_date': r.sewa_start_date.isoformat() if r.sewa_start_date else '',
        'sewa_end_date': r.sewa_end_date.isoformat(),
        'sewadar_count': len(r.sewadars),
        'editable': r.sewa_end_date >= today,
        'created_by': r.created_by or ''
    } for r in rolls]

    return render_template('nominal_roll_list.html', rolls=rolls_data, current_year=today.year)


@nominal_roll_bp.route('/search_sewadars')
@login_required
@permission_required('access_nominal_roll_form')
def search_sewadars():
    """Looks up sewadars by (partial) name or badge number for the nominal roll's type-ahead search."""
    query_text = request.args.get('q', '').strip()
    if len(query_text) < 2:
        return jsonify([])

    pattern = f'%{query_text}%'
    results = Sewadar.query.filter(
        case_insensitive_like(Sewadar.sewadar_name, pattern) |
        case_insensitive_like(Sewadar.badge_number, pattern)
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
        'mobile_no': s.contact_no or '',
        'centre': s.centre or '',
        'department': s.department or ''
    } for s in results])


@nominal_roll_bp.route('/save', methods=['POST'])
@login_required
@permission_required('access_nominal_roll_form')
def save_roll():
    """Creates a new nominal roll, or updates an existing one (if 'id' is given and still editable)."""
    data = request.get_json(silent=True) or {}
    header = data.get('header', {})
    rows = data.get('rows', [])
    roll_id = data.get('id')

    area = (header.get('area') or '').strip()
    centre = (header.get('centre') or '').strip()
    if not area or not centre:
        return jsonify({'success': False, 'error': 'Area and Satsang Place/Centre are required.'}), 400

    sewa_end_date_str = (header.get('sewa_end_date') or '').strip()
    if not sewa_end_date_str:
        return jsonify({'success': False, 'error': 'Sewa End Date is required to save a nominal roll.'}), 400
    try:
        sewa_end_date = datetime.datetime.strptime(sewa_end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid Sewa End Date.'}), 400

    sewa_start_date = None
    sewa_start_date_str = (header.get('sewa_start_date') or '').strip()
    if sewa_start_date_str:
        try:
            sewa_start_date = datetime.datetime.strptime(sewa_start_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid Sewa Start Date.'}), 400

    try:
        if roll_id:
            roll = NominalRoll.query.get(roll_id)
            if not roll:
                return jsonify({'success': False, 'error': 'Nominal roll not found.'}), 404
            if roll.sewa_end_date < datetime.date.today():
                return jsonify({'success': False, 'error': 'This nominal roll has ended and is read-only.'}), 403
        else:
            roll = NominalRoll(created_by=current_user.id)
            db.session.add(roll)

        roll.nominal_roll_id = header.get('nominal_roll_id') or None
        roll.area = area
        roll.centre = centre
        roll.zone = header.get('zone') or None
        roll.area_jathedar = header.get('area_jathedar') or None
        roll.vehicle_type = header.get('vehicle_type') or None
        roll.vehicle_no = header.get('vehicle_no') or None
        roll.driver = header.get('driver') or None
        roll.place_of_sewa = header.get('place_of_sewa') or None
        roll.sewa_start_date = sewa_start_date
        roll.sewa_end_date = sewa_end_date
        roll.jathedar_sign_date = header.get('jathedar_sign_date') or None
        roll.jathedar_contact_no = header.get('jathedar_contact_no') or None
        roll.functionary_sign_date = header.get('functionary_sign_date') or None
        roll.functionary_contact_no = header.get('functionary_contact_no') or None
        roll.updated_at = datetime.datetime.utcnow()

        new_rows = []
        for i, row in enumerate(rows, start=1):
            name = (row.get('sewadar_name') or '').strip()
            if not name:
                continue
            age_val = row.get('age')
            try:
                age_val = int(age_val) if age_val not in (None, '') else None
            except (TypeError, ValueError):
                age_val = None
            new_rows.append(NominalRollSewadar(
                sr_no=i,
                sewadar_name=name,
                relation=row.get('relation') or None,
                father_husband_name=row.get('father_husband_name') or None,
                gender=row.get('gender') or None,
                age=age_val,
                address=row.get('address') or None,
                mobile_no=row.get('mobile_no') or None,
                badge_number=row.get('badge_number') or None,
                jatha=row.get('jatha') or None,
                helpline=row.get('helpline') or None,
                calling_status=row.get('calling_status') or None
            ))
        roll.sewadars = new_rows

        db.session.commit()
        logger.info(f"Saved nominal roll {roll.id} ({'update' if roll_id else 'create'}) by {current_user.id}")
        return jsonify({'success': True, 'id': roll.id})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving nominal roll: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@nominal_roll_bp.route('/export/<int:roll_id>')
@login_required
@permission_required('access_nominal_roll_form')
def export_roll(roll_id):
    """Exports only sewadar details plus the jatha/helpline/calling-status tracking columns to .xlsx."""
    roll = NominalRoll.query.get(roll_id)
    if not roll:
        flash('Nominal roll not found.', 'error')
        return redirect(url_for('nominal_roll.list_page'))

    wb = Workbook()
    ws = wb.active
    ws.title = 'Sewadar Calling List'

    headers = ['Sr No', 'Sewadar Name', 'Relation', 'Father/Husband Name', 'Gender', 'Age',
               'Address', 'Mobile No', 'Badge Number', 'Jatha', 'Helpline', 'Calling Status']
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for i, r in enumerate(sorted(roll.sewadars, key=lambda x: x.sr_no), start=1):
        ws.append([
            i,
            r.sewadar_name or '',
            r.relation or '',
            r.father_husband_name or '',
            r.gender or '',
            r.age if r.age is not None else '',
            r.address or '',
            r.mobile_no or '',
            r.badge_number or '',
            r.jatha or '',
            r.helpline or '',
            r.calling_status or ''
        ])

    column_widths = [6, 22, 10, 22, 8, 6, 28, 14, 14, 14, 10, 14]
    for col_idx, width in enumerate(column_widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    safe_centre = (roll.centre or 'roll').replace(' ', '_').replace('/', '-')
    date_part = roll.sewa_end_date.isoformat() if roll.sewa_end_date else str(roll.id)
    filename = f"NominalRoll_{safe_centre}_{date_part}.xlsx"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@nominal_roll_bp.route('/delete/<int:roll_id>', methods=['POST'])
@login_required
@permission_required('access_nominal_roll_form')
def delete_roll(roll_id):
    """Deletes a saved nominal roll."""
    roll = NominalRoll.query.get(roll_id)
    if not roll:
        return jsonify({'success': False, 'error': 'Nominal roll not found.'}), 404
    db.session.delete(roll)
    db.session.commit()
    logger.info(f"Deleted nominal roll {roll_id} by {current_user.id}")
    return jsonify({'success': True})

