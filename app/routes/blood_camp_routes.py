# blood_camp_routes.py (Updated for circular import fix, RBAC, and ID format)
import datetime
import re
import logging
import collections # For Counter
import threading # For thread-safe ID generation
import time # For retry delays
from dateutil import parser as date_parser

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify,
    current_app # current_app can be useful for accessing app context if needed
)
from flask_login import login_required
# current_user is available globally via context_processor in app.py
from flask_login import current_user


# Import shared utilities and configuration
from app import utils
from app import config
from app import db_helpers
from app.models import db, BloodCampDonor
from sqlalchemy import and_
# Import the decorator from the new decorators.py file
from app.decorators import permission_required

# --- Blueprint Definition ---
blood_camp_bp = Blueprint('blood_camp', __name__, url_prefix='/blood_camp')
logger = logging.getLogger(__name__)

# Thread-safe lock for atomic ID generation and row insertion
# This prevents race conditions when multiple users submit forms simultaneously
_donor_id_lock = threading.Lock()

# Mapping from sheet header names to incoming form field names where they differ.
# This resolves issues where certain headers were transformed into incorrect keys
# (e.g., "Name of Donor" -> "name_of_donor" but form uses "donor_name").
CUSTOM_HEADER_MAP = {
    "Name of Donor": "donor_name",
    "Father's/Husband's Name": "father_husband_name",
    "Date of Birth": "dob",
    "House No.": "house_no",
    "Mobile Number": "mobile_no",
    # "Area": "area"  # Removed: we now derive Area dynamically
}

# Build a centre->area lookup from SNE_BADGE_CONFIG to derive Area for Blood Camp entries.
try:
    from app.config import SNE_BADGE_CONFIG
    CENTRE_TO_AREA_MAP = {
        centre: area for area, centres in SNE_BADGE_CONFIG.items() for centre in centres.keys()
    }
except Exception:
    CENTRE_TO_AREA_MAP = {}

def infer_area(donation_location: str, city: str, existing_area: str = "") -> str:
    """Infer the Area value.
    Priority:
      1. Existing donor's Area if provided (keep historical consistency)
      2. Area derived from donation_location using CENTRE_TO_AREA_MAP
      3. City if it matches a known area key
      4. Empty string if none found
    """
    if existing_area:
        return existing_area
    loc = (donation_location or "").strip()
    if loc in CENTRE_TO_AREA_MAP:
        return CENTRE_TO_AREA_MAP[loc]
    city_val = (city or "").strip()
    if city_val in CENTRE_TO_AREA_MAP.values() or city_val in [*SNE_BADGE_CONFIG.keys()]:
        return city_val
    return ""

# Predefined rejection reasons for status updates
REJECTION_REASONS = [
    "High BP",
    "Low BP",
    "Cold/Cough",
    "Baby feeding",
    "Others"
]

# --- Helper Functions Specific to Blood Camp (Copied and adapted) ---

def find_donor_by_mobile_and_name(sheet, mobile_number, donor_name):
    """Finds the LATEST Blood Camp donor entry by mobile number AND name (PostgreSQL version).
    Sheet parameter is ignored - kept for compatibility.
    """
    # PostgreSQL version - sheet parameter ignored
    return db_helpers.find_donor_by_mobile_and_name_postgres(mobile_number, donor_name)

