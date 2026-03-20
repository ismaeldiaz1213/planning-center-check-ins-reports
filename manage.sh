#!/usr/bin/env bash
# =============================================================================
# manage.sh
# Day-to-day management of the church roster Cloud Run deployment.
# Run this any time after setup_gcloud.sh has been completed.
#
# Usage:
#   chmod +x manage.sh
#   ./manage.sh
# =============================================================================

set -e

PROJECT_ID="ibl-planning-center-check-ins"
REGION="us-central1"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/roster-repo/roster:latest"
SA_EMAIL="ministry-account-pc@ibl-planning-center-check-ins.iam.gserviceaccount.com"
SECRET_ENV="PCO_APP_ID=PCO_APP_ID:latest,PCO_SECRET=PCO_SECRET:latest,GOOGLE_DRIVE_PARENT_FOLDER_ID=GOOGLE_DRIVE_PARENT_FOLDER_ID:latest"

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

# ── Main menu ─────────────────────────────────────────────────────────────────
show_menu() {
    clear
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║        Church Roster — Cloud Management Menu             ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}SECRETS${NC}"
    echo -e "  ${CYAN}1)${NC} Update PCO App ID"
    echo -e "  ${CYAN}2)${NC} Update PCO Secret"
    echo -e "  ${CYAN}3)${NC} Update Google Drive Folder ID"
    echo -e "  ${CYAN}4)${NC} View current secret values"
    echo ""
    echo -e "  ${BOLD}DEPLOYMENT${NC}"
    echo -e "  ${CYAN}5)${NC} Update credentials.json (rebuild + redeploy jobs)"
    echo -e "  ${CYAN}6)${NC} Deploy updated main.py to Cloud"
    echo -e "  ${CYAN}7)${NC} Change campaign theme"
    echo ""
    echo -e "  ${BOLD}TESTING & LOGS${NC}"
    echo -e "  ${CYAN}8)${NC} Run Rutas job now (test)"
    echo -e "  ${CYAN}9)${NC} Run Escuela Dominical job now (test)"
    echo -e "  ${CYAN}10)${NC} View logs — Rutas"
    echo -e "  ${CYAN}11)${NC} View logs — Escuela Dominical"
    echo -e "  ${CYAN}12)${NC} View job status (last run results)"
    echo ""
    echo -e "  ${BOLD}SCHEDULER${NC}"
    echo -e "  ${CYAN}13)${NC} View scheduled jobs"
    echo -e "  ${CYAN}14)${NC} Pause scheduled jobs (stop auto-run)"
    echo -e "  ${CYAN}15)${NC} Resume scheduled jobs"
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

    echo ""
    echo -e "${BOLD}── Update $secret_name ─────────────────────────────────────${NC}"
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

    success "$secret_name updated. Will take effect on next job run."
}

view_secrets() {
    echo ""
    echo -e "${BOLD}── Current Secret Values ───────────────────────────────────${NC}"
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
}

# ── Deployment ────────────────────────────────────────────────────────────────
update_credentials() {
    echo ""
    echo -e "${BOLD}── Update credentials.json ─────────────────────────────────${NC}"
    echo ""
    info "This will rebuild the Docker image with the new credentials.json"
    info "and recreate both Cloud Run jobs."
    echo ""
    read -rp "  Path to new credentials.json (default: ./credentials.json): " CREDS_PATH
    CREDS_PATH="${CREDS_PATH:-./credentials.json}"

    if [[ ! -f "$CREDS_PATH" ]]; then
        error "File not found: $CREDS_PATH"
        return
    fi

    # Copy to project root if it's not already there
    if [[ "$CREDS_PATH" != "./credentials.json" ]]; then
        cp "$CREDS_PATH" ./credentials.json
        success "Copied to ./credentials.json"
    fi

    info "Rebuilding image..."
    gcloud builds submit \
        --tag "$IMAGE" \
        --project="$PROJECT_ID"

    success "Image rebuilt with new credentials."
    _recreate_jobs
}

deploy_script() {
    echo ""
    echo -e "${BOLD}── Deploy Updated main.py ───────────────────────────────────${NC}"
    echo ""

    if [[ ! -f "main.py" ]]; then
        error "main.py not found. Run this from your project folder."
        return
    fi

    info "Building and pushing Docker image..."
    info "This takes 2-3 minutes..."
    echo ""

    gcloud builds submit \
        --tag "$IMAGE" \
        --project="$PROJECT_ID"

    success "Image deployed."
    echo ""
    info "Updating jobs to use new image..."

    gcloud run jobs update roster-rutas \
        --image="$IMAGE" \
        --region="$REGION" \
        --project="$PROJECT_ID"

    gcloud run jobs update roster-escuela-dominical \
        --image="$IMAGE" \
        --region="$REGION" \
        --project="$PROJECT_ID"

    success "Both jobs updated to latest image."
    echo ""
    read -rp "  Would you like to test Rutas now? (y/N): " RUN_NOW
    if [[ "$RUN_NOW" =~ ^[Yy]$ ]]; then
        _execute_job "roster-rutas" "Rutas"
    fi
}

_recreate_jobs() {
    echo ""
    info "Recreating Cloud Run jobs..."

    for job_name in roster-rutas roster-escuela-dominical; do
        local event_arg
        [[ "$job_name" == "roster-rutas" ]] && event_arg="Rutas" || event_arg="Escuela Dominical"

        if gcloud run jobs describe "$job_name" \
                --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
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
            --args="$event_arg" \
            --task-timeout=3600

        success "Job recreated: $job_name"
    done
}

