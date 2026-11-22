# Notes for Claude sessions

Planning Center Check-Ins tooling for Iglesia Bautista Libertad (IBL, Houston), growing
into **Advanced Reports for Planning Center**, a multi-church hosted platform.

## Where to start
- Platform work: read `docs/advanced-reports-plan.md` (§0 "Start here" and its Status
  section), then `docs/launch-guide.md`.
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
- Local platform: `cd backend && AR_DEV_LOGIN=1 .venv/bin/uvicorn advanced_reports.app:create_app --factory --port 8000`.
- The Planning Center MCP connector is read-only and connected to one church at a time.
  Check which one with `people_current_organization`.
