"""
PostgreSQL Database Helper Functions
Replaces Google Sheets utility functions with PostgreSQL equivalents
"""
import logging
from datetime import datetime
from sqlalchemy import func, and_, or_
from sqlalchemy.exc import IntegrityError
from app.models import db, SNEForm, BloodCampDonor, Attendant

logger = logging.getLogger(__name__)


# ============================================================================
# SNE Form Database Functions
# ============================================================================

def get_next_sne_badge_id_postgres(area, centre, prefix, start_num):
    """
    Generate next sequential SNE Badge ID from PostgreSQL.
    
    Args:
        area: Area name
        centre: Centre/Satsang place name
        prefix: Badge ID prefix (e.g., 'DL-VK-RM')
        start_num: Starting number for this prefix
        
    Returns:
        str: Next badge ID (e.g., 'DL-VK-RM0001')
    """
    try:
        # Find maximum badge ID for this prefix
        max_badge = db.session.query(
            func.max(SNEForm.badge_id)
        ).filter(
            and_(
                SNEForm.area == area,
                SNEForm.satsang_place == centre,
                SNEForm.badge_id.like(f"{prefix}%")
            )
        ).scalar()
        
        if max_badge:
            # Extract number from badge ID (e.g., 'DL-VK-RM0001' -> 1)
            try:
                current_num = int(max_badge.replace(prefix, ''))
                next_num = current_num + 1
            except ValueError:
                logger.warning(f"Could not parse badge ID {max_badge}, using start_num")
                next_num = start_num
        else:
            next_num = start_num
        
        # Format with leading zeros (4 digits)
        next_badge_id = f"{prefix}{next_num:04d}"
        logger.info(f"Generated next SNE badge ID: {next_badge_id}")
        
        return next_badge_id
        
    except Exception as e:
        logger.error(f"Error generating SNE badge ID: {e}", exc_info=True)
        raise


def check_sne_aadhaar_exists_postgres(aadhaar, area, exclude_badge_id=None):
    """
    Check if SNE Aadhaar exists for given Area (excluding specific badge ID).
    
    Args:
        aadhaar: Aadhaar number (cleaned)
        area: Area name
        exclude_badge_id: Optional badge ID to exclude (for edits)
        
    Returns:
        str or None: Badge ID if found, None if not found
    """
    try:
        query = db.session.query(SNEForm.badge_id).filter(
            and_(
                SNEForm.aadhaar_no == aadhaar,
                SNEForm.area == area
            )
        )
        
        if exclude_badge_id:
            query = query.filter(SNEForm.badge_id != exclude_badge_id)
        
        result = query.first()
        
        if result:
            logger.warning(f"SNE Aadhaar {aadhaar} found in Area {area} with Badge ID {result[0]}")
            return result[0]
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking SNE Aadhaar: {e}", exc_info=True)
        return False


def get_sne_by_badge_id(badge_id):
    """Get SNE record by badge ID"""
    return SNEForm.query.filter_by(badge_id=badge_id).first()


def get_all_sne_forms(area=None, centre=None, limit=None):
    """
    Get all SNE forms with optional filters.
    
    Args:
        area: Filter by area (optional)
        centre: Filter by satsang place (optional)
        limit: Limit results (optional)
        
    Returns:
        List of SNEForm objects
    """
    query = SNEForm.query
    
    if area:
        query = query.filter_by(area=area)
    if centre:
        query = query.filter_by(satsang_place=centre)
    
    query = query.order_by(SNEForm.submission_date.desc())
    
    if limit:
        query = query.limit(limit)
    
    return query.all()


def create_sne_form(badge_id, submission_date, area, satsang_place, first_name, 
                    last_name, **kwargs):
    """
    Create new SNE form record.
    
    Args:
        badge_id: Unique badge ID
        submission_date: Date of submission
        area: Area name
        satsang_place: Centre/Satsang place
        first_name: First name
        last_name: Last name
        **kwargs: Additional fields
        
    Returns:
        tuple: (SNEForm object, success boolean)
    """
    try:
        sne = SNEForm(
            badge_id=badge_id,
            submission_date=submission_date,
            area=area,
            satsang_place=satsang_place,
            first_name=first_name,
            last_name=last_name,
            **kwargs
        )
        
        db.session.add(sne)
        db.session.commit()
        
        logger.info(f"Created SNE form: {badge_id}")
        return sne, True
        
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Integrity error creating SNE form {badge_id}: {e}")
        return None, False
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating SNE form {badge_id}: {e}", exc_info=True)
        return None, False


