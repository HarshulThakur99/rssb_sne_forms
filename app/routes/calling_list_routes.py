# calling_list_routes.py
import datetime
import logging
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

from flask import (
    Blueprint, render_template, request, jsonify, current_app
)
from flask_login import login_required, current_user

# Import shared utilities and configuration
from app import utils, config, db_helpers
from app.models import BloodCampDonor
from app.decorators import permission_required

# --- Blueprint Definition ---
calling_list_bp = Blueprint('calling_list', __name__, url_prefix='/calling_list')
logger = logging.getLogger(__name__)

# --- Eligibility Check Functions ---

def calculate_age(date_of_birth_str):
    """Calculate age from date of birth string. Returns None if invalid."""
    try:
        dob = date_parser.parse(date_of_birth_str)
        today = datetime.date.today()
        age = (today - dob.date()).days // 365
        return age
    except (ValueError, TypeError, AttributeError):
        logger.warning(f"Could not parse date of birth: {date_of_birth_str}")
        return None


def is_eligible_age(date_of_birth_str):
    """Check if age is <= 55 years."""
    age = calculate_age(date_of_birth_str)
    if age is None:
        return False
    return age <= 55


def is_last_donation_eligible(donation_date_str):
    """Check if last donation was at least 3 months ago."""
    if not donation_date_str or str(donation_date_str).strip() == "":
        # No donation date recorded - eligible to donate
        return True
    
    try:
        last_donation = date_parser.parse(donation_date_str)
        today = datetime.date.today()
        
        # Check if last donation is at least 3 months ago
        three_months_ago = today - relativedelta(months=3)
        return last_donation.date() <= three_months_ago
    except (ValueError, TypeError, AttributeError):
        logger.warning(f"Could not parse donation date: {donation_date_str}")
        # If we can't parse, consider it eligible
        return True


def is_allow_call_yes(allow_call_str):
    """Check if 'Allow Call' is 'Yes'."""
    if not allow_call_str:
        return False
    return str(allow_call_str).strip().lower() in ['yes', 'y', 'true', '1']


def filter_eligible_donors(donors_data, blood_group_filter):
    """
    Filter donors based on:
    1. Blood type (exact match)
    2. Age <= 55 years
    3. Last donation >= 3 months ago
    4. Allow Call = Yes
    
    Returns list of eligible donor records.
    """
    eligible_donors = []
    
    for donor_record in donors_data:
        # Apply blood group filter
        if blood_group_filter and blood_group_filter.strip():
            donor_blood = str(donor_record.get("Blood Group", "")).strip()
            if donor_blood.upper() != blood_group_filter.upper():
                continue
        
        # Check age eligibility
        dob = donor_record.get("Date of Birth", "")
        if not is_eligible_age(dob):
            continue
        
        # Check last donation eligibility (3 months)
        last_donation = donor_record.get("Donation Date", "")
        if not is_last_donation_eligible(last_donation):
            continue
        
        # Check Allow Call
        allow_call = donor_record.get("Allow Call", "")
        if not is_allow_call_yes(allow_call):
            continue
        
        # Add age to the record for display
        donor_record["Age_Calculated"] = calculate_age(dob)
        donor_record["Status_Eligible"] = "Yes"
        
        eligible_donors.append(donor_record)
    
    return eligible_donors


# --- Calling List Routes ---

@calling_list_bp.route('/')
@login_required
@permission_required('access_calling_list')
def calling_list_page():
    """Display the calling list page with filter options. PostgreSQL version."""
    try:
        # Get all blood donors from PostgreSQL
        all_donors = db_helpers.get_all_donors()
        
        # Extract unique blood groups
        blood_groups = sorted(set(
            d.blood_group.strip() 
            for d in all_donors 
            if d.blood_group and d.blood_group.strip()
        ))
        
        return render_template(
            'calling_list.html',
            blood_groups=blood_groups,
            eligible_donors=[]
        )
    except Exception as e:
        logger.error(f"Error loading calling list page: {e}", exc_info=True)
        return render_template(
            'calling_list.html',
            blood_groups=[],
            eligible_donors=[],
            error="Error loading data. Please try again."
        )


