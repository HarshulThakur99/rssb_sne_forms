# SNE Bio-Data & Badge Generator

This project is a Python Flask web application designed to manage bio-data for senior citizens and individuals with special needs, primarily for organizational use at specific centres (like Satsang places). It provides a web interface to replace a paper-based form (like `bio_data_form SNE.pdf` [cite: 1]), automates data storage, and facilitates badge creation based on an example layout (`sne_badge.png`).

This application combines two main functionalities:
1.  **Data Entry:** Collect detailed bio-data via a web form.
2.  **Badge Printing:** Generate printable PDF badges for registered individuals.

## Key Features

* **Web-Based Data Entry:** An intuitive web form based on the reference PDF [cite: 1] allows users to enter detailed bio-data, including personal information, special requirements, emergency contacts, and optional photo uploads.
* **Google Sheets Integration:** Submitted data is automatically validated and saved to a designated Google Sheet for central access and management.
* **Data Validation:** Includes checks for mandatory fields and verifies Aadhaar number uniqueness within a specific Area before saving.
* **Automatic Badge ID Generation:** Generates unique, sequential Badge IDs based on predefined Area and Centre rules upon successful data submission.
* **PDF Badge Printing:** A separate interface allows users to input comma-separated Badge IDs and generate a printable PDF document containing formatted badges (inspired by `sne_badge.png`, including photos and key details) ready for distribution.
* **Simple Navigation:** Easy switching between the Data Entry and Badge Printing modules via navigation links.

## Technology Stack

* **Backend:** Python 3, Flask
* **Data Storage:** Google Sheets API (via `gspread`)
* **PDF Generation:** `PyFPDF`
* **Image Handling:** `Pillow`
* **Frontend:** HTML, CSS (Basic)

## Screenshots (Optional)

*(Consider adding screenshots here)*

* *Screenshot of the Data Entry form*
* *Screenshot of the Badge Printer form*
* *Example of a generated badge from the PDF*

## Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory-name>
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Activate the environment
    # Windows:
    venv\Scripts\activate
    # macOS/Linux:
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    Create a `requirements.txt` file with the following content:
    ```txt
    Flask
    gspread
    google-auth-oauthlib
    google-auth-httplib2
    PyFPDF
    Pillow
    ```
    Then install the requirements:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Google Sheets API Setup:**
    * Go to the [Google Cloud Console](https://console.cloud.google.com/).
    * Create a new project or select an existing one.
    * Enable the **Google Drive API** and **Google Sheets API**.
    * Create **Service Account** credentials:
        * Go to "Credentials", click "+ Create Credentials", choose "Service account".
        * Follow the steps, download the JSON key file.
    * **Rename** the downloaded JSON file to `service_account.json` and place it in the root project directory (where `combined_app.py` is).
    * **Create your Google Sheet:** Set up a sheet with column headers matching the order defined in the `data_row` list within the `/submit` route in `combined_app.py` (see Configuration section below for the expected list).
    * **Share the Sheet:** Open your Google Sheet, click "Share", and paste the service account's email address (found inside `service_account.json`) into the sharing dialog. Grant it **Editor** permissions.

5.  **Configure the Application:**
    * Open `combined_app.py` in a text editor.
    * Update the following configuration variables near the top of the file:
        * `GOOGLE_SHEET_ID`: Replace `'YOUR_GOOGLE_SHEET_ID'` with the actual ID of your Google Sheet (from the sheet's URL).
        * `SERVICE_ACCOUNT_FILE`: Verify it's set to `'service_account.json'`.
        * `SECRET_KEY`: **Change** the default secret key (`'a_very_strong_combined_secret_key_change_it'`) to a unique, random string. This is important for security.
        * `UPLOAD_FOLDER`: Ensure this path (`'uploads'`) is correct for where photos should be stored relative to `combined_app.py`. The script will try to create this folder if it doesn't exist.
        * `BADGE_CONFIG`: Review and update the Area/Centre mappings, badge prefixes (`SNE-XX-`), starting numbers, and Zone information according to your organization's structure.
        * `STATES`, `RELATIONS`, `AREAS`, `CENTRES`: Update these lists if necessary for your specific dropdown options.

## Usage

1.  **Run the Application:**
    Make sure your virtual environment is activated. From the root project directory, run:
    ```bash
    flask run
    ```

2.  **Access the App:**
    Open your web browser and go to `http://127.0.0.1:5000` (or the address provided in the terminal).

3.  **Navigate:**
    * The default page (`/`) is the **Data Entry Form**.
    * Use the navigation links ("Data Entry Form" | "Badge Printer") at the top to switch between the two modes.

4.  **Data Entry:**
    * Fill in the required fields (marked with `*`).
    * Optionally upload a photo.
    * Click "Save and Generate Badge ID".
    * Upon success, a confirmation message with the generated Badge ID will appear. Data will be saved to the Google Sheet.

5.  **Badge Printing:**
    * Navigate to the "Badge Printer" page (`/printer`).
    * Enter one or more comma-separated Badge IDs into the text area.
    * (Optional) Select a Centre if you want to filter or group (though filtering logic is currently basic).
    * Click "Generate PDF".
    * A PDF file containing the badges for the found IDs will be generated and downloaded by your browser.

## Folder Structure

combined_bio_data_app/
│
├── combined_app.py          # Single Flask script with all logic
├── requirements.txt       # Python package dependencies
├── service_account.json   # Google API credentials (DO NOT COMMIT TO PUBLIC REPOS)
│
├── uploads/               # Folder where uploaded photos are saved
│   └── (photos...)
│
├── static/                # Optional: for CSS/JS
│   └── css/
│       └── style.css
│
└── templates/
├── form.html          # Data entry form template
└── printer_form.html  # Badge printer form template

## Configuration Details

Key variables to configure in `combined_app.py`:

* `GOOGLE_SHEET_ID`: Your target Google Sheet's unique ID.
* `SERVICE_ACCOUNT_FILE`: Path to your Google service account JSON key file.
* `SECRET_KEY`: A long, random string for Flask session security.
* `UPLOAD_FOLDER`: Directory to store uploaded photos.
* `BADGE_CONFIG`: Dictionary defining Area/Centre details for badge ID generation (prefix, starting number, zone).
* `AREAS`, `CENTRES`, `STATES`, `RELATIONS`: Lists populating the dropdown menus in the data entry form.

## Google Sheet Column Headers

Ensure the first row of your Google Sheet has the following headers **in this exact order**:

1.  Submission Date
2.  Area
3.  Satsang Place / Centre
4.  First Name
5.  Last Name
6.  Father/Husband Name
7.  Gender
8.  Date of Birth
9.  Age
10. Blood Group
11. Aadhaar No
12. Physically Challenged (Yes/No)
13. Physically Challenged Details
14. Help Required for Home Pickup (Yes/No)
15. Help Pickup Reasons
16. Handicap (Yes/No)
17. Stretcher Required (Yes/No)
18. Wheelchair Required (Yes/No)
19. Ambulance Required (Yes/No)
20. Pacemaker Operated (Yes/No)
21. Chair Required for Sitting (Yes/No)
22. Special Attendant Required (Yes/No)
23. Hearing Loss (Yes/No)
24. Mobile No
25. Willing to Attend Satsangs (Yes/No)
26. Satsang Pickup Help Details
27. Other Special Requests
28. Emergency Contact Name
29. Emergency Contact Number
30. Emergency Contact Relation
31. Address
32. State
33. PIN Code
34. Photo Filename
35. Badge ID
