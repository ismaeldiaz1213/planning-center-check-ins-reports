#!/usr/bin/env bash
# deploy/platform.sh — deploy Advanced Reports to Google Cloud.
#
#   bash deploy/platform.sh staging     # mannabyte-reports-staging
#   bash deploy/platform.sh prod        # mannabyte-reports-prod
#   DRY_RUN=1 bash deploy/platform.sh staging   # print what would run, change nothing
#   GOOGLE_CLIENT_JSON=~/Downloads/client_secret_….json bash deploy/platform.sh staging
#       also stores the Google Drive client (once; later deploys reuse the secrets)
#
# Safe to run again: every step creates what is missing and updates the rest.
# Run it signed in to gcloud as the Mannabyte account (ismael@mannabyte.com),
# with Docker running. The image is built on this machine and pushed; Cloud
# Build isn't used (the organization's locked-down defaults make its account
# unusable without extra grants).
#
# What it sets up, all inside free tiers at our size:
#   - Artifact Registry repo "advanced-reports" (keeps only the 3 newest images)
#   - service account advanced-reports@<project> with only what it needs
#   - bucket <project>-files for run PDFs and logos (private, encrypted per church)
#   - secrets pco-oauth-client-id / -secret, copied from backend/.env if missing
#   - Cloud Run job "advanced-reports-runner" (one execution per church run)
#   - Cloud Run service "advanced-reports" (the website)
#   - Cloud Scheduler job "advanced-reports-dispatch" (every 10 minutes)
#
# Never prints a secret value.

set -euo pipefail

ENVIRONMENT="${1:-}"
case "$ENVIRONMENT" in
  staging) PROJECT=mannabyte-reports-staging ;;
  prod)    PROJECT=mannabyte-reports-prod ;;
  *) echo "usage: bash deploy/platform.sh staging|prod" >&2; exit 2 ;;
esac

REGION=us-central1
REPO=advanced-reports
SERVICE=advanced-reports
JOB=advanced-reports-runner
SCHEDULER=advanced-reports-dispatch
SA_NAME=advanced-reports
SA="$SA_NAME@$PROJECT.iam.gserviceaccount.com"
BUCKET="$PROJECT-files"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="$(git -C "$ROOT" rev-parse --short HEAD)$(git -C "$ROOT" diff --quiet HEAD -- backend Dockerfile.platform || echo -dirty)"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/$REPO/platform:$TAG"

run() {  # dry-run lines go to stderr, so they show even where output is silenced
  if [[ "${DRY_RUN:-}" == 1 ]]; then printf '  [dry-run] %s\n' "$*" >&2; else "$@"; fi
}
step() { printf '\n▶ %s\n' "$*"; }
exists() { "$@" >/dev/null 2>&1; }

ACCOUNT="$(gcloud config get-value account 2>/dev/null)"
[[ "$ACCOUNT" == *@mannabyte.com ]] || { echo "gcloud is signed in as '$ACCOUNT'. Run: gcloud auth login (Mannabyte account)" >&2; exit 1; }
NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
URL="https://$SERVICE-$NUMBER.$REGION.run.app"
echo "Deploying $TAG to $PROJECT as $ACCOUNT"
echo "Website address: $URL"

step "Services"
run gcloud services enable storage.googleapis.com run.googleapis.com artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com secretmanager.googleapis.com firestore.googleapis.com --project="$PROJECT"

step "Artifact Registry repository"
if ! exists gcloud artifacts repositories describe "$REPO" --location="$REGION" --project="$PROJECT"; then
  run gcloud artifacts repositories create "$REPO" --repository-format=docker --location="$REGION" \
    --project="$PROJECT" --description="Advanced Reports images"
fi
POLICY="$(mktemp)"; trap 'rm -f "$POLICY"' EXIT
cat > "$POLICY" <<'JSON'
[{"name": "keep-3-newest", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 3}},
 {"name": "delete-the-rest", "action": {"type": "Delete"}, "condition": {"tagState": "any"}}]
JSON
run gcloud artifacts repositories set-cleanup-policies "$REPO" --location="$REGION" --project="$PROJECT" \
  --policy="$POLICY" --no-dry-run --quiet >/dev/null

