# Blood Donation Calling List Service - Implementation Summary

## Overview
A new calling list service has been built within the blood donation module to help identify and contact eligible blood donors based on specific blood requirements.

## Features

### 1. **Donor Eligibility Criteria**
The calling list filters donors based on:
- **Blood Group Match**: Exact match with selected blood group
- **City Match**: Exact match with selected city  
- **Age Requirement**: Donor age must be ≤ 55 years
- **Last Donation Window**: Last donation must be ≥ 3 months ago
- **Permission**: "Allow Call" field must be set to "Yes"

### 2. **Key Components Created**

#### a. **Backend Routes** (`app/routes/calling_list_routes.py`)
- **GET `/calling_list/`**: Main page displaying filter options
  - Loads unique blood groups and cities from the Google Sheet
  - Permission required: `access_calling_list`
  
- **POST `/calling_list/filter`**: Filter API endpoint
  - Accepts JSON with `blood_group` and `city` parameters
  - Returns filtered eligible donors with calculated age
  - Permission required: `filter_calling_list`
  
- **POST `/calling_list/export`**: Export calling list to CSV
  - Exports filtered donor list in CSV format
  - Columns: Donor ID, Name, Mobile, Age, Blood Group, City, Sector, House No., Last Donation Date
  - Permission required: `export_calling_list`

#### b. **Eligibility Functions**
- `calculate_age(date_of_birth_str)`: Calculates current age from DOB
- `is_eligible_age(dob)`: Verifies age ≤ 55 years
- `is_last_donation_eligible(donation_date)`: Checks last donation ≥ 3 months ago
- `is_allow_call_yes(allow_call_str)`: Verifies "Allow Call" permission
- `filter_eligible_donors()`: Main filtering function combining all criteria

#### c. **Frontend Template** (`app/templates/calling_list.html`)
- **Filter Section**: Dropdowns for blood group and city selection
- **Results Table**: Displays eligible donors with:
  - Donor ID, Name, Age, Mobile Number, Blood Group, City, Sector, House No., Last Donation Date
- **Action Buttons**:
  - Call: Opens modal to record call details
  - WhatsApp: Direct link to WhatsApp chat
- **Export Button**: Downloads filtered list as CSV
- **No Results Message**: Displays when no donors match criteria

### 3. **Google Sheets Integration**
- Uses existing `BLOOD_CAMP_SHEET_ID` from config
- Reads all columns from the blood camp sheet
- Uses service account authentication (existing setup)
- Column mapping from sheet headers automatically handled

### 4. **User Permissions (RBAC)**
Added to `blood_camp_operator` role:
- `access_calling_list`: View calling list page
- `filter_calling_list`: Filter and search donors
- `export_calling_list`: Export donor list as CSV

### 5. **Application Integration**
- Registered blueprint in `app/__init__.py`
- Added permissions to config.py RBAC settings
- Blueprint URL prefix: `/calling_list`
- All routes protected with login and permission requirements

## File Locations
- Backend: [app/routes/calling_list_routes.py](app/routes/calling_list_routes.py)
- Frontend: [app/templates/calling_list.html](app/templates/calling_list.html)
- Config Updates: [app/config.py](app/config.py)
- App Registration: [app/__init__.py](app/__init__.py)

## Usage

### Access the Calling List
1. Login with blood_camp_user credentials
2. Navigate to `/calling_list`
3. Select Blood Group and City from dropdowns
4. Click "Filter Donors" to see eligible donors
5. Use "Call" buttons to record donor interactions
6. Use "Export as CSV" to download the list

### API Endpoints
```
GET  /calling_list/              - Main page
POST /calling_list/filter        - Filter donors
POST /calling_list/export        - Export to CSV
```

## Data Flow
1. User selects blood group and city
2. Frontend sends POST request to `/filter` endpoint
3. Backend retrieves all blood camp donor data
4. Applies eligibility filters (age, donation date, allow call)
5. Returns filtered list with calculated age
6. Frontend populates table with results
7. User can call, WhatsApp, or export list

## Eligibility Logic
```
Donor is eligible if:
- Blood Group = Selected blood group (case-insensitive)
- City = Selected city (case-insensitive)
- Age calculated from DOB ≤ 55 years
- Last Donation Date is empty OR ≥ 3 months ago from today
- Allow Call = "Yes" (case-insensitive)
```

## Error Handling
- Validates blood group and city parameters
- Handles date parsing errors gracefully
- Shows appropriate error messages to users
- Logs all errors to application logger
- Returns empty list if no donors match criteria

## Future Enhancements
- Record call outcomes (contacted, not available, agreed to donate, etc.)
- Track call history per donor
- Add filters for additional criteria (sector, occupation, etc.)
- SMS integration for automated messages
- Analytics dashboard for call success rates
- Bulk SMS/email campaign functionality

## Technical Stack
- **Backend**: Flask/Python with gspread for Google Sheets
- **Frontend**: Bootstrap 5, JavaScript (vanilla)
- **Data Storage**: Google Sheets (BLOOD_CAMP_SHEET_ID)
- **Authentication**: Flask-Login with RBAC
- **Export Format**: CSV

## Testing
The application has been successfully started with all new blueprints registered. The calling list service is integrated and ready for use by blood_camp_operator users.
