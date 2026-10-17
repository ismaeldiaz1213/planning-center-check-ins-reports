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

# Absolute path to this script's directory, so report_ids() can reach backend/
# regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env so GCP_PROJECT_ID, GCP_SA_EMAIL, GOOGLE_CLIENT_ID, etc. are available.
if [[ -f ".env" ]]; then
    set -a
    # shellcheck source=.env
    source .env
    set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:-}"
SA_EMAIL="${GCP_SA_EMAIL:-}"
if [[ -z "$PROJECT_ID" ]]; then
    read -rp "  GCP_PROJECT_ID not set in .env — enter your GCP project ID: " PROJECT_ID
fi
if [[ -z "$SA_EMAIL" ]]; then
    read -rp "  GCP_SA_EMAIL not set in .env — enter your service account email: " SA_EMAIL
fi

REGION="us-central1"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/roster-repo/roster:latest"
API_IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/roster-repo/roster-api:latest"
API_SERVICE_NAME="roster-api"
DEMO_SERVICE_NAME="roster-api-demo"
CRED_MOUNT_PATH="/secrets/credentials.json"
# credentials.json is mounted outside /app: Cloud Run secret volumes replace the entire
# last directory of the mount path, which would hide main.py/planning_center_reports/
# if mounted straight into /app. drive_client.py reads GOOGLE_APPLICATION_CREDENTIALS
# to find it there instead.
SECRET_ENV="$CRED_MOUNT_PATH=google-service-account-key:latest,PCO_APP_ID=PCO_APP_ID:latest,PCO_SECRET=PCO_SECRET:latest,GOOGLE_DRIVE_PARENT_FOLDER_ID=GOOGLE_DRIVE_PARENT_FOLDER_ID:latest"
# One scheduled job runs every report in a single process (python main.py --all),
# so shared PCO data is fetched once and PCO is never hit by parallel jobs.
# The per-report roster-<id> jobs stay, unscheduled, for one-off runs (option 8).
WEEKLY_JOB="roster-weekly"
WEEKLY_SCHEDULE="run-roster-weekly"
LOCAL_IMAGE="roster-job-local"
LOCAL_OUT_DIR="./out"

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
# ── Report registry ───────────────────────────────────────────────────────────
# The set of reports comes from reports.yaml (or the built-in defaults when
# there is no such file), read through the CLI. Adding a report there makes it
# appear in every menu below with no edit to this script.

report_ids() {
    local ids
    ids=$(cd "$SCRIPT_DIR/backend" && python3 main.py --list-reports --format ids 2>/dev/null) || ids=""
    if [[ -z "$ids" ]]; then
        warn "Could not read reports.yaml — falling back to 'rutas escuela'" >&2
        echo "rutas escuela"
    else
        echo "$ids"
    fi
}