step "Service account"
if ! exists gcloud iam service-accounts describe "$SA" --project="$PROJECT"; then
  run gcloud iam service-accounts create "$SA_NAME" --project="$PROJECT" --display-name="Advanced Reports"
fi
run gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" \
  --role=roles/datastore.user --condition=None --quiet >/dev/null
# Starting a run means running the job "as" this account.
run gcloud iam service-accounts add-iam-policy-binding "$SA" --project="$PROJECT" \
  --member="serviceAccount:$SA" --role=roles/iam.serviceAccountUser --quiet >/dev/null

step "Bucket for run PDFs and logos"
if ! exists gcloud storage buckets describe "gs://$BUCKET" --project="$PROJECT"; then
  run gcloud storage buckets create "gs://$BUCKET" --project="$PROJECT" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
fi
# Safety net behind decision D2 (latest run only): nothing lives longer than 45 days.
LIFECYCLE="$(mktemp)"; trap 'rm -f "$POLICY" "$LIFECYCLE"' EXIT
echo '{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 45}}]}' > "$LIFECYCLE"
run gcloud storage buckets update "gs://$BUCKET" --lifecycle-file="$LIFECYCLE" >/dev/null
run gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$SA" \
  --role=roles/storage.objectAdmin >/dev/null

step "Secrets"
env_value() {  # a value from backend/.env, never echoed
  grep -E "^$1=" "$ROOT/backend/.env" 2>/dev/null | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}
for pair in pco-oauth-client-id:PCO_OAUTH_CLIENT_ID pco-oauth-client-secret:PCO_OAUTH_CLIENT_SECRET; do
  name="${pair%%:*}"; var="${pair#*:}"
  if ! exists gcloud secrets describe "$name" --project="$PROJECT"; then
    value="$(env_value "$var")"
    [[ -n "$value" ]] || { echo "Secret $name is missing and $var is not in backend/.env" >&2; exit 1; }
    if [[ "${DRY_RUN:-}" == 1 ]]; then echo "  [dry-run] create secret $name from backend/.env"; else
      printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --project="$PROJECT" >/dev/null
      echo "  created $name"
    fi
  fi
done
# Google Drive client (optional): from the JSON file Google gave you, if the secrets don't exist yet.
if ! exists gcloud secrets describe google-oauth-client-id --project="$PROJECT" && [[ -n "${GOOGLE_CLIENT_JSON:-}" ]]; then
  [[ -f "$GOOGLE_CLIENT_JSON" ]] || { echo "GOOGLE_CLIENT_JSON: no file at $GOOGLE_CLIENT_JSON" >&2; exit 1; }
  for field in client_id:google-oauth-client-id client_secret:google-oauth-client-secret; do
    key="${field%%:*}"; name="${field#*:}"
    if [[ "${DRY_RUN:-}" == 1 ]]; then echo "  [dry-run] create secret $name from the Google JSON file"; else
      python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["web"][sys.argv[2]], end="")' \
        "$GOOGLE_CLIENT_JSON" "$key" | gcloud secrets create "$name" --data-file=- --project="$PROJECT" >/dev/null
      echo "  created $name"
    fi
  done
fi
GOOGLE=0
exists gcloud secrets describe google-oauth-client-id --project="$PROJECT" && GOOGLE=1
SECRETS=(ar-master-key ar-session-secret ar-dispatch-key pco-oauth-client-id pco-oauth-client-secret)
[[ "$GOOGLE" == 1 ]] && SECRETS+=(google-oauth-client-id google-oauth-client-secret)
[[ "$GOOGLE" == 1 ]] || echo "  (no Google Drive client stored: deploying without \"Connect Google Drive\")"
for name in "${SECRETS[@]}"; do
  exists gcloud secrets describe "$name" --project="$PROJECT" || [[ "${DRY_RUN:-}" == 1 ]] \
    || { echo "Secret $name is missing in $PROJECT (see docs/launch-guide.md 1.2)" >&2; exit 1; }
  run gcloud secrets add-iam-policy-binding "$name" --project="$PROJECT" --member="serviceAccount:$SA" \
    --role=roles/secretmanager.secretAccessor --quiet >/dev/null
done

step "Build and push the image ($TAG)"
run gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet >/dev/null
run docker build --platform linux/amd64 -f "$ROOT/Dockerfile.platform" -t "$IMAGE" "$ROOT"
run docker push "$IMAGE"

