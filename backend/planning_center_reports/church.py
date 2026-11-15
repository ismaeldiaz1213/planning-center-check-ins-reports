# planning_center_reports/church.py
#
# Everything the engine needs to know about one church, passed in explicitly.
# Nothing here is read from the environment or from module globals: the legacy
# adapter (legacy.py) builds it from .env + reports.yaml for IBL's old job, and
# the platform builds it from that church's stored settings.

from __future__ import annotations

from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from planning_center_reports.i18n import LANGUAGES, Catalog, catalog
from planning_center_reports.reports import VALID_THEMES, ReportSpec


@dataclass(frozen=True)
class Branding:
    """What a church can put on its PDFs. Empty values are simply not drawn."""
    logo_path:    str | None = None   # image file for the page header
    verse_text:   str = ""            # footer line, e.g. a Bible verse
    verse_ref:    str = ""
    help_contact: str = ""            # who volunteers ask for help (instructions cover)
    video_url:    str = ""            # check-in walkthrough (instructions cover, QR)
    feedback_url: str = ""            # feedback form linked from every PDF


@dataclass(frozen=True)
class ChurchConfig:
    org_id:   str                     # Planning Center organization id ("legacy" for the old job)
    name:     str
    timezone: str                     # IANA name, e.g. "America/Chicago"
    language: str = "en"
    theme:    str | None = None       # default campaign theme for every report
    branding: Branding = field(default_factory=Branding)
    drive_parent_folder_id: str | None = None
    reports:  tuple[ReportSpec, ...] = ()

    def __post_init__(self):
        if not str(self.org_id or "").strip():
            raise ValueError("org_id is required")
        if self.language not in LANGUAGES:
            raise ValueError(f"unknown language {self.language!r}; expected one of {sorted(LANGUAGES)}")
        if self.theme is not None and self.theme not in VALID_THEMES:
            raise ValueError(f"unknown theme {self.theme!r}; expected one of {sorted(VALID_THEMES)}")
        ZoneInfo(self.timezone)       # raises on an unknown timezone
        object.__setattr__(self, "reports", tuple(self.reports))

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def texts(self) -> Catalog:
        return catalog(self.language)

    @property
    def enabled_reports(self) -> tuple[ReportSpec, ...]:
        return tuple(s for s in self.reports if s.enabled)