# --- Blood Camp Routes ---
@blood_camp_bp.route('/form')
@login_required
@permission_required('access_blood_camp_form')
def form_page():
    """Displays the Blood Camp donor registration/donation form."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('blood_camp_form.html',
                           today_date=today_date,
                           current_year=current_year,
                           # current_user is available globally
                           donation_locations=config.BLOOD_CAMP_DONATION_LOCATIONS)

@blood_camp_bp.route('/search_donor', methods=['GET'])
@login_required
@permission_required('search_blood_donor')
def search_donor_route():
    """Endpoint called by JS to search for an existing donor by mobile and name.
    PostgreSQL version - requires both mobile number and name for accurate donor identification."""
    mobile_number = request.args.get('mobile', '').strip()
    donor_name = request.args.get('name', '').strip()
    
    if not mobile_number or not re.fullmatch(r'\d{10}', mobile_number):
        return jsonify({"error": "Invalid mobile number format (must be 10 digits)."}), 400
    
    if not donor_name:
        return jsonify({"error": "Donor name is required."}), 400

    # Find donor using PostgreSQL (returns BloodCampDonor object or None)
    donor = find_donor_by_mobile_and_name(None, mobile_number, donor_name)
    
    if donor:
        # Convert donor object to dict format for frontend compatibility
        donor_dict = {
            "Donor ID": donor.donor_id,
            "Name of Donor": donor.name_of_donor,
            "Father's/Husband's Name": donor.father_husband_name or '',
            "Date of Birth": donor.date_of_birth.isoformat() if donor.date_of_birth else '',
            "Gender": donor.gender or '',
            "Occupation": donor.occupation or '',
            "House No.": donor.house_no or '',
            "Sector": donor.sector or '',
            "City": donor.city or '',
            "Mobile Number": donor.mobile_number,
            "Blood Group": donor.blood_group or '',
            "Allow Call": donor.allow_call or '',
            "Donation Date": donor.donation_date.isoformat() if donor.donation_date else '',
            "Donation Location": donor.donation_location or '',
            "First Donation Date": donor.first_donation_date.isoformat() if donor.first_donation_date else '',
            "Total Donations": donor.total_donations or 1,
            "Area": donor.area or '',
            "Status": donor.status or '',
            "Reason for Rejection": donor.reason_for_rejection or ''
        }
        return jsonify({"found": True, "donor": donor_dict})
    else:
        return jsonify({"found": False})

@blood_camp_bp.route('/submit', methods=['POST'])
@login_required
@permission_required('submit_blood_camp_form')
def submit_form():
    """Handles blood camp form submission (new donor or new donation).
    Now uses phone number + name to identify unique donors. PostgreSQL version."""
    form_data = request.form.to_dict()
    mobile_number = form_data.get('mobile_no', '').strip()
    donor_name = form_data.get('donor_name', '').strip()

    if not mobile_number:
        flash("Mobile number is required.", "error")
        return redirect(url_for('blood_camp.form_page'))
    
    if not donor_name:
        flash("Donor name is required.", "error")
        return redirect(url_for('blood_camp.form_page'))
        
    cleaned_mobile_number = utils.clean_phone_number(mobile_number)
    if len(cleaned_mobile_number) != 10:
        flash("Mobile number must be 10 digits.", "error")
        return redirect(url_for('blood_camp.form_page'))

    required_fields = ['donor_name', 'father_husband_name', 'dob', 'gender', 'city', 'blood_group', 'donation_date', 'donation_location']
    missing_fields = [field for field in required_fields if not form_data.get(field)]
    if missing_fields:
        flash(f"Missing required fields: {', '.join(missing_fields)}", "error")
        return redirect(url_for('blood_camp.form_page'))

    try:
        # Search by BOTH mobile number AND name (returns BloodCampDonor object or None)
        existing_donor_data = find_donor_by_mobile_and_name(None, cleaned_mobile_number, donor_name)
        current_donation_date = form_data.get('donation_date', datetime.date.today().isoformat())

        if existing_donor_data:
            # --- Record New Donation for Existing Donor ---
            donor_id = existing_donor_data.donor_id
            first_donation_date = existing_donor_data.first_donation_date or current_donation_date
            total_donations = (existing_donor_data.total_donations or 0) + 1
            
            # Derive area (prefer existing donor's area)
            derived_area = infer_area(
                form_data.get('donation_location', ''),
                form_data.get('city', ''),
                existing_donor_data.area or ''
            )
            
            # Parse donation date
            try:
                if isinstance(current_donation_date, str):
                    donation_date_obj = date_parser.parse(current_donation_date).date()
                else:
                    donation_date_obj = current_donation_date
            except:
                donation_date_obj = datetime.date.today()
            
            # Parse DOB
            try:
                dob_str = form_data.get('dob', '')
                dob_obj = date_parser.parse(dob_str).date() if dob_str else None
            except:
                dob_obj = None
            
            # Parse first donation date
            try:
                if isinstance(first_donation_date, str):
                    first_donation_date_obj = date_parser.parse(first_donation_date).date()
                else:
                    first_donation_date_obj = first_donation_date
            except:
                first_donation_date_obj = donation_date_obj
            
            # Create new donation record (each donation is a separate row/record)
            donor_dict = {
                'father_husband_name': form_data.get('father_husband_name', existing_donor_data.father_husband_name or ''),
                'date_of_birth': dob_obj,
                'gender': form_data.get('gender', existing_donor_data.gender or ''),
                'occupation': form_data.get('occupation', existing_donor_data.occupation or ''),
                'house_no': form_data.get('house_no', existing_donor_data.house_no or ''),
                'sector': form_data.get('sector', existing_donor_data.sector or ''),
                'city': form_data.get('city', existing_donor_data.city or ''),
                'blood_group': form_data.get('blood_group', existing_donor_data.blood_group or ''),
                'allow_call': form_data.get('allow_call', existing_donor_data.allow_call or ''),
                'donation_date': donation_date_obj,
                'donation_location': form_data.get('donation_location', ''),
                'first_donation_date': first_donation_date_obj,
                'total_donations': total_donations,
                'area': derived_area,
                'status': '',  # Reset status for new donation
                'reason_for_rejection': ''
            }
            
            new_donor, success = db_helpers.create_blood_donor(donor_id, cleaned_mobile_number, donor_name, **donor_dict)
            if success:
                flash(f'New donation recorded successfully for Donor ID: {donor_id} (Total Donations: {total_donations})', 'success')
            else:
                flash("Error recording new donation. Please try again.", "error")
        else:
            # --- Register New Donor ---
            first_donation_date = current_donation_date
            total_donations = 1
            derived_area = infer_area(
                form_data.get('donation_location', ''),
                form_data.get('city', ''),
                ''
            )
            
            # Generate new donor ID
            new_donor_id = db_helpers.get_next_donor_id_postgres(prefix="BD")
            
            # Parse donation date
            try:
                if isinstance(current_donation_date, str):
                    donation_date_obj = date_parser.parse(current_donation_date).date()
                else:
                    donation_date_obj = current_donation_date
            except:
                donation_date_obj = datetime.date.today()
            
            # Parse DOB
            try:
                dob_str = form_data.get('dob', '')
                dob_obj = date_parser.parse(dob_str).date() if dob_str else None
            except:
                dob_obj = None
            
            # Create new donor record
            donor_dict = {
                'father_husband_name': form_data.get('father_husband_name', ''),
                'date_of_birth': dob_obj,
                'gender': form_data.get('gender', ''),
                'occupation': form_data.get('occupation', ''),
                'house_no': form_data.get('house_no', ''),
                'sector': form_data.get('sector', ''),
                'city': form_data.get('city', ''),
                'blood_group': form_data.get('blood_group', ''),
                'allow_call': form_data.get('allow_call', ''),
                'donation_date': donation_date_obj,
                'donation_location': form_data.get('donation_location', ''),
                'first_donation_date': donation_date_obj,
                'total_donations': total_donations,
                'area': derived_area,
                'status': '',
                'reason_for_rejection': ''
            }
            
            new_donor, success = db_helpers.create_blood_donor(new_donor_id, cleaned_mobile_number, donor_name, **donor_dict)
            if success:
                flash(f'New donor registered successfully! Donor ID: {new_donor_id}', 'success')
            else:
                flash("Error registering new donor. Please try again.", "error")
                
        return redirect(url_for('blood_camp.form_page'))
    except Exception as e:
        logger.error(f"Error during blood camp submission: {e}", exc_info=True)
        flash(f"A server error occurred during submission: {e}", "error")
        return redirect(url_for('blood_camp.form_page'))

@blood_camp_bp.route('/status')
@login_required
@permission_required('access_blood_camp_status_update')
def status_page():
    """Displays the page to update blood donor status."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('blood_donor_status.html',
                           today_date=today_date,
                           current_year=current_year,
                           rejection_reasons=REJECTION_REASONS)

