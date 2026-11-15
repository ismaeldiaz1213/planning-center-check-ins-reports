# Launch guide: Advanced Reports for Planning Center

What has to happen, in order, to take Advanced Reports from "runs on Ismael's laptop" to
"IBL and Liberty Baptist get their rosters from it every week". Written 2026-11-14.

Each step says **who** does it (you, or the next coding session), **how long** it should
take, and **what it costs**. Times are estimates for hands-on work, not waiting time;
where something depends on someone else replying, that is called out.

Read [Where things stand](#where-things-stand) first. The short version of the plan:

1. **You** create the accounts only you can create (about 3–4 hours, spread over a few days).
2. **The next sessions** build what is missing for production: database, Google Drive,
   real sign-in, deploy (about 4–6 working sessions).
3. **IBL runs on both systems side by side** for two Sundays, without teachers noticing.
4. **IBL switches over**: the old job is paused, not deleted, so it can come back in minutes.
5. **Liberty signs up**, with you sitting next to their admin.

Nothing here touches IBL's current weekly job until step 4, and step 4 is reversible.

---

## Where things stand

**Built and tested (455 automated tests, 3 commits on `feat/platform-m1`):**

- The report engine serves any number of churches. IBL's PDFs are byte-for-byte the same
  text as before, checked against a live run of IBL's real data (105 files, identical).
- The platform: per-church storage with encrypted connections, signed sessions, the
  runner (one run = one church, with progress, time estimate and cancel), the weekly
  schedule, the set-up wizard with live preview, and the full dashboard in English and
  Spanish, light and dark, phone and desktop.

**Not built yet (needs your accounts first):**

| Missing piece | Why it matters | Who / how long |
|---|---|---|
| Firestore storage | Today settings live in JSON files on one computer | Next session, ~½ day |
| Google Drive connection | Rosters must land in the church's Drive folder | Next session, ~1 day |
| Real Planning Center sign-in | Today it is a "local development" button | Code exists; needs your OAuth app, then ~½ day to test and fix |
| Container image and deploy scripts | Nothing is online yet | Next session, ~½ day |
| Scheduler hookup in Google Cloud | Weekly runs without anyone pressing a button | ~1 hour once deployed |
| Privacy policy and terms pages | You will store children's names and parents' phones for other churches | Draft by next session (~1 hour); **you** must review |

**Known gaps you have already seen:** the home page promises Google Drive (not built
yet); the "why we built it" section is written in your voice and needs your review; the
roster preview always uses the same sample people; the wizard can't yet change the
separate volunteer event that IBL's bus report uses (IBL's existing setting is kept).

---

## Phase 1 — Accounts only you can create

**Total: about 3–4 hours of your time, plus waiting for Planning Center to reply.**
Do 1.1–1.3 first; they unblock the most work.

> **Never paste a secret (client secret, key, token) into the chat.** Put it into Secret
> Manager with the commands below and tell the session only the secret's *name*.

### 1.1 Google Cloud projects (≈ 45 min)

You already have the organization and billing account. Create two projects: one to test
on (staging) and one for churches (production).

1. Pick project IDs. Suggested: `mannabyte-reports-staging` and `mannabyte-reports-prod`
   (IDs are permanent and globally unique; if taken, add a suffix).
2. In a terminal (or Cloud Shell):

   ```bash
   gcloud auth login                       # your mannabyte.com account, not IBL's
   gcloud organizations list               # note the ORG ID
   gcloud billing accounts list            # note the BILLING ACCOUNT ID

   for P in mannabyte-reports-staging mannabyte-reports-prod; do
     gcloud projects create "$P" --organization=ORG_ID
     gcloud billing projects link "$P" --billing-account=BILLING_ACCOUNT_ID
     gcloud services enable run.googleapis.com firestore.googleapis.com \
       cloudscheduler.googleapis.com secretmanager.googleapis.com \
       artifactregistry.googleapis.com cloudbuild.googleapis.com \
       iamcredentials.googleapis.com drive.googleapis.com --project="$P"
     gcloud firestore databases create --location=us-central1 --project="$P"
   done
   ```

3. **Budget alerts (do not skip).** Console → Billing → Budgets & alerts → Create budget.
   One budget per project, amount **$10/month**, email alerts at 50%, 90% and 100%.
   A budget only emails you; it does not stop spending. At this size an alert almost
   certainly means a bug (for example a run stuck in a loop), so look the same day.

