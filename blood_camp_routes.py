# blood_camp_routes.py
import datetime
import re
import logging
import collections
from dateutil import parser as date_parser

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify,
    current_app
)
from flask_login import login_required, current_user
import gspread

# Import shared utilities and configuration
import utils
import config

# --- Blueprint Definition ---
blood_camp_bp = Blueprint('blood_camp', __name__, url_prefix='/blood_camp') # Add prefix
logger = logging.getLogger(__name__)

# --- Helper Functions Specific to Blood Camp ---

def find_donor_by_mobile(sheet, mobile_number):
    """Finds the LATEST Blood Camp donor entry by mobile number."""
    if not sheet:
        logger.error("Blood Camp sheet object is None in find_donor_by_mobile.")
        return None

    try:
        # Get column indices from config
        mobile_header = "Mobile Number"
        timestamp_header = "Submission Timestamp"
        mobile_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index(mobile_header) + 1
        timestamp_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index(timestamp_header) + 1
    except ValueError:
        logger.error(f"Headers '{mobile_header}' or '{timestamp_header}' missing in BLOOD_CAMP_SHEET_HEADERS.")
        return None

    try:
        all_data = sheet.get_all_values()
        matching_entries = []
        if len(all_data) <= 1: # Only header row or empty
            return None

        cleaned_search_mobile = utils.clean_phone_number(mobile_number)
        if not cleaned_search_mobile:
            return None # Cannot search for empty mobile number

        header_row = config.BLOOD_CAMP_SHEET_HEADERS
        num_headers = len(header_row)

        for i, row in enumerate(all_data[1:], start=2): # Start from row 2 (1-based index)
            # Pad row if needed
            padded_row = row + [''] * (num_headers - len(row))
            current_row = padded_row[:num_headers] # Ensure correct length

            # Check if mobile number column exists and matches
            if len(current_row) >= mobile_col_index:
                sheet_mobile_raw = str(current_row[mobile_col_index - 1]).strip()
                cleaned_sheet_mobile = utils.clean_phone_number(sheet_mobile_raw)

                if cleaned_sheet_mobile == cleaned_search_mobile:
                    # Parse timestamp to find the latest entry
                    timestamp_str = str(current_row[timestamp_col_index - 1]).strip() if len(current_row) >= timestamp_col_index else ''
                    row_timestamp = datetime.datetime.min # Default for sorting if parse fails
                    try:
                        if timestamp_str:
                            row_timestamp = date_parser.parse(timestamp_str)
                    except date_parser.ParserError:
                        logger.warning(f"Could not parse timestamp '{timestamp_str}' for row {i}. Using default min date.")
                        pass # Use min date if timestamp is unparsable

                    matching_entries.append({
                        "data": dict(zip(header_row, current_row)), # Store data as dict
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
    """Generates the next sequential persistent Donor ID (BDXXXXX format)."""
    if not sheet:
        logger.error("Blood Camp sheet object is None in generate_next_donor_id.")
        return None

    prefix = "BD"
    start_num = 1

    try:
        # Get Donor ID column index from config
        donor_id_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
    except ValueError:
        logger.error("Header 'Donor ID' not found in BLOOD_CAMP_SHEET_HEADERS.")
        return None

    try:
        # Fetch all values from the Donor ID column
        all_donor_ids = sheet.col_values(donor_id_col_index)
        max_num = 0

        # Iterate through existing IDs (skip header)
        for existing_id_str in all_donor_ids[1:]:
            existing_id = str(existing_id_str).strip().upper()
            if existing_id.startswith(prefix):
                try:
                    # Extract the numeric part
                    num_part_str = existing_id[len(prefix):]
                    if num_part_str.isdigit():
                        max_num = max(max_num, int(num_part_str))
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse number from existing Donor ID: {existing_id}")
                    pass # Ignore IDs that don't parse correctly

        # Calculate the next number
        next_num = max(start_num, max_num + 1)
        # Format as BD followed by 5 digits (zero-padded)
        next_donor_id = f"{prefix}{next_num:05d}"
        logger.info(f"Generated next Donor ID: {next_donor_id}")
        return next_donor_id
    except Exception as e:
        logger.error(f"Error generating Donor ID: {e}", exc_info=True)
        return None

# --- Blood Camp Routes ---

@blood_camp_bp.route('/form')
@login_required
def form_page():
    """Displays the Blood Camp donor registration/donation form."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('blood_camp_form.html',
                           today_date=today_date,
                           current_year=current_year,
                           current_user=current_user,
                           # Pass donation locations from config
                           donation_locations=config.BLOOD_CAMP_DONATION_LOCATIONS)

@blood_camp_bp.route('/search_donor', methods=['GET'])
@login_required
def search_donor_route():
    """Endpoint called by JS to search for an existing donor by mobile."""
    mobile_number = request.args.get('mobile', '').strip()
    if not mobile_number or not re.fullmatch(r'\d{10}', mobile_number):
        return jsonify({"error": "Invalid mobile number format (must be 10 digits)."}), 400

    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
        return jsonify({"error": "Could not connect to donor database."}), 500

    donor_record = find_donor_by_mobile(sheet, mobile_number) # Finds latest entry
    if donor_record:
        return jsonify({"found": True, "donor": donor_record})
    else:
        return jsonify({"found": False})

@blood_camp_bp.route('/submit', methods=['POST'])
@login_required
def submit_form():
    """Handles blood camp form submission (new donor or new donation)."""
    form_data = request.form.to_dict()
    mobile_number = form_data.get('mobile_no', '').strip()

    # --- Basic Validation ---
    if not mobile_number:
        flash("Mobile number is required.", "error")
        return redirect(url_for('blood_camp.form_page'))

    cleaned_mobile_number = utils.clean_phone_number(mobile_number)
    if len(cleaned_mobile_number) != 10:
        flash("Mobile number must be 10 digits.", "error")
        return redirect(url_for('blood_camp.form_page'))

    # Validate other required fields from the form
    required_fields = ['donor_name', 'father_husband_name', 'dob', 'gender', 'city', 'blood_group', 'donation_date', 'donation_location']
    missing_fields = [field for field in required_fields if not form_data.get(field)]
    if missing_fields:
        flash(f"Missing required fields: {', '.join(missing_fields)}", "error")
        return redirect(url_for('blood_camp.form_page')) # Consider re-rendering with data

    # --- Connect to Sheet ---
    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to the donor database.", "error")
        return redirect(url_for('blood_camp.form_page'))

    try:
        # Check if donor exists using the mobile number from the form
        existing_donor_data = find_donor_by_mobile(sheet, cleaned_mobile_number)
        current_donation_date = form_data.get('donation_date', datetime.date.today().isoformat())
        submission_timestamp = datetime.datetime.now().isoformat()

        if existing_donor_data:
            # --- Record New Donation for Existing Donor ---
            donor_id = existing_donor_data.get("Donor ID")
            if not donor_id:
                 # This case should ideally not happen if find_donor_by_mobile worked
                 logger.error(f"Data Inconsistency: Donor found by mobile {cleaned_mobile_number} but has no Donor ID in record: {existing_donor_data}")
                 flash("Data inconsistency found for existing donor. Please contact support.", "error")
                 return redirect(url_for('blood_camp.form_page'))

            # Determine first donation date and increment total donations
            first_donation_date = existing_donor_data.get("First Donation Date", current_donation_date) # Use existing or current
            try:
                total_donations = int(existing_donor_data.get("Total Donations", 0)) + 1
            except (ValueError, TypeError):
                total_donations = 1 # Start count if previous value was invalid

            # Prepare data row for the new donation entry
            data_row = []
            for header in config.BLOOD_CAMP_SHEET_HEADERS:
                form_key = header.lower().replace("'", "").replace('/', '_').replace(' ', '_')
                if header == "Donor ID": value = donor_id
                elif header == "Submission Timestamp": value = submission_timestamp
                elif header == "Mobile Number": value = cleaned_mobile_number # Use cleaned number
                elif header == "Donation Date": value = current_donation_date # Current donation
                elif header == "Donation Location": value = form_data.get('donation_location', '') # Current location
                elif header == "First Donation Date": value = first_donation_date # Keep original first date
                elif header == "Total Donations": value = total_donations # Incremented count
                elif header in ["Status", "Reason for Rejection"]: value = '' # Reset status for new donation
                else:
                    # Update other fields from form, fallback to existing data if not in form
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

            first_donation_date = current_donation_date # This is their first donation
            total_donations = 1

            # Prepare data row for the new donor
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
                else: value = form_data.get(form_key, '') # Get value from form
                data_row.append(str(value))

            sheet.append_row(data_row, value_input_option='USER_ENTERED')
            flash(f'New donor registered successfully! Donor ID: {new_donor_id}', 'success')

        return redirect(url_for('blood_camp.form_page')) # Redirect after success

    except Exception as e:
        logger.error(f"Error during blood camp submission: {e}", exc_info=True)
        flash(f"A server error occurred during submission: {e}", "error")
        return redirect(url_for('blood_camp.form_page'))


@blood_camp_bp.route('/status')
@login_required
def status_page():
    """Displays the page to update blood donor status."""
    today_date = datetime.date.today()
    current_year = today_date.year
    return render_template('blood_donor_status.html',
                           today_date=today_date,
                           current_year=current_year,
                           current_user=current_user)

@blood_camp_bp.route('/get_donor_details/<donor_id>', methods=['GET'])
@login_required
def get_donor_details_route(donor_id):
    """Endpoint called by JS to fetch donor details for status update."""
    # Validate Donor ID format
    if not donor_id or not re.fullmatch(r'BD\d{5}', donor_id):
        return jsonify({"error": "Invalid Donor ID format (must be BD followed by 5 digits)."}), 400

    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
        return jsonify({"error": "Could not connect to donor database."}), 500

    try:
        # Find the LATEST entry for this Donor ID to get current name/status/reason
        all_data = sheet.get_all_values()
        matching_rows = []

        # Get column indices from config
        try:
            donor_id_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
            timestamp_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Submission Timestamp") + 1
            name_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Name of Donor") + 1
            status_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Status") + 1
            reason_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Reason for Rejection") + 1
        except ValueError as e:
            logger.error(f"Header config error for blood camp sheet: {e}")
            return jsonify({"error": "Server configuration error regarding sheet headers."}), 500

        num_headers = len(config.BLOOD_CAMP_SHEET_HEADERS)
        for i, row in enumerate(all_data[1:], start=2): # Start from row 2
             # Pad row if needed
             padded_row = row + [''] * (num_headers - len(row))
             current_row = padded_row[:num_headers] # Ensure correct length

             # Check if Donor ID matches
             if len(current_row) >= donor_id_col_index and str(current_row[donor_id_col_index - 1]).strip().upper() == donor_id:
                 # Parse timestamp
                 timestamp_str = str(current_row[timestamp_col_index - 1]).strip() if len(current_row) >= timestamp_col_index else ''
                 row_timestamp = datetime.datetime.min
                 try:
                     if timestamp_str: row_timestamp = date_parser.parse(timestamp_str)
                 except date_parser.ParserError: pass

                 matching_rows.append({
                     "index": i,
                     "timestamp": row_timestamp,
                     "name": str(current_row[name_col_index - 1]) if len(current_row) >= name_col_index else 'N/A',
                     "status": str(current_row[status_col_index - 1]) if len(current_row) >= status_col_index else '',
                     "reason": str(current_row[reason_col_index - 1]) if len(current_row) >= reason_col_index else ''
                 })

        if not matching_rows:
            return jsonify({"found": False, "error": f"Donor ID '{donor_id}' not found."}), 404

        # Get the info from the row with the latest timestamp
        latest_row_info = max(matching_rows, key=lambda x: x["timestamp"])
        return jsonify({
            "found": True,
            "name": latest_row_info["name"],
            "status": latest_row_info["status"],
            "reason": latest_row_info["reason"]
        })

    except Exception as e:
        logger.error(f"Error fetching donor details for {donor_id}: {e}", exc_info=True)
        return jsonify({"error": "Server error while fetching donor details."}), 500


@blood_camp_bp.route('/update_status', methods=['POST'])
@login_required
def update_status_route():
    """Handles the submission to update a donor's status."""
    donor_id = request.form.get('token_id', '').strip().upper() # Use token_id from form
    status = request.form.get('status', '').strip().capitalize() # Accepted or Rejected
    reason = request.form.get('reason', '').strip()

    # --- Validation ---
    if not donor_id or not re.fullmatch(r'BD\d{5}', donor_id):
        flash("A valid Donor ID (e.g., BD00001) is required.", "error")
        return redirect(url_for('blood_camp.status_page'))
    if not status or status not in ['Accepted', 'Rejected']:
        flash("Status must be 'Accepted' or 'Rejected'.", "error")
        return redirect(url_for('blood_camp.status_page'))
    if status == 'Rejected' and not reason:
        flash("A reason is required when rejecting a donor.", "error")
        return redirect(url_for('blood_camp.status_page'))
    if status == 'Accepted':
        reason = '' # Clear reason if accepted

    # --- Connect to Sheet ---
    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=False)
    if not sheet:
        flash("Error connecting to the donor database.", "error")
        return redirect(url_for('blood_camp.status_page'))

    try:
        # Find the LATEST row for this Donor ID to update
        all_data = sheet.get_all_values()
        matching_rows = []
        try:
            donor_id_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Donor ID") + 1
            timestamp_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Submission Timestamp") + 1
            status_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Status") + 1
            reason_col_index = config.BLOOD_CAMP_SHEET_HEADERS.index("Reason for Rejection") + 1
        except ValueError as e:
            logger.error(f"Header config error for blood camp sheet: {e}")
            flash("Server configuration error regarding sheet headers.", "error")
            return redirect(url_for('blood_camp.status_page'))

        num_headers = len(config.BLOOD_CAMP_SHEET_HEADERS)
        for i, row in enumerate(all_data[1:], start=2): # Start from row 2
             padded_row = row + [''] * (num_headers - len(row))
             current_row = padded_row[:num_headers]
             if len(current_row) >= donor_id_col_index and str(current_row[donor_id_col_index - 1]).strip().upper() == donor_id:
                 timestamp_str = str(current_row[timestamp_col_index - 1]).strip() if len(current_row) >= timestamp_col_index else ''
                 row_timestamp = datetime.datetime.min
                 try:
                     if timestamp_str: row_timestamp = date_parser.parse(timestamp_str)
                 except date_parser.ParserError: pass
                 matching_rows.append({"index": i, "timestamp": row_timestamp})

        if not matching_rows:
            flash(f"Donor ID '{donor_id}' not found in the database.", "error")
            return redirect(url_for('blood_camp.status_page'))

        # Get the index of the row with the latest timestamp
        latest_row_info = max(matching_rows, key=lambda x: x["timestamp"])
        row_index_to_update = latest_row_info["index"]

        # --- Update Cells ---
        # Create Cell objects for batch update
        updates = [
            gspread.Cell(row=row_index_to_update, col=status_col_index, value=status),
            gspread.Cell(row=row_index_to_update, col=reason_col_index, value=reason)
        ]
        sheet.update_cells(updates, value_input_option='USER_ENTERED')

        logger.info(f"Successfully updated status to '{status}' for Donor ID {donor_id} in row {row_index_to_update}.")
        flash(f"Status successfully updated to '{status}' for Donor ID: {donor_id}", "success")
        return redirect(url_for('blood_camp.status_page')) # Redirect back after success

    except Exception as e:
        logger.error(f"Error updating status for Donor ID {donor_id}: {e}", exc_info=True)
        flash(f"An error occurred while updating status: {e}", "error")
        return redirect(url_for('blood_camp.status_page'))


@blood_camp_bp.route('/dashboard')
@login_required
def dashboard_page():
    """Displays the blood camp dashboard."""
    logger.info("Dashboard route accessed")
    current_year = datetime.date.today().year
    return render_template('dashboard.html',
                           current_year=current_year,
                           current_user=current_user)

@blood_camp_bp.route('/dashboard_data')
@login_required
def dashboard_data_route():
    """Provides data for the blood camp dashboard charts."""
    sheet = utils.get_sheet(config.BLOOD_CAMP_SHEET_ID, config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE, read_only=True)
    if not sheet:
        return jsonify({"error": "Could not connect to data source."}), 500

    try:
        all_values = sheet.get_all_values()
        # Default structure with zeros/empty if sheet is empty or has only header
        default_data = {
            "kpis": {"registrations_today": 0, "accepted_total": 0, "rejected_total": 0, "acceptance_rate": 0.0},
            "blood_group_distribution": {}, "gender_distribution": {}, "age_group_distribution": {},
            "status_counts": {"Accepted": 0, "Rejected": 0, "Other/Pending": 0},
            "rejection_reasons": {}, "donor_types": {"First-Time": 0, "Repeat": 0},
            "communication_opt_in": {"Yes": 0, "No": 0, "Unknown": 0}
        }
        if not all_values or len(all_values) < 2:
            return jsonify(default_data)

        header_row = config.BLOOD_CAMP_SHEET_HEADERS
        data_rows = all_values[1:]
        today_str = datetime.date.today().isoformat()

        # Get column indices safely
        try:
            donor_id_col = header_row.index("Donor ID")
            timestamp_col = header_row.index("Submission Timestamp")
            dob_col = header_row.index("Date of Birth")
            gender_col = header_row.index("Gender")
            blood_group_col = header_row.index("Blood Group")
            allow_call_col = header_row.index("Allow Call")
            total_donations_col = header_row.index("Total Donations")
            status_col = header_row.index("Status")
            reason_col = header_row.index("Reason for Rejection")
        except ValueError as e:
            logger.error(f"Dashboard Data: Missing required header in BLOOD_CAMP_SHEET_HEADERS: {e}")
            return jsonify({"error": f"Server configuration error: Missing column '{e}'"}), 500

        # --- Process Data: Find latest entry per Donor ID ---
        latest_donor_entries = {}
        num_headers = len(header_row)
        for row_index, row in enumerate(data_rows):
            padded_row = row + [''] * (num_headers - len(row))
            current_row = padded_row[:num_headers]
            donor_id = str(current_row[donor_id_col]).strip().upper()
            if not donor_id: continue # Skip rows without Donor ID

            timestamp_str = str(current_row[timestamp_col]).strip()
            row_timestamp = datetime.datetime.min
            try:
                if timestamp_str: row_timestamp = date_parser.parse(timestamp_str)
            except date_parser.ParserError: pass # Use min date if unparsable

            # Keep only the latest entry for each donor
            if donor_id not in latest_donor_entries or row_timestamp > latest_donor_entries[donor_id].get("timestamp", datetime.datetime.min):
                 latest_donor_entries[donor_id] = {"data": current_row, "timestamp": row_timestamp}

        # --- Aggregate Data from Latest Entries ---
        registrations_today = 0; accepted_count = 0; rejected_count = 0
        blood_groups = []; genders = []; ages = []; statuses = []
        rejection_reasons = []; donor_types_list = []; allow_calls = []

        for donor_id, entry in latest_donor_entries.items():
            row_data = entry["data"]; row_timestamp = entry["timestamp"]

            # KPI: Registrations Today (based on latest entry timestamp)
            if row_timestamp and row_timestamp.date().isoformat() == today_str:
                registrations_today += 1

            # Status, Acceptance Rate, Rejection Reasons
            stat = str(row_data[status_col]).strip().capitalize()
            if stat == "Accepted":
                accepted_count += 1
                statuses.append("Accepted")
            elif stat == "Rejected":
                rejected_count += 1
                statuses.append("Rejected")
                reason_text = str(row_data[reason_col]).strip()
                if reason_text: rejection_reasons.append(reason_text)
            else:
                statuses.append("Other/Pending") # Count entries without 'Accepted' or 'Rejected'

            # Distributions
            bg = str(row_data[blood_group_col]).strip().upper()
            blood_groups.append(bg if bg else "Unknown")

            gen = str(row_data[gender_col]).strip().capitalize()
            genders.append(gen if gen else "Unknown")

            age = utils.calculate_age_from_dob(str(row_data[dob_col]).strip())
            if age is not None: ages.append(age)

            # Donor Type (First-Time vs Repeat)
            donations_str = str(row_data[total_donations_col]).strip()
            try:
                num_donations = int(donations_str)
                donor_types_list.append("Repeat" if num_donations > 1 else "First-Time")
            except (ValueError, TypeError):
                donor_types_list.append("First-Time") # Treat invalid/missing as first-time

            # Communication Preference
            call_pref = str(row_data[allow_call_col]).strip().capitalize()
            allow_calls.append(call_pref if call_pref in ["Yes", "No"] else "Unknown")

        # --- Calculate Final Stats ---
        total_decided = accepted_count + rejected_count
        acceptance_rate = (accepted_count / total_decided * 100) if total_decided > 0 else 0.0

        # Age Grouping
        age_group_counts = collections.defaultdict(int)
        for age in ages:
            binned = False
            for min_age, max_age in config.AGE_GROUP_BINS:
                if min_age <= age <= max_age:
                    age_group_counts[f"{min_age}-{max_age}"] += 1
                    binned = True; break
            if not binned:
                age_group_counts["> 65" if age > 65 else "< 18"] += 1 # Catch outliers

        # Sort age groups numerically for chart display
        try:
            sorted_age_group_keys = sorted(age_group_counts.keys(), key=lambda x: int(re.search(r'\d+', x.replace('<','').replace('>','')).group()))
        except: # Fallback if parsing fails
            sorted_age_group_keys = sorted(age_group_counts.keys())
        sorted_age_group_counts = {k: age_group_counts[k] for k in sorted_age_group_keys}

        # Counters for distributions
        blood_group_counts = collections.Counter(blood_groups)
        gender_counts = collections.Counter(genders)
        status_counts = collections.Counter(statuses)
        rejection_reason_counts = collections.Counter(rejection_reasons)
        donor_type_counts = collections.Counter(donor_types_list)
        communication_counts = collections.Counter(allow_calls)

        # Ensure all expected keys exist in final counts
        final_status_counts = {"Accepted": status_counts.get("Accepted", 0), "Rejected": status_counts.get("Rejected", 0), "Other/Pending": status_counts.get("Other/Pending", 0)}
        final_donor_type_counts = {"First-Time": donor_type_counts.get("First-Time", 0), "Repeat": donor_type_counts.get("Repeat", 0)}
        final_communication_counts = {"Yes": communication_counts.get("Yes", 0), "No": communication_counts.get("No", 0), "Unknown": communication_counts.get("Unknown", 0)}

        # --- Return JSON Data ---
        return jsonify({
            "kpis": {
                "registrations_today": registrations_today,
                "accepted_total": accepted_count,
                "rejected_total": rejected_count,
                "acceptance_rate": round(acceptance_rate, 1)
            },
            "blood_group_distribution": dict(blood_group_counts),
            "gender_distribution": dict(gender_counts),
            "age_group_distribution": sorted_age_group_counts,
            "status_counts": final_status_counts,
            "rejection_reasons": dict(rejection_reason_counts.most_common(10)), # Top 10 reasons
            "donor_types": final_donor_type_counts,
            "communication_opt_in": final_communication_counts
        })
    except Exception as e:
        logger.error(f"Dashboard Data: Error processing data: {e}", exc_info=True)
        return jsonify({"error": f"Server error while processing dashboard data: {e}"}), 500

