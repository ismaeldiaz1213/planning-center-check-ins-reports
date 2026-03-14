#!/usr/bin/env bash
# =============================================================================
# setup_gcloud.sh
# Interactive setup script for deploying the church roster generator to
# Google Cloud Run + Cloud Scheduler.
#
# Requirements before running:
#   - Google Cloud SDK installed  (https://cloud.google.com/sdk/docs/install)
#   - Docker installed            (https://docs.docker.com/get-docker/)
#   - A Google Cloud account      (https://cloud.google.com)
#
# Usage:
#   chmod +x setup_gcloud.sh
#   ./setup_gcloud.sh
# =============================================================================

set -e  # Exit immediately on any error

# ── Colours ──────────────────────────────────────────────────────────────────
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Colour

info()    { echo -e "${CYAN}ℹ ${NC}$1"; }
success() { echo -e "${GREEN}✓ ${NC}$1"; }
warn()    { echo -e "${YELLOW}⚠ ${NC}$1"; }
error()   { echo -e "${RED}✗ ${NC}$1"; exit 1; }
prompt()  { echo -e "${BOLD}→ $1${NC}"; }

echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD}   Church Roster Generator — Google Cloud Setup${NC}"
echo -e "${BOLD}============================================================${NC}"
echo ""
echo "This script will:"
echo "  1. Log you into Google Cloud"
echo "  2. Create (or reuse) a Google Cloud project"
echo "  3. Enable the required APIs"
echo "  4. Store your secrets securely"
echo "  5. Build and push the Docker image"
echo "  6. Create Cloud Run Jobs for Rutas + Escuela Dominical"
echo "  7. Schedule them to run every Monday at 2 AM (US Central)"
echo ""
read -rp "Press ENTER to begin, or Ctrl+C to cancel..."

# ── Step 1: Check prerequisites ───────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 1: Checking prerequisites ──────────────────────────${NC}"

command -v gcloud &>/dev/null || error "gcloud not found. Install it from https://cloud.google.com/sdk/docs/install"
success "gcloud found"

command -v docker &>/dev/null || error "Docker not found. Install it from https://docs.docker.com/get-docker/"
success "Docker found"

# Check required files exist
for f in main.py ibl_logo.png credentials.json Dockerfile requirements.txt; do
    [[ -f "$f" ]] || error "Missing required file: $f — make sure you're running this from your project folder."
    success "Found $f"
done

# ── Step 2: Google Cloud login ────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 2: Google Cloud login ──────────────────────────────${NC}"
info "Opening browser for Google Cloud login..."
gcloud auth login
success "Logged in"

# ── Step 3: Project setup ─────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 3: Google Cloud project ────────────────────────────${NC}"
echo ""
echo "You need a Google Cloud project. You can use an existing one or create new."
echo ""
prompt "Enter your Google Cloud project ID (e.g. church-roster-2024):"
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

# ── Step 4: Enable APIs ───────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 4: Enabling required Google Cloud APIs ─────────────${NC}"
info "This may take a minute..."

gcloud services enable \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com

success "All APIs enabled"

# ── Step 5: Collect secrets ───────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 5: Your credentials ────────────────────────────────${NC}"
echo ""
info "These will be stored securely in Google Secret Manager — not in any file."
echo ""

prompt "PCO App ID (from https://api.planningcenteronline.com/oauth/applications):"
read -rp "  PCO_APP_ID: " PCO_APP_ID
[[ -n "$PCO_APP_ID" ]] || error "PCO_APP_ID cannot be empty"

prompt "PCO Secret:"
read -rsp "  PCO_SECRET: " PCO_SECRET
echo ""
[[ -n "$PCO_SECRET" ]] || error "PCO_SECRET cannot be empty"

prompt "Google Drive parent folder ID (from the folder's URL in Drive):"
read -rp "  DRIVE_FOLDER_ID: " DRIVE_FOLDER_ID
[[ -n "$DRIVE_FOLDER_ID" ]] || error "DRIVE_FOLDER_ID cannot be empty"

# ── Step 6: Store secrets ─────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 6: Storing secrets in Secret Manager ───────────────${NC}"

store_secret() {
    local name=$1
    local value=$2
    if gcloud secrets describe "$name" --project="$PROJECT_ID" &>/dev/null; then
        info "Secret $name already exists — updating..."
        echo -n "$value" | gcloud secrets versions add "$name" --data-file=-
    else
        echo -n "$value" | gcloud secrets create "$name" --data-file=- --replication-policy="automatic"
    fi
    success "Stored secret: $name"
}

store_secret "PCO_APP_ID"                    "$PCO_APP_ID"
store_secret "PCO_SECRET"                    "$PCO_SECRET"
store_secret "GOOGLE_DRIVE_PARENT_FOLDER_ID" "$DRIVE_FOLDER_ID"