@blood_camp_bp.route('/get_donor_details/<donor_id>', methods=['GET'])
@login_required
@permission_required('get_blood_donor_details')
def get_donor_details_route(donor_id):
    """Endpoint called by JS to fetch donor details for status update. PostgreSQL version."""
    cleaned_donor_id = donor_id.strip().upper()
    # Allow numeric-only input and prepend BD automatically
    if re.fullmatch(r'\d{4,}', cleaned_donor_id):
        cleaned_donor_id = f"BD{cleaned_donor_id}"
    if not cleaned_donor_id or not re.fullmatch(r'BD\d{4,}', cleaned_donor_id):
        logger.warning(f"Invalid Donor ID format received in get_donor_details: {donor_id}")
        return jsonify({"error": "Invalid Donor ID format (e.g., BD0001)."}), 400

    try:
        # Get latest donor record by ID (most recent submission)
        donor = db_helpers.get_donor_by_id(cleaned_donor_id)
        
        if not donor:
            return jsonify({"found": False, "error": f"Donor ID '{cleaned_donor_id}' not found."}), 404
        
        return jsonify({
            "found": True,
            "name": donor.name_of_donor or 'N/A',
            "status": donor.status or '',
            "reason": donor.reason_for_rejection or ''
        })
    except Exception as e:
        logger.error(f"Error fetching donor details for {cleaned_donor_id}: {e}", exc_info=True)
        return jsonify({"error": "Server error fetching details."}), 500

