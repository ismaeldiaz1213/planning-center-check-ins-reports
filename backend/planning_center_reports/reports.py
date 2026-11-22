# planning_center_reports/reports.py
#
# Declarative report definitions. A "report" is one PCO Check-Ins event plus the
# set of optional features its rosters need — bus-route lookup, attendance
# summaries, the volunteer arrival report, instructions, where to upload them.
#
# This module only describes and validates reports. Where a church's reports
# come from is somebody else's job: legacy.py reads reports.yaml and .env for
# IBL's original job, and the platform reads each church's stored settings.
# Nothing here touches the environment or keeps state.
#
# Every optional feature defaults to OFF. A church with no bus ministry writes a
# spec with no route_source_event and no volunteer_event, and the pipeline never
# contacts those events at all. See docs/reports.md.
#
# ReportSpec is a plain frozen dataclass rather than a pydantic model on purpose:
# cli.py imports it, and the Cloud Run job image installs only requirements.txt.

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date, timedelta

# Output kinds a report can request.
#   "simple"  → the class/route roster (the file is named by the church's
#               language: "Roster.pdf", see i18n "file.roster")
OUTPUT_KINDS: tuple[str, ...] = ("simple",)

# What a report may leave off its rosters (the `hide` field). Names always show.
HIDEABLE: tuple[str, ...] = ("birthday", "phone", "grade", "attendance", "added", "address",
                             "parents", "workers", "inactive", "summary")


# Theme keys accepted in default_theme — mirrors config.THEMES minus the None key.
VALID_THEMES = {"primavera", "verano", "otono", "invierno"}


class ReportConfigError(Exception):
    """Raised when reports.yaml is malformed or a requested report is unknown."""


