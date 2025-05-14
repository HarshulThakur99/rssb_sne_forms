# blood_camp_routes.py (Updated for circular import fix, RBAC, and ID format)
import datetime
import re
import logging
import collections # For Counter
from dateutil import parser as date_parser

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify,
    current_app # current_app can be useful for accessing app context if needed
)
from flask_login import login_required
# current_user is available globally via context_processor in app.py
from flask_login import current_user


# Import shared utilities and configuration
import utils
import config
# Import the decorator from the new decorators.py file
from decorators import permission_required

# --- Blueprint Definition ---
blood_camp_bp = Blueprint('blood_camp', __name__, url_prefix='/blood_camp')
logger = logging.getLogger(__name__)

# --- Helper Functions Specific to Blood Camp (Copied and adapted) ---

def find_donor_by_mobile(sheet, mobile_number):
    """Finds the LATEST Blood Camp donor entry by mobile number."""
    if not sheet:
        logger.error("Blood Camp sheet object is None in find_donor_by_mobile.")
        return None

    try:
        mobile_header = "Mobile Number"
        timestamp_header = "Submission Timestamp"
        mobile_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index(mobile_header) + 1
        timestamp_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index(timestamp_header) + 1
    except ValueError:
        logger.error(f"Headers '{mobile_header}' or '{timestamp_header}' missing in BLOOD_CAMP_SHEET_HEADERS.")
        return None # Indicate configuration error

    try:
        all_data = sheet.get_all_values()
        matching_entries = []
        if len(all_data) <= 1: # Only header row or empty
            return None

        cleaned_search_mobile = utils.clean_phone_number(mobile_number)
        if not cleaned_search_mobile: # Cannot search for empty mobile number
            return None

        header_row = config.BLOOD_CAMP_SHEET_HEADERS
        num_headers = len(header_row)

        for i, row in enumerate(all_data[1:], start=2): # Start from row 2 (1-based index)
            # Pad row if needed
            padded_row = row + [''] * (num_headers - len(row))
            current_row_list = padded_row[:num_headers] # Ensure correct length

            # Check if mobile number column exists and matches
            if len(current_row_list) >= mobile_col_index:
                sheet_mobile_raw = str(current_row_list[mobile_col_index - 1]).strip()
                cleaned_sheet_mobile = utils.clean_phone_number(sheet_mobile_raw)

                if cleaned_sheet_mobile == cleaned_search_mobile:
                    # Parse timestamp to find the latest entry
                    timestamp_str = str(current_row_list[timestamp_col_index - 1]).strip() if len(current_row_list) >= timestamp_col_index else ''
                    row_timestamp = datetime.datetime.min # Default for sorting if parse fails
                    try:
                        if timestamp_str:
                            row_timestamp = date_parser.parse(timestamp_str)
                    except date_parser.ParserError:
                        logger.warning(f"Could not parse timestamp '{timestamp_str}' for row {i}. Using default min date.")
                        pass # Use min date if timestamp is unparsable

                    matching_entries.append({
                        "data": dict(zip(header_row, current_row_list)), # Store data as dict
                        "timestamp": row_timestamp,
                        "row_index": i
                    })

        if not matching_entries:
            logger.info(f"No donor found with mobile number: {cleaned_search_mobile}")
            return None # No matching entries found

        # Find the entry with the latest timestamp
        latest_entry = max(matching_entries, key=lambda x: x["timestamp"])
        logger.info(f"Found latest entry for mobile {cleaned_search_mobile} at row {latest_entry['row_index']}")
        return latest_entry["data"] # Return the dictionary of the latest entry

    except Exception as e:
        logger.error(f"Error searching donor by mobile {mobile_number}: {e}", exc_info=True)
        return None # Indicate error