@blood_camp_bp.route('/update_status', methods=['POST'])
@login_required
@permission_required('update_blood_donor_status')
def update_status_route():
    """Handles the submission to update a donor's status. PostgreSQL version."""
    donor_id_from_form = request.form.get('token_id', '').strip().upper()
    status = request.form.get('status', '').strip().capitalize()
    reason = request.form.get('reason', '').strip()

    # Validate donor ID
    if not donor_id_from_form:
        flash("A valid Donor ID (e.g., BD0001) is required.", "error")
        return redirect(url_for('blood_camp.status_page'))
    if re.fullmatch(r'\d{4,}', donor_id_from_form):
        donor_id_from_form = f"BD{donor_id_from_form}"
    if not re.fullmatch(r'BD\d{4,}', donor_id_from_form):
        flash("A valid Donor ID (e.g., BD0001) is required.", "error")
        return redirect(url_for('blood_camp.status_page'))
    if not status or status not in ['Accepted', 'Rejected']:
        flash("Status must be 'Accepted' or 'Rejected'.", "error")
        return redirect(url_for('blood_camp.status_page'))
    if status == 'Rejected' and not reason:
        flash("A reason is required when rejecting a donor.", "error")
        return redirect(url_for('blood_camp.status_page'))
    if status == 'Accepted':
        reason = ''  # Clear reason if accepted

    try:
        # Update donor status in PostgreSQL
        success = db_helpers.update_donor_status(donor_id_from_form, status, reason)
        
        if success:
            logger.info(f"Updated status to '{status}' for Donor ID {donor_id_from_form}.")
            flash(f"Status updated to '{status}' for Donor ID: {donor_id_from_form}", "success")
        else:
            flash(f"Donor ID '{donor_id_from_form}' not found.", "error")
            
        return redirect(url_for('blood_camp.status_page'))
    except Exception as e:
        logger.error(f"Error updating status for Donor ID {donor_id_from_form}: {e}", exc_info=True)
        flash(f"Error updating status: {e}", "error")
        return redirect(url_for('blood_camp.status_page'))

@blood_camp_bp.route('/dashboard')
@login_required
@permission_required('access_blood_camp_dashboard')
def dashboard_page():
    """Displays the blood camp dashboard."""
    logger.info("Dashboard route accessed by user: %s", current_user.id)
    current_year = datetime.date.today().year
    return render_template('dashboard.html', current_year=current_year)

