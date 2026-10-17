#!/usr/bin/env bash
# =============================================================================
# setup_gcloud.sh
# Interactive setup script for deploying the church roster generator to
# Google Cloud Run + Cloud Scheduler.
#
# Requirements before running:
#   - Google Cloud SDK installed  (https://cloud.google.com/sdk/docs/install)
#   - A Google Cloud account      (https://cloud.google.com)
#   - credentials.json in this folder (Google service account key)
#
# Usage:
#   chmod +x setup_gcloud.sh
#   ./setup_gcloud.sh
# =============================================================================

set -e

# ── Colours ───────────────────────────────────────────────────────────────────
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${CYAN}ℹ  ${NC}$1"; }
success() { echo -e "${GREEN}✓  ${NC}$1"; }
warn()    { echo -e "${YELLOW}⚠  ${NC}$1"; }
error()   { echo -e "${RED}✗  ${NC}$1"; exit 1; }
prompt()  { echo -e "${BOLD}→  $1${NC}"; }

# ── Report registry ───────────────────────────────────────────────────────────
# The reports to create Cloud Run jobs for come from reports.yaml (or the
# built-in defaults when there is no such file), read through the CLI so this
# script never has to know the report names. Falls back to the two original
# reports if Python is unavailable.
report_ids() {
    local ids
    ids=$(cd "$(dirname "$0")/backend" && python3 main.py --list-reports --format ids 2>/dev/null) || ids=""
    if [[ -z "$ids" ]]; then
        warn "Could not read reports.yaml — falling back to 'rutas escuela'" >&2
        echo "rutas escuela"
    else
        echo "$ids"
    fi
}

echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD}   Church Roster Generator — Google Cloud Setup${NC}"
echo -e "${BOLD}============================================================${NC}"
echo ""
echo "This script will:"
echo "  1. Log you into Google Cloud"
echo "  2. Create (or reuse) a Google Cloud project"
echo "  3. Enable the required APIs"
echo "  4. Store your PCO credentials and credentials.json securely in Secret Manager"
echo "  5. Build and push the Docker image"
echo "  6. Create one Cloud Run Job per report in reports.yaml"
echo "  7. Schedule them to run every Monday at 2 AM US Central"
echo ""
read -rp "Press ENTER to begin, or Ctrl+C to cancel..."

# ── Step 1: Check prerequisites ───────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 1: Checking prerequisites ──────────────────────────${NC}"

command -v gcloud &>/dev/null || error "gcloud not found. Install from https://cloud.google.com/sdk/docs/install"
success "gcloud found"

for f in main.py logo.png credentials.json Dockerfile requirements.txt; do
    [[ -f "$f" ]] || error "Missing required file: $f — run this from your project folder."
    success "Found $f"
done
[[ -d "planning_center_reports" ]] || error "Missing planning_center_reports/ package — run this from your project folder."
success "Found planning_center_reports/"

# ── Step 2: Create .gcloudignore ──────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 2: Configuring build file exclusions ───────────────${NC}"

# credentials.json is stored in Secret Manager, not baked into the image —
# exclude both it and .env from the build context sent to Cloud Build.
cat > .gcloudignore << 'EOF'
.env
credentials.json
EOF
success "Created .gcloudignore (credentials.json and .env excluded from builds)"

# ── Step 3: Google Cloud login ────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 3: Google Cloud login ──────────────────────────────${NC}"
info "Opening browser for Google Cloud login..."
gcloud auth login
success "Logged in"

# ── Step 4: Project setup ─────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 4: Google Cloud project ────────────────────────────${NC}"
echo ""
prompt "Enter your Google Cloud project ID (e.g. ibl-planning-center-check-ins):"
read -rp "  Project ID: " PROJECT_ID

if gcloud projects describe "$PROJECT_ID" &>/dev/null; then
    success "Using existing project: $PROJECT_ID"
else
    info "Project not found — creating it..."
    gcloud projects create "$PROJECT_ID" --name="Church Roster Generator"
    success "Created project: $PROJECT_ID"
fi

gcloud config set project "$PROJECT_ID"