def generate_next_donor_id(sheet):
    """Generates the next sequential persistent Donor ID (e.g., BD0001, BD00001)."""
    if not sheet:
        logger.error("Blood Camp sheet object is None in generate_next_donor_id.")
        return None

    prefix = "BD"
    # Start with a default padding, e.g., 4 if that's the common existing format.
    # This will adjust based on the longest numeric part found.
    default_padding = 4 # Adjusted based on user feedback (e.g., BD0001)
    max_num = 0
    current_max_padding = default_padding # To track the length of the largest number found

    try:
        # Get Donor ID column index from config
        donor_id_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
    except ValueError:
        logger.error("Header 'Donor ID' not found in BLOOD_CAMP_SHEET_HEADERS.")
        return None

    try:
        # Fetch all values from the Donor ID column
        all_donor_ids_in_column = sheet.col_values(donor_id_col_index)
        
        # Iterate through existing IDs (skip header)
        for existing_id_str in all_donor_ids_in_column[1:]:
            existing_id = str(existing_id_str).strip().upper()
            if existing_id.startswith(prefix):
                try:
                    # Extract the numeric part
                    num_part_str = existing_id[len(prefix):]
                    if num_part_str.isdigit():
                        num_val = int(num_part_str)
                        max_num = max(max_num, num_val)
                        current_max_padding = max(current_max_padding, len(num_part_str)) # Update padding based on found IDs
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse number from existing Donor ID: {existing_id}")
                    pass # Ignore IDs that don't parse correctly

        next_num = max_num + 1 # If max_num is 0 (no prior IDs), next_num will be 1.
        
        # Determine the final padding: it should be at least default_padding,
        # but also accommodate the length of the next_num or the current_max_padding.
        final_padding = max(default_padding, len(str(next_num)), current_max_padding)

        next_donor_id = f"{prefix}{next_num:0{final_padding}d}" # Apply dynamic padding
        logger.info(f"Generated next Donor ID: {next_donor_id} (Padding: {final_padding})")
        return next_donor_id
    except Exception as e:
        logger.error(f"Error generating Donor ID: {e}", exc_info=True)
        return None

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
    """Endpoint called by JS to search for an existing donor by mobile."""
    mobile_number = request.args.get('mobile', '').strip()
    if not mobile_number or not re.fullmatch(r'\d{10}', mobile_number):
        return jsonify({"error": "Invalid mobile number format (must be 10 digits)."}), 400

    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
        return jsonify({"error": "Could not connect to donor database."}), 500

    donor_record = find_donor_by_mobile(sheet, mobile_number)
    if donor_record:
        return jsonify({"found": True, "donor": donor_record})
    else:
        return jsonify({"found": False})

@blood_camp_bp.route('/submit', methods=['POST'])
@login_required
@permission_required('submit_blood_camp_form')
def submit_form():
    """Handles blood camp form submission (new donor or new donation)."""
    form_data = request.form.to_dict()
    mobile_number = form_data.get('mobile_no', '').strip()

    if not mobile_number:
        flash("Mobile number is required.", "error")
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
        existing_donor_data = find_donor_by_mobile(sheet, cleaned_mobile_number)
        current_donation_date = form_data.get('donation_date', datetime.date.today().isoformat())
        submission_timestamp = datetime.datetime.now().isoformat()

        if existing_donor_data:
            # --- Record New Donation for Existing Donor ---
            donor_id = existing_donor_data.get("Donor ID")
            if not donor_id:
                 logger.error(f"Data Inconsistency: Donor found by mobile {cleaned_mobile_number} but has no Donor ID in record: {existing_donor_data}")
                 flash("Data inconsistency found for existing donor. Please contact support.", "error")
                 return redirect(url_for('blood_camp.form_page'))

            first_donation_date = existing_donor_data.get("First Donation Date", current_donation_date)
            try:
                total_donations = int(existing_donor_data.get("Total Donations", 0)) + 1
            except (ValueError, TypeError):
                total_donations = 1
            data_row = []
            for header in config.BLOOD_CAMP_SHEET_HEADERS:
                form_key = header.lower().replace("'", "").replace('/', '_').replace(' ', '_')
                if header == "Donor ID": value = donor_id
                elif header == "Submission Timestamp": value = submission_timestamp
                elif header == "Mobile Number": value = cleaned_mobile_number
                elif header == "Donation Date": value = current_donation_date
                elif header == "Donation Location": value = form_data.get('donation_location', '')
                elif header == "First Donation Date": value = first_donation_date
                elif header == "Total Donations": value = total_donations
                elif header in ["Status", "Reason for Rejection"]: value = '' # Reset status for new donation
                else:
                    value = form_data.get(form_key, existing_donor_data.get(header, ''))
                data_row.append(str(value))
            sheet.append_row(data_row, value_input_option='USER_ENTERED')
            flash(f'New donation recorded successfully for Donor ID: {donor_id} (Total Donations: {total_donations})', 'success')
        else:
            # --- Register New Donor ---
            new_donor_id = generate_next_donor_id(sheet)
            if not new_donor_id:
                flash("Critical error: Could not generate a new Donor ID.", "error")
                return redirect(url_for('blood_camp.form_page'))

            first_donation_date = current_donation_date
            total_donations = 1
            data_row = []
            for header in config.BLOOD_CAMP_SHEET_HEADERS:
                form_key = header.lower().replace("'", "").replace('/', '_').replace(' ', '_')
                if header == "Donor ID": value = new_donor_id
                elif header == "Submission Timestamp": value = submission_timestamp
                elif header == "Mobile Number": value = cleaned_mobile_number
                elif header == "Donation Date": value = current_donation_date
                elif header == "First Donation Date": value = first_donation_date
                elif header == "Total Donations": value = total_donations
                elif header in ["Status", "Reason for Rejection"]: value = '' # Initial status is empty
                else: value = form_data.get(form_key, '')
                data_row.append(str(value))
            sheet.append_row(data_row, value_input_option='USER_ENTERED')
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
                           current_year=current_year)

