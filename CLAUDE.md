# Notes for Claude sessions

Planning Center Check-Ins tooling for Iglesia Bautista Libertad (IBL, Houston), growing
into **Advanced Reports for Planning Center**, a multi-church hosted platform.

## Where to start
- Platform work: read `docs/platform.md` first (what runs where, code map, running,
  deploying, operating, known gaps), then `docs/advanced-reports-plan.md` (decisions and the
  Status section, which you update as work lands) and `docs/launch-guide.md` (the owner's
  checklist; keep its status table current).
- Bulk check-ins / pre-select (roster spreadsheets, grade promotion, IBL bus classes):
  read `docs/check-in-tools.md`. It covers which script to use, setup per church,
  the safety rules, and how to read the match report.
- IBL specifics: `docs/IBL.md`. Configuration: `docs/configuration.md`.

## Rules from the owner
- **Git:** the owner commits and opens PRs. Commit only when they ask in that session.
  Never push.
- **Planning Center writes:** every real run that creates check-ins needs the owner's
  explicit yes, one run at a time. Dry run first. Never create people or edit People
  records. Report mismatched names instead of forcing them.
- **Secrets:** never ask for tokens or cookies in chat. They go in git-ignored env files
  (`.env`, `.env.<church>`).
- **IBL's output:** never change it without a deliberate golden-test update
  (`backend/tests/golden/`).
- `backend/previews/*.pdf` is tracked. `preview.py` and `demo_run.py` overwrite those
  files, so restore them after running either.

## Environment
- Python: `backend/.venv` (3.11). Tests: `cd backend && .venv/bin/python -m pytest`.
- Firestore store checks against real staging (writes under a throwaway `ci-tests/…`,
  deleted afterwards): `GOOGLE_CLOUD_QUOTA_PROJECT=mannabyte-reports-staging
  AR_TEST_FIRESTORE_PROJECT=mannabyte-reports-staging .venv/bin/python -m pytest tests/platform -k Stores`.
  Needs `gcloud auth application-default login` as ismael@mannabyte.com.
- Google Cloud: `mannabyte-reports-staging` and `mannabyte-reports-prod` (Mannabyte account).
  IBL's old weekly job lives in `ibl-planning-center-check-ins` (IBL account); leave it alone.
- Deploy: `bash deploy/platform.sh staging` (or `prod`; `DRY_RUN=1` to preview). The owner
  runs it (creating cloud resources needs their approval). Staging:
  https://advanced-reports-300061322405.us-central1.run.app
- Local platform: `cd backend && AR_DEV_LOGIN=1 .venv/bin/uvicorn advanced_reports.app:create_app --factory --port 8000`.
- The Planning Center MCP connector is read-only and connected to one church at a time.
  Check which one with `people_current_organization`.

## Working with the owner
- They want to **see things working**, step by step. Give exact, click-level instructions
  (which page, which button, what text to paste) and say what they should see next.
- In auto mode, creating or changing cloud resources is blocked for Claude. Prepare the command
  (and a `DRY_RUN=1` preview where the script supports it) and ask the owner to run it with `!`.
- Screenshots for docs or posts: use the local demo's made-up church only, never staging or
  production (they show real children's names and parents' phone numbers). Rename the demo
  church in Settings first; its default name is a real church.
- The repo is public. Before pushing, check the commits for real people's names, phone numbers,
  emails and secrets.
