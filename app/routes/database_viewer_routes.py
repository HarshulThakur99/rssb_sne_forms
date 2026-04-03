# database_viewer_routes.py - Admin-only database table viewer
import datetime
import logging
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app import config, db_helpers
from app.models import db, SNEForm, BloodCampDonor, Attendant
from app.decorators import permission_required

# --- Blueprint Definition ---
db_viewer_bp = Blueprint('db_viewer', __name__, url_prefix='/database')
logger = logging.getLogger(__name__)


@db_viewer_bp.route('/')
@login_required
@permission_required('access_database_viewer')
def viewer_home():
    """Main database viewer page - shows table list and statistics."""
    try:
        # Get counts for each table
        sne_count = db.session.query(SNEForm).count()
        blood_count = db.session.query(BloodCampDonor).count()
        attendant_count = db.session.query(Attendant).count()
        
        # Get latest records timestamps
        latest_sne = db.session.query(SNEForm).order_by(SNEForm.submission_date.desc()).first()
        latest_blood = db.session.query(BloodCampDonor).order_by(BloodCampDonor.submission_timestamp.desc()).first()
        latest_attendant = db.session.query(Attendant).order_by(Attendant.submission_date.desc()).first()
        
        tables_info = [
            {
                'name': 'SNE Forms',
                'table': 'sne_forms',
                'count': sne_count,
                'latest': latest_sne.submission_date if latest_sne else None,
                'description': 'SNE Member registration forms and badges'
            },
            {
                'name': 'Blood Camp Donors',
                'table': 'blood_camp_donors',
                'count': blood_count,
                'latest': latest_blood.submission_timestamp if latest_blood else None,
                'description': 'Blood donation camp registrations and donations'
            },
            {
                'name': 'Attendants',
                'table': 'attendants',
                'count': attendant_count,
                'latest': latest_attendant.submission_date if latest_attendant else None,
                'description': 'SNE attendant and family member badges'
            }
        ]
        
        return render_template('database_viewer.html',
                             tables=tables_info,
                             current_year=datetime.date.today().year)
    except Exception as e:
        logger.error(f"Error loading database viewer: {e}", exc_info=True)
        return render_template('database_viewer.html',
                             tables=[],
                             error=f"Error loading database: {e}",
                             current_year=datetime.date.today().year)