echo ""
warn "Make sure billing is enabled for this project, otherwise Cloud Run won't work."
warn "Enable it at: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
read -rp "Press ENTER once billing is enabled (or if it already is)..."

# ── Step 5: Enable APIs ───────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 5: Enabling required Google Cloud APIs ─────────────${NC}"
info "This may take a minute..."

gcloud services enable \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com

success "All APIs enabled"

# ── Step 6: Collect and store PCO secrets ────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 6: Your PCO credentials ────────────────────────────${NC}"
echo ""
info "These will be stored securely in Google Secret Manager."
echo ""

prompt "PCO App ID (from https://api.planningcenteronline.com/oauth/applications):"
read -rp "  PCO_APP_ID: " PCO_APP_ID
[[ -n "$PCO_APP_ID" ]] || error "PCO_APP_ID cannot be empty"

prompt "PCO Secret:"
read -rsp "  PCO_SECRET: " PCO_SECRET
echo ""
[[ -n "$PCO_SECRET" ]] || error "PCO_SECRET cannot be empty"

prompt "Google Drive parent folder ID (from the folder URL in Drive):"
read -rp "  DRIVE_FOLDER_ID: " DRIVE_FOLDER_ID
[[ -n "$DRIVE_FOLDER_ID" ]] || error "DRIVE_FOLDER_ID cannot be empty"

echo ""
echo -e "${BOLD}── Step 6b: Storing secrets ────────────────────────────────${NC}"

store_secret() {
    local name=$1
    local value=$2
    if gcloud secrets describe "$name" --project="$PROJECT_ID" &>/dev/null; then
        info "Secret $name already exists — updating..."
        echo -n "$value" | gcloud secrets versions add "$name" --data-file=-
    else
        echo -n "$value" | gcloud secrets create "$name" \
            --data-file=- \
            --replication-policy="automatic"
    fi
    success "Stored: $name"
}

store_secret "PCO_APP_ID"                    "$PCO_APP_ID"
store_secret "PCO_SECRET"                    "$PCO_SECRET"
store_secret "GOOGLE_DRIVE_PARENT_FOLDER_ID" "$DRIVE_FOLDER_ID"

if gcloud secrets describe google-service-account-key --project="$PROJECT_ID" &>/dev/null; then
    info "Secret google-service-account-key already exists — updating..."
    gcloud secrets versions add google-service-account-key \
        --data-file="credentials.json" \
        --project="$PROJECT_ID"
else
    gcloud secrets create google-service-account-key \
        --data-file="credentials.json" \
        --replication-policy="automatic" \
        --project="$PROJECT_ID"
fi
success "Stored: google-service-account-key"

# ── Step 7: Service account ───────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 7: Service account ─────────────────────────────────${NC}"
echo ""
info "The service account in credentials.json will run the Cloud Run jobs."
info "It must already have Editor access to your Google Drive roster folder."
echo ""
prompt "Enter the service account email from your credentials.json:"
prompt "(e.g. ministry-account-pc@your-project.iam.gserviceaccount.com)"
read -rp "  Service account email: " SA_EMAIL
[[ -n "$SA_EMAIL" ]] || error "Service account email cannot be empty"

# Grant access to secrets at project level
info "Granting $SA_EMAIL access to secrets..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor" &>/dev/null

# Grant permission to trigger Cloud Run jobs (needed for scheduler)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.invoker" &>/dev/null

success "Permissions granted to $SA_EMAIL"

# ── Step 8: Build and push Docker image ──────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 8: Building and pushing Docker image ───────────────${NC}"

REGION="us-central1"
REPO="roster-repo"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/roster:latest"

if ! gcloud artifacts repositories describe "$REPO" \
        --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    info "Creating Artifact Registry repository..."
    gcloud artifacts repositories create "$REPO" \
        --repository-format=docker \
        --location="$REGION" \
        --project="$PROJECT_ID"
fi

info "Building and pushing image (takes 2-3 minutes the first time)..."
gcloud builds submit \
    --tag "$IMAGE" \
    --project="$PROJECT_ID"

success "Image pushed: $IMAGE"

# ── Step 9: Create Cloud Run Jobs ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 9: Creating Cloud Run Jobs ─────────────────────────${NC}"