### 1.2 Secrets the platform needs (≈ 15 min, after 1.1)

Run once per project. These generate the values on your machine and put them straight
into Secret Manager, so they never appear on screen or in chat.

```bash
P=mannabyte-reports-staging     # then repeat with mannabyte-reports-prod

python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode(),end='')" \
  | gcloud secrets create ar-master-key --data-file=- --project="$P"
python3 -c "import secrets;print(secrets.token_urlsafe(48),end='')" \
  | gcloud secrets create ar-session-secret --data-file=- --project="$P"
python3 -c "import secrets;print(secrets.token_urlsafe(32),end='')" \
  | gcloud secrets create ar-dispatch-key --data-file=- --project="$P"
```

**The master key protects every church's stored connection. If it is lost, every church
must reconnect; if it leaks, rotate it.** Do not delete or overwrite `ar-master-key`
once churches are connected.

### 1.3 Planning Center OAuth app (≈ 30 min, plus waiting)

1. Create a Planning Center account for Mannabyte Labs using a mannabyte.com address.
2. Go to `https://api.planningcenteronline.com/oauth/applications` and create an
   application named **Advanced Reports**.
3. Add these redirect URIs (exactly):
   - `http://localhost:8000/auth/pco/callback`
   - `https://STAGING-URL/auth/pco/callback` (add once staging has an address; the
     next session will tell you what it is)
   - `https://reports.mannabyte.com/auth/pco/callback`
4. The app asks for the scopes `people` and `check_ins` (read only in practice; the code
   never writes to Planning Center).
5. Store the client ID and secret:

   ```bash
   for P in mannabyte-reports-staging mannabyte-reports-prod; do
     printf '%s' 'PASTE_CLIENT_ID'     | gcloud secrets create pco-oauth-client-id     --data-file=- --project="$P"
     read -rs -p "PCO client secret: " S; printf '%s' "$S" \
       | gcloud secrets create pco-oauth-client-secret --data-file=- --project="$P"; echo
   done
   ```

   (The client ID is not secret, but keeping both in one place is simpler.)

6. **A test church.** You need a Planning Center organization with Check-Ins and some
   made-up people to test sign-in against. Ask Planning Center (step 1.4) whether they
   provide a developer sandbox. If not, the options are a small paid Check-Ins
   subscription for a fake church, or testing sign-in against IBL with leadership's OK
   (sign-in only reads). **I don't know Planning Center's current pricing for this;
   check before paying.**

### 1.4 Email Planning Center developer support (≈ 20 min to write; replies take days)

Send this early because you will wait for it. Ask:

1. May a hosted app charge churches a subscription, and are there rules for listing it?
2. Is there a developer sandbox organization with Check-Ins?
3. **How should an app tell that the signed-in person is an organization administrator?**
   The sign-in code currently checks a field called `site_administrator` on the person
   record. That is a guess; if it is wrong, either nobody can sign up or anybody can.
   This must be confirmed before Liberty signs in.
4. Is "Advanced Reports for Planning Center" an acceptable name, or should it avoid
   "Planning Center" in the title?

### 1.5 Google OAuth client for Drive (≈ 45 min, production project)

This is how a church lets the app save rosters into its own Google Drive.

1. Console → **Google Auth Platform** (formerly "OAuth consent screen") in
   `mannabyte-reports-prod`.
2. **Branding:** app name *Advanced Reports*, support email `support@mannabyte.com`
   (or your address), logo optional, home page `https://reports.mannabyte.com`,
   privacy policy and terms URLs (the pages from Phase 2; you can add them later, but
   you need them before publishing).
3. **Audience:** *External*. Then **Publish app** so it is *In production*.
   **Important:** while it says *Testing*, Google refresh tokens expire after 7 days,
   and every church's weekly run would break after a week.
4. **Data access:** add only `https://www.googleapis.com/auth/drive.file`. This scope
   only lets the app see files it created or that the user picked, which is why Google
   treats it as non-sensitive. Expect no security review; you may be asked to verify
   the brand (domain ownership, step 1.6).
5. **Clients → Create client → Web application.** Authorized redirect URI:
   `https://reports.mannabyte.com/auth/google/callback` (plus the staging one later, and
   `http://localhost:8000/auth/google/callback` for development).
