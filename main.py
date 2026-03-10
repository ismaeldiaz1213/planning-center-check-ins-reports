import os
import time
import requests
from requests.auth import HTTPBasicAuth
from collections import defaultdict

# Cache so each unique person_id is only fetched once
_person_cache = {}
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()

PCO_APP_ID = os.getenv("PCO_APP_ID")
PCO_SECRET = os.getenv("PCO_SECRET")
PCO_EVENT_NAME = os.getenv("PCO_EVENT_NAME")
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")

BASE_URL = "https://api.planningcenteronline.com"
auth = HTTPBasicAuth(PCO_APP_ID, PCO_SECRET)


# ------------------------------
# Planning Center Functions
# ------------------------------

def get_event_id():
    url = f"{BASE_URL}/check-ins/v2/events"
    response = requests.get(url, auth=auth)
    response.raise_for_status()

    for event in response.json()["data"]:
        if event["attributes"]["name"] == PCO_EVENT_NAME:
            return event["id"]

    raise Exception(f"Event '{PCO_EVENT_NAME}' not found")


def get_recent_event_periods(event_id, weeks=5):
    """Return the IDs of the most recent N event periods."""
    url = f"{BASE_URL}/check-ins/v2/events/{event_id}/event_periods"
    params = {"order": "-created_at", "per_page": weeks}

    response = requests.get(url, auth=auth, params=params)
    response.raise_for_status()

    data = response.json()["data"]
    if not data:
        raise Exception("No event periods found")

    print(f"  Using {len(data)} event period(s):", flush=True)
    for ep in data:
        print(f"    - {ep['id']} ({ep['attributes'].get('starts_at', 'unknown date')})", flush=True)

    return [ep["id"] for ep in data]


def get_checkins_for_event_periods(event_id, event_period_ids):
    """
    Fetch check-ins for the given event, then filter client-side by event_period_id.
    The API's where[event_period_id] param is unreliable — it returns all check-ins
    regardless, so we fetch once and filter ourselves.
    """
    all_checkins = []
    all_included = []

    valid_period_ids = set(event_period_ids)

    print(f"  Fetching all check-ins for event {event_id}...", flush=True)
    url = f"{BASE_URL}/check-ins/v2/check_ins"
    params = {
        "where[event_id]": event_id,
        "include": "locations,person",
        "per_page": 100,
    }
    page = 1

    while url:
        print(f"    Page {page}...", flush=True)
        response = requests.get(url, auth=auth, params=params)
        print(f"    Status: {response.status_code}", flush=True)
        response.raise_for_status()

        body = response.json()
        batch = body["data"]

        # Filter client-side: only keep check-ins from our target event periods
        kept = 0
        for checkin in batch:
            ep_id = checkin.get("relationships", {}).get("event_period", {}).get("data", {}).get("id")
            if ep_id in valid_period_ids:
                all_checkins.append(checkin)
                kept += 1

        all_included.extend(body.get("included", []))
        print(f"    Got {len(batch)} check-ins, kept {kept} matching target periods", flush=True)

        next_url = body.get("links", {}).get("next")
        if next_url == url:
            print("    WARNING: next link loop detected, stopping.", flush=True)
            break
        url = next_url
        params = {}
        page += 1

    print(f"  Total matching check-ins: {len(all_checkins)}", flush=True)
    return all_checkins, all_included





def get_person_details(person_id):
    """
    Fetch a person's full profile from the People API, including
    their emails, phone numbers, addresses, and birthdate.
    Results are cached so duplicate person_ids cost zero extra calls.
    Retries automatically on 429 rate-limit responses.
    """
    if person_id in _person_cache:
        return _person_cache[person_id]

    url = f"{BASE_URL}/people/v2/people/{person_id}"
    params = {"include": "emails,phone_numbers,addresses"}

    max_retries = 5
    response = None
    for attempt in range(max_retries):
        response = requests.get(url, auth=auth, params=params)
        if response.status_code == 404:
            _person_cache[person_id] = {}
            return {}
        if response.status_code == 429:
            wait = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
            print(f"  Rate limited — waiting {wait}s before retry...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        break
    else:
        print(f"  Skipping person {person_id} after {max_retries} retries.")
        _person_cache[person_id] = {}
        return {}

    body = response.json()
    person_attrs = body["data"]["attributes"]
    included = body.get("included", [])

    # Pull primary (or first) email
    emails = [i for i in included if i["type"] == "Email"]
    primary_email = next(
        (e["attributes"]["address"] for e in emails if e["attributes"].get("primary")),
        emails[0]["attributes"]["address"] if emails else ""
    )

    # Pull primary (or first) phone number
    phones = [i for i in included if i["type"] == "PhoneNumber"]
    primary_phone = next(
        (p["attributes"]["number"] for p in phones if p["attributes"].get("primary")),
        phones[0]["attributes"]["number"] if phones else ""
    )

    # Pull primary (or first) address
    addresses = [i for i in included if i["type"] == "Address"]
    primary_address = ""
    if addresses:
        addr = next(
            (a for a in addresses if a["attributes"].get("primary")),
            addresses[0]
        )
        a = addr["attributes"]
        parts = filter(None, [
            a.get("street_line_1"),
            a.get("street_line_2"),
            a.get("city"),
            a.get("state"),
            a.get("zip"),
        ])
        primary_address = ", ".join(parts)

    # Birthdate
    birthday = person_attrs.get("birthdate") or ""

    result = {
        "email": primary_email,
        "phone": primary_phone,
        "address": primary_address,
        "birthday": birthday,
    }
    _person_cache[person_id] = result
    return result


# ------------------------------
# PDF Generator
# ------------------------------

def generate_pdf(location_name, attendees):
    filename = "Roster.pdf"
    doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"{PCO_EVENT_NAME} — {location_name}", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    headers = ["First Name", "Last Name", "Birthday", "Email", "Phone", "Address"]
    data = [headers]

    for person in attendees:
        data.append([
            person.get("first_name", ""),
            person.get("last_name", ""),
            person.get("birthday", ""),
            person.get("email", ""),
            person.get("phone", ""),
            person.get("address", ""),
        ])

    col_widths = [70, 70, 75, 160, 100, 230]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4A90D9")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF4FB")]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(table)
    doc.build(elements)
    return filename