@dataclass(frozen=True)
class ReportSpec:
    """One configured report.

    Field defaults define the minimal report: a single roster PDF per location
    covering a rolling 26 weeks, with no route column or volunteer report.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    id:        str                     # slug — CLI arg, API path segment, tile key
    label:     str                     # human-readable name shown in the UI
    pco_event: str                     # exact PCO Check-Ins event name

    # ── Presentation ──────────────────────────────────────────────────────────
    subtitle: str | None = None     # PDF header subtitle; defaults to label
    icon:     str = "📋"               # emoji for the frontend tile
    enabled:  bool = True              # hide from the UI/CLI without deleting

    # ── Outputs ───────────────────────────────────────────────────────────────
    outputs: tuple[str, ...] = ("simple",)

    # ── History ───────────────────────────────────────────────────────────────
    # Two ways to bound the history a roster looks at:
    #   start_date    — fixed first Sunday (back-to-school). Anyone seen since then
    #                   is on the roster; "date added" is their first check-in in
    #                   the class after it. Classes reset every school year.
    #   history_weeks — rolling window used when start_date is unset (e.g. a
    #                   quarter, 13, for bus routes that run all year with adults).
    start_date:        date | None = None
    history_weeks:     int = 26
    max_history_weeks: int = 52        # safety cap on how many Sundays are fetched

    # ── Optional features (all off by default) ────────────────────────────────
    # None ⇒ the corresponding PCO event is never fetched.
    route_source_event: str | None = None
    show_route:         bool = False   # render the "Ruta" column
    # Columns and sections left off the roster: any of "birthday", "phone", "grade",
    # "attendance", "added", "address", "parents", "workers", "inactive", "summary".
    hide:               tuple[str, ...] = ()
    attendance_summary: bool = False   # per-route breakdown under the roster
    instructions:       bool = False   # Instrucciones.pdf in every location folder

    # Volunteer attendance (Voluntarios.pdf). Volunteers are the check-ins
    # Planning Center tags as kind "Volunteer" in this report's own event — or,
    # when volunteer_event is set, everyone volunteer_min_age+ who checked into
    # that event (e.g. the bus workers' "Junta de Rutas" meeting).
    volunteer_report:  bool = False
    volunteer_event:   str | None = None
    volunteer_min_age: int = 16
    volunteer_weeks:   int = 4

    # ── Destination ───────────────────────────────────────────────────────────
    # None ⇒ location folders sit directly under the church's destination folder.
    drive_folder_prefix: str | None = None

    # ── Run defaults ──────────────────────────────────────────────────────────
    # The "active" window: people seen in the last default_weeks Sundays are on
    # the roster; everyone else since start_date moves to "Hace tiempo".
    default_weeks: int = 6
    default_theme: str | None = None

    # ── Demo mode ─────────────────────────────────────────────────────────────
    # Location names demo_run.py invents when DEMO_MODE=true.
    demo_locations: tuple[str, ...] = field(default=())

    def __post_init__(self):
        for name in ("id", "label", "pco_event"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} is required and must be non-empty")

        # Allow a bare string or a list in YAML; normalise to a tuple.
        outputs = self.outputs
        if isinstance(outputs, str):
            outputs = (outputs,)
        outputs = tuple(outputs)
        if not outputs:
            raise ValueError("outputs must list at least one of 'simple'")
        unknown = [o for o in outputs if o not in OUTPUT_KINDS]
        if unknown:
            raise ValueError(
                f"unknown output(s) {unknown}; expected any of {sorted(OUTPUT_KINDS)}"
            )
        object.__setattr__(self, "outputs", outputs)
        object.__setattr__(self, "demo_locations", tuple(self.demo_locations or ()))

        hide = (self.hide,) if isinstance(self.hide, str) else tuple(dict.fromkeys(self.hide or ()))
        unknown = [h for h in hide if h not in HIDEABLE]
        if unknown:
            raise ValueError(f"unknown hide value(s) {unknown}; expected any of {list(HIDEABLE)}")
        object.__setattr__(self, "hide", hide)

        theme = self.default_theme or None
        if theme is not None and theme not in VALID_THEMES:
            raise ValueError(f"unknown theme {theme!r}; expected one of {sorted(VALID_THEMES)}")
        object.__setattr__(self, "default_theme", theme)

        if not (1 <= int(self.default_weeks) <= 52):
            raise ValueError(f"default_weeks must be between 1 and 52, got {self.default_weeks}")
        if not (1 <= int(self.history_weeks) <= 104):
            raise ValueError(f"history_weeks must be between 1 and 104, got {self.history_weeks}")
        if not (1 <= int(self.max_history_weeks) <= 104):
            raise ValueError(
                f"max_history_weeks must be between 1 and 104, got {self.max_history_weeks}"
            )
        if not (1 <= int(self.volunteer_weeks) <= 12):
            raise ValueError(f"volunteer_weeks must be between 1 and 12, got {self.volunteer_weeks}")
        if not (0 <= int(self.volunteer_min_age) <= 120):
            raise ValueError(
                f"volunteer_min_age must be between 0 and 120, got {self.volunteer_min_age}"
            )

        # YAML gives a date for 2026-08-23 but a string for "2026-08-23".
        start = self.start_date
        if isinstance(start, str):
            try:
                start = date.fromisoformat(start.strip())
            except ValueError as exc:
                raise ValueError(f"start_date must be YYYY-MM-DD, got {self.start_date!r}") from exc
        object.__setattr__(self, "start_date", start)

        # show_route without a source would silently render an always-blank column.
        if self.show_route and not self.route_source_event:
            raise ValueError(
                "show_route is true but route_source_event is not set — "
                "the Ruta column would always be blank"
            )

    # ── Derived values ────────────────────────────────────────────────────────
    @property
    def pdf_subtitle(self) -> str:
        """Subtitle drawn in the PDF header."""
        return self.subtitle if self.subtitle else self.label

    def history_start(self, today: date | None = None) -> date:
        """First local date whose Sunday is fetched."""
        if self.start_date:
            return self.start_date
        # One day short of history_weeks, so exactly history_weeks Sundays fit.
        return (today or date.today()) - timedelta(weeks=self.history_weeks, days=-1)


_KNOWN_FIELDS = {f.name for f in fields(ReportSpec)}


# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_reports(raw: object, source: str = "<memory>") -> tuple[ReportSpec, ...]:
    """Validate a parsed YAML document into ReportSpecs.

    Accepts either a bare list of specs or a mapping with a top-level 'reports' key.
    """
    if isinstance(raw, dict):
        raw = raw.get("reports")
    if raw is None:
        raise ReportConfigError(f"{source}: no 'reports' list found")
    if not isinstance(raw, list):
        raise ReportConfigError(f"{source}: 'reports' must be a list, got {type(raw).__name__}")

    specs: list[ReportSpec] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ReportConfigError(f"{source}: reports[{i}] must be a mapping")
        ident = entry.get("id", f"index {i}")
        unknown = sorted(set(entry) - _KNOWN_FIELDS)
        if unknown:
            raise ReportConfigError(
                f"{source}: report {ident!r} has unknown key(s) {unknown}; "
                f"valid keys are {sorted(_KNOWN_FIELDS)}"
            )
        try:
            specs.append(ReportSpec(**entry))
        except Exception as exc:
            raise ReportConfigError(f"{source}: report {ident!r} is invalid — {exc}") from exc

    seen: set[str] = set()
    for spec in specs:
        if spec.id in seen:
            raise ReportConfigError(f"{source}: duplicate report id {spec.id!r}")
        seen.add(spec.id)

    if not specs:
        raise ReportConfigError(f"{source}: 'reports' list is empty")
    return tuple(specs)


def find_report(specs: tuple[ReportSpec, ...], key: str) -> ReportSpec:
    """Resolve a report by id, then by exact PCO event name.

    Matching pco_event is what keeps `python main.py "Escuela Dominical"` and the
    existing Cloud Run job arguments working after the move to ids.
    """
    for spec in specs:
        if spec.id == key:
            return spec
    for spec in specs:
        if spec.pco_event == key:
            return spec
    # Last resort: case-insensitive match, so "Rutas" resolves to id "rutas".
    lowered = key.strip().lower()
    for spec in specs:
        if spec.id.lower() == lowered or spec.pco_event.lower() == lowered:
            return spec
    known = ", ".join(f"{s.id} ({s.pco_event!r})" for s in specs)
    raise ReportConfigError(f"unknown report {key!r}. Configured reports: {known}")
