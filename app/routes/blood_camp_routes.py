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
# Import shared utilities and configuration
from app import utils
from app import config
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
    """Finds the LATEST Blood Camp donor entry by mobile number AND name.
    This allows multiple family members to share the same phone number.
    Returns the most recent donation record for this specific person.
    """
    if not sheet:
        logger.error("Blood Camp sheet object is None in find_donor_by_mobile_and_name.")
        return None

    try:
        mobile_header = "Mobile Number"
        donor_name_header = "Name of Donor"
        timestamp_header = "Submission Timestamp"
        mobile_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index(mobile_header) + 1
        donor_name_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index(donor_name_header) + 1
        timestamp_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index(timestamp_header) + 1
    except ValueError:
        logger.error(f"Headers missing in BLOOD_CAMP_SHEET_HEADERS.")
        return None

    try:
        all_data = sheet.get_all_values()
        matching_entries = []
        if len(all_data) <= 1:
            return None

        cleaned_search_mobile = utils.clean_phone_number(mobile_number)
        cleaned_search_name = donor_name.strip().lower() if donor_name else ""
        
        if not cleaned_search_mobile or not cleaned_search_name:
            return None

        header_row = config.BLOOD_CAMP_SHEET_HEADERS
        num_headers = len(header_row)

        for i, row in enumerate(all_data[1:], start=2):
            padded_row = row + [''] * (num_headers - len(row))
            current_row_list = padded_row[:num_headers]

            if len(current_row_list) >= max(mobile_col_index, donor_name_col_index):
                sheet_mobile_raw = str(current_row_list[mobile_col_index - 1]).strip()
                cleaned_sheet_mobile = utils.clean_phone_number(sheet_mobile_raw)
                
                sheet_name_raw = str(current_row_list[donor_name_col_index - 1]).strip()
                cleaned_sheet_name = sheet_name_raw.lower()

                # Match on mobile number AND partial name match
                # This allows "harshul" to match "Harshul Thakur"
                mobile_matches = cleaned_sheet_mobile == cleaned_search_mobile
                name_matches = (cleaned_search_name in cleaned_sheet_name or 
                               cleaned_sheet_name in cleaned_search_name)
                
                if mobile_matches and name_matches:
                    
                    timestamp_str = str(current_row_list[timestamp_col_index - 1]).strip() if len(current_row_list) >= timestamp_col_index else ''
                    row_timestamp = datetime.datetime.min
                    try:
                        if timestamp_str:
                            row_timestamp = date_parser.parse(timestamp_str)
                    except date_parser.ParserError:
                        logger.warning(f"Could not parse timestamp '{timestamp_str}' for row {i}.")
                        pass

                    matching_entries.append({
                        "data": dict(zip(header_row, current_row_list)),
                        "timestamp": row_timestamp,
                        "row_index": i
                    })

        if not matching_entries:
            logger.info(f"No donor found with mobile {cleaned_search_mobile} and name matching '{donor_name}'")
            return None

        # Find the entry with the latest timestamp
        latest_entry = max(matching_entries, key=lambda x: x["timestamp"])
        matched_name = latest_entry["data"].get("Name of Donor", "Unknown")
        logger.info(f"Found '{matched_name}' (searched: '{donor_name}') at mobile {cleaned_search_mobile}, row {latest_entry['row_index']}")
        return latest_entry["data"]

    except Exception as e:
        logger.error(f"Error searching donor by mobile {mobile_number} and name {donor_name}: {e}", exc_info=True)
        return None

