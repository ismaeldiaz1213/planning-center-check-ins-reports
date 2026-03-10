# Check-ins Automated Reports for Google Drive

This project automatically:

-   Connects to **Planning Center Check-Ins**
-   Pulls attendance data for a specific event
-   Generates a **PDF roster per location**
-   Uploads (and overwrites) `Roster.pdf` files inside a **Google Shared
    Drive**

This is designed for churches using Planning Center who want automated
Sunday School / class rosters stored in Google Drive.

------------------------------------------------------------------------

# Overview

The script performs the following:

1.  Authenticates with Planning Center API
2.  Finds a specific Check-Ins Event (e.g., `Escuela Dominical`)
3.  Finds the most recent event period
4.  Pulls check-ins for that event period
5.  Groups check-ins by location
6.  Fetches additional person details (birthdate, phone, email, address)
7.  Generates a PDF roster per location
8.  Uploads the roster to a Google Shared Drive folder
9.  Overwrites the existing `Roster.pdf` each run

------------------------------------------------------------------------

# Requirements

-   Python 3.10+
-   Planning Center account with API access
-   Google Workspace account (Shared Drives required)
-   A Google Cloud project with Drive API enabled

Install required Python packages:

    pip install requests reportlab google-api-python-client google-auth python-dotenv

------------------------------------------------------------------------

# Environment Variables (.env)

Create a `.env` file in the project root:

    PCO_APP_ID=TODO_FILL_IN
    PCO_SECRET=TODO_FILL_IN
    PCO_EVENT_NAME=TODO_FILL_IN
    GOOGLE_DRIVE_PARENT_FOLDER_ID=TODO_FILL_IN

------------------------------------------------------------------------

# Step 1 --- Create Planning Center Personal Access Token

1.  Log into Planning Center.
2.  Navigate to Developer → Personal Access Tokens.
3.  Click **New Personal Access Token**
4.  Enable:
    -   ✔ Check-Ins
    -   ✔ People
5.  Copy the **Client ID** and **Secret**.

Fill in your `.env`:

    PCO_APP_ID=<Client ID>
    PCO_SECRET=<Secret>
    PCO_EVENT_NAME=<Exact Event Name>

------------------------------------------------------------------------

# Step 2 --- Verify API Access

Test your credentials:

    curl -u CLIENT_ID:SECRET https://api.planningcenteronline.com/check-ins/v2/events

You should receive HTTP 200 and JSON data.

------------------------------------------------------------------------

# Step 3 --- Set Up Google Cloud Service Account

## Create Google Cloud Project

1.  Visit https://console.cloud.google.com/
2.  Create a new project.

## Enable Google Drive API

1.  Go to APIs & Services → Library.
2.  Enable **Google Drive API**.

## Create Service Account

1.  IAM & Admin → Service Accounts.
2.  Click **Create Service Account**.
3.  Complete setup.

## Create JSON Key

1.  Open the service account.
2.  Go to **Keys**.
3.  Add Key → Create New Key → JSON.
4.  Download and rename to:

credentials.json

Place it in the project root.

------------------------------------------------------------------------

# Step 4 --- Create Google Shared Drive

⚠ Service accounts cannot upload to My Drive. You must use a Shared
Drive.

1.  Create a Shared Drive (example: IBL-SS).
2.  Add your service account as **Content Manager**.

------------------------------------------------------------------------

# Step 5 --- Create Folder Structure

Inside the Shared Drive:

IBL-SS\
└── Escuela Dominical

Do not create location folders manually --- the script will create them.

------------------------------------------------------------------------

# Step 6 --- Get Parent Folder ID

Open the Escuela Dominical folder.

The URL will look like:

https://drive.google.com/drive/folders/XXXXXXXXXXXX

Copy the ID and place it in `.env`:

GOOGLE_DRIVE_PARENT_FOLDER_ID=XXXXXXXXXXXX

------------------------------------------------------------------------

# Step 7 --- Run the Script

python main.py

Expected output:

Finding event... Event ID: XXXXX Finding latest event period... Event
Period ID: XXXXX Fetching check-ins... Generating roster for Location
1... Uploaded roster for Location 1 Done.

------------------------------------------------------------------------

# Resulting Structure

Shared Drive\
└── Escuela Dominical\
├── Location 1\
│ └── Roster.pdf\
├── Location 2\
│ └── Roster.pdf

Each run overwrites Roster.pdf.

------------------------------------------------------------------------

# Security Notes

-   Never commit `.env`
-   Never commit `credentials.json`
-   Revoke exposed tokens immediately
-   Store credentials securely

Add to `.gitignore`:

.env\
credentials.json

------------------------------------------------------------------------

# Optional Automation

Cron Example:

0 8 \* \* MON /usr/bin/python3 /path/to/main.py \>\> /path/to/log.txt
2\>&1

------------------------------------------------------------------------

If this works --- congratulations.\
You now have an automated reporting system for your ministry.