@calling_list_bp.route('/filter', methods=['POST'])
@login_required
@permission_required('filter_calling_list')
def filter_donors_route():
    """API endpoint to filter donors based on blood type. PostgreSQL version."""
    try:
        data = request.get_json()
        blood_group = data.get('blood_group', '').strip()
        
        if not blood_group:
            return jsonify({
                "success": False,
                "error": "Blood group is required."
            }), 400
        
        # Get all blood donors from PostgreSQL
        all_donors_objs = db_helpers.get_all_donors()
        
        # Convert to dict format for filter_eligible_donors function
        all_donors = []
        for donor in all_donors_objs:
            all_donors.append({
                "Donor ID": donor.donor_id,
                "Name of Donor": donor.name_of_donor,
                "Mobile Number": donor.mobile_number,
                "Blood Group": donor.blood_group or '',
                "City": donor.city or '',
                "Date of Birth": donor.date_of_birth.isoformat() if donor.date_of_birth else '',
                "Donation Date": donor.donation_date.isoformat() if donor.donation_date else '',
                "Sector": donor.sector or '',
                "House No.": donor.house_no or '',
                "Allow Call": donor.allow_call or ''
            })
        
        # Filter eligible donors
        eligible_donors = filter_eligible_donors(all_donors, blood_group)
        
        # Prepare response data (only include necessary fields)
        response_donors = []
        for donor in eligible_donors:
            response_donors.append({
                "Donor ID": donor.get("Donor ID", ""),
                "Name of Donor": donor.get("Name of Donor", ""),
                "Mobile Number": donor.get("Mobile Number", ""),
                "Blood Group": donor.get("Blood Group", ""),
                "City": donor.get("City", ""),
                "Age_Calculated": donor.get("Age_Calculated", ""),
                "Date of Birth": donor.get("Date of Birth", ""),
                "Donation Date": donor.get("Donation Date", ""),
                "Sector": donor.get("Sector", ""),
                "House No.": donor.get("House No.", "")
            })
        
        return jsonify({
            "success": True,
            "count": len(response_donors),
            "donors": response_donors
        })
    
    except Exception as e:
        logger.error(f"Error filtering donors: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Error filtering donors. Please try again."
        }), 500


@calling_list_bp.route('/export', methods=['POST'])
@login_required
@permission_required('export_calling_list')
def export_calling_list():
    """Export filtered calling list as CSV. PostgreSQL version."""
    try:
        from io import StringIO
        import csv
        
        data = request.get_json()
        blood_group = data.get('blood_group', '').strip()
        
        if not blood_group:
            return jsonify({
                "success": False,
                "error": "Blood group is required."
            }), 400
        
        # Get all blood donors from PostgreSQL
        all_donors_objs = db_helpers.get_all_donors()
        
        # Convert to dict format for filter_eligible_donors function
        all_donors = []
        for donor in all_donors_objs:
            all_donors.append({
                "Donor ID": donor.donor_id,
                "Name of Donor": donor.name_of_donor,
                "Mobile Number": donor.mobile_number,
                "Blood Group": donor.blood_group or '',
                "City": donor.city or '',
                "Date of Birth": donor.date_of_birth.isoformat() if donor.date_of_birth else '',
                "Donation Date": donor.donation_date.isoformat() if donor.donation_date else '',
                "Sector": donor.sector or '',
                "House No.": donor.house_no or '',
                "Allow Call": donor.allow_call or ''
            })
        
        # Filter eligible donors
        eligible_donors = filter_eligible_donors(all_donors, blood_group)
        
        # Create CSV
        output = StringIO()
        fieldnames = [
            "Donor ID", "Name of Donor", "Mobile Number", "Age", 
            "Blood Group", "City", "Sector", "House No.", "Donation Date"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for donor in eligible_donors:
            writer.writerow({
                "Donor ID": donor.get("Donor ID", ""),
                "Name of Donor": donor.get("Name of Donor", ""),
                "Mobile Number": donor.get("Mobile Number", ""),
                "Age": donor.get("Age_Calculated", ""),
                "Blood Group": donor.get("Blood Group", ""),
                "City": donor.get("City", ""),
                "Sector": donor.get("Sector", ""),
                "House No.": donor.get("House No.", ""),
                "Donation Date": donor.get("Donation Date", "")
            })
        
        csv_data = output.getvalue()
        return jsonify({
            "success": True,
            "csv": csv_data
        })
    
    except Exception as e:
        logger.error(f"Error exporting calling list: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Error exporting data. Please try again."
        }), 500