def generate_next_donor_id_and_reserve(sheet, data_row, max_retries=3):
    """Atomically generates next Donor ID and writes the row to prevent duplicates.
    
    This function uses a lock to ensure thread-safety and implements immediate write-after-generate
    to minimize the window for race conditions. Returns (success, donor_id, error_message).
    
    Args:
        sheet: Google Sheets worksheet object
        data_row: Complete data row to write (Donor ID will be updated in this list)
        max_retries: Maximum retry attempts if collision is detected
    
    Returns:
        tuple: (success: bool, donor_id: str, error_message: str)
    """
    if not sheet:
        logger.error("Blood Camp sheet object is None in generate_next_donor_id_and_reserve.")
        return (False, None, "Sheet object is None")

    prefix = "BD"
    default_padding = 4
    
    try:
        donor_id_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
    except ValueError:
        logger.error("Header 'Donor ID' not found in BLOOD_CAMP_SHEET_HEADERS.")
        return (False, None, "Configuration error: Donor ID header not found")

    for attempt in range(max_retries):
        try:
            # Acquire lock to make read-generate-write atomic
            with _donor_id_lock:
                # Fetch all existing Donor IDs
                all_donor_ids_in_column = sheet.col_values(donor_id_col_index)
                
                max_num = 0
                current_max_padding = default_padding
                
                # Find the maximum ID number (skip header row)
                for existing_id_str in all_donor_ids_in_column[1:]:
                    existing_id = str(existing_id_str).strip().upper()
                    if existing_id.startswith(prefix):
                        try:
                            num_part_str = existing_id[len(prefix):]
                            if num_part_str.isdigit():
                                num_val = int(num_part_str)
                                max_num = max(max_num, num_val)
                                current_max_padding = max(current_max_padding, len(num_part_str))
                        except (ValueError, IndexError):
                            logger.warning(f"Could not parse number from existing Donor ID: {existing_id}")
                            pass
                
                # Generate next ID
                next_num = max_num + 1
                final_padding = max(default_padding, len(str(next_num)), current_max_padding)
                next_donor_id = f"{prefix}{next_num:0{final_padding}d}"
                
                # Update the Donor ID in the data row
                data_row[donor_id_col_index - 1] = next_donor_id
                
                # Immediately write the row while still holding the lock
                sheet.append_row(data_row, value_input_option='USER_ENTERED')
                
                logger.info(f"Successfully generated and reserved Donor ID: {next_donor_id} (Attempt {attempt + 1})")
                return (True, next_donor_id, None)
                
        except Exception as e:
            logger.error(f"Error in generate_next_donor_id_and_reserve (attempt {attempt + 1}): {e}", exc_info=True)
            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff
            else:
                return (False, None, f"Failed after {max_retries} attempts: {str(e)}")
    
    return (False, None, "Max retries exceeded")

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
    Now requires both mobile number and name for accurate donor identification."""
    mobile_number = request.args.get('mobile', '').strip()
    donor_name = request.args.get('name', '').strip()
    
    if not mobile_number or not re.fullmatch(r'\d{10}', mobile_number):
        return jsonify({"error": "Invalid mobile number format (must be 10 digits)."}), 400
    
    if not donor_name:
        return jsonify({"error": "Donor name is required."}), 400

    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
        return jsonify({"error": "Could not connect to donor database."}), 500

    donor_record = find_donor_by_mobile_and_name(sheet, mobile_number, donor_name)
    if donor_record:
        return jsonify({"found": True, "donor": donor_record})
    else:
        return jsonify({"found": False})

@blood_camp_bp.route('/submit', methods=['POST'])
@login_required
@permission_required('submit_blood_camp_form')
def submit_form():
    """Handles blood camp form submission (new donor or new donation).
    Now uses phone number + name to identify unique donors."""
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

    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to the donor database.", "error")
        return redirect(url_for('blood_camp.form_page'))

    try:
        # Search by BOTH mobile number AND name
        existing_donor_data = find_donor_by_mobile_and_name(sheet, cleaned_mobile_number, donor_name)
        current_donation_date = form_data.get('donation_date', datetime.date.today().isoformat())
        submission_timestamp = datetime.datetime.now().isoformat()

        if existing_donor_data:
            # --- Record New Donation for Existing Donor ---
            donor_id = existing_donor_data.get("Donor ID")
            if not donor_id:
                 logger.error(f"Data Inconsistency: Donor found by mobile {cleaned_mobile_number} and name {donor_name} but has no Donor ID in record: {existing_donor_data}")
                 flash("Data inconsistency found for existing donor. Please contact support.", "error")
                 return redirect(url_for('blood_camp.form_page'))

            first_donation_date = existing_donor_data.get("First Donation Date", current_donation_date)
            try:
                total_donations = int(existing_donor_data.get("Total Donations", 0)) + 1
            except (ValueError, TypeError):
                total_donations = 1
            # Derive area (prefer existing donor's area)
            derived_area = infer_area(
                form_data.get('donation_location', ''),
                form_data.get('city', ''),
                existing_donor_data.get('Area', '')
            )
            data_row = []
            for header in config.BLOOD_CAMP_SHEET_HEADERS:
                # Determine the correct form key (explicit map overrides generic transformation)
                form_key = CUSTOM_HEADER_MAP.get(
                    header,
                    header.lower()
                          .replace("'", "")
                          .replace('.', '')  # remove period ("House No.")
                          .replace('/', '_')
                          .replace(' ', '_')
                )
                if header == "Donor ID": value = donor_id
                elif header == "Submission Timestamp": value = submission_timestamp
                elif header == "Mobile Number": value = cleaned_mobile_number
                elif header == "Donation Date": value = current_donation_date
                elif header == "Donation Location": value = form_data.get('donation_location', '')
                elif header == "First Donation Date": value = first_donation_date
                elif header == "Total Donations": value = total_donations
                elif header == "Area": value = derived_area
                elif header in ["Status", "Reason for Rejection"]: value = '' # Reset status for new donation
                else:
                    value = form_data.get(form_key, existing_donor_data.get(header, ''))
                data_row.append(str(value))
            sheet.append_row(data_row, value_input_option='USER_ENTERED')
            flash(f'New donation recorded successfully for Donor ID: {donor_id} (Total Donations: {total_donations})', 'success')
        else:
            # --- Register New Donor ---
            first_donation_date = current_donation_date
            total_donations = 1
            derived_area = infer_area(
                form_data.get('donation_location', ''),
                form_data.get('city', ''),
                ''
            )
            
            # Build data row with placeholder for Donor ID (will be set atomically)
            data_row = []
            for header in config.BLOOD_CAMP_SHEET_HEADERS:
                form_key = CUSTOM_HEADER_MAP.get(
                    header,
                    header.lower()
                          .replace("'", "")
                          .replace('.', '')
                          .replace('/', '_')
                          .replace(' ', '_')
                )
                if header == "Donor ID": value = ""  # Placeholder, will be set by atomic function
                elif header == "Submission Timestamp": value = submission_timestamp
                elif header == "Mobile Number": value = cleaned_mobile_number
                elif header == "Donation Date": value = current_donation_date
                elif header == "First Donation Date": value = first_donation_date
                elif header == "Total Donations": value = total_donations
                elif header == "Area": value = derived_area
                elif header in ["Status", "Reason for Rejection"]: value = '' # Initial status is empty
                else: value = form_data.get(form_key, '')
                data_row.append(str(value))
            
            # Atomically generate ID and write row (prevents duplicate IDs in concurrent submissions)
            success, new_donor_id, error_msg = generate_next_donor_id_and_reserve(sheet, data_row)
            if not success:
                flash(f"Critical error: Could not generate a new Donor ID. {error_msg}", "error")
                return redirect(url_for('blood_camp.form_page'))
            
            flash(f'New donor registered successfully! Donor ID: {new_donor_id}', 'success')
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
    """Endpoint called by JS to fetch donor details for status update."""
    # Regex updated to accept BD followed by 4 or more digits, case-insensitive for robustness
    # The .strip().upper() ensures we match against uppercase BD internally.
    cleaned_donor_id = donor_id.strip().upper()
    # Allow numeric-only input and prepend BD automatically
    if re.fullmatch(r'\d{4,}', cleaned_donor_id):
        cleaned_donor_id = f"BD{cleaned_donor_id}"
    if not cleaned_donor_id or not re.fullmatch(r'BD\d{4,}', cleaned_donor_id):
        logger.warning(f"Invalid Donor ID format received in get_donor_details: {donor_id}")
        return jsonify({"error": "Invalid Donor ID format (e.g., BD0001)."}), 400

    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
        return jsonify({"error": "Could not connect to donor database."}), 500
    try:
        all_data = sheet.get_all_values()
        matching_rows = []
        try:
            donor_id_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
            timestamp_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Submission Timestamp") + 1
            name_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Name of Donor") + 1
            status_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Status") + 1
            reason_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Reason for Rejection") + 1
        except ValueError as e:
            logger.error(f"Header config error for blood camp sheet: {e}")
            return jsonify({"error": "Server configuration error (headers)."}), 500

        num_headers = len(config.BLOOD_CAMP_SHEET_HEADERS)
        for i, row_list in enumerate(all_data[1:], start=2): # Start from row 2
             padded_row = row_list + [''] * (num_headers - len(row_list))
             current_row_list_vals = padded_row[:num_headers]
             if len(current_row_list_vals) >= donor_id_col_index and str(current_row_list_vals[donor_id_col_index - 1]).strip().upper() == cleaned_donor_id:
                 timestamp_str = str(current_row_list_vals[timestamp_col_index - 1]).strip() if len(current_row_list_vals) >= timestamp_col_index else ''
                 row_timestamp = datetime.datetime.min
                 try:
                     if timestamp_str: row_timestamp = date_parser.parse(timestamp_str)
                 except date_parser.ParserError: pass
                 matching_rows.append({
                     "index": i, "timestamp": row_timestamp,
                     "name": str(current_row_list_vals[name_col_index - 1]) if len(current_row_list_vals) >= name_col_index else 'N/A',
                     "status": str(current_row_list_vals[status_col_index - 1]) if len(current_row_list_vals) >= status_col_index else '',
                     "reason": str(current_row_list_vals[reason_col_index - 1]) if len(current_row_list_vals) >= reason_col_index else ''
                 })
        if not matching_rows:
            return jsonify({"found": False, "error": f"Donor ID '{cleaned_donor_id}' not found."}), 404
        latest_row_info = max(matching_rows, key=lambda x: x["timestamp"])
        return jsonify({
            "found": True, "name": latest_row_info["name"],
            "status": latest_row_info["status"], "reason": latest_row_info["reason"]
        })
    except Exception as e:
        logger.error(f"Error fetching donor details for {cleaned_donor_id}: {e}", exc_info=True)
        return jsonify({"error": "Server error fetching details."}), 500

@blood_camp_bp.route('/update_status', methods=['POST'])
@login_required
@permission_required('update_blood_donor_status')
def update_status_route():
    """Handles the submission to update a donor's status."""
    donor_id_from_form = request.form.get('token_id', '').strip().upper() # 'token_id' is the name in the HTML form
    status = request.form.get('status', '').strip().capitalize()
    reason = request.form.get('reason', '').strip()

    # Regex updated for Donor ID validation
    # Accept numeric-only input and prepend BD automatically
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
    if status == 'Accepted': reason = '' # Clear reason if accepted

    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to the donor database.", "error")
        return redirect(url_for('blood_camp.status_page'))
    try:
        all_data = sheet.get_all_values()
        matching_rows = []
        try:
            donor_id_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
            timestamp_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Submission Timestamp") + 1
            status_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Status") + 1
            reason_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Reason for Rejection") + 1
        except ValueError as e:
            logger.error(f"Header config error for blood camp sheet: {e}")
            flash("Server configuration error (headers).", "error")
            return redirect(url_for('blood_camp.status_page'))

        num_headers = len(config.BLOOD_CAMP_SHEET_HEADERS)
        for i, row_list in enumerate(all_data[1:], start=2): # Start from row 2
             padded_row = row_list + [''] * (num_headers - len(row_list))
             current_row_list_vals = padded_row[:num_headers]
             if len(current_row_list_vals) >= donor_id_col_index and str(current_row_list_vals[donor_id_col_index - 1]).strip().upper() == donor_id_from_form:
                 timestamp_str = str(current_row_list_vals[timestamp_col_index - 1]).strip() if len(current_row_list_vals) >= timestamp_col_index else ''
                 row_timestamp = datetime.datetime.min
                 try:
                     if timestamp_str: row_timestamp = date_parser.parse(timestamp_str)
                 except date_parser.ParserError: pass
                 matching_rows.append({"index": i, "timestamp": row_timestamp})
        if not matching_rows:
            flash(f"Donor ID '{donor_id_from_form}' not found.", "error")
            return redirect(url_for('blood_camp.status_page'))

        latest_row_info = max(matching_rows, key=lambda x: x["timestamp"])
        row_index_to_update = latest_row_info["index"]

        import gspread # For gspread.Cell
        updates = [
            gspread.Cell(row=row_index_to_update, col=status_col_index, value=status),
            gspread.Cell(row=row_index_to_update, col=reason_col_index, value=reason)
        ]
        sheet.update_cells(updates, value_input_option='USER_ENTERED')
        logger.info(f"Updated status to '{status}' for Donor ID {donor_id_from_form} in row {row_index_to_update}.")
        flash(f"Status updated to '{status}' for Donor ID: {donor_id_from_form}", "success")
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
    """Provides data for the blood camp dashboard charts.

    Optional Query Param:
        date=YYYY-MM-DD -> If provided, metrics (KPIs & distributions) are computed ONLY for latest entries whose
        latest submission timestamp's date matches this value. If omitted or invalid -> full dataset (existing behavior).
    """
    # Parse optional date filter
    date_str = request.args.get('date', '').strip()
    filter_date = None
    if date_str:
        try:
            filter_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            # Invalid date format; ignore and proceed with full data (do not error out for UX)
            filter_date = None
    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
        return jsonify({"error": "Could not connect to data source."}), 500
    try:
        # --- Fetch all rows ---
        all_values = sheet.get_all_values()
        default_data = {
            "kpis": {"registrations_today": 0, "accepted_total": 0, "rejected_total": 0, "acceptance_rate": 0.0},
            "blood_group_distribution": {}, "gender_distribution": {}, "age_group_distribution": {},
            "status_counts": {"Accepted": 0, "Rejected": 0, "Other/Pending": 0},
            "rejection_reasons": {}, "donor_types": {"First-Time": 0, "Repeat": 0},
            "communication_opt_in": {"Yes": 0, "No": 0, "Unknown": 0}
        }
        if not all_values or len(all_values) < 2:
            # If a filter date was supplied, include it in response even if empty
            if filter_date:
                default_data["filter_date"] = filter_date.isoformat()
            return jsonify(default_data)

        header_row = config.BLOOD_CAMP_SHEET_HEADERS; data_rows = all_values[1:]
        today_str = datetime.date.today().isoformat()
        try:
            donor_id_col = header_row.index("Donor ID"); timestamp_col = header_row.index("Submission Timestamp")
            dob_col = header_row.index("Date of Birth"); gender_col = header_row.index("Gender")
            blood_group_col = header_row.index("Blood Group"); allow_call_col = header_row.index("Allow Call")
            total_donations_col = header_row.index("Total Donations"); status_col = header_row.index("Status")
            reason_col = header_row.index("Reason for Rejection")
            donation_location_col = header_row.index("Donation Location") if "Donation Location" in header_row else None
        except ValueError as e:
            logger.error(f"Dashboard Data: Missing header in BLOOD_CAMP_SHEET_HEADERS: {e}")
            return jsonify({"error": f"Server config error: Missing column '{e}'"}), 500

        # --- Build map of latest entries per donor ---
        latest_donor_entries = {}; num_headers = len(header_row)
        for row_index, row_list_vals in enumerate(data_rows):
            padded_row = row_list_vals + [''] * (num_headers - len(row_list_vals))
            current_row_list_vals_data = padded_row[:num_headers]
            donor_id = str(current_row_list_vals_data[donor_id_col]).strip().upper()
            if not donor_id:
                continue
            timestamp_str = str(current_row_list_vals_data[timestamp_col]).strip()
            row_timestamp = datetime.datetime.min
            try:
                if timestamp_str:
                    row_timestamp = date_parser.parse(timestamp_str)
            except date_parser.ParserError:
                pass
            prev_ts = latest_donor_entries.get(donor_id, {}).get("timestamp", datetime.datetime.min)
            if row_timestamp > prev_ts:
                latest_donor_entries[donor_id] = {"data": current_row_list_vals_data, "timestamp": row_timestamp}

        # --- Aggregation containers ---
        registrations_today = 0  # If filtered: counts entries on filter date; else same behavior as original (today)
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

        for donor_id, entry in latest_donor_entries.items():
            row_data = entry["data"]
            row_timestamp = entry["timestamp"]
            entry_date = row_timestamp.date() if row_timestamp and row_timestamp != datetime.datetime.min else None

            # Filter logic
            if filter_date and entry_date != filter_date:
                continue

            # Registrations KPI logic
            if filter_date:
                if entry_date == filter_date:
                    registrations_today += 1
            else:
                if entry_date and entry_date.isoformat() == today_str:
                    registrations_today += 1

            stat = str(row_data[status_col]).strip().capitalize()
            if stat == "Accepted":
                accepted_count += 1
                statuses.append("Accepted")
            elif stat == "Rejected":
                rejected_count += 1
                statuses.append("Rejected")
                reason_text = str(row_data[reason_col]).strip()
                if reason_text:
                    rejection_reasons.append(reason_text)
            else:
                statuses.append("Other/Pending")

            bg = str(row_data[blood_group_col]).strip().upper()
            blood_groups.append(bg if bg else "Unknown")

            gen = str(row_data[gender_col]).strip().capitalize()
            genders.append(gen if gen else "Unknown")

            age = utils.calculate_age_from_dob(str(row_data[dob_col]).strip())
            if age is not None:
                ages.append(age)

            donations_str = str(row_data[total_donations_col]).strip()
            try:
                num_donations = int(donations_str)
                donor_types_list.append("Repeat" if num_donations > 1 else "First-Time")
            except (ValueError, TypeError):
                donor_types_list.append("First-Time")

            call_pref = str(row_data[allow_call_col]).strip().capitalize()
            allow_calls.append(call_pref if call_pref in ["Yes", "No"] else "Unknown")

            if donation_location_col is not None:
                loc_raw = str(row_data[donation_location_col]).strip()
                location_values.append(loc_raw if loc_raw else "Unknown")

        # --- Derived metrics ---
        total_decided = accepted_count + rejected_count
        acceptance_rate = (accepted_count / total_decided * 100) if total_decided > 0 else 0.0

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
        try:
            sorted_age_group_keys = sorted(
                age_group_counts.keys(),
                key=lambda x: int(re.search(r'\d+', x.replace('<', '').replace('>', '')).group())
            )
        except Exception:
            sorted_age_group_keys = sorted(age_group_counts.keys())
        sorted_age_group_counts_final = {k: age_group_counts[k] for k in sorted_age_group_keys}

        final_status_counts = {
            "Accepted": collections.Counter(statuses).get("Accepted", 0),
            "Rejected": collections.Counter(statuses).get("Rejected", 0),
            "Other/Pending": collections.Counter(statuses).get("Other/Pending", 0)
        }

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
            "status_counts": final_status_counts,
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
    """Fetches donor details for certificate printing (only accepted donors)."""
    donor_id = donor_id.strip().upper()
    
    # Auto-prepend BD if only digits provided
    if re.fullmatch(r'\d{4,}', donor_id):
        donor_id = f"BD{donor_id}"
    
    if not re.fullmatch(r'BD\d{4,}', donor_id):
        return jsonify({"found": False, "error": "Invalid Donor ID format."}), 400

    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
        return jsonify({"error": "Could not connect to donor database."}), 500

    try:
        all_data = sheet.get_all_values()
        if len(all_data) <= 1:
            return jsonify({"found": False, "error": "No data in database."}), 404

        try:
            donor_id_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
            name_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Name of Donor") + 1
            status_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Status") + 1
            donation_date_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Donation Date") + 1
            donation_location_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Donation Location") + 1
            timestamp_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Submission Timestamp") + 1
        except ValueError as e:
            logger.error(f"Header config error: {e}")
            return jsonify({"error": "Server configuration error."}), 500

        matching_rows = []
        num_headers = len(config.BLOOD_CAMP_SHEET_HEADERS)

        for i, row_list in enumerate(all_data[1:], start=2):
            padded_row = row_list + [''] * (num_headers - len(row_list))
            current_row_list_vals = padded_row[:num_headers]
            
            if len(current_row_list_vals) >= donor_id_col_index:
                sheet_donor_id = str(current_row_list_vals[donor_id_col_index - 1]).strip().upper()
                
                if sheet_donor_id == donor_id:
                    timestamp_str = str(current_row_list_vals[timestamp_col_index - 1]).strip() if len(current_row_list_vals) >= timestamp_col_index else ''
                    row_timestamp = datetime.datetime.min
                    try:
                        if timestamp_str:
                            row_timestamp = date_parser.parse(timestamp_str)
                    except date_parser.ParserError:
                        pass
                    
                    matching_rows.append({
                        "timestamp": row_timestamp,
                        "name": str(current_row_list_vals[name_col_index - 1]) if len(current_row_list_vals) >= name_col_index else 'N/A',
                        "status": str(current_row_list_vals[status_col_index - 1]).strip().capitalize() if len(current_row_list_vals) >= status_col_index else '',
                        "donation_date": str(current_row_list_vals[donation_date_col_index - 1]).strip() if len(current_row_list_vals) >= donation_date_col_index else '',
                        "donation_location": str(current_row_list_vals[donation_location_col_index - 1]).strip() if len(current_row_list_vals) >= donation_location_col_index else ''
                    })

        if not matching_rows:
            return jsonify({"found": False, "error": f"Donor ID '{donor_id}' not found."}), 404

        latest_row_info = max(matching_rows, key=lambda x: x["timestamp"])
        
        return jsonify({
            "found": True,
            "name": latest_row_info["name"],
            "status": latest_row_info["status"],
            "donation_date": latest_row_info["donation_date"],
            "donation_location": latest_row_info["donation_location"]
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

