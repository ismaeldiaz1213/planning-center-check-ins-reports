# Contributing

Thanks for your interest in contributing to this project.

## Project Goals

This project helps churches generate Planning Center Check-Ins roster PDFs and optionally upload them to Google Drive on a schedule. The target user is a church administrator or volunteer so not necessarily a software engineer. Contributions that make setup simpler, reduce required steps, or improve error messages are especially welcome.

## Local Setup

```bash
cp .env.example .env
# Fill in PCO_APP_ID, PCO_SECRET, GOOGLE_DRIVE_PARENT_FOLDER_ID

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-web.txt -r requirements-dev.txt
pytest
ruff check .
```

```bash
cd frontend
npm ci
npm test
npm run build
```

See [docs/getting-started.md](docs/getting-started.md) for the full walkthrough.

## Pull Request Checklist

Before opening a PR:

- [ ] I did not commit `.env`, `credentials.json`, real PDFs, screenshots, or exported attendee data
- [ ] Backend tests pass (`cd backend && pytest`)
- [ ] Frontend tests pass (`cd frontend && npm test -- --run`)
- [ ] Linting/type-checking passes (`ruff check .` and `npx tsc --noEmit`)
- [ ] Docs were updated if setup or behavior changed
- [ ] New behavior has tests where practical

## Data Privacy Rule

Use fake data in tests, screenshots, and sample PDFs. Do not include real names, birthdays, phone numbers, addresses, or child information in any committed file.

---

Done when: someone can understand how to contribute without messaging you.
