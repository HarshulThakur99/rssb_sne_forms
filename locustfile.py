from locust import HttpUser, task, between
from random import randint, choice
from datetime import datetime

USERNAME = "bc_user"
PASSWORD = "bloodpass"

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login once per simulated user
        self.client.post("/login", data={
            "username": USERNAME,
            "password": PASSWORD,
            "remember": "y"
        })

    @task
    def register_donor(self):
        today = datetime.now().strftime("%Y-%m-%d")
        data = {
            "donor_id": "",
            "donor_name": f"TestUser{randint(1000,9999)}",
            "father_husband_name": f"Father{randint(1000,9999)}",
            "dob": "1990-01-01",
            "gender": choice(["Male", "Female", "Other"]),
            "occupation": "Engineer",
            "house_no": "123",
            "sector": "Sector 1",
            "city": "Chandigarh",
            "mobile_no": f"9{randint(100000000,999999999)}",
            "allow_call": "Yes",
            "blood_group": "A+",
            "donation_date": today,
            "donation_location": "CHD-I (Sec 27)"
        }
        self.client.post("/blood_camp/submit", data=data)