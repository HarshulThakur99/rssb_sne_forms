from locust import HttpUser, task, between
from random import randint, choice
from datetime import datetime, timedelta

# Update these credentials from your .env file
USERNAME = "blood_camp_user"
PASSWORD = "bloodpass@123!"

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login once per simulated user
        self.client.post("/login", data={
            "username": USERNAME,
            "password": PASSWORD,
            "remember": "y"
        })

    @task(5)  # Higher weight - test blood camp ID generation
    def register_donor(self):
        """Test concurrent blood donor registration with unique mobile numbers"""
        today = datetime.now().strftime("%Y-%m-%d")
        # Use timestamp + random to ensure unique mobile numbers for testing
        timestamp = int(datetime.now().timestamp() * 1000) % 1000000000
        unique_mobile = f"9{timestamp:09d}"
        
        data = {
            "donor_id": "",
            "donor_name": f"LoadTest{randint(1000,9999)}",
            "father_husband_name": f"TestFather{randint(1000,9999)}",
            "dob": "1990-05-15",
            "gender": choice(["Male", "Female"]),
            "occupation": choice(["Engineer", "Doctor", "Teacher", "Student"]),
            "house_no": str(randint(1, 999)),
            "sector": f"Sector {randint(1, 50)}",
            "city": "Chandigarh",
            "mobile_no": unique_mobile,
            "allow_call": "Yes",
            "blood_group": choice(["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]),
            "donation_date": today,
            "donation_location": choice(["CHD-I (Sec 27)", "CHD-II (Maloya)", "CHD-III (Khuda Alisher)"])
        }
        self.client.post("/blood_camp/submit", data=data)
    
    @task(2)  # Test SNE registration
    def register_sne(self):
        """Test concurrent SNE member registration"""
        timestamp = int(datetime.now().timestamp() * 1000) % 1000000000
        unique_aadhaar = f"{timestamp:012d}"
        unique_mobile = f"9{timestamp:09d}"
        
        data = {
            "area": "Chandigarh",
            "centre": "CHD-I (Sec 27)",
            "first_name": f"SNETest{randint(1000,9999)}",
            "last_name": "User",
            "father_husband_name": f"Father{randint(1000,9999)}",
            "gender": choice(["Male", "Female"]),
            "dob": "1950-01-15",
            "blood_group": choice(["A+", "B+", "O+", "AB+"]),
            "aadhaar_no": unique_aadhaar,
            "mobile_no": unique_mobile,
            "physically_challenged": "No",
            "willing_to_attend": "Yes",
            "emergency_contact_name": "Emergency Contact",
            "emergency_contact_number": "9999999999",
            "emergency_contact_relation": "Son",
            "address": "Test Address",
            "state": "Punjab",
            "pincode": "160001"
        }
        # Note: This won't include photo upload in load test
        self.client.post("/sne/submit", data=data)
    
    @task(1)  # Test attendant registration
    def register_attendant(self):
        """Test concurrent attendant registration"""
        timestamp = int(datetime.now().timestamp() * 1000) % 1000000000
        unique_phone = f"9{timestamp:09d}"
        
        data = {
            "area": "Chandigarh",
            "centre": "CHD-I (Sec 27)",
            "name": f"AttendantTest{randint(1000,9999)}",
            "phone_number": unique_phone,
            "address": "Test Attendant Address",
            "attendant_type": choice(["Sewadar", "Family"])
        }
        self.client.post("/attendant/submit", data=data)