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
                    'Submitted': record.submission_date.strftime('%Y-%m-%d') if record.submission_date else '',
                    'Area': record.area,
                    'Centre': record.satsang_place,
                    'First Name': record.first_name,
                    'Last Name': record.last_name,
                    'Father/Husband': record.father_husband_name or '',
                    'Gender': record.gender or '',
                    'DOB': record.date_of_birth.strftime('%Y-%m-%d') if record.date_of_birth else '',
                    'Age': record.age or '',
                    'Blood Group': record.blood_group or '',
                    'Aadhaar': record.aadhaar_no or '',
                    'Mobile': record.mobile_no or '',
                    'Address': record.address or '',
                    'State': record.state or '',
                    'Pin Code': record.pin_code or '',
                    'Physically Challenged': record.physically_challenged or '',
                    'PC Details': record.physically_challenged_details or '',
                    'Home Pickup': record.help_required_home_pickup or '',
                    'Pickup Reasons': record.help_pickup_reasons or '',
                    'Handicap': record.handicap or '',
                    'Stretcher': record.stretcher_required or '',
                    'Wheelchair': record.wheelchair_required or '',
                    'Ambulance': record.ambulance_required or '',
                    'Pacemaker': record.pacemaker_operated or '',
                    'Chair Sitting': record.chair_required_sitting or '',
                    'Special Attendant': record.special_attendant_required or '',
                    'Hearing Loss': record.hearing_loss or '',
                    'Attend Satsangs': record.willing_attend_satsangs or '',
                    'Satsang Pickup Help': record.satsang_pickup_help_details or '',
                    'Other Requests': record.other_special_requests or '',
                    'Emergency Contact': record.emergency_contact_name or '',
                    'Emergency Phone': record.emergency_contact_number or '',
                    'Emergency Relation': record.emergency_contact_relation or '',
                    'Photo': record.photo_filename or ''
                })
            
            columns = ['ID', 'Badge ID', 'Submitted', 'Area', 'Centre', 'First Name', 'Last Name', 'Father/Husband', 
                      'Gender', 'DOB', 'Age', 'Blood Group', 'Aadhaar', 'Mobile', 'Address', 'State', 'Pin Code',
                      'Physically Challenged', 'PC Details', 'Home Pickup', 'Pickup Reasons', 'Handicap', 'Stretcher',
                      'Wheelchair', 'Ambulance', 'Pacemaker', 'Chair Sitting', 'Special Attendant', 'Hearing Loss',
                      'Attend Satsangs', 'Satsang Pickup Help', 'Other Requests', 'Emergency Contact', 'Emergency Phone',
                      'Emergency Relation', 'Photo']
            
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
                # Calculate age from date of birth
                age = ''
                if record.date_of_birth:
                    today = datetime.date.today()
                    age = today.year - record.date_of_birth.year - ((today.month, today.day) < (record.date_of_birth.month, record.date_of_birth.day))
                
                records.append({
                    'ID': record.id,
                    'Donor ID': record.donor_id,
                    'Submitted': record.submission_timestamp.strftime('%Y-%m-%d %H:%M') if record.submission_timestamp else '',
                    'Area': record.area or '',
                    'Name': record.name_of_donor,
                    'Father/Husband': record.father_husband_name or '',
                    'DOB': record.date_of_birth.strftime('%Y-%m-%d') if record.date_of_birth else '',
                    'Gender': record.gender or '',
                    'Occupation': record.occupation or '',
                    'House No': record.house_no or '',
                    'Sector': record.sector or '',
                    'City': record.city or '',
                    'Mobile': record.mobile_number or '',
                    'Blood Group': record.blood_group or '',
                    'Allow Call': record.allow_call or '',
                    'Donation Date': record.donation_date.strftime('%Y-%m-%d') if record.donation_date else '',
                    'Donation Location': record.donation_location or '',
                    'First Donation': record.first_donation_date.strftime('%Y-%m-%d') if record.first_donation_date else '',
                    'Total Donations': record.total_donations or 0,
                    'Status': record.status or '',
                    'Rejection Reason': record.reason_for_rejection or '',
                    'Age': age
                })
            
            columns = ['ID', 'Donor ID', 'Submitted', 'Area', 'Name', 'Father/Husband', 'DOB', 'Gender', 'Occupation', 
                      'House No', 'Sector', 'City', 'Mobile', 'Blood Group', 'Allow Call', 'Donation Date', 
                      'Donation Location', 'First Donation', 'Total Donations', 'Status', 'Rejection Reason', 'Age']
            
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
                    'Submitted': record.submission_date.strftime('%Y-%m-%d') if record.submission_date else '',
                    'Area': record.area,
                    'Centre': record.centre,
                    'Name': record.name,
                    'Phone': record.phone_number or '',
                    'Address': record.address or '',
                    'Type': record.attendant_type,
                    'Photo': record.photo_filename or '',
                    'SNE ID': record.sne_id or '',
                    'SNE Name': record.sne_name or '',
                    'SNE Gender': record.sne_gender or '',
                    'SNE Address': record.sne_address or '',
                    'SNE Photo': record.sne_photo_filename or ''
                })
            
            columns = ['ID', 'Badge ID', 'Submitted', 'Area', 'Centre', 'Name', 'Phone', 'Address', 'Type', 'Photo',
                      'SNE ID', 'SNE Name', 'SNE Gender', 'SNE Address', 'SNE Photo']
            
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
            writer.writerow(['Badge ID', 'Submission Date', 'Area', 'Satsang Centre', 'First Name', 'Last Name', 
                           "Father's/Husband's Name", 'Gender', 'Date of Birth', 'Age', 'Blood Group', 'Aadhaar No', 
                           'Mobile No', 'Address', 'State', 'Pin Code', 'Physically Challenged', 'PC Details', 
                           'Help Required Home Pickup', 'Pickup Reasons', 'Handicap', 'Stretcher Required', 
                           'Wheelchair Required', 'Ambulance Required', 'Pacemaker Operated', 'Chair Required Sitting', 
                           'Special Attendant Required', 'Hearing Loss', 'Willing to Attend Satsangs', 
                           'Satsang Pickup Help Details', 'Other Special Requests', 'Emergency Contact Name', 
                           'Emergency Contact Number', 'Emergency Contact Relation', 'Photo Filename'])
            
            for record in query:
                writer.writerow([
                    record.badge_id,
                    record.submission_date.strftime('%Y-%m-%d') if record.submission_date else '',
                    record.area,
                    record.satsang_place,
                    record.first_name,
                    record.last_name,
                    record.father_husband_name or '',
                    record.gender or '',
                    record.date_of_birth.strftime('%Y-%m-%d') if record.date_of_birth else '',
                    record.age or '',
                    record.blood_group or '',
                    record.aadhaar_no or '',
                    record.mobile_no or '',
                    record.address or '',
                    record.state or '',
                    record.pin_code or '',
                    record.physically_challenged or '',
                    record.physically_challenged_details or '',
                    record.help_required_home_pickup or '',
                    record.help_pickup_reasons or '',
                    record.handicap or '',
                    record.stretcher_required or '',
                    record.wheelchair_required or '',
                    record.ambulance_required or '',
                    record.pacemaker_operated or '',
                    record.chair_required_sitting or '',
                    record.special_attendant_required or '',
                    record.hearing_loss or '',
                    record.willing_attend_satsangs or '',
                    record.satsang_pickup_help_details or '',
                    record.other_special_requests or '',
                    record.emergency_contact_name or '',
                    record.emergency_contact_number or '',
                    record.emergency_contact_relation or '',
                    record.photo_filename or ''
                ])
            
            filename = f'sne_forms_{datetime.date.today().strftime("%Y%m%d")}.csv'
            
        elif table_name == 'blood_camp_donors':
            query = BloodCampDonor.query.order_by(BloodCampDonor.submission_timestamp.desc()).all()
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Donor ID', 'Submission Timestamp', 'Area', 'Name of Donor', "Father's/Husband's Name", 
                           'Date of Birth', 'Gender', 'Occupation', 'House No.', 'Sector', 'City', 'Mobile Number', 
                           'Blood Group', 'Allow Call', 'Donation Date', 'Donation Location', 'First Donation Date', 
                           'Total Donations', 'Status', 'Reason for Rejection', 'Age'])
            
            for record in query:
                # Calculate age from date of birth
                age = ''
                if record.date_of_birth:
                    today = datetime.date.today()
                    age = today.year - record.date_of_birth.year - ((today.month, today.day) < (record.date_of_birth.month, record.date_of_birth.day))
                
                writer.writerow([
                    record.donor_id,
                    record.submission_timestamp.strftime('%Y-%m-%d %H:%M') if record.submission_timestamp else '',
                    record.area or '',
                    record.name_of_donor,
                    record.father_husband_name or '',
                    record.date_of_birth.strftime('%Y-%m-%d') if record.date_of_birth else '',
                    record.gender or '',
                    record.occupation or '',
                    record.house_no or '',
                    record.sector or '',
                    record.city or '',
                    record.mobile_number or '',
                    record.blood_group or '',
                    record.allow_call or '',
                    record.donation_date.strftime('%Y-%m-%d') if record.donation_date else '',
                    record.donation_location or '',
                    record.first_donation_date.strftime('%Y-%m-%d') if record.first_donation_date else '',
                    record.total_donations or 0,
                    record.status or '',
                    record.reason_for_rejection or '',
                    age
                ])
            
            filename = f'blood_camp_donors_{datetime.date.today().strftime("%Y%m%d")}.csv'
            
        elif table_name == 'attendants':
            query = Attendant.query.order_by(Attendant.submission_date.desc()).all()
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Badge ID', 'Submission Date', 'Area', 'Centre', 'Name', 'Phone Number', 'Address', 
                           'Attendant Type', 'Photo Filename', 'SNE ID', 'SNE Name', 'SNE Gender', 'SNE Address', 
                           'SNE Photo Filename'])
            
            for record in query:
                writer.writerow([
                    record.badge_id,
                    record.submission_date.strftime('%Y-%m-%d') if record.submission_date else '',
                    record.area,
                    record.centre,
                    record.name,
                    record.phone_number or '',
                    record.address or '',
                    record.attendant_type,
                    record.photo_filename or '',
                    record.sne_id or '',
                    record.sne_name or '',
                    record.sne_gender or '',
                    record.sne_address or '',
                    record.sne_photo_filename or ''
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