@blood_camp_bp.route('/dashboard_data')
@login_required
@permission_required('view_blood_camp_dashboard_data')
def dashboard_data_route():
    """Provides data for the blood camp dashboard charts. PostgreSQL version.
    
    Optional Query Param:
        date=YYYY-MM-DD -> If provided, metrics are computed ONLY for entries on that date.
    """
    # Parse optional date filter
    date_str = request.args.get('date', '').strip()
    filter_date = None
    if date_str:
        try:
            filter_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            filter_date = None
    
    try:
        # Get all blood donors (latest entries per donor_id)
        from sqlalchemy import func
        
        # Subquery to get latest submission timestamp for each donor_id
        latest_subquery = db.session.query(
            BloodCampDonor.donor_id,
            func.max(BloodCampDonor.submission_timestamp).label('max_timestamp')
        ).group_by(BloodCampDonor.donor_id).subquery()
        
        # Join to get the full records of latest entries
        query = db.session.query(BloodCampDonor).join(
            latest_subquery,
            and_(
                BloodCampDonor.donor_id == latest_subquery.c.donor_id,
                BloodCampDonor.submission_timestamp == latest_subquery.c.max_timestamp
            )
        )
        
        # Apply date filter if provided
        if filter_date:
            query = query.filter(func.date(BloodCampDonor.submission_timestamp) == filter_date)
        
        donors = query.all()
        
        # Initialize aggregation containers
        today_str = datetime.date.today().isoformat()
        registrations_today = 0
        accepted_count = 0
        rejected_count = 0
        blood_groups = []
        genders = []
        ages = []
        statuses = []
        rejection_reasons = []
        donor_types_list = []
        allow_calls = []
        location_values = []
        
        # Process each donor
        for donor in donors:
            entry_date = donor.submission_timestamp.date() if donor.submission_timestamp else None
            
            # Registrations KPI logic
            if filter_date:
                if entry_date == filter_date:
                    registrations_today += 1
            else:
                if entry_date and entry_date.isoformat() == today_str:
                    registrations_today += 1
            
            # Status counts
            stat = (donor.status or '').strip().capitalize()
            if stat == "Accepted":
                accepted_count += 1
                statuses.append("Accepted")
            elif stat == "Rejected":
                rejected_count += 1
                statuses.append("Rejected")
                reason_text = (donor.reason_for_rejection or '').strip()
                if reason_text:
                    rejection_reasons.append(reason_text)
            else:
                statuses.append("Other/Pending")
            
            # Blood group distribution
            bg = (donor.blood_group or '').strip().upper()
            blood_groups.append(bg if bg else "Unknown")
            
            # Gender distribution
            gen = (donor.gender or '').strip().capitalize()
            genders.append(gen if gen else "Unknown")
            
            # Age distribution
            if donor.date_of_birth:
                age = utils.calculate_age_from_dob(donor.date_of_birth.isoformat())
                if age is not None:
                    ages.append(age)
            
            # Donor types (first-time vs repeat)
            num_donations = donor.total_donations or 1
            donor_types_list.append("Repeat" if num_donations > 1 else "First-Time")
            
            # Communication opt-in
            call_pref = (donor.allow_call or '').strip().capitalize()
            allow_calls.append(call_pref if call_pref in ["Yes", "No"] else "Unknown")
            
            # Donation locations
            loc_raw = (donor.donation_location or '').strip()
            location_values.append(loc_raw if loc_raw else "Unknown")
        
        # Calculate derived metrics
        total_decided = accepted_count + rejected_count
        acceptance_rate = (accepted_count / total_decided * 100) if total_decided > 0 else 0.0
        
        # Age group binning
        age_group_counts = collections.defaultdict(int)
        for age_val in ages:
            binned = False
            for min_age, max_age in config.AGE_GROUP_BINS:
                if min_age <= age_val <= max_age:
                    age_group_counts[f"{min_age}-{max_age}"] += 1
                    binned = True
                    break
            if not binned:
                age_group_counts["> 65" if age_val > 65 else "< 18"] += 1
        
        # Sort age groups
        try:
            sorted_age_group_keys = sorted(
                age_group_counts.keys(),
                key=lambda x: int(re.search(r'\d+', x.replace('<', '').replace('>', '')).group())
            )
        except Exception:
            sorted_age_group_keys = sorted(age_group_counts.keys())
        sorted_age_group_counts_final = {k: age_group_counts[k] for k in sorted_age_group_keys}
        
        # Build response
        response_payload = {
            "kpis": {
                "registrations_today": registrations_today,
                "accepted_total": accepted_count,
                "rejected_total": rejected_count,
                "acceptance_rate": round(acceptance_rate, 1)
            },
            "blood_group_distribution": dict(collections.Counter(blood_groups)),
            "gender_distribution": dict(collections.Counter(genders)),
            "age_group_distribution": sorted_age_group_counts_final,
            "status_counts": {
                "Accepted": collections.Counter(statuses).get("Accepted", 0),
                "Rejected": collections.Counter(statuses).get("Rejected", 0),
                "Other/Pending": collections.Counter(statuses).get("Other/Pending", 0)
            },
            "rejection_reasons": dict(collections.Counter(rejection_reasons).most_common(10)),
            "donor_types": dict(collections.Counter(donor_types_list)),
            "communication_opt_in": dict(collections.Counter(allow_calls)),
            "donation_location_distribution": dict(collections.Counter(location_values))
        }
        
        if filter_date:
            response_payload["filter_date"] = filter_date.isoformat()
        
        return jsonify(response_payload)
        
    except Exception as e:
        logger.error(f"Dashboard Data: Error processing data: {e}", exc_info=True)
        return jsonify({"error": f"Server error processing dashboard data: {e}"}), 500

@blood_camp_bp.route('/certificate_printer')
@login_required
@permission_required('access_blood_camp_certificate_printer')
def certificate_printer_page():
    """Displays the blood donation certificate printer form."""
    current_year = datetime.date.today().year
    # Default position values (can be adjusted in the form)
    default_positions = {
        'name_x': 50,
        'name_y': 80,
        'location_x': 50,
        'location_y': 110,
        'date_x': 50,
        'date_y': 140,
        'serial_x': 50,
        'serial_y': 170,
        'font_size': 12
    }
    return render_template('blood_certificate_printer_form.html',
                           current_year=current_year,
                           default_positions=default_positions)