# ── Job runners ───────────────────────────────────────────────────────────────
_execute_job() {
    local job_name=$1
    local display_name=$2

    echo ""
    warn "This will run the full script against live data and upload real PDFs."
    read -rp "  Confirm? (y/N): " CONFIRM
    [[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Cancelled."; return; }

    echo ""
    gcloud run jobs execute "$job_name" \
        --region="$REGION" \
        --project="$PROJECT_ID"

    success "Job started. Watch logs with option 9 or 10."
}

# ── Log viewers ───────────────────────────────────────────────────────────────
view_logs() {
    local job_name=$1
    local display_name=$2

    echo ""
    echo -e "${BOLD}── Logs — $display_name ────────────────────────────────────${NC}"
    echo ""
    echo -e "  ${DIM}1) Last run${NC}"
    echo -e "  ${DIM}2) Last 3 runs${NC}"
    echo -e "  ${DIM}3) Open in browser${NC}"
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
                --freshness=2d 2>/dev/null | head -100 || warn "No logs found."
            ;;
        2)
            echo ""
            gcloud logging read \
                "resource.type=cloud_run_job AND resource.labels.job_name=$job_name" \
                --project="$PROJECT_ID" \
                --limit=500 \
                --format="table(timestamp,textPayload)" \
                --freshness=14d 2>/dev/null | head -300 || warn "No logs found."
            ;;
        3)
            URL="https://console.cloud.google.com/run/jobs/details/$REGION/$job_name/logs?project=$PROJECT_ID"
            xdg-open "$URL" 2>/dev/null || echo -e "  Visit: ${CYAN}$URL${NC}"
            ;;
        *)
            warn "Invalid choice."
            ;;
    esac
}

view_job_status() {
    echo ""
    echo -e "${BOLD}── Job Status ───────────────────────────────────────────────${NC}"
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
    echo -e "  Full history: ${CYAN}https://console.cloud.google.com/run/jobs?project=$PROJECT_ID${NC}"
}

# ── Scheduler controls ────────────────────────────────────────────────────────
view_scheduler() {
    echo ""
    echo -e "${BOLD}── Scheduled Jobs ───────────────────────────────────────────${NC}"
    echo ""
    gcloud scheduler jobs list \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --format="table(name,schedule,state,lastAttemptTime)" \
        2>/dev/null || warn "No scheduled jobs found."
}

pause_scheduler() {
    echo ""
    warn "This stops the jobs from running automatically on Mondays."
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
    echo ""
    info "This re-enables automatic Monday runs."
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

change_theme() {
    echo ""
    echo -e "${BOLD}── Change Campaign Theme ────────────────────────────────────${NC}"
    echo ""
    echo -e "  ${DIM}1) Default — azul IBL (sin campaña)${NC}"
    echo -e "  ${DIM}2) 🌿 Campaña de Primavera${NC}"
    echo -e "  ${DIM}3) ☀️  Campaña de Verano${NC}"
    echo -e "  ${DIM}4) 🍂 Campaña de Otoño${NC}"
    echo -e "  ${DIM}5) ❄️  Campaña de Invierno${NC}"
    echo ""
    read -rp "  Choose: " THEME_CHOICE

    case $THEME_CHOICE in
        1) THEME_FLAG="" ;                   THEME_LABEL="Default (azul IBL)" ;;
        2) THEME_FLAG="--theme primavera";   THEME_LABEL="Campaña de Primavera" ;;
        3) THEME_FLAG="--theme verano";      THEME_LABEL="Campaña de Verano" ;;
        4) THEME_FLAG="--theme otono";       THEME_LABEL="Campaña de Otoño" ;;
        5) THEME_FLAG="--theme invierno";    THEME_LABEL="Campaña de Invierno" ;;
        *) warn "Invalid choice."; return ;;
    esac

    echo ""
    info "Updating both jobs to: $THEME_LABEL"

    for job_name in roster-rutas roster-escuela-dominical; do
        local event_arg
        [[ "$job_name" == "roster-rutas" ]] && event_arg="Rutas" || event_arg="Escuela Dominical"

        if [[ -n "$THEME_FLAG" ]]; then
            gcloud run jobs update "$job_name" \
                --args="$event_arg,$THEME_FLAG" \
                --region="$REGION" \
                --project="$PROJECT_ID"
        else
            gcloud run jobs update "$job_name" \
                --args="$event_arg" \
                --region="$REGION" \
                --project="$PROJECT_ID"
        fi
        success "Updated: $job_name → $THEME_LABEL"
    done

    echo ""
    info "Theme will apply on the next run. To test now, use option 8 or 9."
}

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
        4)  view_secrets ;;
        5)  update_credentials ;;
        6)  deploy_script ;;
        7)  change_theme ;;
        8)  _execute_job "roster-rutas" "Rutas" ;;
        9)  _execute_job "roster-escuela-dominical" "Escuela Dominical" ;;
        10) view_logs "roster-rutas" "Rutas" ;;
        11) view_logs "roster-escuela-dominical" "Escuela Dominical" ;;
        12) view_job_status ;;
        13) view_scheduler ;;
        14) pause_scheduler ;;
        15) resume_scheduler ;;
        q|Q) echo ""; info "Goodbye!"; echo ""; exit 0 ;;
        *)  warn "Invalid option — please choose 1-15 or q." ;;
    esac

    echo ""
    read -rp "  Press ENTER to return to menu..."
done