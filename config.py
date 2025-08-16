# config.py
import os

# --- General App Config ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'a_very_strong_combined_secret_key_change_it_for_production')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Max upload size (16MB)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# --- S3 Configuration ---
S3_BUCKET_NAME = 'rssbsne'  # Your S3 bucket name

# --- Google Sheets & Service Accounts ---
SNE_SHEET_ID = '1M9dHOwtVldpruZoBzH23vWIVdcvMlHTdf_fWJGWVmLM'
SNE_SERVICE_ACCOUNT_FILE = 'rssbsneform-57c1113348b0.json'
BLOOD_CAMP_SHEET_ID = '1fkswOZnDXymKblLsYi79c1_NROn3mMaSua7u5hEKO_E'
BLOOD_CAMP_SERVICE_ACCOUNT_FILE = 'grand-nimbus-458116-f5-8295ebd9144b.json'
ATTENDANT_SHEET_ID = '13kSQ28X8Gyyba3z3uVJfOqXCYM6ruaw2sIp-nRnqcrM'
ATTENDANT_SERVICE_ACCOUNT_FILE = 'grand-nimbus-458116-f5-8295ebd9144b.json'

# --- Sheet Headers (Keep as is) ---
SNE_SHEET_HEADERS = [
    "Badge ID", "Submission Date", "Area", "Satsang Place", "First Name", "Last Name",
    "Father's/Husband's Name", "Gender", "Date of Birth", "Age", "Blood Group",
    "Aadhaar No", "Mobile No", "Physically Challenged (Yes/No)", "Physically Challenged Details",
    "Help Required for Home Pickup (Yes/No)", "Help Pickup Reasons", "Handicap (Yes/No)",
    "Stretcher Required (Yes/No)", "Wheelchair Required (Yes/No)", "Ambulance Required (Yes/No)",
    "Pacemaker Operated (Yes/No)", "Chair Required for Sitting (Yes/No)",
    "Special Attendant Required (Yes/No)", "Hearing Loss (Yes/No)",
    "Willing to Attend Satsangs (Yes/No)", "Satsang Pickup Help Details", "Other Special Requests",
    "Emergency Contact Name", "Emergency Contact Number", "Emergency Contact Relation",
    "Address", "State", "PIN Code", "Photo Filename"
]
BLOOD_CAMP_SHEET_HEADERS = [
    "Donor ID", "Submission Timestamp", "Area",
    "Name of Donor", "Father's/Husband's Name",
    "Date of Birth", "Gender", "Occupation", "House No.", "Sector", "City", "Mobile Number",
    "Blood Group", "Allow Call", "Donation Date", "Donation Location",
    "First Donation Date", "Total Donations",
    "Status", "Reason for Rejection"
]
ATTENDANT_SHEET_HEADERS = [
    "Badge ID", "Submission Date", "Area", "Centre", "Name",
    "Phone Number", "Address", "Attendant Type", "Photo Filename"
]

# --- Badge Generation Config (Keep as is) ---
FONT_PATH = 'static/fonts/times new roman.ttf'
FONT_BOLD_PATH = 'static/fonts/times new roman bold.ttf'
SNE_BADGE_TEMPLATE_PATH = 'static/images/sne_badge.png'
SNE_PHOTO_PASTE_X_PX = 825; SNE_PHOTO_PASTE_Y_PX = 475
SNE_PHOTO_BOX_WIDTH_PX = 525; SNE_PHOTO_BOX_HEIGHT_PX = 700
SNE_TEXT_ELEMENTS = {
    "badge_id": {"coords": (100, 1200), "size": 130, "color": (139,0,0), "is_bold": True},
    "name":     {"coords": (100, 1350), "size": 110, "color": "black", "is_bold": True},
    "gender":   {"coords": (100, 1500), "size": 110, "color": "black", "is_bold": True},
    "age":      {"coords": (100, 1650), "size": 110, "color": (139,0,0), "is_bold": True},
    "centre":   {"coords": (100, 1800), "size": 110, "color": "black", "is_bold": True},
    "area":     {"coords": (100, 1950), "size": 110, "color": "black", "is_bold": True},
    "address":  {"coords": (1750, 250), "size": 110, "color": "black", "is_bold": True}
}
ATTENDANT_BADGE_SEWADAR_TEMPLATE_PATH = 'static/images/sne_attendant_badge_sewadar.png'
ATTENDANT_BADGE_FAMILY_TEMPLATE_PATH = 'static/images/sne_attendant_badge_family.png'
ATTENDANT_PHOTO_PASTE_X_PX = 70; ATTENDANT_PHOTO_PASTE_Y_PX = 100
ATTENDANT_PHOTO_BOX_WIDTH_PX = 100; ATTENDANT_PHOTO_BOX_HEIGHT_PX = 140
ATTENDANT_TEXT_ELEMENTS = {
    "badge_id": {"coords": (20, 250), "size": 30, "color": (0,0,139), "is_bold": True},
    "name":     {"coords": (20, 290), "size": 27, "color": "black", "is_bold": True},
    "phone":    {"coords": (20, 330), "size": 27, "color": "black", "is_bold": False},
    "centre":   {"coords": (20, 370), "size": 23, "color": "black", "is_bold": True},
    "area":     {"coords": (20, 405), "size": 23, "color": "black", "is_bold": True},
    "address":  {"coords": (375, 75), "size": 24, "color": "black", "is_bold": True}
}
BAAL_SATSANG_SANGAT_TOKEN_TEMPLATE_PATH = 'static/images/baal_satsang_sangat_token.png'
BAAL_SATSANG_VISITOR_TOKEN_TEMPLATE_PATH = 'static/images/baal_satsang_visitor_token.png'
BAAL_SATSANG_SIBLING_PARENT_TOKEN_TEMPLATE_PATH = 'static/images/baal_satsang_sibling_parent_token.png'
BAAL_SATSANG_SINGLE_CHILD_PARENT_TOKEN_TEMPLATE_PATH = 'static/images/baal_satsang_single_child_parent_token.png'

