# advanced_reports/importers/ibl.py
#
# One-off: copy IBL's single-church setup (.env + reports.yaml, read through the
# legacy adapter) into the platform's store as a church. This is the only
# platform code that may import planning_center_reports.legacy.
#
# The Planning Center Personal Access Token is stored encrypted as a "pat"
# connection, so IBL can run on the platform before OAuth sign-in exists.

from __future__ import annotations

import os
from pathlib import Path

from advanced_reports.core.tenant_repo import TenantRepo
from advanced_reports.modules import checkin_reports

DEV_ORG_ID = "dev-ibl"


def available() -> bool:
    from planning_center_reports import legacy  # noqa: F401 — loads .env
    return bool(os.getenv("PCO_APP_ID") and os.getenv("PCO_SECRET"))


def import_church(repo: TenantRepo, overwrite_reports: bool = False) -> None:
    from planning_center_reports import legacy

    church = legacy.church()
    b = church.branding
    if not repo.exists():
        repo.create_church(
            name=church.name, timezone=church.timezone, language=church.language,
            branding={"verse_text": b.verse_text, "verse_ref": b.verse_ref,
                      "help_contact": b.help_contact, "video_url": b.video_url,
                      "feedback_url": b.feedback_url},
            imported_from="ibl-legacy",
        )
        if b.logo_path and Path(b.logo_path).is_file():
            repo.save_logo(Path(b.logo_path).read_bytes())
    if overwrite_reports or not repo.module(checkin_reports.MODULE_ID):
        repo.save_module(checkin_reports.MODULE_ID,
                         {"reports": [checkin_reports.spec_to_dict(s) for s in church.reports]})
    repo.save_secret("pco", {"kind": "pat", "app_id": os.getenv("PCO_APP_ID"),
                             "secret": os.getenv("PCO_SECRET")},
                     kind="pat", status="connected", connected_by="importer")
