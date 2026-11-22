# Check-In tools: seeding pre-select history

Four small scripts in `backend/` create check-ins in bulk so that Planning Center
Check-Ins **pre-select** suggests the right class for people the next Sunday. They are
operator tools run from a laptop, not part of the Advanced Reports product.

| Script | Who it checks in | Typical use |
|---|---|---|
| `checkin_people_list.py` | Names from a **roster spreadsheet** (CSV) | A teacher's class list → pre-select that class. Works for **any church**. |
| `promote_checkins.py` | Everyone seen at one class in the last N Sundays | Grade promotion (see [grade-promotion.md](grade-promotion.md)) |
| `backfill_bus_class.py` | IBL bus kids, placed by grade and gender | IBL's "C" Escuela Dominical (see [IBL.md](IBL.md)) |
| `groups_to_check_ins.py` | Members of a PCO **Group** | Older, IBL-only, hard-coded names. Prefer `checkin_people_list.py`. |

## Why these exist and how they work

- **Pre-select** suggests the location a person checked into **most recently** within
  that event. It overrides grade and age filters. Only check-in history changes it.
- The public Check-Ins API is **read-only** for check-ins, so there is no `POST`. The
  scripts call `POST /event_periods/{id}/bulk_check_ins` on
  `check-ins.planningcenteronline.com`, the endpoint the Check-Ins web app itself uses.
  The calls are signed in with a browser session cookie and CSRF token. That's why this
  stays out of the hosted product (see `docs/advanced-reports-plan.md` §4.4).
- Reads (people, events, locations, periods) go through the public API with a
  Personal Access Token (`PCO_APP_ID` / `PCO_SECRET`).
- Re-running is safe. Planning Center reports existing check-ins as duplicates and
  doesn't double them.
- **Side effect to tell the church about:** these are real check-ins. The target
  Sunday's attendance numbers go up by everyone submitted.

## `checkin_people_list.py`: from a roster to pre-select

### Rules (the owner's, keep them)
- **Never create people, never change People records.** The script only reads People.
- **Never force a match.** Only an exact first + last name match on one *active* person
  is checked in automatically. Everything else is skipped and reported, and the owner
  decides.
- **Dry run first, always.** Show the owner the report, and get an explicit yes before
  the real run.
- **Target a past Sunday, by exact date.** The script refuses today and future dates.

### Gotcha: "the latest period" can include tomorrow
Some churches' weekly periods start mid-week. Liberty's, for example, opens Wednesday
7pm and runs through Sunday. On a Saturday, the "most recent started period" is
**tomorrow's** week. `promote_checkins.py` and `groups_to_check_ins.py` pick by "most
recent", so they would check people into the coming Sunday. `checkin_people_list.py`
instead matches the session by **local date and time** (`--date`, `--time`, `--tz`).

### Setup for a church
1. **A Personal Access Token for that church.** Sign in at
   <https://api.planningcenteronline.com/oauth/applications> with that church as the
   active organization, then go to *Personal Access Tokens* and create one.
2. **An env file per church**, e.g. `backend/.env.liberty`. `.env.*` is git-ignored;
   never commit it, and never paste its values into a chat.
   ```
   PCO_APP_ID=...
   PCO_SECRET=...
   PCO_SESSION_COOKIE=...   # only for the real run
   PCO_CSRF_TOKEN=...       # only for the real run
   ```
   The file overrides the project's `.env` (IBL's), so IBL's credentials stay as they
   are. For safety, a real run requires the cookie to be in *this* file.
3. **Session cookie and CSRF token.** Get these right before the real run, because they
   expire. In Chrome, open `check-ins.planningcenteronline.com` signed in, **with the
   same church active** (if the wrong church is active, posts go nowhere or fail).
   - Cookie: DevTools (F12) → *Application* → *Cookies* →
     `check-ins.planningcenteronline.com` → value of `planning_center_session`.
   - CSRF token: DevTools *Console*:
     `document.querySelector('meta[name=csrf-token]').content`

### The roster
A CSV with a `Last Name` and a `First Name` header cell, in any row and any column.
Suffixes on the last name (`Smith, II`, `Jones, Jr.`) are stripped for the lookup.
Spreadsheets exported from Numbers or Excel have one tab per quarter. Export every tab
with LibreOffice and use the **current quarter's** tab:

```bash
soffice --headless --convert-to 'csv:Text - txt - csv (StarCalc):44,34,UTF8,1,,0,false,true,false,false,false,-1' roster.xlsx
# writes roster-<Sheet Name>.csv for every sheet
```

Keep roster files out of the repo (they hold phones and addresses). Use a scratch
directory.

### Run it
```bash
cd backend
# 1. Dry run: matches names, prints the report, changes nothing.
.venv/bin/python checkin_people_list.py --env-file .env.liberty \
    --roster /path/to/roster.csv --event "Adult Bible Classes" \
    --location "Life Builders Bible Class" --date 2026-11-15 --time 09:30 \
    --report /path/to/match_report.csv --dry-run

# 2. Real run, after the owner says yes. --add-ids adds people resolved by hand.
.venv/bin/python checkin_people_list.py ...same args without --dry-run... \
    --add-ids 158526200,1982170

# 3. Follow-up run for only the extra people.
.venv/bin/python checkin_people_list.py ...same args... --only-added --add-ids 133442236
```

`--event` and `--location` are exact names. Check them first with the Planning Center
MCP (`check_ins_events`, `check_ins_locations`) or `promote_checkins.py --list-locations`.

### Reading the report
| Group | Meaning | What to do |
|---|---|---|
| Matched | Exactly one active person with that first + last name (or nickname) | Checked in |
| NOT IN PLANNING CENTER | No exact match. `did you mean` lists similar names: first-name spellings (Jon → John), short forms (Ben → Benjamin), and last-name typos (Smtih → Smith) | Show the owner. On a yes, look up the ID and pass `--add-ids`. "No close match" means really missing, or a nickname with different letters (Bob → Robert): leave it to the owner. |
| MORE THAN ONE active person | Duplicate profiles in Planning Center | Pick the profile whose **phone, email or birthdate matches the roster row** (MCP `people_search` with `ids` and `include: ["emails","phone_numbers"]`). Often the extra profile is an empty one flagged as a child. Pass the right ID with `--add-ids`. Tell the owner which you picked and why. |
| ONLY AN INACTIVE profile | The person exists but is inactive | Skipped. Don't check in inactive people unless the owner asks. |

### Verify afterwards
The script's "submitted successfully" means only that Planning Center accepted the
request. Confirm with the MCP: `check_ins_check_ins` with the event, `include:
["event_period"]`, newest first. The period's `regular_count` should match. Then check
one or two people at a station on Sunday.

### Worked example: Liberty Baptist, Life Builders (2026-11-21)
- Event `Adult Bible Classes` (46486), location `Life Builders Bible Class` (1196952),
  Sunday 2026-11-15 9:30 (period 49856630, event time 64239340), time zone
  America/New_York.
- 115 roster names: 84 exact matches, 7 duplicates resolved by phone, email or birthday,
  11 spellings confirmed by the owner. **102 checked in.** 6 were not in Planning
  Center, and 7 had only inactive profiles.
- Planning Center data issues found and passed to the office: duplicate profiles where
  one spouse's contact details sit on a profile with the other spouse's first name.

## Running these through Claude

- The Planning Center MCP connector is **read-only**, so use it for lookups and for
  verifying. The writes only happen through these scripts.
- The MCP is connected to **one** church at a time. Confirm which one with
  `people_current_organization` before anything else.
- Every real run needs the owner's explicit yes, one at a time.