# ------------------------------
# Google Drive Functions
# ------------------------------

def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=credentials)


def get_or_create_folder(service, parent_id, folder_name):
    query = (
        f"name='{folder_name}' and "
        f"mimeType='application/vnd.google-apps.folder' and "
        f"'{parent_id}' in parents and trashed=false"
    )

    results = service.files().list(
        q=query,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    files = results.get('files', [])
    if files:
        return files[0]['id']

    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(
        body=metadata,
        fields='id',
        supportsAllDrives=True
    ).execute()
    return folder['id']


def upload_and_replace(service, folder_id, filename):
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"

    results = service.files().list(
        q=query,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    files = results.get('files', [])
    media = MediaFileUpload(filename, mimetype='application/pdf')

    if files:
        service.files().update(
            fileId=files[0]['id'],
            media_body=media,
            supportsAllDrives=True
        ).execute()
    else:
        metadata = {'name': filename, 'parents': [folder_id]}
        service.files().create(
            body=metadata,
            media_body=media,
            supportsAllDrives=True
        ).execute()


# ------------------------------
# Main Logic
# ------------------------------

def main():
    print("Finding event...")
    event_id = get_event_id()
    print("Event ID:", event_id)

    print("Finding recent event periods (last 5 weeks)...")
    event_period_ids = get_recent_event_periods(event_id, weeks=5)

    print("Fetching check-ins...")
    checkins, included = get_checkins_for_event_periods(event_id, event_period_ids)

    # Build lookups from the included array
    location_lookup = {
        item["id"]: item["attributes"]["name"]
        for item in included
        if item["type"] == "Location"
    }
    person_lookup = {
        item["id"]: item
        for item in included
        if item["type"] == "Person"
    }
    print(f"Locations found: {list(location_lookup.values())}", flush=True)

    grouped = defaultdict(list)
    seen = defaultdict(set)  # location_name -> set of person_ids already added

    unique_count = 0
    skipped_count = 0
    for checkin in checkins:
        location_data = checkin["relationships"]["locations"]["data"]
        if not location_data:
            print(f"  Skipping check-in with no location: {checkin['attributes']['first_name']} {checkin['attributes']['last_name']}", flush=True)
            continue

        location_id = location_data[0]["id"]
        location_name = location_lookup.get(location_id, "Unknown Location")

        # Resolve the person ID from the check-in relationship
        person_rel = checkin["relationships"].get("person", {}).get("data")
        person_id = person_rel["id"] if person_rel else None

        # Skip if we've already added this person to this location
        if person_id and person_id in seen[location_name]:
            skipped_count += 1
            print(f"  Skipping duplicate: {checkin['attributes']['first_name']} {checkin['attributes']['last_name']} @ {location_name}", flush=True)
            continue
        if person_id:
            seen[location_name].add(person_id)

        # Base info always available on the check-in
        record = {
            "first_name": checkin["attributes"]["first_name"],
            "last_name": checkin["attributes"]["last_name"],
            "email": "",
            "phone": "",
            "address": "",
            "birthday": "",
        }

        if person_id:
            # Try the sideloaded person first (no extra HTTP call)
            sideloaded = person_lookup.get(person_id)
            if sideloaded:
                record["birthday"] = sideloaded["attributes"].get("birthdate") or ""

            # Only log + delay for genuine new API calls
            if person_id not in _person_cache:
                print(f"  [{unique_count + 1}] Fetching details for {record['first_name']} {record['last_name']} (id: {person_id})...", flush=True)
                time.sleep(0.3)  # ~3 req/s — well under PCO's rate limit
            else:
                print(f"  [{unique_count + 1}] Using cached details for {record['first_name']} {record['last_name']}", flush=True)
            details = get_person_details(person_id)
            record.update(details)

        unique_count += 1
        grouped[location_name].append(record)

    print(f"\nProcessed {unique_count} unique attendees, skipped {skipped_count} duplicates.", flush=True)

    print("\nConnecting to Google Drive...", flush=True)
    drive_service = get_drive_service()

    for location_name, attendees in grouped.items():
        print(f"\nGenerating PDF for {location_name} ({len(attendees)} attendees)...", flush=True)

        pdf_file = generate_pdf(location_name, attendees)
        print(f"  PDF generated: {pdf_file}", flush=True)

        print(f"  Getting/creating Drive folder for '{location_name}'...", flush=True)
        location_folder_id = get_or_create_folder(
            drive_service,
            GOOGLE_DRIVE_PARENT_FOLDER_ID,
            location_name
        )

        print(f"  Uploading to Drive (folder id: {location_folder_id})...", flush=True)
        upload_and_replace(drive_service, location_folder_id, pdf_file)
        os.remove(pdf_file)

        print(f"  ✓ Uploaded roster for {location_name}", flush=True)

    print("Done.")


if __name__ == "__main__":
    main()