info "Storing credentials.json as a secret..."
gcloud secrets create "GOOGLE_CREDENTIALS" \
    --data-file=credentials.json \
    --replication-policy="automatic" \
    --project="$PROJECT_ID" 2>/dev/null || \
gcloud secrets versions add "GOOGLE_CREDENTIALS" \
    --data-file=credentials.json \
    --project="$PROJECT_ID"
success "Stored secret: GOOGLE_CREDENTIALS"

# ── Step 7: Get service account ───────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 7: Service account ─────────────────────────────────${NC}"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
SA_EMAIL="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
info "Using default Compute service account: $SA_EMAIL"

# Grant it access to secrets
for secret in PCO_APP_ID PCO_SECRET GOOGLE_DRIVE_PARENT_FOLDER_ID GOOGLE_CREDENTIALS; do
    gcloud secrets add-iam-policy-binding "$secret" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" &>/dev/null
done
success "Service account granted access to secrets"

# ── Step 8: Build and push Docker image ──────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 8: Building and pushing Docker image ───────────────${NC}"

REGION="us-central1"
REPO="roster-repo"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/roster:latest"

# Create Artifact Registry repo if it doesn't exist
if ! gcloud artifacts repositories describe "$REPO" --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    info "Creating Artifact Registry repository..."
    gcloud artifacts repositories create "$REPO" \
        --repository-format=docker \
        --location="$REGION" \
        --project="$PROJECT_ID"
fi

info "Building and pushing image (this takes 2-3 minutes the first time)..."
gcloud builds submit \
    --tag "$IMAGE" \
    --project="$PROJECT_ID"

success "Image pushed: $IMAGE"

# ── Step 9: Create Cloud Run Jobs ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 9: Creating Cloud Run Jobs ─────────────────────────${NC}"

SECRET_ENV="PCO_APP_ID=PCO_APP_ID:latest,PCO_SECRET=PCO_SECRET:latest,GOOGLE_DRIVE_PARENT_FOLDER_ID=GOOGLE_DRIVE_PARENT_FOLDER_ID:latest,GOOGLE_CREDENTIALS=GOOGLE_CREDENTIALS:latest"

create_job() {
    local job_name=$1
    local event_arg=$2

    if gcloud run jobs describe "$job_name" --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        info "Job $job_name already exists — updating..."
        gcloud run jobs update "$job_name" \
            --image "$IMAGE" \
            --region "$REGION" \
            --project "$PROJECT_ID" \
            --set-secrets "$SECRET_ENV" \
            --args="$event_arg"
    else
        gcloud run jobs create "$job_name" \
            --image "$IMAGE" \
            --region "$REGION" \
            --project "$PROJECT_ID" \
            --set-secrets "$SECRET_ENV" \
            --args="$event_arg" \
            --service-account "$SA_EMAIL"
    fi
    success "Job ready: $job_name"
}

create_job "roster-rutas"            "Rutas"
create_job "roster-escuela-dominical" "Escuela Dominical"

# ── Step 10: Schedule the jobs ────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 10: Scheduling jobs (Monday 2 AM US Central) ───────${NC}"

# 2 AM CST  = 8 AM UTC  (UTC-6, Nov–Mar)
# 2 AM CDT  = 7 AM UTC  (UTC-5, Mar–Nov)
# We schedule for 8 AM UTC which is 2 AM CST; adjust if you're in CDT
info "Scheduling at 08:00 UTC every Monday (= 2:00 AM US Central Standard Time)"
warn "If you're on CDT (summer), change the hour to 07 in Cloud Scheduler."

schedule_job() {
    local scheduler_name=$1
    local job_name=$2
    local job_uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$job_name:run"

    if gcloud scheduler jobs describe "$scheduler_name" --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
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

# Grant scheduler permission to invoke Cloud Run jobs
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.invoker" &>/dev/null

schedule_job "run-roster-rutas"            "roster-rutas"
schedule_job "run-roster-escuela-dominical" "roster-escuela-dominical"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${GREEN}${BOLD}   All done! Setup complete.${NC}"
echo -e "${BOLD}============================================================${NC}"
echo ""
echo "  Your jobs will run every Monday at 2 AM US Central (08:00 UTC)."
echo ""
echo "  To test a job manually right now:"
echo -e "  ${CYAN}gcloud run jobs execute roster-rutas --region=$REGION --project=$PROJECT_ID${NC}"
echo -e "  ${CYAN}gcloud run jobs execute roster-escuela-dominical --region=$REGION --project=$PROJECT_ID${NC}"
echo ""
echo "  To update the script after making changes to main.py:"
echo -e "  ${CYAN}gcloud builds submit --tag $IMAGE --project=$PROJECT_ID${NC}"
echo ""
echo "  To view logs:"
echo -e "  ${CYAN}https://console.cloud.google.com/run/jobs?project=$PROJECT_ID${NC}"
echo ""