"""
SQLAlchemy Database Models for RSSB SNE Forms Application
Replaces Google Sheets with PostgreSQL database
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class SNEForm(db.Model):
    """Special Needs Entry (SNE) Form - Main table for SNE registrations"""
    __tablename__ = 'sne_forms'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    badge_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Submission Info
    submission_date = db.Column(db.Date, nullable=False, index=True)
    area = db.Column(db.String(100), nullable=False, index=True)
    satsang_place = db.Column(db.String(100), nullable=False, index=True)
    
    # Personal Information
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    father_husband_name = db.Column(db.String(100))
    gender = db.Column(db.String(20))
    date_of_birth = db.Column(db.Date)
    age = db.Column(db.Integer)
    blood_group = db.Column(db.String(10))
    
    # Identification
    aadhaar_no = db.Column(db.String(12), index=True)  # Cleaned, no spaces
    mobile_no = db.Column(db.String(15))
    
    # Medical/Special Needs Information
    physically_challenged = db.Column(db.String(10))  # Yes/No
    physically_challenged_details = db.Column(db.Text)
    help_required_home_pickup = db.Column(db.String(10))  # Yes/No
    help_pickup_reasons = db.Column(db.Text)
    handicap = db.Column(db.String(10))  # Yes/No
    stretcher_required = db.Column(db.String(10))  # Yes/No
    wheelchair_required = db.Column(db.String(10))  # Yes/No
    ambulance_required = db.Column(db.String(10))  # Yes/No
    pacemaker_operated = db.Column(db.String(10))  # Yes/No
    chair_required_sitting = db.Column(db.String(10))  # Yes/No
    special_attendant_required = db.Column(db.String(10))  # Yes/No
    hearing_loss = db.Column(db.String(10))  # Yes/No
    
    # Satsang Attendance
    willing_attend_satsangs = db.Column(db.String(10))  # Yes/No
    satsang_pickup_help_details = db.Column(db.Text)
    other_special_requests = db.Column(db.Text)
    
    # Emergency Contact
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_number = db.Column(db.String(15))
    emergency_contact_relation = db.Column(db.String(50))
    
    # Address Information
    address = db.Column(db.Text)
    state = db.Column(db.String(100))
    pin_code = db.Column(db.String(10))
    
    # Photo
    photo_filename = db.Column(db.String(255))  # S3 key
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Composite index for common queries
    __table_args__ = (
        db.Index('idx_sne_area_aadhaar', 'area', 'aadhaar_no'),
        db.Index('idx_sne_area_centre', 'area', 'satsang_place'),
    )
    
    def __repr__(self):
        return f'<SNEForm {self.badge_id} - {self.first_name} {self.last_name}>'


class BloodCampDonor(db.Model):
    """Blood Camp Donor Registration and Tracking"""
    __tablename__ = 'blood_camp_donors'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    donor_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Submission Info
    submission_timestamp = db.Column(db.DateTime, nullable=False, index=True)
    area = db.Column(db.String(100), index=True)
    
    # Personal Information
    name_of_donor = db.Column(db.String(100), nullable=False)
    father_husband_name = db.Column(db.String(100))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(20))
    occupation = db.Column(db.String(100))
    
    # Address Information
    house_no = db.Column(db.String(50))
    sector = db.Column(db.String(50))
    city = db.Column(db.String(100))
    
    # Contact
    mobile_number = db.Column(db.String(15), index=True)
    
    # Blood Information
    blood_group = db.Column(db.String(10))
    allow_call = db.Column(db.String(10))  # Yes/No for follow-up calls
    
    # Donation Information
    donation_date = db.Column(db.Date, index=True)
    donation_location = db.Column(db.String(100))
    first_donation_date = db.Column(db.Date)
    total_donations = db.Column(db.Integer, default=1)
    
    # Status Tracking
    status = db.Column(db.String(50), default='Pending', index=True)  # Pending/Accepted/Rejected
    reason_for_rejection = db.Column(db.String(255))
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Composite indexes for common queries
    __table_args__ = (
        db.Index('idx_donor_mobile_name', 'mobile_number', 'name_of_donor'),
        db.Index('idx_donor_area_status', 'area', 'status'),
        db.Index('idx_donor_donation_date', 'donation_date'),
    )
    
    def __repr__(self):
        return f'<BloodCampDonor {self.donor_id} - {self.name_of_donor}>'


class Attendant(db.Model):
    """SNE Attendant (Sewadar or Family) Badge Registration"""
    __tablename__ = 'attendants'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    badge_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Submission Info
    submission_date = db.Column(db.Date, nullable=False, index=True)
    area = db.Column(db.String(100), nullable=False, index=True)
    centre = db.Column(db.String(100), nullable=False)
    
    # Attendant Information
    name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(15))
    address = db.Column(db.Text)
    attendant_type = db.Column(db.String(20), nullable=False)  # Sewadar/Family
    photo_filename = db.Column(db.String(255))  # S3 key
    
    # Associated SNE Information (for Family attendants)
    sne_id = db.Column(db.String(20), index=True)  # Foreign key to SNE badge_id (soft)
    sne_name = db.Column(db.String(100))
    sne_gender = db.Column(db.String(20))
    sne_address = db.Column(db.Text)
    sne_photo_filename = db.Column(db.String(255))  # S3 key
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Composite index
    __table_args__ = (
        db.Index('idx_attendant_area_centre', 'area', 'centre'),
        db.Index('idx_attendant_sne_id', 'sne_id'),
    )
    
    def __repr__(self):
        return f'<Attendant {self.badge_id} - {self.name} ({self.attendant_type})>'
