# Route Update Examples: Google Sheets → PostgreSQL

This document shows how to update your routes from Google Sheets to PostgreSQL.

## Pattern Overview

**Before (Google Sheets):**
```python
# Get data from Google Sheets
sheet = utils.get_sheet(config.SNE_SHEET_ID, config.SNE_SERVICE_ACCOUNT_FILE)
all_data = utils.get_all_sheet_data(sheet_id, service_account, headers)

# Add new row
row_data = [badge_id, name, area, ...]
sheet.append_row(row_data)

# Find row by value
row_index = utils.find_row_index_by_value(sheet, 'Badge ID', badge_id, headers)

# Update row
sheet.update(f'A{row_index}:Z{row_index}', [updated_data])
```

**After (PostgreSQL):**
```python
# Import models and helpers
from app.models import SNEForm, BloodCampDonor, Attendant, db
from app import db_helpers

# Get data
all_data = SNEForm.query.filter_by(area=area).all()

# Add new record
new_sne = SNEForm(badge_id=badge_id, name=name, area=area, ...)
db.session.add(new_sne)
db.session.commit()

# Find by ID
record = SNEForm.query.filter_by(badge_id=badge_id).first()

# Update
record.name = new_name
record.updated_at = datetime.utcnow()
db.session.commit()
```

---

## Example 1: SNE Form Submission

### Before (Google Sheets):

```python
@sne_bp.route('/submit', methods=['POST'])
@login_required
@permission_required('submit_sne_form')
def submit_form():
    form_data = request.form.to_dict()
    files = request.files
    
    # Get Google Sheet
    sheet = utils.get_sheet(
        config.SNE_SHEET_ID,
        config.SNE_SERVICE_ACCOUNT_FILE
    )
    if not sheet:
        flash("Could not connect to database", "error")
        return redirect(url_for('sne.form_page'))
    
    # Check for duplicate Aadhaar
    aadhaar = utils.clean_aadhaar_number(form_data.get('aadhaar_no', ''))
    existing_badge_id = check_sne_aadhaar_exists(sheet, aadhaar, area)
    if existing_badge_id:
        flash(f"Aadhaar already registered with Badge ID: {existing_badge_id}", "error")
        return redirect(url_for('sne.form_page'))
    
    # Generate next badge ID
    badge_id = get_next_sne_badge_id(sheet, area, centre)
    
    # Prepare row data
    row_data = [
        badge_id,
        datetime.now().strftime("%Y-%m-%d"),
        area,
        centre,
        form_data.get('first_name', ''),
        form_data.get('last_name', ''),
        # ... all other fields
    ]
    
    # Append to sheet
    try:
        sheet.append_row(row_data)
        flash(f"SNE form submitted successfully! Badge ID: {badge_id}", "success")
    except Exception as e:
        logger.error(f"Error appending to sheet: {e}")
        flash("Error saving form", "error")
        return redirect(url_for('sne.form_page'))
    
    return redirect(url_for('sne.printer_form', badge_id=badge_id))
```

### After (PostgreSQL):

