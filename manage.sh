#!/usr/bin/env bash
# =============================================================================
# manage.sh
# Day-to-day management of the church roster Cloud Run deployment.
# Run this any time after the initial setup_gcloud.sh has been completed.
#
# Usage:
#   chmod +x manage.sh
#   ./manage.sh
# =============================================================================

set -e

PROJECT_ID="ibl-planning-center-check-ins"
REGION="us-central1"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/roster-repo/roster:latest"
SA_EMAIL="991091227497-compute@developer.gserviceaccount.com"

# ── Colours ───────────────────────────────────────────────────────────────────
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

info()    { echo -e "${CYAN}ℹ  ${NC}$1"; }
success() { echo -e "${GREEN}✓  ${NC}$1"; }
warn()    { echo -e "${YELLOW}⚠  ${NC}$1"; }
error()   { echo -e "${RED}✗  ${NC}$1"; }
header()  { echo -e "\n${BOLD}── $1 ──────────────────────────────────────────────${NC}"; }

# ── Main menu ─────────────────────────────────────────────────────────────────
show_menu() {
    clear
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║        Church Roster — Cloud Management Menu             ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}SECRETS & CREDENTIALS${NC}"
    echo -e "  ${CYAN}1)${NC} Update PCO App ID"
    echo -e "  ${CYAN}2)${NC} Update PCO Secret"
    echo -e "  ${CYAN}3)${NC} Update Google Drive Folder ID"
    echo -e "  ${CYAN}4)${NC} Update credentials.json (service account key)"
    echo -e "  ${CYAN}5)${NC} View current secret values"
    echo ""
    echo -e "  ${BOLD}DEPLOYMENT${NC}"
    echo -e "  ${CYAN}6)${NC} Deploy updated main.py to Cloud"
    echo ""
    echo -e "  ${BOLD}TESTING & LOGS${NC}"
    echo -e "  ${CYAN}7)${NC} Run Rutas job now (test)"
    echo -e "  ${CYAN}8)${NC} Run Escuela Dominical job now (test)"
    echo -e "  ${CYAN}9)${NC} View logs — Rutas"
    echo -e "  ${CYAN}10)${NC} View logs — Escuela Dominical"
    echo -e "  ${CYAN}11)${NC} View job status (last run results)"
    echo ""
    echo -e "  ${BOLD}SCHEDULER${NC}"
    echo -e "  ${CYAN}12)${NC} View scheduled jobs"
    echo -e "  ${CYAN}13)${NC} Pause scheduled jobs (stop auto-run)"
    echo -e "  ${CYAN}14)${NC} Resume scheduled jobs"
    echo ""
    echo -e "  ${DIM}q)  Quit${NC}"
    echo ""
    read -rp "  Choose an option: " CHOICE
}

# ── Secret helpers ────────────────────────────────────────────────────────────
update_secret() {
    local secret_name=$1
    local prompt_text=$2
    local is_password=${3:-false}

    header "Update $secret_name"
    echo ""

    if [[ "$is_password" == "true" ]]; then
        read -rsp "  New value for $prompt_text: " NEW_VALUE
        echo ""
    else
        read -rp "  New value for $prompt_text: " NEW_VALUE
    fi

    if [[ -z "$NEW_VALUE" ]]; then
        warn "No value entered — secret not changed."
        return
    fi

    echo -n "$NEW_VALUE" | gcloud secrets versions add "$secret_name" \
        --data-file=- \
        --project="$PROJECT_ID"

    success "$secret_name updated successfully."
    echo ""
    info "The new value will be used on the next job run automatically."
}

update_credentials_file() {
    header "Update credentials.json"
    echo ""
    info "Enter the path to your new credentials.json file."
    read -rp "  Path (default: ./credentials.json): " CREDS_PATH
    CREDS_PATH="${CREDS_PATH:-./credentials.json}"

    if [[ ! -f "$CREDS_PATH" ]]; then
        error "File not found: $CREDS_PATH"
        return
    fi

    gcloud secrets versions add "GOOGLE_CREDENTIALS" \
        --data-file="$CREDS_PATH" \
        --project="$PROJECT_ID"

    success "credentials.json updated in Secret Manager."
    info "The new credentials will be used on the next job run automatically."
}