CRED_MOUNT_PATH="/secrets/credentials.json"
# credentials.json is mounted outside /app: Cloud Run secret volumes replace the entire
# last directory of the mount path, which would hide main.py/planning_center_reports/
# if mounted straight into /app. drive_client.py reads GOOGLE_APPLICATION_CREDENTIALS
# to find it there instead.
SECRET_ENV="$CRED_MOUNT_PATH=google-service-account-key:latest,PCO_APP_ID=PCO_APP_ID:latest,PCO_SECRET=PCO_SECRET:latest,GOOGLE_DRIVE_PARENT_FOLDER_ID=GOOGLE_DRIVE_PARENT_FOLDER_ID:latest"

create_job() {
    local job_name=$1
    local event_arg=$2

    # Always delete and recreate to ensure a clean state
    if gcloud run jobs describe "$job_name" \
            --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        info "Job $job_name already exists — recreating cleanly..."
        gcloud run jobs delete "$job_name" \
            --region="$REGION" \
            --project="$PROJECT_ID" \
            --quiet
    fi

    gcloud run jobs create "$job_name" \
        --image="$IMAGE" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --service-account="$SA_EMAIL" \
        --set-secrets="$SECRET_ENV" \
        --set-env-vars="GOOGLE_APPLICATION_CREDENTIALS=$CRED_MOUNT_PATH" \
        --args="$event_arg" \
        --task-timeout=3600

    success "Job created: $job_name"
}

# One Cloud Run job per report configured in reports.yaml. report_ids() is
# defined near the top of this script and reads the config via the CLI, so
# adding a report there is enough — no edit needed here.
for report_id in $(report_ids); do
    create_job "roster-$report_id" "$report_id"
done

# ── Step 10: Schedule the jobs ────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 10: Scheduling jobs (Monday 2 AM US Central) ───────${NC}"

# 2 AM CST = 08:00 UTC (UTC-6, Nov–Mar)
# 2 AM CDT = 07:00 UTC (UTC-5, Mar–Nov)
info "Scheduling at 08:00 UTC every Monday (= 2:00 AM US Central Standard Time)"
warn "During daylight saving time (CDT) this runs at 3 AM instead of 2 AM."
warn "To fix, update the schedule to '0 7 * * 1' in Cloud Scheduler during summer."

schedule_job() {
    local scheduler_name=$1
    local job_name=$2
    local job_uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$job_name:run"

    if gcloud scheduler jobs describe "$scheduler_name" \
            --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        info "Scheduler $scheduler_name already exists — updating..."
        gcloud scheduler jobs update http "$scheduler_name" \
            --schedule="0 8 * * 1" \
            --uri="$job_uri" \
            --message-body='{}' \
            --oauth-service-account-email="$SA_EMAIL" \
            --location="$REGION" \
            --project="$PROJECT_ID"
    else
        gcloud scheduler jobs create http "$scheduler_name" \
            --schedule="0 8 * * 1" \
            --uri="$job_uri" \
            --message-body='{}' \
            --oauth-service-account-email="$SA_EMAIL" \
            --location="$REGION" \
            --project="$PROJECT_ID"
    fi
    success "Scheduled: $scheduler_name"
}

for report_id in $(report_ids); do
    schedule_job "run-roster-$report_id" "roster-$report_id"
done

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${GREEN}${BOLD}   All done! Setup complete.${NC}"
echo -e "${BOLD}============================================================${NC}"
echo ""
echo "  Jobs will run every Monday at 2 AM US Central (08:00 UTC)."
echo ""
echo "  To test manually right now:"
echo -e "  ${CYAN}gcloud run jobs execute roster-rutas --region=$REGION --project=$PROJECT_ID${NC}"
echo -e "  ${CYAN}gcloud run jobs execute roster-escuela-dominical --region=$REGION --project=$PROJECT_ID${NC}"
echo ""
echo "  To deploy updates after editing any code:"
echo -e "  ${CYAN}./manage.sh  →  option 6${NC}"
echo ""
echo "  To view logs:"
echo -e "  ${CYAN}https://console.cloud.google.com/run/jobs?project=$PROJECT_ID${NC}"
echo ""