MOBILE_TOKEN_LAYOUT_CONFIG = {
    "template_path": 'static/images/mobile_token.png', # You need to create this image
    "font_path": FONT_PATH,
    "font_bold_path": FONT_BOLD_PATH,
    "text_elements": {
        # Adjust coordinates as needed for your mobile_token.png template
        "token_id":       {"coords": (500, 255), "size": 27, "color": "black", "is_bold": True},
        "area_display":   {"coords": (25, 255), "size": 34, "color": "black", "is_bold": True},
        "centre_display": {"coords": (25, 300), "size": 35, "color": "black", "is_bold": True}
    },
    "pdf_layout": {
        'orientation': 'P', 'unit': 'mm', 'format': 'A4', 
        'margin_mm': 5, 'gap_mm': 2,
        'badge_w_mm': 160, 'badge_h_mm': 60 # Example size, adjust as needed
    }
}

BAAL_SATSANG_TOKEN_TEXT_ELEMENTS = {
    "token_id":       {"coords": (220, 330), "size": 50, "color": "black", "is_bold": True},
    "area_display":   {"coords": (25, 450), "size": 37, "color": "black", "is_bold": True},
    "centre_display": {"coords": (25, 550), "size": 35, "color": "black", "is_bold": True}
}
BAAL_SATSANG_VISITOR_TEXT_ELEMENTS = {
    "token_id":       {"coords": (320, 185), "size": 50, "color": "black", "is_bold": True},
    "area_display":   {"coords": (300, 440), "size": 33, "color": "White", "is_bold": True},
    "centre_display": {"coords": (160, 355), "size": 35, "color": "black", "is_bold": True}
}
BAAL_SATSANG_SIBLING_PARENT_TEXT_ELEMENTS = {
    "token_id":       {"coords": (330, 195), "size": 50, "color": "black", "is_bold": True},
    "area_display":   {"coords": (315, 465), "size": 33, "color": "White", "is_bold": True},
    "centre_display": {"coords": (160, 375), "size": 35, "color": "black", "is_bold": True}
}
BAAL_SATSANG_SINGLE_CHILD_PARENT_TEXT_ELEMENTS = {
    "token_id":       {"coords": (330, 195), "size": 50, "color": "black", "is_bold": True},
    "area_display":   {"coords": (315, 465), "size": 33, "color": "White", "is_bold": True},
    "centre_display": {"coords": (160, 375), "size": 35, "color": "black", "is_bold": True}
}
_COMMON_BAAL_SATSANG_PDF_LAYOUT_DEFAULTS = {
    'orientation': 'P', 'unit': 'mm', 'format': 'A4', 'margin_mm': 10, 'gap_mm': 5
}
BAAL_SATSANG_PDF_LAYOUTS = {
    "sangat": {**_COMMON_BAAL_SATSANG_PDF_LAYOUT_DEFAULTS, 'badge_w_mm': 65, 'badge_h_mm': 87.5, 'margin_mm': 3, 'gap_mm': 0.5},
    "visitor": {**_COMMON_BAAL_SATSANG_PDF_LAYOUT_DEFAULTS, 'badge_w_mm': 100, 'badge_h_mm': 35, 'margin_mm': 3, 'gap_mm': 0},
    "sibling_parent": {**_COMMON_BAAL_SATSANG_PDF_LAYOUT_DEFAULTS, 'badge_w_mm': 100, 'badge_h_mm': 35, 'margin_mm': 3, 'gap_mm': 0},
    "single_child_parent": {**_COMMON_BAAL_SATSANG_PDF_LAYOUT_DEFAULTS, 'badge_w_mm': 100, 'badge_h_mm': 35, 'margin_mm': 3, 'gap_mm': 0},
    "default": {**_COMMON_BAAL_SATSANG_PDF_LAYOUT_DEFAULTS, 'badge_w_mm': 100, 'badge_h_mm': 35, 'margin_mm': 3, 'gap_mm': 0}
}