view_secrets() {
    header "Current Secret Values"
    echo ""
    warn "Showing secret values — don't share your screen if others are around."
    echo ""
    read -rp "  Are you sure? (y/N): " CONFIRM
    [[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Cancelled."; return; }

    echo ""
    for secret in PCO_APP_ID PCO_SECRET GOOGLE_DRIVE_PARENT_FOLDER_ID; do
        VALUE=$(gcloud secrets versions access latest \
            --secret="$secret" \
            --project="$PROJECT_ID" 2>/dev/null || echo "(not set)")
        echo -e "  ${BOLD}$secret${NC}: $VALUE"
    done

    # Show credentials.json summary without dumping the whole thing
    echo ""
    CREDS=$(gcloud secrets versions access latest \
        --secret="GOOGLE_CREDENTIALS" \
        --project="$PROJECT_ID" 2>/dev/null || echo "")
    if [[ -n "$CREDS" ]]; then
        CLIENT_EMAIL=$(echo "$CREDS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('client_email','(unknown)'))" 2>/dev/null || echo "(parse error)")
        echo -e "  ${BOLD}GOOGLE_CREDENTIALS${NC}: ✓ set (service account: $CLIENT_EMAIL)"
    else
        echo -e "  ${BOLD}GOOGLE_CREDENTIALS${NC}: (not set)"
    fi
}

# ── Deployment ────────────────────────────────────────────────────────────────
deploy_script() {
    header "Deploy Updated main.py"
    echo ""

    if [[ ! -f "main.py" ]]; then
        error "main.py not found in current directory."
        info "Make sure you're running this from your project folder."
        return
    fi

    info "Building and pushing Docker image..."
    info "This takes 2-3 minutes..."
    echo ""

    gcloud builds submit \
        --tag "$IMAGE" \
        --project="$PROJECT_ID"

    success "Image deployed successfully!"
    echo ""
    info "Both Cloud Run jobs will use the new code on their next run."
    echo ""
    read -rp "  Would you like to test it now? (y/N): " RUN_NOW
    if [[ "$RUN_NOW" =~ ^[Yy]$ ]]; then
        run_job "roster-rutas" "Rutas"
    fi
}

# ── Job runners ───────────────────────────────────────────────────────────────
run_job() {
    local job_name=$1
    local display_name=$2

    header "Running $display_name job"
    echo ""
    info "Starting job — this will run the full script against live data."
    warn "This will generate and upload real PDFs to Google Drive."
    echo ""
    read -rp "  Confirm run? (y/N): " CONFIRM
    [[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Cancelled."; return; }

    echo ""
    info "Executing job..."
    EXECUTION=$(gcloud run jobs execute "$job_name" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(metadata.name)" 2>/dev/null)

    success "Job started: $EXECUTION"
    echo ""
    info "Streaming logs (Ctrl+C to stop following, job will keep running)..."
    echo ""

    sleep 3  # Give it a moment to start

    gcloud logging read \
        "resource.type=cloud_run_job AND resource.labels.job_name=$job_name" \
        --project="$PROJECT_ID" \
        --limit=50 \
        --format="value(textPayload)" \
        --freshness=5m \
        2>/dev/null || warn "Could not stream logs. Check Cloud Console for output."

    echo ""
    info "To see full logs, select 'View logs' from the main menu."
}

# ── Log viewers ───────────────────────────────────────────────────────────────
view_logs() {
    local job_name=$1
    local display_name=$2

    header "Logs — $display_name"
    echo ""
    echo -e "  ${DIM}1) Last run only${NC}"
    echo -e "  ${DIM}2) Last 3 runs${NC}"
    echo -e "  ${DIM}3) Open in browser (Cloud Console)${NC}"
    echo ""
    read -rp "  Choose: " LOG_CHOICE

    case $LOG_CHOICE in
        1)
            echo ""
            gcloud logging read \
                "resource.type=cloud_run_job AND resource.labels.job_name=$job_name" \
                --project="$PROJECT_ID" \
                --limit=200 \
                --format="table(timestamp,textPayload)" \
                --freshness=2d \
                2>/dev/null | head -100 || warn "No logs found."
            ;;
        2)
            echo ""
            gcloud logging read \
                "resource.type=cloud_run_job AND resource.labels.job_name=$job_name" \
                --project="$PROJECT_ID" \
                --limit=500 \
                --format="table(timestamp,textPayload)" \
                --freshness=14d \
                2>/dev/null | head -300 || warn "No logs found."
            ;;
        3)
            URL="https://console.cloud.google.com/run/jobs/details/$REGION/$job_name/logs?project=$PROJECT_ID"
            info "Opening: $URL"
            xdg-open "$URL" 2>/dev/null || echo "  Visit: $URL"
            ;;
        *)
            warn "Invalid choice."
            ;;
    esac
}

# ── Job status ────────────────────────────────────────────────────────────────
view_job_status() {
    header "Job Status"
    echo ""

    for job in roster-rutas roster-escuela-dominical; do
        echo -e "  ${BOLD}$job${NC}"
        gcloud run jobs describe "$job" \
            --region="$REGION" \
            --project="$PROJECT_ID" \
            --format="table[no-heading](status.latestCreatedExecution.name,status.latestCreatedExecution.completionTime,status.conditions[0].type)" \
            2>/dev/null || echo "    (not found)"
        echo ""
    done

    info "Full job history:"
    echo -e "  ${CYAN}https://console.cloud.google.com/run/jobs?project=$PROJECT_ID${NC}"
}

# ── Scheduler controls ────────────────────────────────────────────────────────
view_scheduler() {
    header "Scheduled Jobs"
    echo ""
    gcloud scheduler jobs list \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --format="table(name,schedule,state,lastAttemptTime)" \
        2>/dev/null || warn "No scheduled jobs found."
}

pause_scheduler() {
    header "Pause Scheduled Jobs"
    echo ""
    warn "This will stop the jobs from running automatically on Mondays."
    read -rp "  Confirm pause? (y/N): " CONFIRM
    [[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Cancelled."; return; }

    for job in run-roster-rutas run-roster-escuela-dominical; do
        gcloud scheduler jobs pause "$job" \
            --location="$REGION" \
            --project="$PROJECT_ID" 2>/dev/null && \
            success "Paused: $job" || warn "Could not pause $job (may already be paused)"
    done
}

resume_scheduler() {
    header "Resume Scheduled Jobs"
    echo ""
    info "This will re-enable automatic Monday runs."
    read -rp "  Confirm resume? (y/N): " CONFIRM
    [[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Cancelled."; return; }

    for job in run-roster-rutas run-roster-escuela-dominical; do
        gcloud scheduler jobs resume "$job" \
            --location="$REGION" \
            --project="$PROJECT_ID" 2>/dev/null && \
            success "Resumed: $job" || warn "Could not resume $job"
    done
}

# ── Main loop ─────────────────────────────────────────────────────────────────
# Verify gcloud is available
command -v gcloud &>/dev/null || {
    echo "gcloud not found. Install from https://cloud.google.com/sdk/docs/install"
    exit 1
}

while true; do
    show_menu
    echo ""

    case $CHOICE in
        1)  update_secret "PCO_APP_ID" "PCO App ID" ;;
        2)  update_secret "PCO_SECRET" "PCO Secret" true ;;
        3)  update_secret "GOOGLE_DRIVE_PARENT_FOLDER_ID" "Google Drive Folder ID" ;;
        4)  update_credentials_file ;;
        5)  view_secrets ;;
        6)  deploy_script ;;
        7)  run_job "roster-rutas" "Rutas" ;;
        8)  run_job "roster-escuela-dominical" "Escuela Dominical" ;;
        9)  view_logs "roster-rutas" "Rutas" ;;
        10) view_logs "roster-escuela-dominical" "Escuela Dominical" ;;
        11) view_job_status ;;
        12) view_scheduler ;;
        13) pause_scheduler ;;
        14) resume_scheduler ;;
        q|Q) echo ""; info "Goodbye!"; echo ""; exit 0 ;;
        *)  warn "Invalid option — please choose 1-14 or q." ;;
    esac

    echo ""
    read -rp "  Press ENTER to return to menu..."
done
