# Blood Donation Calling List - Quick Reference

## Feature Overview
A calling list service for blood donation requirements that identifies eligible donors based on:
- Selected blood type
- Selected city
- Age ≤ 55 years
- Last donation ≥ 3 months ago
- Donor consent to be called ("Allow Call" = Yes)

## Access URL
```
http://localhost:5000/calling_list
```

## Eligible User Role
- **blood_camp_operator** (credentials: blood_camp_user / bloodpass)

## Key Features

### 1. Filter Donors
- Select Blood Group from dropdown
- Select City from dropdown
- Click "Filter Donors" button
- View results in table with:
  - Donor ID, Name, Age, Mobile, Blood Group, City, Sector, House No., Last Donation Date

### 2. Contact Actions
- **Call Button**: Opens modal to record call details and notes
- **WhatsApp Button**: Opens WhatsApp directly with donor's phone number

### 3. Export List
- Click "Export as CSV" to download filtered list
- Filename: `calling_list_[bloodgroup]_[city]_[date].csv`

## Column Details from Google Sheet
```
Donor ID              - Unique identifier for donor
Submission Timestamp  - When donor was registered
Area                  - Geographic area
Name of Donor         - Full name
Father's/Husband's Name - Family reference
Date of Birth         - Used for age calculation
Gender                - Donor gender
Occupation            - Donor's occupation
House No.             - Address detail
Sector                - Address detail
City                  - Filtered criteria
Mobile Number         - Contact number (displayed)
Blood Group           - Filtered criteria
Allow Call            - Eligibility criteria (must be "Yes")
Donation Date         - Used for 3-month eligibility check
Donation Location     - Where last donation was made
First Donation Date   - Historical data
Total Donations       - Donor's donation count
Status                - Donor status
Reason for Rejection  - If applicable
Age                   - Calculated field (display only)
```

## Eligibility Calculation Example

**Donor Profile:**
```
Name: John Doe
Date of Birth: 1975-05-15 (Age: 48 years) ✓ Eligible
Blood Group: O+
City: New Delhi
Last Donation: 2025-11-10 (90+ days ago) ✓ Eligible
Allow Call: Yes ✓ Eligible
```

**If Searching for: O+ blood in New Delhi**
→ John will appear in the calling list

## API Endpoints

### 1. Main Page
```
GET /calling_list/
Returns: HTML page with filter form
Auth: Requires login + access_calling_list permission
```

### 2. Filter Donors
```
POST /calling_list/filter
Content-Type: application/json

Request:
{
  "blood_group": "O+",
  "city": "New Delhi"
}

Response:
{
  "success": true,
  "count": 25,
  "donors": [
    {
      "Donor ID": "BD0001",
      "Name of Donor": "John Doe",
      "Mobile Number": "9876543210",
      "Blood Group": "O+",
      "City": "New Delhi",
      "Age_Calculated": 48,
      "Donation Date": "2025-11-10",
      ...
    }
  ]
}

Auth: Requires login + filter_calling_list permission
```

### 3. Export to CSV
```
POST /calling_list/export
Content-Type: application/json

Request:
{
  "blood_group": "O+",
  "city": "New Delhi"
}

Response:
{
  "success": true,
  "csv": "Donor ID,Name of Donor,Mobile Number,Age,Blood Group,City,...\nBD0001,John Doe,9876543210,48,O+,New Delhi,..."
}

Auth: Requires login + export_calling_list permission
```

## Eligibility Rules (Code Reference)

### Age Calculation
```python
Age = (Today - Date of Birth) / 365 days
Valid if Age ≤ 55
```

### Last Donation Check
```python
Days Since Last Donation = Today - Last Donation Date
Valid if Days Since Last Donation ≥ 90 days (3 months)
Note: If no donation date exists, considered eligible
```

### Allow Call Verification
```python
Valid if Allow Call value is one of: "Yes", "Y", "true", "1" (case-insensitive)
```

## Example Scenarios

### ✓ WILL APPEAR
- Name: Raj Kumar
- Age: 52 (≤55 years)
- Last Donation: 2025-10-01 (4 months ago, ≥3 months)
- Blood Group: AB-
- City: Mumbai  
- Allow Call: Yes
- Searching for: AB- in Mumbai

### ✗ WON'T APPEAR
- Name: Priya Singh
- Age: 58 (>55 years) - TOO OLD
- Last Donation: 1 month ago (<3 months) - TOO RECENT
- Blood Group: B+
- City: Bangalore
- Allow Call: No - NOT PERMITTED

## Troubleshooting

**Q: No donors appearing in results?**
A: Check if:
- Selected blood group and city exist in data
- Donors in that city are under 55 years old
- No recent donations (within last 3 months)
- "Allow Call" is marked as "Yes" in sheet

**Q: CSV export not working?**
A: Ensure you have `export_calling_list` permission in your role

**Q: Mobile numbers not displaying?**
A: Check if "Mobile Number" column exists in Google Sheet

## Files Modified

1. **Created**: `app/routes/calling_list_routes.py` - Backend logic
2. **Created**: `app/templates/calling_list.html` - Frontend UI
3. **Modified**: `app/config.py` - Added permissions
4. **Modified**: `app/__init__.py` - Registered blueprint

## Role Permissions Required
```python
'blood_camp_operator': [
    'access_calling_list',      # View page
    'filter_calling_list',      # Search/filter
    'export_calling_list'       # Export CSV
]
```

## Date Formats Supported
- ISO format: 2025-02-02
- US format: 02/02/2025
- Various other formats via dateutil parser

## Performance Notes
- Fetches all blood camp data on each filter request
- No caching implemented (can be added for optimization)
- Suitable for datasets up to 10,000 donors
- CSV export works client-side (no server size limits)
