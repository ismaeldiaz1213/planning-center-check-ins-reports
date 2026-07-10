# Security Policy

## Supported Versions

This project is currently pre-1.0. Security fixes will be applied to the latest version on `main`.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security problems.**

This app handles sensitive church data: Planning Center API credentials, Google Drive access, and personal information including names, phone numbers, birthdays, addresses, grades, and children's ministry attendance records.

To report a vulnerability, email: **diazismael6521@gmail.com**

Please include:
- A description of the issue
- Steps to reproduce, if safe to do so
- The affected file, route, workflow, or deployment step
- Whether any real credentials or personal data may be exposed

You can expect a response within 72 hours.

## Sensitive Data — Do Not Commit

- `.env` (contains API keys and tokens)
- `credentials.json` (Google service account key)
- Planning Center API secrets
- Google service account keys
- Real roster PDFs
- Real attendee exports
- Screenshots containing names, birthdays, phone numbers, addresses, or child data

These are all listed in `.gitignore`. If you accidentally commit any of them, rotate the affected credentials immediately.

## Credential Rotation

| Secret | Where to rotate |
|--------|----------------|
| Planning Center API key | https://api.planningcenteronline.com/oauth/applications |
| Google service account key | https://console.cloud.google.com/iam-admin/serviceaccounts |
| Google OAuth client | https://console.cloud.google.com/apis/credentials |

## Runtime Secrets (Cloud Run)

`credentials.json` and `.env` values should be injected at runtime, never baked into Docker images:

```bash
# Mount credentials.json via Secret Manager
gcloud run jobs update YOUR_JOB \
  --set-secrets=credentials.json=google-service-account-key:latest

# Pass env vars via Secret Manager
gcloud run jobs update YOUR_JOB \
  --set-secrets=PCO_APP_ID=pco-app-id:latest,PCO_SECRET=pco-secret:latest
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full setup guide.