6. Store it in both projects as `google-oauth-client-id` / `google-oauth-client-secret`
   the same way as step 1.3.5.

### 1.6 Domain (≈ 20 min, then up to a day for DNS)

1. Verify `mannabyte.com` in Google Search Console (you may have done this for
   Workspace already; Google Auth Platform branding needs it).
2. When the next session deploys production, it will tell you the exact DNS record for
   `reports.mannabyte.com` (a CNAME to Cloud Run or Firebase Hosting, depending on which
   we pick, see [Decisions](#decisions-you-need-to-make)). Adding it takes 5 minutes;
   certificates take up to a few hours to issue.

### 1.7 IBL production baseline (optional, ≈ 5 min)

Only if you still want "how long the real Cloud Run job takes" in `docs/benchmarks.md`:
run `! gcloud auth login` **with the IBL Google account** and the next session will read
the job history with read-only commands. Not needed for launch.

---

## Phase 2 — Building what is missing (next sessions)

Once 1.1, 1.2, 1.3 and 1.5 exist. Estimates are in coding sessions like tonight's.

| # | Work | Estimate | Needs from you |
|---|---|---|---|
| 2.1 | **Firestore store**: the same four operations as today's JSON store, plus a transaction for "one run at a time" | ½ session | Project from 1.1 |
| 2.2 | **Google Drive connection**: "Connect Google Drive" button, the app creates an *Advanced Reports* folder in the church's Drive, uploads rosters there each run, replaces last week's files in place | 1 session | Client from 1.5 |
| 2.3 | **IBL Drive delivery that keeps the old folder** (see Phase 3) | ½ session | IBL folder shared with the new service account |
| 2.4 | **Real Planning Center sign-in**: test against a real org, fix whatever the guesses got wrong, finish "is this person an admin" | ½ session | 1.3, 1.4 answer |
| 2.5 | **Container image and deploy**: one image for the web service and the runner, scripts for staging and production, Cloud Scheduler calling `/internal/dispatch` every 10 minutes | ½–1 session | 1.1, 1.2 |
| 2.6 | **What happens to PDFs after a run** (see Decisions) | ¼ session | Your decision |
| 2.7 | **Privacy policy, terms, and a data-deletion page** | ¼ session to draft | Your review (yours to sign off; not legal advice) |
| 2.8 | **Liberty-ready polish**: preview with English sample names for English churches, editable volunteer event, address-column widths | ½ session | — |

**Total: about 4–6 sessions.** Staging is usable after 2.1, 2.2, 2.4 and 2.5.

---

## Phase 3 — IBL: switching with no interruption

The goal is that teachers notice nothing. The old weekly job keeps running the whole
time until the new one has proved itself, and the switch can be undone in minutes.

**Today:** IBL's Cloud Run job in project `ibl-planning-center-check-ins` runs every
Monday at 08:00 UTC (2 AM Central in winter, 3 AM in summer) and writes into IBL's
existing Drive folder with a service account. Teachers bookmark folders in it.

### 3.1 Keep the same Drive folder (recommended)

With the new app's normal Drive permission (`drive.file`), it can't see files it did not
create, so it would put a second `Roster.pdf` next to every old one. To avoid that for
IBL only, the new platform writes to the old folder the same way the old job does: as a
**service account that the folder is shared with**.

What you do (≈ 10 min, after 2.5 tells you the new service account's email):
1. In IBL's Google Drive, open the parent rosters folder → Share → add the new
   platform's service account email as **Editor**.
2. That's all. No key file has to move between projects if the session can use the
   service account's own identity; if Google requires a key for Drive, the session will
   ask you to create one in the *new* project and store it in Secret Manager (never
   in chat, never in the repo).

Result: same folder, same file names, files replaced in place, every teacher's link keeps
working.

### 3.2 IBL signs in for real (≈ 15 min with an IBL Planning Center admin)

Today IBL on the platform uses your Personal Access Token from `.env`. In production:
1. An IBL Planning Center administrator (you, if you are one) signs in at
   `reports.mannabyte.com`. This creates IBL's church under its real Planning Center id.
2. The session runs the IBL importer once against that church: same reports, same
   branding, Spanish, the Bautista Libertad logo, and the guide languages.
3. Check **Set up**: three report sets (Rutas, Escuela, Escuela C) should be there.

### 3.3 Run side by side for two Sundays (≈ 10 min a week of your time)

For two weeks, the old job keeps writing the real folder on Monday at 2 AM. The new
platform runs too, but delivers into a **separate test folder** (or keeps the PDFs on
the platform only), never the real one.

Each week:
1. Saturday or Sunday night: press **Make rosters now** for IBL on production.
2. Monday morning: the session (or a script it leaves you) compares the text of the new
   PDFs with the old job's files, like tonight's check. Expect identical text except the
   "generated at" time.
3. Any difference is a bug to fix before switching. Nothing reaches teachers.

### 3.4 Switch (≈ 15 min, a weekday, not Sunday)

When two weeks matched:
1. Change IBL's delivery on the new platform from the test folder to the real folder.
2. **Pause** the old job's Cloud Scheduler trigger. Do not delete anything:

   ```bash
   gcloud scheduler jobs list --location=us-central1 --project=ibl-planning-center-check-ins
   gcloud scheduler jobs pause JOB_NAME --location=us-central1 --project=ibl-planning-center-check-ins
   ```

3. In the new platform: **Schedule** → on, **Monday 02:00** (America/Chicago). That keeps
   IBL's timing, and now it follows daylight saving time automatically.
4. The next Monday at about 2:05 AM, check the Overview and open two or three rosters in
   the real Drive folder.

### 3.5 If anything goes wrong (≈ 5 min)

```bash
gcloud scheduler jobs resume JOB_NAME --location=us-central1 --project=ibl-planning-center-check-ins
gcloud run jobs execute RUN_JOB_NAME --region=us-central1 --project=ibl-planning-center-check-ins
```

(`gcloud run jobs list --region=us-central1 --project=ibl-planning-center-check-ins` shows
the job's name; the plan calls it `roster-weekly`. Write both names down during 3.4 so
this step is copy-paste when you need it.)

and turn the new platform's schedule off for IBL. Teachers get the old job's rosters
within minutes. Fix, then try the switch again the following week.

### 3.6 Retire the old setup (a month later)

After about four good Mondays: delete nothing yet, but you can stop thinking about the
old project. Deleting `ibl-planning-center-check-ins` is a separate decision for when you
are sure (and before you leave IBL in May 2027, so nothing depends on your personal
access). Revoke the old Personal Access Token in Planning Center once IBL no longer uses
it anywhere.

---

## Phase 4 — Onboarding Liberty Baptist Church

**Before the meeting (≈ 30 min, you):**
- Ask Liberty: who is their Planning Center **organization administrator** (that person
  must sign in), which Check-Ins events they use for Sunday school, whether they have a
  bus or van ministry (optional, nothing breaks without it), and who should get the
  Drive folder.
- Make sure 2.4 (sign-in) and 2.2 (Drive) work on staging, and that the privacy policy
  and terms are live (2.7). Liberty is trusting you with children's information.
- Tell their leadership plainly what is stored: settings, an encrypted connection to
  Planning Center and Google, run history, and (depending on decision D2) copies of the
  rosters. Show them **Settings → Disconnect**, which deletes all of it.

**The meeting (≈ 45 min, their admin drives, you watch and take notes):**
1. They open `reports.mannabyte.com` → **Sign in with Planning Center** → approve.
2. **Settings → Church**: confirm name, time zone, language English.
3. **Settings → Connections → Connect Google Drive**: they sign in with the Google
   account that should own the folder. The app creates an *Advanced Reports* folder there.
4. **Set up → Add a roster → Sunday school or classes** → pick their event → tick what
   each roster shows while watching the preview → save. Repeat for bus routes if they
   have them.
5. **Overview → Make rosters now.** Watch the progress bar. Open two rosters together and
   check names against what they know.
6. **Schedule**: Saturday 6 PM is a good default; let them choose.
7. Share the Drive folder with their teachers (Google Drive's normal sharing).
8. Write down every moment they hesitated. That list is the next session's work.

**The week after (≈ 15 min):** check their first scheduled run on Monday, and ask one
teacher what they think of the roster.

---

## What it costs

**Short answer: expect $0 to $5 a month while it is IBL and Liberty.** Your existing
Mannabyte Workspace and the mannabyte.com domain are already paid for and not counted.

These are estimates from Google's published free tiers as I understand them (my
knowledge runs to mid-2026). **Check each pricing page before relying on it**; free tiers
change.

| Service | Free allowance (approx.) | Two churches use | Expected cost |
|---|---|---|---|
| Cloud Run (web service + weekly runs) | ~180k vCPU-seconds, 360k GiB-seconds, 2M requests per month, per billing account | A few minutes of CPU per church per week, light dashboard traffic | **$0** |
| Firestore | 1 GiB stored, 50k reads and 20k writes per day, one free database per project | Settings and run history: kilobytes; hundreds of reads a day | **$0** |
| Secret Manager | ~6 active secret versions, 10k accesses per month | About 7 secrets per project | **$0–0.10/month** (about $0.06 per version beyond the free ones) |
| Cloud Scheduler | 3 jobs per billing account | 1 per project = 2 | **$0** (about $0.10/job/month beyond 3) |
| Artifact Registry (container images) | 0.5 GB stored | 1–3 images of ~0.5 GB if old ones are cleaned up | **$0–0.30/month** |
| Cloud Build | A monthly allowance of build minutes | A few builds a week, ~5 min each | **$0** |
| Network egress | Some free egress per month | A few MB of PDFs per church per week to Google Drive | **$0** |
| Cloud Logging | 50 GiB per project per month | Megabytes | **$0** |
| Firebase Hosting (only if decision D1 picks it) | 10 GB stored, ~360 MB/day transfer | Under 2 MB of page files | **$0** |
| Planning Center developer account / test church | Unknown, see 1.3.6 | One test org | **$0 to a small monthly fee**; check |
| Google OAuth verification | Free for `drive.file` | — | **$0** |
| IBL's old project (until you retire it) | Whatever it costs today | Paused scheduler, no runs | **Drops to about $0** after the switch |

**What could make it cost more:** leaving many old container images (clean up, or the
session can add an automatic cleanup policy), a bug that loops Planning Center calls
(the budget alert catches it), or keeping copies of every church's PDFs for a long time
(decision D2). Growth to ~50 IBL-sized churches should still fit in free tiers; that is
an estimate, and `docs/benchmarks.md` will get real numbers once production runs.

---

## Decisions you need to make

| # | Decision | My recommendation | Why |
|---|---|---|---|
| D1 | Host the dashboard on Cloud Run directly, or Firebase Hosting in front of it | **Cloud Run directly**, for now | It already serves the pages; one thing to deploy. Use Firebase only if the custom-domain mapping gives trouble. |
| D2 | Keep copies of each run's PDFs on the platform (for the Rosters tab preview) | **Keep the latest run only**, in an encrypted Cloud Storage bucket, deleted when the next run finishes | The Rosters tab stays useful, and you never hold more than one week of children's data. The alternative (keep nothing, link to Drive) is more private but the Rosters tab becomes a list of links. |
| D3 | IBL's Drive folder | **Keep the old folder** via service account (3.1) | Zero change for teachers. |
| D4 | Where the session should start | **2.1 + 2.5 first** (store and deploy to staging), then 2.2 | You get a real URL to click early, and every later piece can be tested online. |
| D5 | Reply time you promise on the Help page | Currently "A real person reads every message" (no time promise) | Promise only what you can keep while working at IBL. |

---

## Timeline at a glance

Assuming you can give this a few evenings a week:

| When | What | Your time |
|---|---|---|
| Week 1 | Phase 1 accounts (1.1–1.6); email Planning Center | 3–4 h |
| Weeks 1–2 | Sessions build 2.1, 2.5, 2.2, 2.4 → staging online | ~30 min per session to answer questions |
| Week 2 | IBL signs in on production; delivery to a test folder | 30 min |
| Weeks 3–4 | Two side-by-side Sundays for IBL | 10 min a week |
| Week 4–5 | IBL switches (Phase 3.4) | 15 min |
| Week 5–6 | Privacy pages live; Liberty onboarding meeting | 1–1.5 h |

The original cutover date of 2026-11-15 is not realistic; the plan above puts IBL on the
new platform about a month out, with no interruption for teachers in between.

---

## Quick reference

- Run locally: `cd backend && AR_DEV_LOGIN=1 .venv/bin/uvicorn advanced_reports.app:create_app --factory --port 8000`
- Tests: `cd backend && .venv/bin/pytest -q` and `.venv/bin/ruff check .`
- Plan and status: `docs/advanced-reports-plan.md`
- Developer notes: `DEVELOPMENT.md`
- Contact shown to churches: ismael@mannabyte.com (Help tab and home page)