# --- SNE Area/Centre Configuration (Keep as is) ---
SNE_BADGE_CONFIG = {
    "Chandigarh": {
        "CHD-I (Sec 27)": {"prefix": "SNE-AH-0", "start": 61001, "zone": "ZONE-I"},
        "CHD-II (Maloya)": {"prefix": "SNE-AH-0", "start": 71001, "zone": "ZONE-I"},
        "CHD-III (Khuda Alisher)": {"prefix": "SNE-AH-0", "start": 81001, "zone": "ZONE-I"},
        "CHD-IV (KAJHERI)": {"prefix": "SNE-AH-0", "start": 91001, "zone": "ZONE-I"},
    },
    "Mullanpur Garibdass": {
        "Baltana": {"prefix": "SNE-AX-0", "start": 11001, "zone": "ZONE-III"},
        "Banur": {"prefix": "SNE-AX-0", "start": 21002, "zone": "ZONE-III"},
        "Basma": {"prefix": "SNE-AX-0", "start": 31001, "zone": "ZONE-III"},
        "Barauli": {"prefix": "SNE-AX-0", "start": 41001, "zone": "ZONE-III"},
        "Dhakoran Kalan": {"prefix": "SNE-AX-0", "start": 51001, "zone": "ZONE-III"},
        "Gholu Majra": {"prefix": "SNE-AX-0", "start": 61001, "zone": "ZONE-III"},
        "Hamayunpur Tisambly": {"prefix": "SNE-AX-0", "start": 71001, "zone": "ZONE-III"},
        "Haripur Hinduan": {"prefix": "SNE-AX-0", "start": 81001, "zone": "ZONE-III"},
        "Jarout": {"prefix": "SNE-AX-0", "start": 91001, "zone": "ZONE-III"},
        "Khizrabad": {"prefix": "SNE-AX-", "start": 101001, "zone": "ZONE-III"},
        "Kurari": {"prefix": "SNE-AX-", "start": 111001, "zone": "ZONE-III"},
        "Lalru": {"prefix": "SNE-AX-", "start": 121001, "zone": "ZONE-III"},
        "Malikpur Jaula": {"prefix": "SNE-AX-", "start": 131001, "zone": "ZONE-III"},
        "Mullanpur Garibdass": {"prefix": "SNE-AX-", "start": 141001, "zone": "ZONE-III"},
        "Samgoli": {"prefix": "SNE-AX-", "start": 151001, "zone": "ZONE-III"},
        "Tewar": {"prefix": "SNE-AX-", "start": 161001, "zone": "ZONE-III"},
        "Zirakpur": {"prefix": "SNE-AX-", "start": 171001, "zone": "ZONE-III"},
    }
}
AREAS = list(SNE_BADGE_CONFIG.keys())
CENTRES = sorted(list(set(centre for area_centres in SNE_BADGE_CONFIG.values() for centre in area_centres.keys())))


# --- NEW: Attendant Badge Prefix Configuration ---
# This configuration will determine the prefix for attendant badges.
# The prefix is based on Area, Centre, and Attendant Type.
# We'll derive the Area/Centre code part from SNE_BADGE_CONFIG for consistency.
# Example: SNE_BADGE_CONFIG["Chandigarh"]["CHD-I (Sec 27)"]["prefix"] is "SNE-AH-0"
# The "AH" part is the area/centre code.
# Attendant Type Codes: "ATN" for Sewadar, "PA" for Family

ATTENDANT_BADGE_PREFIX_CONFIG = {}
for area, centres_config in SNE_BADGE_CONFIG.items():
    ATTENDANT_BADGE_PREFIX_CONFIG[area] = {}
    for centre, sne_details in centres_config.items():
        # Extract the area/centre specific part from the SNE prefix.
        # e.g., if SNE prefix is "SNE-AH-0", we want "AH"
        # e.g., if SNE prefix is "SNE-AX-", we want "AX"
        parts = sne_details["prefix"].split('-')
        area_centre_code = "DEFAULT" # Fallback
        if len(parts) > 1:
            area_centre_code = parts[1] # This should be like "AH" or "AX"

        ATTENDANT_BADGE_PREFIX_CONFIG[area][centre] = {
            "Sewadar": f"SNE-ATN-{area_centre_code}-", # e.g., SNE-ATN-AH-
            "Family":  f"SNE-PA-{area_centre_code}-"  # e.g., SNE-PA-AH-
        }
