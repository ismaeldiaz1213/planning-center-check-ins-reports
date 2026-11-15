# advanced_reports/modules/checkin_reports.py
#
# The Check-In Reports module (plan §4.1): a church's list of reports, stored as
# plain dicts and validated by the engine's own ReportSpec, plus the step that
# turns a church's stored settings into the ChurchConfig the engine runs on.

from __future__ import annotations

from dataclasses import asdict

from planning_center_reports.church import Branding, ChurchConfig
from planning_center_reports.reports import ReportSpec, parse_reports

MODULE_ID = "checkin_reports"
_BRANDING_FIELDS = ("verse_text", "verse_ref", "help_contact", "video_url", "feedback_url")


def spec_to_dict(spec: ReportSpec) -> dict:
    data = asdict(spec)
    data["start_date"] = spec.start_date.isoformat() if spec.start_date else None
    data["outputs"] = list(spec.outputs)
    data["demo_locations"] = list(spec.demo_locations)
    data["hide"] = list(spec.hide)
    return data


def parse(reports: list[dict]) -> tuple[ReportSpec, ...]:
    """Validate stored or submitted report settings. Raises ReportConfigError."""
    return parse_reports(list(reports), source="reports")


def church_config(org_id: str, church: dict, module: dict | None, logo_path: str | None = None) -> ChurchConfig:
    branding = church.get("branding") or {}
    return ChurchConfig(
        org_id=org_id,
        name=church["name"],
        timezone=church["timezone"],
        language=church["language"],
        theme=church.get("theme") or None,
        branding=Branding(logo_path=logo_path,
                          guide_languages=tuple(church["instructions_languages"])
                          if church.get("instructions_languages") else None,
                          **{k: branding.get(k) or "" for k in _BRANDING_FIELDS}),
        drive_parent_folder_id=None,
        reports=parse((module or {}).get("reports") or []) if (module or {}).get("reports") else (),
    )