@blood_camp_bp.route('/get_donor_details/<donor_id>', methods=['GET'])
@login_required
@permission_required('get_blood_donor_details')
def get_donor_details_route(donor_id):
    """Endpoint called by JS to fetch donor details for status update."""
    # Regex updated to accept BD followed by 4 or more digits, case-insensitive for robustness
    # The .strip().upper() ensures we match against uppercase BD internally.
    cleaned_donor_id = donor_id.strip().upper()
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
    if not donor_id_from_form or not re.fullmatch(r'BD\d{4,}', donor_id_from_form):
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
    """Provides data for the blood camp dashboard charts."""
    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
        return jsonify({"error": "Could not connect to data source."}), 500
    try:
        all_values = sheet.get_all_values()
        default_data = {
            "kpis": {"registrations_today": 0, "accepted_total": 0, "rejected_total": 0, "acceptance_rate": 0.0},
            "blood_group_distribution": {}, "gender_distribution": {}, "age_group_distribution": {},
            "status_counts": {"Accepted": 0, "Rejected": 0, "Other/Pending": 0},
            "rejection_reasons": {}, "donor_types": {"First-Time": 0, "Repeat": 0},
            "communication_opt_in": {"Yes": 0, "No": 0, "Unknown": 0}
        }
        if not all_values or len(all_values) < 2: return jsonify(default_data)

        header_row = config.BLOOD_CAMP_SHEET_HEADERS; data_rows = all_values[1:]
        today_str = datetime.date.today().isoformat()
        try:
            donor_id_col = header_row.index("Donor ID"); timestamp_col = header_row.index("Submission Timestamp")
            dob_col = header_row.index("Date of Birth"); gender_col = header_row.index("Gender")
            blood_group_col = header_row.index("Blood Group"); allow_call_col = header_row.index("Allow Call")
            total_donations_col = header_row.index("Total Donations"); status_col = header_row.index("Status")
            reason_col = header_row.index("Reason for Rejection")
        except ValueError as e:
            logger.error(f"Dashboard Data: Missing header in BLOOD_CAMP_SHEET_HEADERS: {e}")
            return jsonify({"error": f"Server config error: Missing column '{e}'"}), 500

        latest_donor_entries = {}; num_headers = len(header_row)
        for row_index, row_list_vals in enumerate(data_rows):
            padded_row = row_list_vals + [''] * (num_headers - len(row_list_vals)); current_row_list_vals_data = padded_row[:num_headers]
            donor_id = str(current_row_list_vals_data[donor_id_col]).strip().upper()
            if not donor_id: continue
            timestamp_str = str(current_row_list_vals_data[timestamp_col]).strip(); row_timestamp = datetime.datetime.min
            try:
                if timestamp_str: row_timestamp = date_parser.parse(timestamp_str)
            except date_parser.ParserError: pass
            if donor_id not in latest_donor_entries or row_timestamp > latest_donor_entries[donor_id].get("timestamp", datetime.datetime.min):
                 latest_donor_entries[donor_id] = {"data": current_row_list_vals_data, "timestamp": row_timestamp}

        registrations_today = 0; accepted_count = 0; rejected_count = 0
        blood_groups = []; genders = []; ages = []; statuses = []
        rejection_reasons = []; donor_types_list = []; allow_calls = []

        for donor_id, entry in latest_donor_entries.items():
            row_data = entry["data"]; row_timestamp = entry["timestamp"]
            if row_timestamp and row_timestamp.date().isoformat() == today_str: registrations_today += 1
            stat = str(row_data[status_col]).strip().capitalize()
            if stat == "Accepted": accepted_count += 1; statuses.append("Accepted")
            elif stat == "Rejected":
                rejected_count += 1; statuses.append("Rejected")
                reason_text = str(row_data[reason_col]).strip()
                if reason_text: rejection_reasons.append(reason_text)
            else: statuses.append("Other/Pending")
            bg = str(row_data[blood_group_col]).strip().upper(); blood_groups.append(bg if bg else "Unknown")
            gen = str(row_data[gender_col]).strip().capitalize(); genders.append(gen if gen else "Unknown")
            age = utils.calculate_age_from_dob(str(row_data[dob_col]).strip())
            if age is not None: ages.append(age)
            donations_str = str(row_data[total_donations_col]).strip()
            try:
                num_donations = int(donations_str)
                donor_types_list.append("Repeat" if num_donations > 1 else "First-Time")
            except (ValueError, TypeError): donor_types_list.append("First-Time")
            call_pref = str(row_data[allow_call_col]).strip().capitalize()
            allow_calls.append(call_pref if call_pref in ["Yes", "No"] else "Unknown")

        total_decided = accepted_count + rejected_count
        acceptance_rate = (accepted_count / total_decided * 100) if total_decided > 0 else 0.0
        age_group_counts = collections.defaultdict(int)
        for age_val in ages: # Renamed age to age_val to avoid conflict
            binned = False
            for min_age, max_age in config.AGE_GROUP_BINS:
                if min_age <= age_val <= max_age: age_group_counts[f"{min_age}-{max_age}"] += 1; binned = True; break
            if not binned: age_group_counts["> 65" if age_val > 65 else "< 18"] += 1
        try: sorted_age_group_keys = sorted(age_group_counts.keys(), key=lambda x: int(re.search(r'\d+', x.replace('<','').replace('>','')).group()))
        except: sorted_age_group_keys = sorted(age_group_counts.keys()) # Fallback sort
        sorted_age_group_counts_final = {k: age_group_counts[k] for k in sorted_age_group_keys}

        final_status_counts = {"Accepted": collections.Counter(statuses).get("Accepted", 0),
                               "Rejected": collections.Counter(statuses).get("Rejected", 0),
                               "Other/Pending": collections.Counter(statuses).get("Other/Pending", 0)}
        return jsonify({
            "kpis": {"registrations_today": registrations_today, "accepted_total": accepted_count,
                     "rejected_total": rejected_count, "acceptance_rate": round(acceptance_rate, 1)},
            "blood_group_distribution": dict(collections.Counter(blood_groups)),
            "gender_distribution": dict(collections.Counter(genders)),
            "age_group_distribution": sorted_age_group_counts_final, # Use the sorted version
            "status_counts": final_status_counts,
            "rejection_reasons": dict(collections.Counter(rejection_reasons).most_common(10)),
            "donor_types": dict(collections.Counter(donor_types_list)),
            "communication_opt_in": dict(collections.Counter(allow_calls))
        })
    except Exception as e:
        logger.error(f"Dashboard Data: Error processing data: {e}", exc_info=True)
        return jsonify({"error": f"Server error processing dashboard data: {e}"}), 500