```python
from app.models import SNEForm, db
from app import db_helpers
from datetime import datetime

@sne_bp.route('/submit', methods=['POST'])
@login_required
@permission_required('submit_sne_form')
def submit_form():
    form_data = request.form.to_dict()
    files = request.files
    
    # Extract form fields
    area = form_data.get('area_select', '').strip()
    centre = form_data.get('centre_select', '').strip()
    
    # Check for duplicate Aadhaar
    aadhaar = utils.clean_aadhaar_number(form_data.get('aadhaar_no', ''))
    existing_badge_id = db_helpers.check_sne_aadhaar_exists_postgres(aadhaar, area)
    if existing_badge_id:
        flash(f"Aadhaar already registered with Badge ID: {existing_badge_id}", "error")
        return redirect(url_for('sne.form_page'))
    
    # Generate next badge ID
    try:
        centre_config = config.SNE_BADGE_CONFIG[area][centre]
        prefix = centre_config["prefix"]
        start_num = centre_config["start"]
        badge_id = db_helpers.get_next_sne_badge_id_postgres(area, centre, prefix, start_num)
    except Exception as e:
        logger.error(f"Error generating badge ID: {e}")
        flash("Invalid Area or Centre selection", "error")
        return redirect(url_for('sne.form_page'))
    
    # Handle photo upload (same as before)
    photo_filename = "N/A"
    if 'photo' in files and files['photo'].filename:
        photo_file = files['photo']
        if utils.allowed_file(photo_file.filename):
            photo_filename = utils.handle_photo_upload(
                photo_file, config.S3_BUCKET_NAME, 'sne-photos', badge_id
            )
    
    # Create new SNE record
    try:
        new_sne = SNEForm(
            badge_id=badge_id,
            submission_date=datetime.now().date(),
            area=area,
            satsang_place=centre,
            first_name=form_data.get('first_name', '').strip(),
            last_name=form_data.get('last_name', '').strip(),
            father_husband_name=form_data.get('father_husband_name', '').strip(),
            gender=form_data.get('gender', '').strip(),
            date_of_birth=utils.parse_date(form_data.get('dob')),
            age=utils.parse_int(form_data.get('age')),
            blood_group=form_data.get('blood_group', '').strip(),
            aadhaar_no=aadhaar,
            mobile_no=utils.clean_phone_number(form_data.get('mobile_no', '')),
            physically_challenged=form_data.get('physically_challenged', 'No'),
            physically_challenged_details=form_data.get('physically_challenged_details', '').strip(),
            help_required_home_pickup=form_data.get('help_required_home_pickup', 'No'),
            help_pickup_reasons=form_data.get('help_pickup_reasons', '').strip(),
            handicap=form_data.get('handicap', 'No'),
            stretcher_required=form_data.get('stretcher_required', 'No'),
            wheelchair_required=form_data.get('wheelchair_required', 'No'),
            ambulance_required=form_data.get('ambulance_required', 'No'),
            pacemaker_operated=form_data.get('pacemaker_operated', 'No'),
            chair_required_sitting=form_data.get('chair_required_sitting', 'No'),
            special_attendant_required=form_data.get('special_attendant_required', 'No'),
            hearing_loss=form_data.get('hearing_loss', 'No'),
            willing_attend_satsangs=form_data.get('willing_attend_satsangs', 'Yes'),
            satsang_pickup_help_details=form_data.get('satsang_pickup_help_details', '').strip(),
            other_special_requests=form_data.get('other_special_requests', '').strip(),
            emergency_contact_name=form_data.get('emergency_contact_name', '').strip(),
            emergency_contact_number=form_data.get('emergency_contact_number', '').strip(),
            emergency_contact_relation=form_data.get('emergency_contact_relation', '').strip(),
            address=form_data.get('address', '').strip(),
            state=form_data.get('state', '').strip(),
            pin_code=form_data.get('pin_code', '').strip(),
            photo_filename=photo_filename
        )
        
        db.session.add(new_sne)
        db.session.commit()
        
        logger.info(f"SNE form submitted successfully: {badge_id}")
        flash(f"SNE form submitted successfully! Badge ID: {badge_id}", "success")
        
        return redirect(url_for('sne.printer_form', badge_id=badge_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving SNE form: {e}", exc_info=True)
        flash("Error saving form. Please try again.", "error")
        return redirect(url_for('sne.form_page'))
```

---

## Example 2: Blood Donor Registration

### Before (Google Sheets):

```python
@blood_camp_bp.route('/submit', methods=['POST'])
@login_required
@permission_required('submit_blood_camp_form')
def submit_form():
    form_data = request.form.to_dict()
    
    sheet = utils.get_sheet(
        config.BLOOD_CAMP_SHEET_ID,
        config.BLOOD_CAMP_SERVICE_ACCOUNT_FILE
    )
    
    mobile_number = utils.clean_phone_number(form_data.get('mobile_no', ''))
    donor_name = form_data.get('donor_name', '').strip()
    
    # Check if existing donor
    existing_donor = find_donor_by_mobile_and_name(sheet, mobile_number, donor_name)
    
    if existing_donor:
        # Update existing donor
        donor_id = existing_donor['Donor ID']
        row_index = utils.find_row_index_by_value(sheet, 'Donor ID', donor_id, config.BLOOD_CAMP_SHEET_HEADERS)
        # Update total donations
        total_donations = int(existing_donor.get('Total Donations', 0)) + 1
        # ... prepare updated row
        sheet.update(f'A{row_index}:Z{row_index}', [updated_row])
    else:
        # Create new donor
        donor_id = get_next_donor_id(sheet)
        row_data = [donor_id, datetime.now(), area, ...]
        sheet.append_row(row_data)
    
    flash(f"Donor registered: {donor_id}", "success")
    return redirect(url_for('blood_camp.status_page'))
```

### After (PostgreSQL):