ENV_VARS="AR_FIRESTORE_PROJECT=$PROJECT,AR_BUCKET=$BUCKET,AR_BASE_URL=$URL"
ENV_VARS+=",AR_RUNNER_JOB=projects/$PROJECT/locations/$REGION/jobs/$JOB"
SECRET_VARS="AR_MASTER_KEY=ar-master-key:latest,AR_SESSION_SECRET=ar-session-secret:latest"
SECRET_VARS+=",AR_DISPATCH_KEY=ar-dispatch-key:latest"
SECRET_VARS+=",PCO_OAUTH_CLIENT_ID=pco-oauth-client-id:latest,PCO_OAUTH_CLIENT_SECRET=pco-oauth-client-secret:latest"
[[ "$GOOGLE" == 1 ]] && SECRET_VARS+=",GOOGLE_OAUTH_CLIENT_ID=google-oauth-client-id:latest,GOOGLE_OAUTH_CLIENT_SECRET=google-oauth-client-secret:latest"

step "Runner (Cloud Run job)"
run gcloud run jobs deploy "$JOB" --project="$PROJECT" --region="$REGION" --image="$IMAGE" \
  --service-account="$SA" --command=python,-m,advanced_reports.runner --args="" \
  --set-env-vars="$ENV_VARS" --set-secrets="$SECRET_VARS" \
  --tasks=1 --max-retries=0 --task-timeout=30m --cpu=1 --memory=1Gi --quiet
# The website starts executions with per-run arguments <org_id> <run_id>. They
# replace the job's args, so the whole command lives in --command and args stay empty.
run gcloud run jobs add-iam-policy-binding "$JOB" --project="$PROJECT" --region="$REGION" \
  --member="serviceAccount:$SA" --role=roles/run.developer --quiet >/dev/null

step "Website (Cloud Run service)"
# --no-invoker-iam-check makes the site public without granting "allUsers",
# which the organization's domain restriction forbids. The app signs people in itself.
run gcloud run deploy "$SERVICE" --project="$PROJECT" --region="$REGION" --image="$IMAGE" \
  --service-account="$SA" --set-env-vars="$ENV_VARS" --set-secrets="$SECRET_VARS" \
  --no-invoker-iam-check --min-instances=0 --max-instances=2 --cpu=1 --memory=1Gi \
  --concurrency=20 --timeout=60 --quiet

step "Schedule (every 10 minutes)"
if [[ "${DRY_RUN:-}" == 1 ]]; then DISPATCH_KEY="(from secret ar-dispatch-key)"; else
  DISPATCH_KEY="$(gcloud secrets versions access latest --secret=ar-dispatch-key --project="$PROJECT")"
fi
SCHEDULE_ARGS=(--project="$PROJECT" --location="$REGION" --schedule="*/10 * * * *" --time-zone=UTC
  --uri="$URL/internal/dispatch" --http-method=POST --attempt-deadline=60s)
if exists gcloud scheduler jobs describe "$SCHEDULER" --project="$PROJECT" --location="$REGION"; then
  run gcloud scheduler jobs update http "$SCHEDULER" "${SCHEDULE_ARGS[@]}" \
    --update-headers="X-AR-Dispatch-Key=$DISPATCH_KEY" --quiet >/dev/null
else
  run gcloud scheduler jobs create http "$SCHEDULER" "${SCHEDULE_ARGS[@]}" \
    --headers="X-AR-Dispatch-Key=$DISPATCH_KEY" --quiet >/dev/null
fi
unset DISPATCH_KEY

step "Check"
if [[ "${DRY_RUN:-}" != 1 ]]; then
  code="$(curl -s -o /dev/null -w '%{http_code}' "$URL/api/auth/config")"
  echo "  $URL/api/auth/config → HTTP $code"
fi
cat <<EOF

Done. Open: $URL

If this is the first deploy of $ENVIRONMENT, add these once (exact text):
  Planning Center app "Advanced Reports" → Authorization callback URLs, new line:
    $URL/auth/pco/callback
  Google Auth Platform → Clients → "Advanced Reports web" → Authorized redirect URIs:
    $URL/auth/google/callback
EOF
