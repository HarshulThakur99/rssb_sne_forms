"""
Blood Camp Load Test - locustfile_blood_camp.py
================================================
Simulates ~12 concurrent operators working on blood camp day:
  - Filling new donor registration forms
  - Searching for existing/repeat donors before submitting
  - Updating donor acceptance/rejection status
  - Viewing the dashboard

Usage:
  locust -f locustfile_blood_camp.py --host=http://localhost:5000
  locust -f locustfile_blood_camp.py --host=http://localhost:5000 --users 12 --spawn-rate 2 --run-time 2m --headless

Credentials are read from environment variables (same as the app):
  BLOOD_CAMP_PASSWORD  - password for the blood_camp_user account
  ADMIN_PASSWORD       - password for the admin account (used by StatusUpdaterUser)

Set them before running:
  $env:BLOOD_CAMP_PASSWORD="yourpassword"     # PowerShell
  export BLOOD_CAMP_PASSWORD="yourpassword"   # Bash/Linux
"""

import os
import random
import string
import time
import threading
from datetime import date, timedelta

from locust import HttpUser, SequentialTaskSet, task, between, events

# ---------------------------------------------------------------------------
# Credentials  (pulled from env vars — same ones the app uses)
# ---------------------------------------------------------------------------
BLOOD_CAMP_PASSWORD = os.environ.get("BLOOD_CAMP_PASSWORD", "change_me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change_me")

# ---------------------------------------------------------------------------
# Realistic test data pools
# ---------------------------------------------------------------------------
DONATION_LOCATIONS = [
    "CHD-I (Sec 27)",
    "CHD-II (Maloya)",
    "CHD-III (Khuda Alisher)",
    "CHD-IV (KAJHERI)",
    "New Chandigarh",
]

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
GENDERS = ["Male", "Female"]
OCCUPATIONS = ["Engineer", "Doctor", "Teacher", "Student", "Farmer", "Business", "Retired"]
FIRST_NAMES = [
    "Rajesh", "Sunil", "Priya", "Anita", "Harpreet", "Manpreet",
    "Gurpreet", "Simran", "Amandeep", "Balwinder", "Surjit", "Jaspal",
    "Kulwinder", "Ravinder", "Navdeep", "Paramjit", "Daljit", "Satnam",
]
LAST_NAMES = [
    "Singh", "Kaur", "Sharma", "Verma", "Kumar", "Gupta",
    "Patel", "Rana", "Chopra", "Mehta", "Bhatia", "Grewal",
]
CITIES = ["Chandigarh", "Mohali", "Panchkula", "Zirakpur", "Kharar"]
SECTORS = [f"Sector {n}" for n in range(1, 56)]
REJECTION_REASONS = ["High BP", "Low BP", "Cold/Cough", "Baby feeding", "Others"]

# Thread-safe counter for unique mobile numbers during the test run
_mobile_counter = 0
_mobile_lock = threading.Lock()


def unique_mobile() -> str:
    """Generate a unique 10-digit mobile number for each new test donor."""
    global _mobile_counter
    with _mobile_lock:
        _mobile_counter += 1
        # Prefix 98 + 8-digit padded counter — stays within valid 10-digit range
        return f"98{_mobile_counter:08d}"


def random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_dob() -> str:
    """Random date of birth for a donor aged 18–60."""
    days_back = random.randint(18 * 365, 60 * 365)
    return (date.today() - timedelta(days=days_back)).isoformat()


def today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Shared pool of donor IDs that have been successfully registered during the
# test run — the StatusUpdaterUser draws from this pool.
# ---------------------------------------------------------------------------
registered_donor_ids: list[str] = []
_pool_lock = threading.Lock()


def pool_add(donor_id: str):
    with _pool_lock:
        registered_donor_ids.append(donor_id)


def pool_sample() -> str | None:
    with _pool_lock:
        return random.choice(registered_donor_ids) if registered_donor_ids else None


# ---------------------------------------------------------------------------
# Task Sets
# ---------------------------------------------------------------------------