```python
from app.models import BloodCampDonor, db
from app import db_helpers
from datetime import datetime

@blood_camp_bp.route('/submit', methods=['POST'])
@login_required
@permission_required('submit_blood_camp_form')
def submit_form():
    form_data = request.form.to_dict()
    
    mobile_number = utils.clean_phone_number(form_data.get('mobile_no', ''))
    donor_name = form_data.get('donor_name', '').strip()
    
    # Check if existing donor
    existing_donor = db_helpers.find_donor_by_mobile_and_name_postgres(
        mobile_number, donor_name
    )
    
    try:
        if existing_donor:
            # Update existing donor - increment donations
            existing_donor.total_donations += 1
            existing_donor.donation_date = datetime.now().date()
            existing_donor.donation_location = form_data.get('donation_location', '').strip()
            existing_donor.status = 'Pending'
            existing_donor.updated_at = datetime.utcnow()
            
            db.session.commit()
            donor_id = existing_donor.donor_id
            
            logger.info(f"Updated existing donor: {donor_id}")
        else:
            # Create new donor
            donor_id = db_helpers.get_next_donor_id_postgres("BD")
            
            new_donor = BloodCampDonor(
                donor_id=donor_id,
                submission_timestamp=datetime.utcnow(),
                area=form_data.get('area', '').strip(),
                name_of_donor=donor_name,
                father_husband_name=form_data.get('father_husband_name', '').strip(),
                date_of_birth=utils.parse_date(form_data.get('dob')),
                gender=form_data.get('gender', '').strip(),
                occupation=form_data.get('occupation', '').strip(),
                house_no=form_data.get('house_no', '').strip(),
                sector=form_data.get('sector', '').strip(),
                city=form_data.get('city', '').strip(),
                mobile_number=mobile_number,
                blood_group=form_data.get('blood_group', '').strip(),
                allow_call=form_data.get('allow_call', 'No'),
                donation_date=datetime.now().date(),
                donation_location=form_data.get('donation_location', '').strip(),
                first_donation_date=datetime.now().date(),
                total_donations=1,
                status='Pending'
            )
            
            db.session.add(new_donor)
            db.session.commit()
            
            logger.info(f"Created new donor: {donor_id}")
        
        flash(f"Donor registered successfully! Donor ID: {donor_id}", "success")
        return redirect(url_for('blood_camp.status_page', donor_id=donor_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving donor: {e}", exc_info=True)
        flash("Error registering donor. Please try again.", "error")
        return redirect(url_for('blood_camp.form_page'))
```

---

## Example 3: Update Donor Status

### Before (Google Sheets):

```python
@blood_camp_bp.route('/update_status/<donor_id>', methods=['POST'])
@login_required
@permission_required('update_blood_camp_status')
def update_status(donor_id):
    sheet = utils.get_sheet(...)
    
    status = request.form.get('status')
    reason = request.form.get('reason', '')
    
    # Find row
    row_index = utils.find_row_index_by_value(sheet, 'Donor ID', donor_id, headers)
    
    # Get existing data
    row_data = sheet.row_values(row_index)
    
    # Update status fields
    row_data[status_col_index] = status
    row_data[reason_col_index] = reason
    
    # Write back
    sheet.update(f'A{row_index}:Z{row_index}', [row_data])
    
    flash("Status updated", "success")
    return redirect(url_for('blood_camp.dashboard'))
```

### After (PostgreSQL):

```python
from app import db_helpers

@blood_camp_bp.route('/update_status/<donor_id>', methods=['POST'])
@login_required
@permission_required('update_blood_camp_status')
def update_status(donor_id):
    status = request.form.get('status')
    reason = request.form.get('reason', '')
    
    # Update using helper function
    success = db_helpers.update_donor_status(donor_id, status, reason)
    
    if success:
        flash(f"Donor {donor_id} status updated to {status}", "success")
    else:
        flash("Error updating status", "error")
    
    return redirect(url_for('blood_camp.dashboard'))
```

---

## Example 4: Dashboard/List View

### Before (Google Sheets):

```python
@sne_bp.route('/list')
@login_required
def list_sne_forms():
    sheet = utils.get_sheet(...)
    
    # Get all data
    all_data = utils.get_all_sheet_data(
        config.SNE_SHEET_ID,
        config.SNE_SERVICE_ACCOUNT_FILE,
        config.SNE_SHEET_HEADERS
    )
    
    # Filter by area if needed
    if area_filter:
        all_data = [r for r in all_data if r.get('Area') == area_filter]
    
    return render_template('sne_list.html', records=all_data)
```

### After (PostgreSQL):

```python
from app.models import SNEForm

@sne_bp.route('/list')
@login_required
def list_sne_forms():
    # Get query parameters
    area_filter = request.args.get('area')
    centre_filter = request.args.get('centre')
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Build query
    query = SNEForm.query
    
    if area_filter:
        query = query.filter_by(area=area_filter)
    if centre_filter:
        query = query.filter_by(satsang_place=centre_filter)
    
    # Paginate results
    pagination = query.order_by(SNEForm.submission_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    records = pagination.items
    
    return render_template('sne_list.html', 
                         records=records,
                         pagination=pagination)
```

---

## Example 5: Edit Form