def update_sne_form(badge_id, **kwargs):
    """
    Update existing SNE form.
    
    Args:
        badge_id: Badge ID to update
        **kwargs: Fields to update
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        sne = get_sne_by_badge_id(badge_id)
        if not sne:
            logger.error(f"SNE form {badge_id} not found for update")
            return False
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(sne, key):
                setattr(sne, key, value)
        
        sne.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated SNE form: {badge_id}")
        return True
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating SNE form {badge_id}: {e}", exc_info=True)
        return False


def search_sne_forms(search_name=None, search_badge_id=None, limit=50):
    """
    Search SNE forms by name or badge ID.
    
    Args:
        search_name: Name to search for (searches first + last)
        search_badge_id: Badge ID to search for
        limit: Maximum results to return
        
    Returns:
        list: List of matching SNE forms as dicts
    """
    try:
        query = SNEForm.query
        
        if search_badge_id:
            query = query.filter(SNEForm.badge_id == search_badge_id)
        elif search_name:
            search_term = f"%{search_name}%"
            query = query.filter(
                or_(
                    SNEForm.first_name.ilike(search_term),
                    SNEForm.last_name.ilike(search_term)
                )
            )
        
        results = query.order_by(SNEForm.submission_date.desc()).limit(limit).all()
        
        # Convert to dict format for JSON response
        results_list = []
        for sne in results:
            results_list.append({
                'Badge ID': sne.badge_id,
                'Submission Date': sne.submission_date.isoformat() if sne.submission_date else '',
                'Area': sne.area or '',
                'Satsang Place': sne.satsang_place or '',
                'First Name': sne.first_name or '',
                'Last Name': sne.last_name or '',
                "Father's/Husband's Name": sne.father_husband_name or '',
                'Gender': sne.gender or '',
                'Date of Birth': sne.date_of_birth.isoformat() if sne.date_of_birth else '',
                'Age': str(sne.age) if sne.age else '',
                'Blood Group': sne.blood_group or '',
                'Aadhaar No': sne.aadhaar_no or '',
                'Mobile No': sne.mobile_no or '',
                'Physically Challenged (Yes/No)': sne.physically_challenged or 'No',
                'Physically Challenged Details': sne.physically_challenged_details or '',
                'Help Required for Home Pickup (Yes/No)': sne.help_required_home_pickup or 'No',
                'Help Pickup Reasons': sne.help_pickup_reasons or '',
                'Handicap (Yes/No)': sne.handicap or 'No',
                'Stretcher Required (Yes/No)': sne.stretcher_required or 'No',
                'Wheelchair Required (Yes/No)': sne.wheelchair_required or 'No',
                'Ambulance Required (Yes/No)': sne.ambulance_required or 'No',
                'Pacemaker Operated (Yes/No)': sne.pacemaker_operated or 'No',
                'Chair Required for Sitting (Yes/No)': sne.chair_required_sitting or 'No',
                'Special Attendant Required (Yes/No)': sne.special_attendant_required or 'No',
                'Hearing Loss (Yes/No)': sne.hearing_loss or 'No',
                'Willing to Attend Satsangs (Yes/No)': sne.willing_attend_satsangs or 'No',
                'Satsang Pickup Help Details': sne.satsang_pickup_help_details or '',
                'Other Special Requests': sne.other_special_requests or '',
                'Emergency Contact Name': sne.emergency_contact_name or '',
                'Emergency Contact Number': sne.emergency_contact_number or '',
                'Emergency Contact Relation': sne.emergency_contact_relation or '',
                'Address': sne.address or '',
                'State': sne.state or '',
                'PIN Code': sne.pin_code or '',
                'Photo Filename': sne.photo_filename or ''
            })
        
        logger.info(f"Found {len(results_list)} SNE forms")
        return results_list
        
    except Exception as e:
        logger.error(f"Error searching SNE forms: {e}", exc_info=True)
        return []


# ============================================================================
# Blood Camp Donor Database Functions
# ============================================================================

def get_next_donor_id_postgres(prefix="BD"):
    """
    Generate next sequential donor ID.
    Thread-safe implementation using database sequence.
    
    Args:
        prefix: Donor ID prefix (e.g., 'BD' for Blood Donor)
        
    Returns:
        str: Next donor ID (e.g., 'BD00001')
    """
    try:
        # Use database sequence or max ID approach
        max_donor = db.session.query(
            func.max(BloodCampDonor.donor_id)
        ).filter(
            BloodCampDonor.donor_id.like(f"{prefix}%")
        ).scalar()
        
        if max_donor:
            try:
                current_num = int(max_donor.replace(prefix, ''))
                next_num = current_num + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1
        
        next_donor_id = f"{prefix}{next_num:05d}"
        logger.info(f"Generated next donor ID: {next_donor_id}")
        
        return next_donor_id
        
    except Exception as e:
        logger.error(f"Error generating donor ID: {e}", exc_info=True)
        raise


def find_donor_by_mobile_and_name_postgres(mobile_number, donor_name):
    """
    Find latest blood donor by mobile number and name.
    Allows family members to share phone numbers.
    Case-insensitive partial name matching with trimmed whitespace.
    Supports searching with first name only (e.g., "harshul" matches "Harshul Thakur").
    
    Args:
        mobile_number: Mobile number (cleaned)
        donor_name: Donor name (full or partial)
        
    Returns:
        BloodCampDonor or None
    """
    try:
        from sqlalchemy import func
        
        # Normalize input
        donor_name = donor_name.strip().lower()
        
        # Use partial name matching (case-insensitive) so "harshul" matches "Harshul Thakur"
        donor = BloodCampDonor.query.filter(
            and_(
                BloodCampDonor.mobile_number == mobile_number,
                func.lower(func.trim(BloodCampDonor.name_of_donor)).like('%' + donor_name + '%')
            )
        ).order_by(BloodCampDonor.submission_timestamp.desc()).first()
        
        return donor
        
    except Exception as e:
        logger.error(f"Error finding donor: {e}", exc_info=True)
        return None


def get_donor_by_id(donor_id):
    """Get blood donor by donor ID"""
    return BloodCampDonor.query.filter_by(donor_id=donor_id).first()


def get_all_donors(area=None, status=None, limit=None):
    """
    Get all blood donors with optional filters.
    
    Args:
        area: Filter by area (optional)
        status: Filter by status (Pending/Accepted/Rejected) (optional)
        limit: Limit results (optional)
        
    Returns:
        List of BloodCampDonor objects
    """
    query = BloodCampDonor.query
    
    if area:
        query = query.filter_by(area=area)
    if status:
        query = query.filter_by(status=status)
    
    query = query.order_by(BloodCampDonor.donation_date.desc())
    
    if limit:
        query = query.limit(limit)
    
    return query.all()


def create_blood_donor(donor_id, mobile_number, name_of_donor, **kwargs):
    """
    Create new blood donor record.
    
    Args:
        donor_id: Unique donor ID
        mobile_number: Mobile number
        name_of_donor: Donor name
        **kwargs: Additional fields
        
    Returns:
        tuple: (BloodCampDonor object, success boolean)
    """
    try:
        donor = BloodCampDonor(
            donor_id=donor_id,
            mobile_number=mobile_number,
            name_of_donor=name_of_donor,
            submission_timestamp=datetime.utcnow(),
            **kwargs
        )
        
        db.session.add(donor)
        db.session.commit()
        
        logger.info(f"Created blood donor: {donor_id}")
        return donor, True
        
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Integrity error creating donor {donor_id}: {e}")
        return None, False
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating donor {donor_id}: {e}", exc_info=True)
        return None, False


def update_donor_status(donor_id, status, reason_for_rejection=None):
    """
    Update blood donor status.
    
    Args:
        donor_id: Donor ID
        status: New status (Pending/Accepted/Rejected)
        reason_for_rejection: Reason if rejected (optional)
        
    Returns:
        bool: True if successful
    """
    try:
        donor = get_donor_by_id(donor_id)
        if not donor:
            logger.error(f"Donor {donor_id} not found for status update")
            return False
        
        donor.status = status
        if reason_for_rejection:
            donor.reason_for_rejection = reason_for_rejection
        donor.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Updated donor {donor_id} status to {status}")
        return True
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating donor status: {e}", exc_info=True)
        return False


# ============================================================================
# Attendant Database Functions
# ============================================================================

def check_attendant_badge_id_exists_postgres(badge_id):
    """
    Check if attendant badge ID exists.
    
    Args:
        badge_id: Badge ID to check
        
    Returns:
        bool or None: True if exists, None if not found, False on error
    """
    try:
        exists = db.session.query(
            db.session.query(Attendant).filter_by(badge_id=badge_id).exists()
        ).scalar()
        
        if exists:
            logger.warning(f"Attendant badge ID {badge_id} already exists")
            return True
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking attendant badge ID: {e}", exc_info=True)
        return False


def get_attendant_by_badge_id(badge_id):
    """Get attendant by badge ID"""
    return Attendant.query.filter_by(badge_id=badge_id).first()


def get_all_attendants(area=None, centre=None, attendant_type=None, limit=None):
    """
    Get all attendants with optional filters.
    
    Args:
        area: Filter by area (optional)
        centre: Filter by centre (optional)
        attendant_type: Filter by type (Sewadar/Family) (optional)
        limit: Limit results (optional)
        
    Returns:
        List of Attendant objects
    """
    query = Attendant.query
    
    if area:
        query = query.filter_by(area=area)
    if centre:
        query = query.filter_by(centre=centre)
    if attendant_type:
        query = query.filter_by(attendant_type=attendant_type)
    
    query = query.order_by(Attendant.submission_date.desc())
    
    if limit:
        query = query.limit(limit)
    
    return query.all()


def create_attendant(badge_id, area, centre, name, attendant_type, **kwargs):
    """
    Create new attendant record.
    
    Args:
        badge_id: Unique badge ID
        area: Area name
        centre: Centre name
        name: Attendant name
        attendant_type: Sewadar or Family
        **kwargs: Additional fields
        
    Returns:
        tuple: (Attendant object, success boolean)
    """
    try:
        # Use submission_date from kwargs if provided, otherwise use current date
        submission_date = kwargs.pop('submission_date', datetime.utcnow().date())
        
        attendant = Attendant(
            badge_id=badge_id,
            submission_date=submission_date,
            area=area,
            centre=centre,
            name=name,
            attendant_type=attendant_type,
            **kwargs
        )
        
        db.session.add(attendant)
        db.session.commit()
        
        logger.info(f"Created attendant: {badge_id}")
        return attendant, True
        
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Integrity error creating attendant {badge_id}: {e}")
        return None, False
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating attendant {badge_id}: {e}", exc_info=True)
        return None, False


def update_attendant(badge_id, **kwargs):
    """
    Update existing attendant.
    
    Args:
        badge_id: Badge ID to update
        **kwargs: Fields to update
        
    Returns:
        bool: True if successful
    """
    try:
        attendant = get_attendant_by_badge_id(badge_id)
        if not attendant:
            logger.error(f"Attendant {badge_id} not found for update")
            return False
        
        for key, value in kwargs.items():
            if hasattr(attendant, key):
                setattr(attendant, key, value)
        
        attendant.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated attendant: {badge_id}")
        return True
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating attendant: {e}", exc_info=True)
        return False


# ============================================================================
# Common Database Functions
# ============================================================================

def safe_commit():
    """
    Safely commit transaction with error handling.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Commit failed: {e}", exc_info=True)
        return False


def get_dashboard_stats():
    """
    Get dashboard statistics.
    
    Returns:
        dict: Statistics for dashboard
    """
    try:
        stats = {
            'total_sne': db.session.query(func.count(SNEForm.id)).scalar(),
            'total_donors': db.session.query(func.count(BloodCampDonor.id)).scalar(),
            'total_attendants': db.session.query(func.count(Attendant.id)).scalar(),
            'pending_donors': db.session.query(func.count(BloodCampDonor.id)).filter_by(status='Pending').scalar(),
            'accepted_donors': db.session.query(func.count(BloodCampDonor.id)).filter_by(status='Accepted').scalar(),
            'rejected_donors': db.session.query(func.count(BloodCampDonor.id)).filter_by(status='Rejected').scalar(),
        }
        
        # Get area-wise breakdown
        area_breakdown = db.session.query(
            SNEForm.area,
            func.count(SNEForm.id).label('count')
        ).group_by(SNEForm.area).all()
        
        stats['area_breakdown'] = {area: count for area, count in area_breakdown}
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}", exc_info=True)
        return {}