# Prompt for one report; sets PICKED_REPORT (id) and PICKED_JOB (Cloud Run job name).
pick_report() {
    local prompt_text=${1:-"Choose a report"}
    local ids=()
    mapfile -t ids < <(report_ids)

    if [[ ${#ids[@]} -eq 0 ]]; then
        warn "No reports configured."
        return 1
    fi

    echo ""
    echo -e "  ${BOLD}$prompt_text${NC}"
    local i=1
    for id in "${ids[@]}"; do
        echo -e "  ${DIM}$i) $id${NC}"
        ((i++))
    done
    echo ""
    read -rp "  Choose: " REPORT_CHOICE

    if ! [[ "$REPORT_CHOICE" =~ ^[0-9]+$ ]] || \
       (( REPORT_CHOICE < 1 || REPORT_CHOICE > ${#ids[@]} )); then
        warn "Invalid choice."
        return 1
    fi

    PICKED_REPORT="${ids[$((REPORT_CHOICE - 1))]}"
    PICKED_JOB="roster-$PICKED_REPORT"
    return 0
}

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
    echo -e "  ${CYAN}5)${NC} Update credentials.json (upload secret + redeploy jobs)"
    echo -e "  ${CYAN}6)${NC} Deploy updated code to Cloud"
    echo -e "  ${CYAN}7)${NC} Change campaign theme"
    echo ""
    echo -e "  ${BOLD}TESTING & LOGS${NC}"
    echo -e "  ${CYAN}8)${NC} Run a report job now (test)"
    echo -e "  ${CYAN}9)${NC} View logs for a report"
    echo -e "  ${CYAN}10)${NC} Sync Cloud Run jobs with reports.yaml"
    echo -e "  ${CYAN}11)${NC} View job status (last run results)"
    echo ""
    echo -e "  ${BOLD}SCHEDULER${NC}"
    echo -e "  ${CYAN}12)${NC} View scheduled jobs"
    echo -e "  ${CYAN}13)${NC} Pause scheduled jobs (stop auto-run)"
    echo -e "  ${CYAN}14)${NC} Resume scheduled jobs"
    echo ""
    echo -e "  ${BOLD}API SERVICE${NC}"
    echo -e "  ${CYAN}15)${NC} Deploy / redeploy API service"
    echo -e "  ${CYAN}16)${NC} View API service URL"
    echo -e "  ${CYAN}17)${NC} View API service logs"
    echo -e "  ${CYAN}18)${NC} Open API service in browser"
    echo ""
    echo -e "  ${BOLD}LOCAL TESTING${NC} ${DIM}(real PCO data — no Drive upload)${NC}"
    echo -e "  ${CYAN}19)${NC} Build local Docker image"
    echo -e "  ${CYAN}20)${NC} Dry-run a report — all locations"
    echo -e "  ${CYAN}21)${NC} Dry-run a report — single location"
    echo ""
    echo -e "  ${BOLD}DEMO SERVICE${NC} ${DIM}(public demo — mock data, no auth)${NC}"
    echo -e "  ${CYAN}22)${NC} Deploy Demo Service (first-time setup)"
    echo -e "  ${CYAN}23)${NC} View Demo URL"
    echo -e "  ${CYAN}24)${NC} Open Demo in browser"
    echo ""
    echo -e "  ${BOLD}GCLOUD${NC} ${DIM}(active: $(gcloud config get-value project 2>/dev/null || echo none))${NC}"
    echo -e "  ${CYAN}25)${NC} Switch active gcloud project"
    echo ""
    echo -e "  ${DIM}q)  Quit${NC}"
    echo ""
    read -rp "  Choose an option: " CHOICE
}

# ── gcloud project switcher ───────────────────────────────────────────────────
# Every command in this script passes --project="$PROJECT_ID" explicitly, so the
# active gcloud project only matters for gcloud commands run by hand. This
# toggles it between this roster project and any other project you own.
switch_gcloud_project() {
    local current
    current=$(gcloud config get-value project 2>/dev/null)
    info "Active gcloud project: ${BOLD}${current:-(none)}${NC}"
    echo ""
    echo -e "  ${CYAN}1)${NC} $PROJECT_ID ${DIM}(this roster project)${NC}"
    echo -e "  ${CYAN}2)${NC} Pick from my other projects"
    echo ""
    read -rp "  Choose: " PROJ_CHOICE

    local target
    case $PROJ_CHOICE in
        1) target="$PROJECT_ID" ;;
        2)
            local projects=()
            mapfile -t projects < <(gcloud projects list --format="value(projectId)" 2>/dev/null)
            if [[ ${#projects[@]} -eq 0 ]]; then
                warn "No projects found (try 'gcloud auth login')."
                return
            fi
            local i=1
            for p in "${projects[@]}"; do
                echo -e "  ${DIM}$i) $p${NC}"
                ((i++))
            done
            read -rp "  Choose: " P
            if ! [[ "$P" =~ ^[0-9]+$ ]] || (( P < 1 || P > ${#projects[@]} )); then
                warn "Invalid choice."
                return
            fi
            target="${projects[$((P - 1))]}"
            ;;
        *) warn "Invalid choice."; return ;;
    esac

    gcloud config set project "$target"
    success "Active gcloud project is now: $target"
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
    info "credentials.json is not baked into the Docker image — it's stored in"
    info "Secret Manager and mounted into the container at runtime. This uploads"
    info "the new file as a secret version; no image rebuild is needed."
    echo ""
    read -rp "  Path to new credentials.json (default: ./credentials.json): " CREDS_PATH
    CREDS_PATH="${CREDS_PATH:-./credentials.json}"

    if [[ ! -f "$CREDS_PATH" ]]; then
        error "File not found: $CREDS_PATH"
        return
    fi

    info "Uploading to Secret Manager..."
    if gcloud secrets describe google-service-account-key --project="$PROJECT_ID" &>/dev/null; then
        gcloud secrets versions add google-service-account-key \
            --data-file="$CREDS_PATH" \
            --project="$PROJECT_ID"
    else
        gcloud secrets create google-service-account-key \
            --data-file="$CREDS_PATH" \
            --replication-policy="automatic" \
            --project="$PROJECT_ID"
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/secretmanager.secretAccessor" &>/dev/null
    fi
    success "Secret google-service-account-key updated."

    _recreate_jobs
}

deploy_script() {
    echo ""
    echo -e "${BOLD}── Deploy Updated Code ──────────────────────────────────────${NC}"
    echo ""

    if [[ ! -f "backend/main.py" ]] || [[ ! -d "backend/planning_center_reports" ]]; then
        error "Project files not found. Run this from the project root folder."
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

    for report_id in $(report_ids); do
        _ensure_job "roster-$report_id" "$report_id"
    done
    _ensure_job "$WEEKLY_JOB" "--all"
    _ensure_schedule

    success "All report jobs updated to latest image."
    info "Run option 10 (Sync Cloud Run jobs) if you have renamed or removed a report."
    echo ""
    read -rp "  Would you like to test a report now? (y/N): " RUN_NOW
    if [[ "$RUN_NOW" =~ ^[Yy]$ ]]; then
        pick_report "Which report should run?" && _execute_job "$PICKED_JOB" "$PICKED_REPORT"
    fi
}

_job_exists() {
    gcloud run jobs describe "$1" --region="$REGION" --project="$PROJECT_ID" &>/dev/null
}

_schedule_exists() {
    gcloud scheduler jobs describe "$1" --location="$REGION" --project="$PROJECT_ID" &>/dev/null
}

# Create a Cloud Run job if it is missing; otherwise point it at the current
# image. Used by both "deploy code" and "sync jobs" so a report newly added to
# reports.yaml does not need a full setup_gcloud run.
#   _ensure_job roster-escuela escuela     # one report, run by hand
#   _ensure_job roster-weekly --all        # every report, run on the schedule
_ensure_job() {
    local job_name=$1
    local job_args=$2

    if _job_exists "$job_name"; then
        gcloud run jobs update "$job_name" \
            --image="$IMAGE" \
            --args="$job_args" \
            --region="$REGION" \
            --project="$PROJECT_ID"
        success "Updated: $job_name"
    else
        info "$job_name does not exist yet — creating it..."
        gcloud run jobs create "$job_name" \
            --image="$IMAGE" \
            --region="$REGION" \
            --project="$PROJECT_ID" \
            --service-account="$SA_EMAIL" \
            --set-secrets="$SECRET_ENV" \
            --set-env-vars="GOOGLE_APPLICATION_CREDENTIALS=$CRED_MOUNT_PATH" \
            --args="$job_args" \
            --task-timeout=3600
        success "Created: $job_name"
    fi
}

# Create the Monday schedule for the weekly all-reports job if it is missing.
_ensure_schedule() {
    local job_uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$WEEKLY_JOB:run"

    if _schedule_exists "$WEEKLY_SCHEDULE"; then
        return
    fi
    info "$WEEKLY_SCHEDULE does not exist yet — creating it..."
    gcloud scheduler jobs create http "$WEEKLY_SCHEDULE" \
        --schedule="0 8 * * 1" \
        --uri="$job_uri" \
        --message-body='{}' \
        --oauth-service-account-email="$SA_EMAIL" \
        --location="$REGION" \
        --project="$PROJECT_ID"
    success "Scheduled: $WEEKLY_SCHEDULE (Mondays 08:00 UTC)"
}

# Reconcile Cloud Run with reports.yaml: create anything missing, and report any
# roster-* job that no longer corresponds to a configured report. Orphans matter
# because a stale job keeps firing on its old schedule and would generate a
# duplicate set of rosters.
sync_jobs() {
    echo ""
    echo -e "${BOLD}── Sync Cloud Run Jobs with reports.yaml ────────────────────${NC}"
    echo ""

    local configured=()
    mapfile -t configured < <(report_ids)
    info "Configured reports: ${configured[*]}"
    echo ""

    for report_id in "${configured[@]}"; do
        _ensure_job "roster-$report_id" "$report_id"
    done
    _ensure_job "$WEEKLY_JOB" "--all"
    _ensure_schedule

    # ── Per-report schedules are replaced by the weekly job ──────────────────
    local old_schedules=()
    mapfile -t old_schedules < <(gcloud scheduler jobs list \
        --location="$REGION" --project="$PROJECT_ID" \
        --format="value(name.basename())" 2>/dev/null \
        | grep '^run-roster-' | grep -v "^$WEEKLY_SCHEDULE\$" || true)
    if [[ ${#old_schedules[@]} -gt 0 && -n "${old_schedules[0]}" ]]; then
        echo ""
        warn "These per-report schedules would run rosters a second time alongside $WEEKLY_SCHEDULE:"
        for name in "${old_schedules[@]}"; do echo -e "    ${YELLOW}$name${NC}"; done
        read -rp "  Delete them? (y/N): " CONFIRM
        if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
            for name in "${old_schedules[@]}"; do
                gcloud scheduler jobs delete "$name" \
                    --location="$REGION" --project="$PROJECT_ID" --quiet \
                    && success "Deleted schedule: $name"
            done
        fi
    fi

    # ── Orphan detection ──────────────────────────────────────────────────────
    echo ""
    info "Checking for jobs that no longer match a configured report..."

    local existing=()
    mapfile -t existing < <(gcloud run jobs list \
        --region="$REGION" --project="$PROJECT_ID" \
        --format="value(metadata.name)" 2>/dev/null | grep '^roster-' || true)

    local orphans=()
    for job_name in "${existing[@]}"; do
        [[ -z "$job_name" || "$job_name" == "$WEEKLY_JOB" ]] && continue
        local id="${job_name#roster-}"
        local found=0
        for report_id in "${configured[@]}"; do
            [[ "$id" == "$report_id" ]] && found=1 && break
        done
        (( found )) || orphans+=("$job_name")
    done

    if [[ ${#orphans[@]} -eq 0 ]]; then
        success "No orphaned jobs. Cloud Run matches reports.yaml."
        return
    fi

    echo ""
    warn "These Cloud Run jobs do not match any report in reports.yaml:"
    for job_name in "${orphans[@]}"; do
        echo -e "    ${YELLOW}$job_name${NC}"
    done
    echo ""
    warn "Left in place, each keeps running on its own schedule and will generate"
    warn "a duplicate set of rosters every week."
    echo ""
    read -rp "  Delete these jobs and their schedules? (y/N): " CONFIRM
    [[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Left in place."; return; }

    for job_name in "${orphans[@]}"; do
        local scheduler_name="run-${job_name}"
        if _schedule_exists "$scheduler_name"; then
            gcloud scheduler jobs delete "$scheduler_name" \
                --location="$REGION" --project="$PROJECT_ID" --quiet \
                && success "Deleted schedule: $scheduler_name"
        fi
        gcloud run jobs delete "$job_name" \
            --region="$REGION" --project="$PROJECT_ID" --quiet \
            && success "Deleted job: $job_name"
    done
}

_recreate_jobs() {
    echo ""
    info "Recreating Cloud Run jobs..."

    for report_id in $(report_ids); do
        local job_name="roster-$report_id"
        local event_arg="$report_id"

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
            --set-env-vars="GOOGLE_APPLICATION_CREDENTIALS=$CRED_MOUNT_PATH" \
            --args="$event_arg" \
            --task-timeout=3600

        success "Job recreated: $job_name"
    done
    _ensure_job "$WEEKLY_JOB" "--all"
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

    success "Job started. Watch logs with option 9."
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
    for report_id in $(report_ids); do
        local job="roster-$report_id"
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

    gcloud scheduler jobs pause "$WEEKLY_SCHEDULE" \
        --location="$REGION" \
        --project="$PROJECT_ID" 2>/dev/null && \
        success "Paused: $WEEKLY_SCHEDULE" || warn "Could not pause $WEEKLY_SCHEDULE (may already be paused)"
}

resume_scheduler() {
    echo ""
    info "This re-enables automatic Monday runs."
    read -rp "  Confirm resume? (y/N): " CONFIRM
    [[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Cancelled."; return; }

    gcloud scheduler jobs resume "$WEEKLY_SCHEDULE" \
        --location="$REGION" \
        --project="$PROJECT_ID" 2>/dev/null && \
        success "Resumed: $WEEKLY_SCHEDULE" || warn "Could not resume $WEEKLY_SCHEDULE"
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
        1) THEME_VALUE="" ;          THEME_LABEL="Default (azul IBL)" ;;
        2) THEME_VALUE="primavera";  THEME_LABEL="Campaña de Primavera" ;;
        3) THEME_VALUE="verano";     THEME_LABEL="Campaña de Verano" ;;
        4) THEME_VALUE="otono";      THEME_LABEL="Campaña de Otoño" ;;
        5) THEME_VALUE="invierno";   THEME_LABEL="Campaña de Invierno" ;;
        *) warn "Invalid choice."; return ;;
    esac

    echo ""
    info "Updating all report jobs to: $THEME_LABEL"

    for report_id in $(report_ids); do
        local job_name="roster-$report_id"
        local event_arg="$report_id"

        # Cloud Run --args is a comma-separated list of individual tokens.
        # "--theme primavera" as one token fails; must be "--theme,primavera" (two).
        if [[ -n "$THEME_VALUE" ]]; then
            gcloud run jobs update "$job_name" \
                --args="$event_arg,--theme,$THEME_VALUE" \
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

# ── API Service ───────────────────────────────────────────────────────────────

deploy_api_service() {
    echo ""
    echo -e "${BOLD}── Deploy API Service ───────────────────────────────────────${NC}"
    echo ""

    if [[ ! -f "Dockerfile.api" ]]; then
        error "Dockerfile.api not found. Run this from the project root folder."
        return
    fi

    if ! gcloud secrets describe google-service-account-key --project="$PROJECT_ID" &>/dev/null; then
        error "Secret google-service-account-key not found in Secret Manager — run option 5 first."
        return
    fi

    info "Building React frontend..."
    (cd frontend && npm run build) || { error "Frontend build failed."; return; }
    success "Frontend built into backend/static/."
    echo ""

    info "Submitting Docker build to Cloud Build..."
    info "This takes 3-5 minutes..."
    echo ""

    gcloud builds submit \
        --config cloudbuild-api.yaml \
        --project="$PROJECT_ID" || { error "Cloud Build failed."; return; }

    success "API image pushed to Artifact Registry."
    echo ""

    # GOOGLE_CLIENT_ID is sourced from .env at startup; prompt if still missing.
    local google_client_id="${GOOGLE_CLIENT_ID:-}"
    if [[ -z "$google_client_id" ]]; then
        echo ""
        info "Google OAuth restricts access to domains in ALLOWED_GOOGLE_DOMAINS (blank = any Google account)."
        read -rp "  Google OAuth Client ID (leave blank to disable auth): " google_client_id
    fi

    info "Deploying Cloud Run service (creates or updates)..."
    echo ""

    # gcloud run deploy creates the service on first run and updates it on subsequent runs.
    gcloud run deploy "$API_SERVICE_NAME" \
        --image="$API_IMAGE" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --set-secrets="$SECRET_ENV" \
        --service-account="$SA_EMAIL" \
        --set-env-vars="GOOGLE_CLIENT_ID=${google_client_id},GOOGLE_APPLICATION_CREDENTIALS=$CRED_MOUNT_PATH" \
        --allow-unauthenticated \
        --port=8080 || { error "Service deploy failed."; return; }

    success "API service deployed."
    echo ""
    _show_api_url

    # If the demo service is already deployed, update it to the same image automatically.
    if gcloud run services describe "$DEMO_SERVICE_NAME" \
            --region="$REGION" --project="$PROJECT_ID" &>/dev/null 2>&1; then
        echo ""
        info "Updating demo service to new image..."
        gcloud run deploy "$DEMO_SERVICE_NAME" \
            --image="$API_IMAGE" \
            --region="$REGION" \
            --project="$PROJECT_ID" \
            --service-account="$SA_EMAIL" \
            --set-env-vars="DEMO_MODE=true" \
            --allow-unauthenticated \
            --port=8080 || { warn "Demo service update failed — use option 25 to redeploy it manually."; return; }
        success "Demo service updated."
        echo ""
        _show_demo_url
    fi
}

_show_api_url() {
    local url
    url=$(gcloud run services describe "$API_SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)" 2>/dev/null) || true
    if [[ -n "$url" ]]; then
        echo -e "  ${BOLD}Service URL:${NC} ${CYAN}$url${NC}"
    else
        warn "Could not retrieve service URL (service may not be deployed yet)."
    fi
}

view_api_url() {
    echo ""
    echo -e "${BOLD}── API Service URL ──────────────────────────────────────────${NC}"
    echo ""
    _show_api_url
}

view_api_logs() {
    echo ""
    echo -e "${BOLD}── API Service Logs ─────────────────────────────────────────${NC}"
    echo ""
    gcloud logging read \
        "resource.type=cloud_run_revision AND resource.labels.service_name=$API_SERVICE_NAME" \
        --project="$PROJECT_ID" \
        --limit=200 \
        --format="table(timestamp,textPayload)" \
        --freshness=2d 2>/dev/null | head -100 || warn "No logs found."
}

open_api_in_browser() {
    echo ""
    local url
    url=$(gcloud run services describe "$API_SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)" 2>/dev/null) || true
    if [[ -z "$url" ]]; then
        warn "Service not deployed yet. Use option 16 to deploy first."
        return
    fi
    xdg-open "$url" 2>/dev/null || echo -e "  Visit: ${CYAN}$url${NC}"
}

# ── Demo Service ──────────────────────────────────────────────────────────────

deploy_demo_service() {
    echo ""
    echo -e "${BOLD}── Deploy Demo Service ──────────────────────────────────────${NC}"
    echo ""
    info "Creates a publicly accessible demo (mock data, no login required)."
    info "Uses the same image as the production API — build it first with option 16."
    echo ""

    if gcloud run services describe "$DEMO_SERVICE_NAME" \
            --region="$REGION" --project="$PROJECT_ID" &>/dev/null 2>&1; then
        warn "Demo service already exists. Option 16 (Deploy API Service) updates it automatically."
        echo ""
        _show_demo_url
        return
    fi

    info "Deploying demo Cloud Run service..."
    echo ""

    gcloud run deploy "$DEMO_SERVICE_NAME" \
        --image="$API_IMAGE" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --service-account="$SA_EMAIL" \
        --set-env-vars="DEMO_MODE=true" \
        --allow-unauthenticated \
        --port=8080 || { error "Demo service deploy failed."; return; }

    success "Demo service deployed."
    echo ""
    _show_demo_url
}

_show_demo_url() {
    local url
    url=$(gcloud run services describe "$DEMO_SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)" 2>/dev/null) || true
    if [[ -n "$url" ]]; then
        echo -e "  ${BOLD}Demo URL:${NC} ${CYAN}$url${NC}"
    else
        warn "Could not retrieve demo URL (service may not be deployed yet — use option 25)."
    fi
}

view_demo_url() {
    echo ""
    echo -e "${BOLD}── Demo Service URL ─────────────────────────────────────────${NC}"
    echo ""
    _show_demo_url
}

open_demo_in_browser() {
    echo ""
    local url
    url=$(gcloud run services describe "$DEMO_SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)" 2>/dev/null) || true
    if [[ -z "$url" ]]; then
        warn "Demo service not deployed yet. Use option 25 to deploy first."
        return
    fi
    xdg-open "$url" 2>/dev/null || echo -e "  Visit: ${CYAN}$url${NC}"
}

# ── Local testing ─────────────────────────────────────────────────────────────

_check_local_prereqs() {
    if ! command -v docker &>/dev/null; then
        error "Docker not found. Install from https://docs.docker.com/get-docker/"
        return 1
    fi
    if [[ ! -f "credentials.json" ]]; then
        error "credentials.json not found in the project root."
        return 1
    fi
    if [[ ! -f ".env" ]]; then
        error ".env not found. Copy .env.example to .env and fill in your credentials."
        return 1
    fi
}

_ensure_local_image() {
    if ! docker image inspect "$LOCAL_IMAGE" &>/dev/null; then
        warn "Local Docker image not found — building it now..."
        echo ""
        build_local_image || return 1
    fi
}

build_local_image() {
    echo ""
    echo -e "${BOLD}── Build Local Docker Image ─────────────────────────────────${NC}"
    echo ""
    _check_local_prereqs || return
    if [[ ! -f "backend/main.py" ]]; then
        error "Project files not found. Run this from the project root folder."
        return
    fi
    info "Building local Docker image (1-2 minutes)..."
    echo ""
    docker build -f Dockerfile -t "$LOCAL_IMAGE" . || { error "Docker build failed."; return; }
    # Remove dangling layers left behind by the previous build
    docker image prune -f &>/dev/null || true
    echo ""
    success "Local image built: $LOCAL_IMAGE"
    info "Use options 21-24 to run dry-run tests against your Planning Center data."
}

dry_run_job() {
    local event_name=$1
    local location_filter=${2:-""}

    echo ""
    echo -e "${BOLD}── Dry-run: $event_name ─────────────────────────────────────${NC}"
    echo ""
    _check_local_prereqs || return
    _ensure_local_image || return

    # Fix permissions so the container can read the file
    chmod 644 credentials.json 2>/dev/null || true
    mkdir -p "$LOCAL_OUT_DIR"

    info "Fetching from Planning Center — nothing will be uploaded to Google Drive."
    if [[ -n "$location_filter" ]]; then
        info "Filtering to locations matching: \"$location_filter\""
    fi
    info "PDFs will be saved to: $(pwd)/$LOCAL_OUT_DIR/"
    echo ""

    local run_args=(--dry-run --output-dir /app/out)
    [[ -n "$location_filter" ]] && run_args+=(--location "$location_filter")

    docker run --rm \
        -v "$(pwd)/credentials.json:/app/credentials.json:ro" \
        -v "$(pwd)/$LOCAL_OUT_DIR:/app/out:z" \
        --env-file .env \
        "$LOCAL_IMAGE" "${run_args[@]}" "$event_name"

    echo ""
    success "Done. PDFs saved to: $(pwd)/$LOCAL_OUT_DIR/"
    xdg-open "$LOCAL_OUT_DIR" 2>/dev/null || true
}

dry_run_single() {
    local event_name=$1
    local location_label=$2
    local example=$3

    echo ""
    echo -e "${BOLD}── Dry-run: $event_name — single location ───────────────────${NC}"
    echo ""
    info "Enter part of the $location_label name (case-insensitive match)."
    info "Example: $example"
    echo ""
    read -rp "  $location_label name (or part of it): " LOCATION_FILTER
    if [[ -z "$LOCATION_FILTER" ]]; then
        warn "No location entered — cancelled."
        return
    fi
    dry_run_job "$event_name" "$LOCATION_FILTER"
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
        8)  pick_report "Which report should run?" && _execute_job "$PICKED_JOB" "$PICKED_REPORT" ;;
        9)  pick_report "Whose logs?" && view_logs "$PICKED_JOB" "$PICKED_REPORT" ;;
        10) sync_jobs ;;
        11) view_job_status ;;
        12) view_scheduler ;;
        13) pause_scheduler ;;
        14) resume_scheduler ;;
        15) deploy_api_service ;;
        16) view_api_url ;;
        17) view_api_logs ;;
        18) open_api_in_browser ;;
        19) build_local_image ;;
        20) pick_report "Which report should dry-run?" && dry_run_job "$PICKED_REPORT" ;;
        21) pick_report "Which report should dry-run?" && \
            dry_run_single "$PICKED_REPORT" "location" "Ruta 1 / Nursery" ;;
        22) deploy_demo_service ;;
        23) view_demo_url ;;
        24) open_demo_in_browser ;;
        25) switch_gcloud_project ;;
        q|Q) echo ""; info "Goodbye!"; echo ""; exit 0 ;;
        *)  warn "Invalid option — please choose 1-25 or q." ;;
    esac

    echo ""
    read -rp "  Press ENTER to return to menu..."
done