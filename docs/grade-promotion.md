# Grade Promotion (`backend/promote_checkins.py`)

Moves a Sunday school class up a grade in Check-Ins **pre-select history**, so that on
promotion weekend the check-in app suggests the new class instead of the old one.

## Why this exists

Planning Center Check-Ins **pre-select** suggests whichever location a person checked
into most recently — this overrides any grade/age filters configured on the location. If
your classes use pre-select (rather than pure grade/age filters), promoting a student's
`grade` field on their People profile does **not** change what pre-select suggests next
Sunday; only their check-in history does.

Planning Center has no bulk or official way to rewrite that history, and the public
Check-Ins API is read-only for check-ins (no `POST` endpoint exists — confirmed against
PCO's own API docs). So this script replays a real check-in into the destination class
using the same internal endpoint the Check-Ins web app itself calls when a staff member
manually bulk-checks-in a room.

If your classes use grade/age filters instead of pre-select, you don't need this script —
use Planning Center's built-in **People → ⚙️ → Promote grades** instead, which is the
official, fully-supported tool for that case.

## One-time setup: session cookie + CSRF token

The internal endpoint requires an authenticated browser session — there's no service
account or API token that works here.

1. Open **https://check-ins.planningcenteronline.com** in Chrome, logged in as usual.
2. Open DevTools (`F12`) → **Application** tab → **Storage → Cookies** →
   `https://check-ins.planningcenteronline.com`.
3. Copy the **Value** of the cookie named `planning_center_session`.
4. Switch to the **Console** tab and run:
   ```js
   document.querySelector('meta[name=csrf-token]').content
   ```
   Copy the printed string.
5. Add both to `.env`:
   ```
   PCO_SESSION_COOKIE=<value from step 3>
   PCO_CSRF_TOKEN=<value from step 4>
   ```

These expire when that browser session ends. If a run fails with a "session invalid"
error (or the response looks like a login page), repeat steps 1–5 for a fresh cookie —
this is normal and expected, not a sign anything is broken.

## Step by step

**1. Confirm the exact class names.** Class naming is rarely a clean pattern (gendered
splits, Spanish/English mixes, age-based vs. grade-based classes below Kindergarten are
common) — always look these up rather than guessing:

```bash
make promote-checkin-locations
# or: cd backend && python promote_checkins.py --list-locations
```

**2. Dry-run one class.**

```bash
make promote-checkin FROM="2nd Grade" TO="3rd Grade" DRY_RUN=1
```

Prints everyone who checked into `FROM` in the last `WEEKS` Sundays (default 2, so a
student who missed one Sunday is still caught) without submitting anything. Check the
names match who you expect before moving on.

**3. Run it for real.**

```bash
make promote-checkin FROM="2nd Grade" TO="3rd Grade"
```

Everyone found is checked into `TO` for the single most recent Sunday that has already
happened, at the service time given by `TIME=` (default `10:00`, 24-hour), so that
becomes their newest check-in. Prints success/duplicate/error counts at the end —
duplicates just mean someone was already checked into the destination class, which is
harmless.

**4. Verify in Planning Center.** Open Check-Ins → the destination class → the most
recent Sunday → confirm the students appear.

**5. Repeat per class**, one at a time so each can be verified before moving to the next.

## Options

| Flag / `make` var | Default | Purpose |
|---|---|---|
| `--from-location` / `FROM=` | *(required)* | Current class — source of who to move |
| `--to-location` / `TO=` | *(required)* | Next class — destination |
| `--event` / `EVENT=` | `Escuela Dominical` | PCO Check-Ins event name |
| `--weeks` / `WEEKS=` | `2` | How many recent Sundays to search `--from-location` for attendees |
| `--time` / `TIME=` | `10:00` | Service time (24-hour `HH:MM`) to check people into, for classes with more than one Sunday service |
| `--max-age` / `MAX_AGE=` | `20` | Skip anyone at or above this age — e.g. an older student sitting in on a younger class shouldn't get swept up in that class's promotion |
| `--dry-run` / `DRY_RUN=1` | off | Preview who would move without submitting |
| `--list-locations` | — | Print every location name for `--event` and exit |

## Limitations

- **One class → one class only.** A class that fans out into multiple destinations (e.g.
  a single toddler room splitting into gendered Pre-K classes) can't be expressed as one
  `promote-checkin` call — this tool doesn't know each attendee's gender or how to route
  them differently. Handle fan-out classes by hand.
- **Age filtering depends on birthday being on file.** Anyone missing a birthday in
  People is kept rather than silently dropped (the script can't tell if they're 8 or 80),
  so double-check `--dry-run` output for anyone whose age you're unsure of.
- Requires a live, unexpired browser session — this isn't something you can safely
  automate unattended (e.g. via Cloud Scheduler) the way the weekly roster jobs are.