# Example of what ATTENDANT_BADGE_PREFIX_CONFIG will look like:
# {
#     "Chandigarh": {
#         "CHD-I (Sec 27)": {
#             "Sewadar": "SNE-ATN-AH-",
#             "Family": "SNE-PA-AH-"
#         },
#         "CHD-II (Maloya)": {
#             "Sewadar": "SNE-ATN-AH-", # Assuming same area code for Maloya from SNE config
#             "Family": "SNE-PA-AH-"
#         },
#         ...
#     },
#     "Mullanpur Garibdass": {
#         "Baltana": {
#             "Sewadar": "SNE-ATN-AX-",
#             "Family": "SNE-PA-AX-"
#         },
#         ...
#     }
# }


# --- Form Dropdown Options (Keep as is) ---
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]
RELATIONS = ["Spouse", "Father", "Mother", "Son", "Daughter", "Brother", "Sister", "Neighbor", "In Laws", "Others"]

# --- Blood Camp Specific Config (Keep as is) ---
BLOOD_CAMP_DONATION_LOCATIONS = [
    "CHD-I (Sec 27)", "CHD-II (Maloya)", "CHD-III (Khuda Alisher)",
    "CHD-IV (KAJHERI)", "Mullanpur Garibdass"
]
BLOOD_GROUP_COLORS = ['#8B0000', '#DC143C', '#FF6347', '#FF7F50', '#CD5C5C', '#F08080', '#E9967A', '#FA8072', '#cccccc']
GENDER_COLORS = {'Male': '#4682B4', 'Female': '#FF69B4', 'Other': '#9370DB', 'Unknown': '#cccccc'}
AGE_GROUP_COLORS = ['#3CB371', '#2E8B57', '#66CDAA', '#8FBC8F', '#98FB98', '#90EE90', '#cccccc']
STATUS_COLORS = {'Accepted': '#22c55e', 'Rejected': '#ef4444', 'Other/Pending': '#f97316'}
COMMUNICATION_COLORS = {'Yes': '#14b8a6', 'No': '#f43f5e', 'Unknown': '#a1a1aa'}
REASON_COLORS = ['#a855f7', '#ec4899', '#f59e0b', '#10b981', '#0ea5e9', '#6366f1', '#84cc16', '#d946ef']
DONOR_TYPE_COLORS = {'First-Time': '#3b82f6', 'Repeat': '#f97316'}
AGE_GROUP_BINS = [(18, 25), (26, 35), (36, 45), (46, 55), (56, 65), (66, 120)]

# --- Baal Satsang Token Types (Keep as is) ---
BAAL_SATSANG_TOKEN_TYPES = {
    "sangat": "Baal Satsang Token Sangat",
    "visitor": "Baal Satsang Token Visitor",
    "sibling_parent": "Baal Satsang Token Sibling & Parent",
    "single_child_parent": "Baal Satsang Token Single Child & Parent"
}

# --- RBAC (Role-Based Access Control) - Simplified Roles ---
ROLES_PERMISSIONS = {
    'admin': [
        'all_access' # Special permission granting access to everything
    ],
    'sne_services_operator': [
        # SNE Module Permissions
        'access_sne_form', 'submit_sne_form',
        'access_sne_printer', 'generate_sne_pdf',
        'access_sne_edit', 'search_sne_entries', 'update_sne_entry',
        # Attendant Module Permissions
        'access_attendant_form', 'submit_attendant_form',
        'access_attendant_printer', 'generate_attendant_pdf',
        'access_attendant_edit', 'search_attendant_entries', 'update_attendant_entry',
        # Common Permissions
        'get_centres'
    ],
    'baal_satsang_operator': [
        'access_baal_satsang_printer', 'generate_baal_satsang_tokens_pdf',
        'access_mobile_token_printer',
        'get_centres' # Assuming Baal Satsang also uses area/centre selection
    ],
    'blood_camp_operator': [
        'access_blood_camp_form', 'search_blood_donor', 'submit_blood_camp_form',
        'access_blood_camp_status_update', 'get_blood_donor_details', 'update_blood_donor_status',
        'access_blood_camp_dashboard', 'view_blood_camp_dashboard_data',
        'get_centres' # If blood camp forms use area/centre selection
    ]
    # 'get_centres' is a common utility permission.
    # Ensure all necessary granular permissions are listed for each role.
}