@blood_camp_bp.route('/get_donor_for_certificate/<donor_id>')
@login_required
@permission_required('access_blood_camp_certificate_printer')
def get_donor_for_certificate(donor_id):
    """Fetches donor details for certificate printing (only accepted donors). PostgreSQL version."""
    donor_id = donor_id.strip().upper()
    
    # Auto-prepend BD if only digits provided
    if re.fullmatch(r'\d{4,}', donor_id):
        donor_id = f"BD{donor_id}"
    
    if not re.fullmatch(r'BD\d{4,}', donor_id):
        return jsonify({"found": False, "error": "Invalid Donor ID format."}), 400

    try:
        # Get latest donor record by ID
        donor = db_helpers.get_donor_by_id(donor_id)
        
        if not donor:
            return jsonify({"found": False, "error": f"Donor ID '{donor_id}' not found."}), 404
        
        return jsonify({
            "found": True,
            "name": donor.name_of_donor or 'N/A',
            "status": (donor.status or '').strip().capitalize(),
            "donation_date": donor.donation_date.isoformat() if donor.donation_date else '',
            "donation_location": donor.donation_location or ''
        })

    except Exception as e:
        logger.error(f"Error fetching donor details for certificate {donor_id}: {e}", exc_info=True)
        return jsonify({"error": "Server error fetching details."}), 500

@blood_camp_bp.route('/generate_certificate_pdf', methods=['POST'])
@login_required
@permission_required('access_blood_camp_certificate_printer')
def generate_certificate_pdf():
    """Generates a PDF for blood donation certificate with adjustable positions."""
    donor_id = request.form.get('donor_id', '').strip().upper()
    donor_name = request.form.get('donor_name', '').strip()
    donation_location = request.form.get('donation_location', '').strip()
    donation_date = request.form.get('donation_date', '').strip()
    hospital_serial_no = request.form.get('hospital_serial_no', '').strip()
    
    # Position parameters
    try:
        name_x = float(request.form.get('name_x', 50))
        name_y = float(request.form.get('name_y', 80))
        location_x = float(request.form.get('location_x', 50))
        location_y = float(request.form.get('location_y', 110))
        date_x = float(request.form.get('date_x', 50))
        date_y = float(request.form.get('date_y', 140))
        serial_x = float(request.form.get('serial_x', 50))
        serial_y = float(request.form.get('serial_y', 170))
        font_size = int(request.form.get('font_size', 12))
        orientation = request.form.get('orientation', 'landscape').strip().lower()
    except ValueError:
        flash("Invalid position values provided.", "error")
        return redirect(url_for('blood_camp.certificate_printer_page'))

    if not all([donor_id, donor_name, donation_location, donation_date, hospital_serial_no]):
        flash("All fields are required to generate a certificate.", "error")
        return redirect(url_for('blood_camp.certificate_printer_page'))

    try:
        # Generate the certificate PDF
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4, landscape
        from io import BytesIO

        buffer = BytesIO()
        # Use landscape or portrait orientation based on form selection
        pagesize = landscape(A4) if orientation == 'landscape' else A4
        c = canvas.Canvas(buffer, pagesize=pagesize)
        width, height = pagesize

        # Convert mm to points (1 mm = 2.834645669 points)
        mm_to_points = 2.834645669
        
        # Set font
        c.setFont("Helvetica-Bold", font_size)

        # Draw text at specified positions (converting mm to points, and flipping Y coordinate)
        # ReportLab uses bottom-left origin, so we need to adjust Y
        c.drawString(name_x * mm_to_points, height - (name_y * mm_to_points), donor_name)
        c.drawString(location_x * mm_to_points, height - (location_y * mm_to_points), donation_location)
        c.drawString(date_x * mm_to_points, height - (date_y * mm_to_points), donation_date)
        c.drawString(serial_x * mm_to_points, height - (serial_y * mm_to_points), hospital_serial_no)

        c.showPage()
        c.save()

        buffer.seek(0)
        
        from flask import make_response
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=certificate_{donor_id}.pdf'
        
        logger.info(f"Generated certificate for Donor ID: {donor_id}")
        return response

    except Exception as e:
        logger.error(f"Error generating certificate PDF for {donor_id}: {e}", exc_info=True)
        flash(f"Error generating certificate: {e}", "error")
        return redirect(url_for('blood_camp.certificate_printer_page'))