### Before (Google Sheets):

```python
@sne_bp.route('/edit/<badge_id>', methods=['GET', 'POST'])
@login_required
def edit_form(badge_id):
    sheet = utils.get_sheet(...)
    
    if request.method == 'GET':
        # Find and load record
        row_index = utils.find_row_index_by_value(sheet, 'Badge ID', badge_id, headers)
        row_data = sheet.row_values(row_index)
        
        # Convert to dict
        record = dict(zip(config.SNE_SHEET_HEADERS, row_data))
        
        return render_template('edit_form.html', record=record)
    
    else:
        # Update
        row_index = utils.find_row_index_by_value(sheet, 'Badge ID', badge_id, headers)
        updated_data = [...]  # Prepare updated row
        sheet.update(f'A{row_index}:Z{row_index}', [updated_data])
        
        flash("Record updated", "success")
        return redirect(url_for('sne.list_sne_forms'))
```

### After (PostgreSQL):

```python
from app.models import SNEForm, db
from datetime import datetime

@sne_bp.route('/edit/<badge_id>', methods=['GET', 'POST'])
@login_required
def edit_form(badge_id):
    # Load record
    record = SNEForm.query.filter_by(badge_id=badge_id).first_or_404()
    
    if request.method == 'GET':
        return render_template('edit_form.html', record=record)
    
    else:
        # Update fields from form
        try:
            record.first_name = request.form.get('first_name', '').strip()
            record.last_name = request.form.get('last_name', '').strip()
            record.mobile_no = utils.clean_phone_number(request.form.get('mobile_no', ''))
            record.address = request.form.get('address', '').strip()
            # ... update all other fields
            
            record.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f"Record {badge_id} updated successfully", "success")
            return redirect(url_for('sne.list_sne_forms'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating record: {e}")
            flash("Error updating record", "error")
            return render_template('edit_form.html', record=record)
```

---

## Common Patterns Summary

### 1. **Query All Records**
```python
# Google Sheets
all_data = utils.get_all_sheet_data(sheet_id, service_account, headers)

# PostgreSQL
all_data = SNEForm.query.all()
```

### 2. **Filter Records**
```python
# Google Sheets
filtered = [r for r in all_data if r.get('Area') == 'Delhi']

# PostgreSQL
filtered = SNEForm.query.filter_by(area='Delhi').all()
```

### 3. **Find By ID**
```python
# Google Sheets
row_index = utils.find_row_index_by_value(sheet, 'Badge ID', badge_id, headers)

# PostgreSQL
record = SNEForm.query.filter_by(badge_id=badge_id).first()
```

### 4. **Create New Record**
```python
# Google Sheets
row_data = [field1, field2, field3, ...]
sheet.append_row(row_data)

# PostgreSQL
new_record = SNEForm(field1=value1, field2=value2, ...)
db.session.add(new_record)
db.session.commit()
```

### 5. **Update Record**
```python
# Google Sheets
sheet.update(f'A{row_index}:Z{row_index}', [updated_data])

# PostgreSQL
record.field1 = new_value
record.field2 = new_value
db.session.commit()
```

### 6. **Delete Record**
```python
# Google Sheets
sheet.delete_row(row_index)

# PostgreSQL
db.session.delete(record)
db.session.commit()
```

---

## Template Updates

No changes needed! Templates receive the same data structure:

```python
# Both work the same way:
return render_template('form.html', records=records)
```

In templates, access fields the same way:
```html
<!-- Google Sheets (dict) -->
{{ record.get('Badge ID') }}
{{ record['First Name'] }}

<!-- PostgreSQL (object) -->
{{ record.badge_id }}
{{ record.first_name }}
```

**Note:** You may need to update template field names to match the new snake_case attribute names.

---

## Testing Checklist

After updating each route:

- [ ] Test form submission (create)
- [ ] Test viewing records (read)
- [ ] Test editing records (update)
- [ ] Test duplicate detection
- [ ] Test ID generation (no duplicates)
- [ ] Test concurrent submissions
- [ ] Test filters and search
- [ ] Test pagination
- [ ] Verify photo uploads still work
- [ ] Check PDF generation
- [ ] Test error handling

---

## Migration Strategy

1. **Start with one module** (e.g., Blood Camp)
2. **Keep Google Sheets code** in place initially
3. **Add feature flag** to toggle between backends
4. **Test thoroughly** in development
5. **Deploy to production** with PostgreSQL
6. **Monitor for 1-2 weeks**
7. **Remove Google Sheets code** once stable

---

## Need Help?

Refer to:
- `app/models.py` - Database schema
- `app/db_helpers.py` - Helper functions
- `POSTGRESQL_MIGRATION_GUIDE.md` - Full migration guide
