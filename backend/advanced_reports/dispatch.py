# advanced_reports/dispatch.py
#
# The weekly schedule. Each church may store
#     schedule = {"enabled": true, "day": "sat", "time": "18:00"}
# in its own time zone. dispatch() starts a run for every church whose time has
# come and that has not already had its scheduled run today.
#
# On Google Cloud, Cloud Scheduler calls POST /internal/dispatch about every ten
# minutes. On a developer's machine the web service calls dispatch() itself once
# a minute, so the schedule works with nothing else set up.

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from advanced_reports.core.store import Store
from advanced_reports.core.tenant_repo import TenantRepo, all_org_ids
from advanced_reports.modules import checkin_reports
from advanced_reports.settings import Settings

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# A run is started up to this long after its time, so a short outage does not
# skip the week but a server that was off all day does not surprise anyone at night.
GRACE_MINUTES = 180


def is_due(church: dict, now_utc: datetime) -> str | None:
    """The local date (YYYY-MM-DD) to record if this church's run is due now, else None."""
    schedule = church.get("schedule") or {}
    if not schedule.get("enabled") or schedule.get("day") not in DAYS:
        return None
    local = now_utc.astimezone(ZoneInfo(church["timezone"]))
    if DAYS[local.weekday()] != schedule["day"]:
        return None
    hour, minute = (int(part) for part in schedule["time"].split(":"))
    late = (local.hour * 60 + local.minute) - (hour * 60 + minute)
    today = local.date().isoformat()
    if not 0 <= late <= GRACE_MINUTES or church.get("schedule_last") == today:
        return None
    return today


def dispatch(settings: Settings, store: Store, launcher, now_utc: datetime) -> list[str]:
    """Start every due run. Returns the ids of the churches that were started."""
    started: list[str] = []
    for org_id in all_org_ids(store):
        repo = TenantRepo(store, settings.vault, settings.files_dir, org_id)
        church = repo.church()
        if not church or church.get("status") != "active":
            continue
        today = is_due(church, now_utc)
        if today is None or repo.active_run():
            continue
        if not (repo.module(checkin_reports.MODULE_ID) or {}).get("reports"):
            continue
        repo.update_church({"schedule_last": today})
        run = repo.create_run("schedule", started_by="")
        launcher.launch(org_id, run["id"])
        started.append(org_id)
    return started
