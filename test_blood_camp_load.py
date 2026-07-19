"""
Blood Camp Concurrent Load Test — test_blood_camp_load.py
==========================================================
No external dependencies. Uses Python 3 stdlib only (urllib + threading).

Simulates 12 concurrent operators on blood camp day:
  - Form operators  : load form → search donor → submit (new registration)
  - Lookup operators: search for existing donors
  - Status updaters : mark donors Accepted / Rejected

Usage:
    python3 test_blood_camp_load.py [--host HOST] [--users N] [--duration SECONDS]

Defaults:
    --host     http://localhost:5000
    --users    12
    --duration 120   (2 minutes)

Credentials are read from environment variables:
    export BLOOD_CAMP_PASSWORD="yourpassword"
    export ADMIN_PASSWORD="adminpassword"
"""

import os
import sys
import time
import random
import threading
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import json
import argparse
from datetime import date, timedelta
from collections import defaultdict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BLOOD_CAMP_PASSWORD = os.environ.get("BLOOD_CAMP_PASSWORD", "")
ADMIN_PASSWORD      = os.environ.get("ADMIN_PASSWORD", "")

DONATION_LOCATIONS = [
    "CHD-I (Sec 27)", "CHD-II (Maloya)", "CHD-III (Khuda Alisher)",
    "CHD-IV (KAJHERI)", "New Chandigarh",
]
BLOOD_GROUPS  = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
GENDERS       = ["Male", "Female"]
OCCUPATIONS   = ["Engineer", "Doctor", "Teacher", "Student", "Farmer", "Retired"]
FIRST_NAMES   = ["Rajesh","Sunil","Priya","Anita","Harpreet","Manpreet",
                 "Gurpreet","Simran","Amandeep","Balwinder","Surjit","Jaspal"]
LAST_NAMES    = ["Singh","Kaur","Sharma","Verma","Kumar","Gupta","Patel","Grewal"]
CITIES        = ["Chandigarh", "Mohali", "Panchkula", "Zirakpur"]
SECTORS       = [f"Sector {n}" for n in range(1, 56)]
REJECTION_REASONS = ["High BP", "Low BP", "Cold/Cough", "Baby feeding", "Others"]

# ---------------------------------------------------------------------------
# Thread-safe shared state
# ---------------------------------------------------------------------------
_mobile_counter  = 0
_mobile_lock     = threading.Lock()
registered_ids   = []
_ids_lock        = threading.Lock()
stats            = defaultdict(lambda: {"count": 0, "failures": 0, "total_ms": 0})
_stats_lock      = threading.Lock()
stop_event       = threading.Event()


def unique_mobile():
    global _mobile_counter
    with _mobile_lock:
        _mobile_counter += 1
        return f"98{_mobile_counter:08d}"


def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_dob():
    days = random.randint(18 * 365, 60 * 365)
    return (date.today() - timedelta(days=days)).isoformat()


def today_str():
    return date.today().isoformat()