@db_viewer_bp.route('/table/<table_name>')
@login_required
@permission_required('access_database_viewer')
def view_table(table_name):
    """View specific table data with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '', type=str)
    
    try:
        if table_name == 'sne_forms':
            query = SNEForm.query
            if search:
                query = query.filter(
                    (SNEForm.badge_id.ilike(f'%{search}%')) |
                    (SNEForm.first_name.ilike(f'%{search}%')) |
                    (SNEForm.last_name.ilike(f'%{search}%')) |
                    (SNEForm.mobile_no.ilike(f'%{search}%'))
                )
            query = query.order_by(SNEForm.submission_date.desc())
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            
            records = []
            for record in pagination.items:
                records.append({
                    'ID': record.id,
                    'Badge ID': record.badge_id,
                    'Name': f"{record.first_name} {record.last_name}",
                    'Mobile': record.mobile_no or '',
                    'Centre': record.satsang_place,
                    'Area': record.area,
                    'Submitted': record.submission_date.strftime('%Y-%m-%d') if record.submission_date else ''
                })
            
            columns = ['ID', 'Badge ID', 'Name', 'Mobile', 'Centre', 'Area', 'Submitted']
            
        elif table_name == 'blood_camp_donors':
            query = BloodCampDonor.query
            if search:
                query = query.filter(
                    (BloodCampDonor.donor_id.ilike(f'%{search}%')) |
                    (BloodCampDonor.name_of_donor.ilike(f'%{search}%')) |
                    (BloodCampDonor.mobile_number.ilike(f'%{search}%'))
                )
            query = query.order_by(BloodCampDonor.submission_timestamp.desc())
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            
            records = []
            for record in pagination.items:
                records.append({
                    'ID': record.id,
                    'Donor ID': record.donor_id,
                    'Name': record.name_of_donor,
                    'Mobile': record.mobile_number,
                    'Blood Group': record.blood_group,
                    'City': record.city,
                    'Status': record.status,
                    'Total Donations': record.total_donations,
                    'Submitted': record.submission_timestamp.strftime('%Y-%m-%d %H:%M') if record.submission_timestamp else ''
                })
            
            columns = ['ID', 'Donor ID', 'Name', 'Mobile', 'Blood Group', 'City', 'Status', 'Total Donations', 'Submitted']
            
        elif table_name == 'attendants':
            query = Attendant.query
            if search:
                query = query.filter(
                    (Attendant.badge_id.ilike(f'%{search}%')) |
                    (Attendant.name.ilike(f'%{search}%')) |
                    (Attendant.phone_number.ilike(f'%{search}%'))
                )
            query = query.order_by(Attendant.submission_date.desc())
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            
            records = []
            for record in pagination.items:
                records.append({
                    'ID': record.id,
                    'Badge ID': record.badge_id,
                    'Name': record.name,
                    'Phone': record.phone_number,
                    'Centre': record.centre,
                    'Area': record.area,
                    'Type': record.attendant_type,
                    'Submitted': record.submission_date.strftime('%Y-%m-%d') if record.submission_date else ''
                })
            
            columns = ['ID', 'Badge ID', 'Name', 'Phone', 'Centre', 'Area', 'Type', 'Submitted']
            
        else:
            return "Table not found", 404
        
        return render_template('database_table_view.html',
                             table_name=table_name,
                             table_display_name=table_name.replace('_', ' ').title(),
                             columns=columns,
                             records=records,
                             pagination=pagination,
                             search=search,
                             current_year=datetime.date.today().year)
                             
    except Exception as e:
        logger.error(f"Error viewing table {table_name}: {e}", exc_info=True)
        return render_template('database_table_view.html',
                             table_name=table_name,
                             table_display_name=table_name.replace('_', ' ').title(),
                             columns=[],
                             records=[],
                             error=f"Error loading table: {e}",
                             current_year=datetime.date.today().year)


@db_viewer_bp.route('/stats')
@login_required
@permission_required('access_database_viewer')
def database_stats():
    """Get database statistics as JSON."""
    try:
        from sqlalchemy import func
        
        # SNE statistics
        sne_stats = {
            'total': db.session.query(SNEForm).count(),
            'by_area': db.session.query(
                SNEForm.area, 
                func.count(SNEForm.id)
            ).group_by(SNEForm.area).all(),
            'recent_24h': db.session.query(SNEForm).filter(
                SNEForm.submission_date >= datetime.date.today() - datetime.timedelta(days=1)
            ).count()
        }
        
        # Blood donor statistics
        blood_stats = {
            'total': db.session.query(BloodCampDonor).count(),
            'by_blood_group': db.session.query(
                BloodCampDonor.blood_group,
                func.count(BloodCampDonor.id)
            ).group_by(BloodCampDonor.blood_group).all(),
            'by_status': db.session.query(
                BloodCampDonor.status,
                func.count(BloodCampDonor.id)
            ).group_by(BloodCampDonor.status).all(),
            'recent_24h': db.session.query(BloodCampDonor).filter(
                BloodCampDonor.submission_timestamp >= datetime.datetime.now() - datetime.timedelta(days=1)
            ).count()
        }
        
        # Attendant statistics
        attendant_stats = {
            'total': db.session.query(Attendant).count(),
            'by_type': db.session.query(
                Attendant.attendant_type,
                func.count(Attendant.id)
            ).group_by(Attendant.attendant_type).all(),
            'by_area': db.session.query(
                Attendant.area,
                func.count(Attendant.id)
            ).group_by(Attendant.area).all()
        }
        
        return jsonify({
            'success': True,
            'sne_forms': {
                'total': sne_stats['total'],
                'by_area': dict(sne_stats['by_area']),
                'recent_24h': sne_stats['recent_24h']
            },
            'blood_donors': {
                'total': blood_stats['total'],
                'by_blood_group': dict(blood_stats['by_blood_group']),
                'by_status': dict(blood_stats['by_status']),
                'recent_24h': blood_stats['recent_24h']
            },
            'attendants': {
                'total': attendant_stats['total'],
                'by_type': dict(attendant_stats['by_type']),
                'by_area': dict(attendant_stats['by_area'])
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@db_viewer_bp.route('/export/<table_name>')
@login_required
@permission_required('access_database_viewer')
def export_table(table_name):
    """Export table data as CSV."""
    import csv
    import io
    from flask import Response
    
    try:
        # Get all records for the table (no pagination)
        if table_name == 'sne_forms':
            query = SNEForm.query.order_by(SNEForm.submission_date.desc()).all()
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Badge ID', 'First Name', 'Last Name', 'Mobile', 'Centre', 'Area', 'Submitted'])
            
            for record in query:
                writer.writerow([
                    record.id,
                    record.badge_id,
                    record.first_name,
                    record.last_name,
                    record.mobile_no or '',
                    record.satsang_place,
                    record.area,
                    record.submission_date.strftime('%Y-%m-%d') if record.submission_date else ''
                ])
            
            filename = f'sne_forms_{datetime.date.today().strftime("%Y%m%d")}.csv'
            
        elif table_name == 'blood_camp_donors':
            query = BloodCampDonor.query.order_by(BloodCampDonor.submission_timestamp.desc()).all()
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Donor ID', 'Name', 'Mobile', 'Blood Group', 'City', 'Status', 'Total Donations', 'Submitted'])
            
            for record in query:
                writer.writerow([
                    record.id,
                    record.donor_id,
                    record.name_of_donor,
                    record.mobile_number,
                    record.blood_group,
                    record.city,
                    record.status,
                    record.total_donations,
                    record.submission_timestamp.strftime('%Y-%m-%d %H:%M') if record.submission_timestamp else ''
                ])
            
            filename = f'blood_camp_donors_{datetime.date.today().strftime("%Y%m%d")}.csv'
            
        elif table_name == 'attendants':
            query = Attendant.query.order_by(Attendant.submission_date.desc()).all()
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Badge ID', 'Name', 'Phone', 'Centre', 'Area', 'Type', 'Submitted'])
            
            for record in query:
                writer.writerow([
                    record.id,
                    record.badge_id,
                    record.name,
                    record.phone_number,
                    record.centre,
                    record.area,
                    record.attendant_type,
                    record.submission_date.strftime('%Y-%m-%d') if record.submission_date else ''
                ])
            
            filename = f'attendants_{datetime.date.today().strftime("%Y%m%d")}.csv'
            
        else:
            return "Table not found", 404
        
        # Return CSV file
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
                             
    except Exception as e:
        logger.error(f"Error exporting table {table_name}: {e}", exc_info=True)
        return f"Error exporting table: {e}", 500