class BloodCampFormFlow(SequentialTaskSet):
    """
    Models a single operator sitting at a blood camp desk:
      1. Open the blood camp form page.
      2. Search whether the donor is already in the system
         (70 % chance the donor is new → no match; 30 % a repeat donor search).
      3. Fill in and submit the form.
    The sequential flow mirrors actual operator behaviour so that think-time
    between page loads is realistic.
    """

    def on_start(self):
        # Each task-set instance gets a fresh donor to register
        self._donor_name = random_name()
        self._mobile = unique_mobile()
        self._dob = random_dob()
        self._blood_group = random.choice(BLOOD_GROUPS)
        self._gender = random.choice(GENDERS)
        self._location = random.choice(DONATION_LOCATIONS)
        self._city = random.choice(CITIES)

    @task
    def load_form_page(self):
        """Step 1 — Open the blood camp form."""
        with self.client.get(
            "/blood_camp/form",
            name="GET /blood_camp/form",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Form page returned {resp.status_code}")

    @task
    def search_donor(self):
        """Step 2 — AJAX donor lookup (operator types mobile + name before submitting)."""
        # 30 % of the time: search for a known donor name to simulate repeat donors
        # 70 % of the time: search with the new unique mobile (returns 'not found' — that's fine)
        if random.random() < 0.30 and self._donor_name in FIRST_NAMES:
            search_mobile = unique_mobile()   # Unknown — will return not-found
            search_name = random_name()
        else:
            search_mobile = self._mobile
            search_name = self._donor_name

        with self.client.get(
            "/blood_camp/search_donor",
            params={"mobile": search_mobile, "name": search_name},
            name="GET /blood_camp/search_donor",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 400):
                resp.success()   # 400 for invalid mobile is an expected validation path
            else:
                resp.failure(f"Donor search returned {resp.status_code}")

    @task
    def submit_form(self):
        """Step 3 — Submit the donation form (new donor registration)."""
        form_data = {
            "donor_name": self._donor_name,
            "father_husband_name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "dob": self._dob,
            "gender": self._gender,
            "occupation": random.choice(OCCUPATIONS),
            "house_no": str(random.randint(1, 999)),
            "sector": random.choice(SECTORS),
            "city": self._city,
            "mobile_no": self._mobile,
            "allow_call": random.choice(["Yes", "No"]),
            "blood_group": self._blood_group,
            "donation_date": today(),
            "donation_location": self._location,
        }

        with self.client.post(
            "/blood_camp/submit",
            data=form_data,
            name="POST /blood_camp/submit",
            catch_response=True,
            allow_redirects=True,
        ) as resp:
            # Successful submit redirects back to the form page (200 after redirect)
            if resp.status_code == 200:
                resp.success()
                # Try to extract the donor ID from the flash message for the status pool
                if "Donor ID:" in resp.text:
                    try:
                        # Flash messages contain text like "Donor ID: BD0042"
                        fragment = resp.text.split("Donor ID:")[-1]
                        donor_id = fragment.split()[0].strip("() ").upper()
                        if donor_id.startswith("BD"):
                            pool_add(donor_id)
                    except Exception:
                        pass
            else:
                resp.failure(f"Submit returned {resp.status_code}")

    # After the 3-step sequence, wait a realistic think-time before the next round
    wait_time = between(4, 10)


class DonorSearchOnlyFlow(SequentialTaskSet):
    """
    Models a supervisor / lookup operator who only searches for donor details —
    no form submission.  Represents users looking up donation history or verifying
    blood group before calling the donor.
    """

    @task(3)
    def search_by_mobile_and_name(self):
        """Search for a donor by mobile number and name."""
        mobile = unique_mobile()
        name = random_name()
        with self.client.get(
            "/blood_camp/search_donor",
            params={"mobile": mobile, "name": name},
            name="GET /blood_camp/search_donor [lookup-only]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 400):
                resp.success()
            else:
                resp.failure(f"Lookup returned {resp.status_code}")

    @task(1)
    def load_form_page(self):
        with self.client.get(
            "/blood_camp/form",
            name="GET /blood_camp/form [lookup-only]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Form page returned {resp.status_code}")

    wait_time = between(2, 6)


class StatusUpdaterFlow(SequentialTaskSet):
    """
    Models the medical officer / Sewadar who marks each donor as Accepted or Rejected
    after the blood test.  Uses the pool of donor IDs collected from registrations.
    If the pool is empty (test started cold), it falls back to fetching the status page.
    """

    @task
    def load_status_page(self):
        with self.client.get(
            "/blood_camp/status",
            name="GET /blood_camp/status",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Status page returned {resp.status_code}")

    @task
    def fetch_donor_details(self):
        """AJAX call to look up a donor ID before updating status."""
        donor_id = pool_sample()
        if not donor_id:
            return   # Pool empty — skip silently until registrations populate it

        with self.client.get(
            f"/blood_camp/get_donor_details/{donor_id}",
            name="GET /blood_camp/get_donor_details/[id]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"get_donor_details returned {resp.status_code}")

    @task
    def update_status(self):
        """Submit a status update (Accepted / Rejected)."""
        donor_id = pool_sample()
        if not donor_id:
            return

        status = random.choices(["Accepted", "Rejected"], weights=[75, 25])[0]
        reason = random.choice(REJECTION_REASONS) if status == "Rejected" else ""

        with self.client.post(
            "/blood_camp/update_status",
            data={
                "token_id": donor_id,
                "status": status,
                "reason": reason,
            },
            name="POST /blood_camp/update_status",
            catch_response=True,
            allow_redirects=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"update_status returned {resp.status_code}")

    wait_time = between(3, 8)


# ---------------------------------------------------------------------------
# User classes  (weight controls how many of each type spawn)
# ---------------------------------------------------------------------------

class FormOperatorUser(HttpUser):
    """
    Main data-entry operator at the blood camp desk.
    Loads form → searches donor → submits form.
    Weight 7 → roughly 8-9 out of 12 concurrent users.
    """
    tasks = [BloodCampFormFlow]
    weight = 7
    wait_time = between(4, 10)

    def on_start(self):
        self.client.post(
            "/login",
            data={
                "username": "blood_camp_user",
                "password": BLOOD_CAMP_PASSWORD,
                "remember": "y",
            },
            name="POST /login [blood_camp_user]",
        )


class LookupOperatorUser(HttpUser):
    """
    Supervisor who only searches / looks up donor details.
    Weight 2 → roughly 2 out of 12 concurrent users.
    """
    tasks = [DonorSearchOnlyFlow]
    weight = 2
    wait_time = between(2, 6)

    def on_start(self):
        self.client.post(
            "/login",
            data={
                "username": "blood_camp_user",
                "password": BLOOD_CAMP_PASSWORD,
                "remember": "y",
            },
            name="POST /login [blood_camp_user]",
        )


class StatusUpdaterUser(HttpUser):
    """
    Medical officer who marks donors accepted/rejected.
    Uses the admin account because status update requires that permission.
    Weight 1 → roughly 1 out of 12 concurrent users.
    """
    tasks = [StatusUpdaterFlow]
    weight = 1
    wait_time = between(3, 8)

    def on_start(self):
        self.client.post(
            "/login",
            data={
                "username": "admin",
                "password": ADMIN_PASSWORD,
                "remember": "y",
            },
            name="POST /login [admin]",
        )
