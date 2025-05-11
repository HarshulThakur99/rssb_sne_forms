# config.py
import os

# --- General App Config ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'a_very_strong_combined_secret_key_change_it_for_production')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Max upload size (16MB)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# --- S3 Configuration ---
S3_BUCKET_NAME = 'rssbsne'  # Your S3 bucket name

# --- Google Sheets & Service Accounts ---
# SNE Sheet
SNE_SHEET_ID = '1M9dHOwtVldpruZoBzH23vWIVdcvMlHTdf_fWJGWVmLM'
SNE_SERVICE_ACCOUNT_FILE = 'rssbsneform-57c1113348b0.json'

# Blood Camp Sheet
BLOOD_CAMP_SHEET_ID = '1fkswOZnDXymKblLsYi79c1_NROn3mMaSua7u5hEKO_E'
BLOOD_CAMP_SERVICE_ACCOUNT_FILE = 'grand-nimbus-458116-f5-8295ebd9144b.json'

# Attendant Sheet
ATTENDANT_SHEET_ID = '13kSQ28X8Gyyba3z3uVJfOqXCYM6ruaw2sIp-nRnqcrM'
ATTENDANT_SERVICE_ACCOUNT_FILE = 'grand-nimbus-458116-f5-8295ebd9144b.json'

# --- Sheet Headers ---
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

# --- Badge Generation Config ---
# Fonts
FONT_PATH = 'static/fonts/times new roman.ttf'
FONT_BOLD_PATH = 'static/fonts/times new roman bold.ttf'

# SNE Badge Layout
SNE_BADGE_TEMPLATE_PATH = 'static/images/sne_badge.png'
SNE_PHOTO_PASTE_X_PX = 825
SNE_PHOTO_PASTE_Y_PX = 475
SNE_PHOTO_BOX_WIDTH_PX = 525
SNE_PHOTO_BOX_HEIGHT_PX = 700
SNE_TEXT_ELEMENTS = {
    "badge_id": {"coords": (100, 1200), "size": 130, "color": (139, 0, 0), "is_bold": True},
    "name":     {"coords": (100, 1350), "size": 110, "color": "black", "is_bold": True},
    "gender":   {"coords": (100, 1500), "size": 110, "color": "black", "is_bold": True},
    "age":      {"coords": (100, 1650), "size": 110, "color": (139, 0, 0), "is_bold": True},
    "centre":   {"coords": (100, 1800), "size": 110, "color": "black", "is_bold": True},
    "area":     {"coords": (100, 1950), "size": 110, "color": "black", "is_bold": True},
    "address":  {"coords": (1750, 250), "size": 110, "color": "black", "is_bold": True}
}

# Attendant Badge Layout
ATTENDANT_BADGE_SEWADAR_TEMPLATE_PATH = 'static/images/sne_attendant_badge_sewadar.png'
ATTENDANT_BADGE_FAMILY_TEMPLATE_PATH = 'static/images/sne_attendant_badge_family.png'
ATTENDANT_PHOTO_PASTE_X_PX = 77
ATTENDANT_PHOTO_PASTE_Y_PX = 115
ATTENDANT_PHOTO_BOX_WIDTH_PX = 125
ATTENDANT_PHOTO_BOX_HEIGHT_PX = 160
ATTENDANT_TEXT_ELEMENTS = {
    "badge_id": {"coords": (20, 300), "size": 30, "color": (0, 0, 139), "is_bold": True},
    "name":     {"coords": (20, 350), "size": 27, "color": "black", "is_bold": True},
    "phone":    {"coords": (20, 400), "size": 27, "color": "black", "is_bold": False},
    "centre":   {"coords": (20, 450), "size": 27, "color": "black", "is_bold": True},
    "area":     {"coords": (20, 500), "size": 27, "color": "black", "is_bold": True},
    "address":  {"coords": (500, 100), "size": 27, "color": "black", "is_bold": True}
}

# Baal Satsang Token Layout
BAAL_SATSANG_SANGAT_TOKEN_TEMPLATE_PATH = 'static/images/baal_satsang_sangat_token.png'
BAAL_SATSANG_VISITOR_TOKEN_TEMPLATE_PATH = 'static/images/baal_satsang_visitor_token.png'
BAAL_SATSANG_SIBLING_PARENT_TOKEN_TEMPLATE_PATH = 'static/images/baal_satsang_sibling_parent_token.png'
BAAL_SATSANG_SINGLE_CHILD_PARENT_TOKEN_TEMPLATE_PATH = 'static/images/baal_satsang_single_child_parent_token.png'

# Define a generic position for the token ID on the Baal Satsang badges.
# Adjust coords, size, color, and is_bold as needed to fit your token designs.
# IMPORTANT: These coordinates are placeholders. You'll need to determine the correct
# pixel coordinates for where the ID should be placed on YOUR actual badge images.
BAAL_SATSANG_TOKEN_TEXT_ELEMENTS = {
    "token_id": {"coords": (220, 325), "size": 50, "color": "black", "is_bold": True} # Example: Place ID at (100,150)
}

# --- SNE Area/Centre Configuration (Used for ID generation and dropdowns) ---
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

# --- Form Dropdown Options ---
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]
RELATIONS = ["Spouse", "Father", "Mother", "Son", "Daughter", "Brother", "Sister", "Neighbor", "In Laws", "Others"]

# --- Blood Camp Specific Config ---
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

# --- Baal Satsang Token Types (for dropdown and template mapping) ---
BAAL_SATSANG_TOKEN_TYPES = {
    "sangat": "Baal Satsang Token Sangat",
    "visitor": "Baal Satsang Token Visitor",
    "sibling_parent": "Baal Satsang Token Sibling & Parent",
    "single_child_parent": "Baal Satsang Token Single Child & Parent"
}
