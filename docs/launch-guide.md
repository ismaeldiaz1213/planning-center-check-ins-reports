# Launch guide: Advanced Reports for Planning Center

What has to happen, in order, to take Advanced Reports from "runs on Ismael's laptop" to
"IBL and Liberty Baptist get their rosters from it every week". Written 2026-11-14.

Each step says **who** does it (you, or the next coding session), **how long** it should
take, and **what it costs**. Times are estimates for hands-on work, not waiting time;
where something depends on someone else replying, that is called out.

Read [Where things stand](#where-things-stand) first. The short version of the plan:

1. **You** create the accounts only you can create (about 1 hour left as of 2026-11-21).
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

_Rewritten 2026-11-21 with exact steps. Progress so far was checked with `gcloud`._

| Step | What | State |
|---|---|---|
| 1.1 | Google Cloud projects `mannabyte-reports-staging` and `mannabyte-reports-prod`: billing, services, Firestore (us-central1) | ✅ Done |
| 1.2 | Platform secrets | ✅ Staging and production (2026-11-21) |
| 1.3 | Budget alerts | ✅ Done by the owner (2026-11-21) |
| 1.4 | Planning Center sign-in app, **owned by IBL** for now | ✅ Created 2026-11-21; client ID and secret in `backend/.env` (not yet in Secret Manager) |
| 1.5 | Test sign-in on your laptop | ✅ Worked first try with IBL (2026-11-21) |
| 1.6 | Google sign-in app for Drive | 🟡 Client created 2026-11-21 (JSON downloaded); app stays in *Testing* until the privacy page and domain exist, then publish |
| 1.7 | Domain `reports.mannabyte.com` | ⬜ Later; the deploy session tells you the exact record |

**Not needed now** (dropped from the earlier version of this guide):
- **A Mannabyte Planning Center account.** The app is owned by IBL for now. See
  [Moving the app to Mannabyte later](#moving-the-app-to-mannabyte-later).
- **Emailing Planning Center support.** The important question ("how does the app know
  someone is a church admin?") was answered by checking real data: your Liberty profile
  has `site_administrator: true`, which is what the sign-in code checks. The other
  questions (charging churches, app name) only matter for the public launch. Ask them in
  December.
- **A fake test church.** We test with Liberty and IBL. Signing in only reads data.

> **Never paste a secret (client secret, key, token) into the chat.** Secrets go into a
> git-ignored file or into Secret Manager. Tell the session only that they're saved.

### 1.2 Production secrets (≈ 2 min)

In this Claude Code session, type each line with a leading `!` so it runs here. It
creates three random keys straight in Secret Manager; you never see their values, and
there is nothing to copy.

```bash
! P=mannabyte-reports-prod; python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode(),end='')" | gcloud secrets create ar-master-key --data-file=- --project=$P
! P=mannabyte-reports-prod; python3 -c "import secrets;print(secrets.token_urlsafe(48),end='')" | gcloud secrets create ar-session-secret --data-file=- --project=$P
! P=mannabyte-reports-prod; python3 -c "import secrets;print(secrets.token_urlsafe(32),end='')" | gcloud secrets create ar-dispatch-key --data-file=- --project=$P
```

Each line should end with `Created version [1] of the secret [...]`. If one says the
secret **already exists**, stop there: don't delete or overwrite `ar-master-key`.

### 1.3 Budget alerts (≈ 5 min)

1. Open <https://console.cloud.google.com/billing>, signed in as ismael@mannabyte.com.
2. Pick the billing account, then **Budgets & alerts** in the left menu.
3. If you already see a budget for each project, you're done. If not, click
   **Create budget**:
   - **Name:** `reports-prod`. **Projects:** only `mannabyte-reports-prod`. Next.
   - **Budget type:** Specified amount, **$10**. Next.
   - **Thresholds:** 50%, 90%, 100% of actual spend. Keep "Email alerts to billing
     admins and users" checked. **Finish**.
4. Repeat for `mannabyte-reports-staging` (name `reports-staging`).

A budget only emails you; it doesn't stop spending. At this size, an alert almost always
means a bug, so look the same day.

### 1.4 Planning Center sign-in app, owned by IBL (≈ 10 min)

This registers the "Sign in with Planning Center" button. Planning Center gives you a
**client ID** and a **client secret** that the website uses to prove who it is.

The app belongs to whichever church you're signed in as when you create it. Ownership
only decides who can manage the app. It doesn't give the app access to that church's
data: every church connects separately by signing in itself.

1. Sign in at <https://login.planningcenteronline.com>.
2. **Switch to IBL first.** Click your name or picture in the top-right corner and pick
   **Iglesia Bautista Libertad** from the church list. If it already says IBL, skip
   this.
3. Go to <https://api.planningcenteronline.com/oauth/applications>. The page has a
   *Personal Access Tokens* section and an *OAuth Applications* section. Don't confuse
   them: you want **OAuth Applications**.
4. Click **New Application** in the OAuth Applications section. Exact labels may differ
   slightly; fill in by meaning:
   - **Name:** `Advanced Reports`
   - **Description / URL / Homepage**, if asked: `https://mannabyte.com`
   - **Callback URL** (it may say *Redirect URI*): type exactly
     `http://localhost:8000/auth/pco/callback`
     This is where Planning Center sends people back after they sign in. For now it's
     your laptop. The staging and production addresses get added later, when they
     exist; the deploy session will give you the exact text.
   - If it asks about **scopes**, choose **People** and **Check-Ins**.
5. Save. The page now shows a **Client ID** and a **Secret**. Leave the tab open.
6. Open `backend/.env` in a text editor. It's git-ignored, so it never gets committed.
   Add these two lines at the bottom:
   ```
   PCO_OAUTH_CLIENT_ID=the-client-id
   PCO_OAUTH_CLIENT_SECRET=the-secret
   ```
   Save the file. Tell the session "1.4 done" without pasting the values.

If something on the page doesn't match these steps, take a screenshot and share it.
That's faster than guessing.

### 1.5 Test sign-in on your laptop (≈ 10 min of your time)

The session starts the website locally with real sign-in turned on. You open
`http://localhost:8000`, click **Sign in with Planning Center**, pick **Liberty**, and
approve. The session fixes whatever breaks. Nothing goes to Google Cloud yet; the client
ID and secret go into Secret Manager during the deploy.

### 1.6 Google sign-in app for Drive (≈ 30 min, production project)

This is how a church lets the app save rosters into its own Google Drive. Do it after
1.5. The Drive connection is built in Phase 2, so it isn't urgent.

1. Open <https://console.cloud.google.com/auth/overview?project=mannabyte-reports-prod>
   (Google Auth Platform). If it shows **Get started**, click it:
   - **App name:** `Advanced Reports`. **User support email:** your mannabyte.com
     address. Next.
   - **Audience:** **External**. Next.
   - **Contact information:** your mannabyte.com address. Next, agree, **Create**.
2. Left menu, **Data Access** → **Add or remove scopes**. In the filter box type
   `drive.file`, tick `.../auth/drive.file`, **Update**, then **Save**. Add nothing
   else. This scope only lets the app see files it created, which is why Google doesn't
   require a security review.
3. Left menu, **Clients** → **Create client**:
   - **Application type:** Web application. **Name:** `Advanced Reports web`.
   - Leave **Authorized JavaScript origins** (the first section) empty; it's for
     browser-only apps and rejects any address with a path.
   - In the **second** section, **Authorized redirect URIs** → **Add URI**:
     `http://localhost:8000/auth/google/callback`
   - Leave "Use this client for an AI-powered agent" unchecked.
     (production and staging addresses get added at deploy time).
   - **Create**. A box shows the client ID and secret. Click **Download JSON** and keep
     the file outside the repo, e.g. in `~/Documents/secrets/`.
4. Left menu, **Audience** → **Test users** → **Add users**: add every Google account
   used for testing (your mannabyte.com account, and the account that will own a test
   church's rosters). Leave the app in **Testing** for now.
   **Publish app** stays greyed out until Branding has a homepage and a privacy policy
   URL, and those pages don't exist until Phase 2 (2.7) and the domain (1.7). In
   *Testing*, a Drive connection expires after 7 days, which is fine for testing.
   **Publish before any church relies on weekly runs:** fill in Branding (homepage
   `https://reports.mannabyte.com`, privacy `https://reports.mannabyte.com/privacy`,
   authorized domain `mannabyte.com`), then **Publish app** so it says
   **In production**. Don't use placeholder links; Google checks them.
5. Tell the session where you saved the JSON file. It puts the values in Secret Manager
   (`google-oauth-client-id`, `google-oauth-client-secret`) for you.

Google may ask you to verify the brand later, when privacy and terms pages exist. That
uses the domain step below.

### 1.7 Domain (later, ≈ 20 min)

When the production deploy is ready, the session gives you one DNS record for
`reports.mannabyte.com`. You add it wherever mannabyte.com's DNS is managed (the same
place you set up Workspace email). Google Auth Platform also wants `mannabyte.com`
verified in <https://search.google.com/search-console>. You may have done that already
for Workspace.

### 1.8 IBL production baseline (optional, ≈ 5 min)

Only if you still want "how long the real Cloud Run job takes" in `docs/benchmarks.md`:
run `! gcloud auth login` **with the IBL Google account**, and the session reads the job
history with read-only commands. Not needed for launch.

### Moving the app to Mannabyte later

When you're ready (before the January launch, or at the latest before you leave IBL in
May 2027):
1. Create a Planning Center organization for Mannabyte Labs. Planning Center People is
   free, but check the sign-up page.
2. Register a new OAuth app there with the same callback addresses (1.4, steps 3–5).
3. The session swaps the client ID and secret in Secret Manager.
4. Each connected church clicks **Sign in with Planning Center** once more. No data is
   lost.

Planning Center doesn't document a way to transfer an app between organizations, so
plan on "new app plus one re-sign-in" and don't count on a transfer.

---

## Phase 2 — Building what is missing (next sessions)

Once 1.1, 1.2, 1.4 and 1.6 exist. Estimates are in coding sessions like tonight's.

| # | Work | Estimate | Needs from you |
|---|---|---|---|
| 2.1 | **Firestore store**: the same four operations as today's JSON store, plus a transaction for "one run at a time" | ✅ Done 2026-11-21: `core/firestore_store.py`, `AR_FIRESTORE_PROJECT`; store checks pass against real staging Firestore | Project from 1.1 |
| 2.2 | **Google Drive connection**: "Connect Google Drive" button, the app creates an *Advanced Reports* folder in the church's Drive, uploads rosters there each run, replaces last week's files in place | 1 session | Client from 1.6 |
| 2.3 | **IBL Drive delivery that keeps the old folder** (see Phase 3) | ½ session | IBL folder shared with the new service account |
| 2.4 | **Real Planning Center sign-in**: test against a real org, fix whatever the guesses got wrong, finish "is this person an admin" | ½ session | 1.4 (tested in 1.5) |
| 2.5 | **Container image and deploy** | ✅ Staging live 2026-11-21 at https://advanced-reports-300061322405.us-central1.run.app — `bash deploy/platform.sh staging\|prod` (image built locally, Cloud Run service + job, bucket, scheduler every 10 min). PDFs and logos in Cloud Storage, encrypted per church, latest run only (D2). | — |
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
| Planning Center developer account / test church | Not needed now (we test with Liberty and IBL) | — | **$0** |
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
| D2 | Keep copies of each run's PDFs on the platform (for the Rosters tab preview) | ✅ **Decided 2026-11-21: latest run only**, in an encrypted Cloud Storage bucket, deleted when the next run finishes. Owner's rule: stay inside free tiers. | The Rosters tab stays useful, and you never hold more than one week of children's data. The alternative (keep nothing, link to Drive) is more private but the Rosters tab becomes a list of links. |
| D3 | IBL's Drive folder | **Keep the old folder** via service account (3.1) | Zero change for teachers. |
| D4 | Where the session should start | **2.1 + 2.5 first** (store and deploy to staging), then 2.2 | You get a real URL to click early, and every later piece can be tested online. |
| D5 | Reply time you promise on the Help page | Currently "A real person reads every message" (no time promise) | Promise only what you can keep while working at IBL. |

---

## Timeline at a glance

Assuming you can give this a few evenings a week:

| When | What | Your time |
|---|---|---|
| Week 1 | Phase 1 (1.2–1.6) | about 1 h |
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