def record(label, elapsed_ms, success):
    with _stats_lock:
        stats[label]["count"]    += 1
        stats[label]["total_ms"] += elapsed_ms
        if not success:
            stats[label]["failures"] += 1


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def make_opener():
    """Return a urllib opener with a per-thread cookie jar (session cookies)."""
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def do_get(opener, host, path, params=None):
    url = host + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    t0 = time.monotonic()
    try:
        with opener.open(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            elapsed = int((time.monotonic() - t0) * 1000)
            return resp.status, body, elapsed
    except urllib.error.HTTPError as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        return e.code, "", elapsed
    except Exception:
        elapsed = int((time.monotonic() - t0) * 1000)
        return 0, "", elapsed


def do_post(opener, host, path, fields):
    url  = host + path
    data = urllib.parse.urlencode(fields).encode()
    req  = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    t0 = time.monotonic()
    try:
        with opener.open(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            elapsed = int((time.monotonic() - t0) * 1000)
            return resp.status, body, elapsed
    except urllib.error.HTTPError as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body, elapsed
    except Exception:
        elapsed = int((time.monotonic() - t0) * 1000)
        return 0, "", elapsed


def login(opener, host, username, password):
    status, _, elapsed = do_post(opener, host, "/login", {
        "username": username,
        "password": password,
        "remember": "y",
    })
    success = status in (200, 302)
    record("POST /login", elapsed, success)
    return success


# ---------------------------------------------------------------------------
# Worker functions
# ---------------------------------------------------------------------------

def form_operator_worker(host, worker_id):
    """Simulates a blood camp desk operator: load form → search → submit."""
    opener = make_opener()
    if not login(opener, host, "blood_camp_user", BLOOD_CAMP_PASSWORD):
        print(f"[Worker {worker_id}] Login failed — check BLOOD_CAMP_PASSWORD")
        return

    while not stop_event.is_set():
        donor_name = random_name()
        mobile     = unique_mobile()

        # Step 1: Load the form page
        status, _, elapsed = do_get(opener, host, "/blood_camp/form")
        record("GET /blood_camp/form", elapsed, status == 200)

        if stop_event.is_set():
            break
        time.sleep(random.uniform(1, 2))   # operator reads the form

        # Step 2: Search for the donor (AJAX)
        status, body, elapsed = do_get(opener, host, "/blood_camp/search_donor",
                                       {"mobile": mobile, "name": donor_name})
        record("GET /blood_camp/search_donor", elapsed, status in (200, 400))

        if stop_event.is_set():
            break
        time.sleep(random.uniform(2, 4))   # operator fills in the form

        # Step 3: Submit the form
        form_data = {
            "donor_name":         donor_name,
            "father_husband_name": random_name(),
            "dob":                random_dob(),
            "gender":             random.choice(GENDERS),
            "occupation":         random.choice(OCCUPATIONS),
            "house_no":           str(random.randint(1, 999)),
            "sector":             random.choice(SECTORS),
            "city":               random.choice(CITIES),
            "mobile_no":          mobile,
            "allow_call":         random.choice(["Yes", "No"]),
            "blood_group":        random.choice(BLOOD_GROUPS),
            "donation_date":      today_str(),
            "donation_location":  random.choice(DONATION_LOCATIONS),
        }
        status, body, elapsed = do_post(opener, host, "/blood_camp/submit", form_data)
        success = status == 200
        record("POST /blood_camp/submit", elapsed, success)

        # Extract donor ID from flash message and add to shared pool
        if success and "Donor ID:" in body:
            try:
                fragment  = body.split("Donor ID:")[-1]
                donor_id  = fragment.split()[0].strip("() ").upper()
                if donor_id.startswith("BD"):
                    with _ids_lock:
                        registered_ids.append(donor_id)
            except Exception:
                pass

        time.sleep(random.uniform(3, 7))   # think time before next donor


def lookup_operator_worker(host, worker_id):
    """Simulates a supervisor searching for existing donors."""
    opener = make_opener()
    if not login(opener, host, "blood_camp_user", BLOOD_CAMP_PASSWORD):
        print(f"[Lookup {worker_id}] Login failed — check BLOOD_CAMP_PASSWORD")
        return

    while not stop_event.is_set():
        status, _, elapsed = do_get(opener, host, "/blood_camp/search_donor",
                                    {"mobile": unique_mobile(), "name": random_name()})
        record("GET /blood_camp/search_donor [lookup]", elapsed, status in (200, 400))
        time.sleep(random.uniform(2, 5))


def status_updater_worker(host, worker_id):
    """Simulates a medical officer marking donors accepted/rejected."""
    opener = make_opener()
    if not login(opener, host, "admin", ADMIN_PASSWORD):
        print(f"[Status {worker_id}] Login failed — check ADMIN_PASSWORD")
        return

    # Wait briefly for registrations to populate the ID pool
    time.sleep(10)

    while not stop_event.is_set():
        # Load status page
        status, _, elapsed = do_get(opener, host, "/blood_camp/status")
        record("GET /blood_camp/status", elapsed, status == 200)

        time.sleep(random.uniform(1, 3))

        with _ids_lock:
            donor_id = random.choice(registered_ids) if registered_ids else None

        if donor_id:
            # Fetch donor details (AJAX)
            status, _, elapsed = do_get(opener, host,
                                        f"/blood_camp/get_donor_details/{donor_id}")
            record("GET /blood_camp/get_donor_details/[id]", elapsed, status in (200, 404))

            time.sleep(random.uniform(1, 2))

            # Update status
            decision = random.choices(["Accepted", "Rejected"], weights=[75, 25])[0]
            reason   = random.choice(REJECTION_REASONS) if decision == "Rejected" else ""
            status, _, elapsed = do_post(opener, host, "/blood_camp/update_status", {
                "token_id": donor_id,
                "status":   decision,
                "reason":   reason,
            })
            record("POST /blood_camp/update_status", elapsed, status == 200)

        time.sleep(random.uniform(4, 8))


# ---------------------------------------------------------------------------
# Reporter thread
# ---------------------------------------------------------------------------

def reporter_thread(interval=15):
    """Prints a stats table every `interval` seconds."""
    while not stop_event.is_set():
        time.sleep(interval)
        print_stats()


def print_stats():
    with _stats_lock:
        snap = {k: dict(v) for k, v in stats.items()}

    print("\n" + "=" * 72)
    print(f"{'Endpoint':<45} {'Reqs':>6} {'Fail':>6} {'Avg ms':>8} {'Fail%':>7}")
    print("-" * 72)
    for label, s in sorted(snap.items()):
        count    = s["count"]
        failures = s["failures"]
        avg_ms   = int(s["total_ms"] / count) if count else 0
        fail_pct = f"{100*failures/count:.1f}%" if count else "—"
        print(f"{label:<45} {count:>6} {failures:>6} {avg_ms:>8} {fail_pct:>7}")
    print(f"\nRegistered donor IDs in pool: {len(registered_ids)}")
    print("=" * 72 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Blood Camp Load Test")
    parser.add_argument("--host",     default="http://localhost:5000")
    parser.add_argument("--users",    type=int, default=12)
    parser.add_argument("--duration", type=int, default=120,
                        help="Test duration in seconds (default 120)")
    args = parser.parse_args()

    if not BLOOD_CAMP_PASSWORD:
        print("ERROR: Set BLOOD_CAMP_PASSWORD environment variable first.")
        print("  export BLOOD_CAMP_PASSWORD='yourpassword'")
        sys.exit(1)
    if not ADMIN_PASSWORD:
        print("ERROR: Set ADMIN_PASSWORD environment variable first.")
        print("  export ADMIN_PASSWORD='yourpassword'")
        sys.exit(1)

    # Distribute users: 75% form operators, 17% lookup, 8% status updater
    n_form   = max(1, int(args.users * 0.75))
    n_lookup = max(1, int(args.users * 0.17))
    n_status = max(1, args.users - n_form - n_lookup)

    print(f"Starting blood camp load test against {args.host}")
    print(f"  {n_form} form operators | {n_lookup} lookup operators | {n_status} status updaters")
    print(f"  Duration: {args.duration}s\n")

    threads = []
    wid = 0

    for _ in range(n_form):
        wid += 1
        t = threading.Thread(target=form_operator_worker,
                             args=(args.host, wid), daemon=True)
        threads.append(t)

    for _ in range(n_lookup):
        wid += 1
        t = threading.Thread(target=lookup_operator_worker,
                             args=(args.host, wid), daemon=True)
        threads.append(t)

    for _ in range(n_status):
        wid += 1
        t = threading.Thread(target=status_updater_worker,
                             args=(args.host, wid), daemon=True)
        threads.append(t)

    rep = threading.Thread(target=reporter_thread, args=(15,), daemon=True)
    threads.append(rep)

    # Spawn with a small ramp-up (0.5 s between users)
    for t in threads[:-1]:   # skip the reporter
        t.start()
        time.sleep(0.5)
    rep.start()

    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    print("\nStopping workers...")
    stop_event.set()

    # Give workers a moment to finish their current request
    time.sleep(3)

    print("\n--- FINAL RESULTS ---")
    print_stats()


if __name__ == "__main__":
    main()
