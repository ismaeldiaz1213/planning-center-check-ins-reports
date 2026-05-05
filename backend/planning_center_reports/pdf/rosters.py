# planning_center_reports/pdf/rosters.py
#
# The two roster generators used by both the production run (services.py) and
# the local preview tool (preview.py).
#
#   generate_address_pdf        — address-grouped layout (Direcciones-Roster.pdf)
#   generate_simple_roster_pdf  — alphabetical layout (Roster.pdf)
#
# Both functions accept a list of Attendee dicts, write a PDF to `filename`,
# and return that filename. The active theme is read from config._theme via the
# imported drawing primitives — callers set the theme in config before calling.

from collections import defaultdict
from datetime import datetime

from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas as rl_canvas

from planning_center_reports.config import (
    MIN_EMPTY_ROWS,
    PAGE_H,
    MARGIN,
    HEADER_H,
    COL_HDR_H,
    FOOTER_H,
    ROW_H,
    ED_COL_WIDTHS,
    ED_HEADERS,
    SR_COL_WIDTHS,
    SR_HEADERS,
)
from planning_center_reports.models import (
    _complex_key,
    _extract_apt,
    _extract_route_number,
    _fmt_birthday,
    _is_bad_address,
    _is_minor,
    _parse_apt_number,
    _resolve_grade,
    _street_only,
)
from planning_center_reports.pdf.layout import (
    _draw_address_bar,
    _draw_column_headers,
    _draw_data_row,
    _draw_escuela_summary,
    _draw_page_footer,
    _draw_page_header,
    _rows_available,
    escuela_summary_height,
)


def generate_address_pdf(location_name: str, attendees: list, filename: str = "Direcciones-Roster.pdf") -> str:
    """Generate the address-grouped roster PDF used by bus secretaries.

    Attendees are grouped by apartment complex, then sorted by unit number
    within each group. Each group gets a coloured address bar and at least
    MIN_EMPTY_ROWS blank write-in rows for walk-in visitors.

    Returns the filename of the written PDF.
    """
    visitor_count = sum(1 for p in attendees if p.get("is_visitor"))
    c      = rl_canvas.Canvas(filename, pagesize=landscape(letter))
    gen_dt = datetime.now()

    # Group by complex, sort within group by apartment number
    complex_groups: dict = defaultdict(list)
    for person in attendees:
        addr = (person.get("address") or "").strip()
        complex_groups[_complex_key(addr)].append(person)
    for key in complex_groups:
        complex_groups[key].sort(key=lambda p: _parse_apt_number(p.get("address") or ""))

    # Complexes with a key sort first; unknown/empty addresses go last
    sorted_groups = sorted(
        complex_groups.items(),
        key=lambda kv: (0, kv[0]) if kv[0] else (1, ""),
    )

    page_num    = 1
    first_group = True

    def new_page(is_first: bool) -> float:
        if not is_first:
            c.showPage()
        return _draw_page_header(c, location_name, "Ministerio de Autobuses", gen_dt, visitor_count)

    cursor_y  = new_page(is_first=True)
    rows_left = _rows_available(is_first_page=True)

    for group_key, group_people in sorted_groups:
        raw_addr = (group_people[0].get("address") or "").strip() if group_people else ""
        bar_addr = _street_only(raw_addr)
        # Ensure the whole group (plus empty rows) fits; if not, start a new page
        needed   = len(group_people) + MIN_EMPTY_ROWS + 1
        if rows_left < needed and not first_group:
            _draw_page_footer(c, page_num)
            page_num += 1
            cursor_y  = new_page(is_first=False)
            rows_left = _rows_available(is_first_page=False)

        first_group = False
        cursor_y    = _draw_address_bar(c, bar_addr, cursor_y)
        cursor_y    = _draw_column_headers(c, cursor_y)
        rows_left  -= 1
        row_index   = 0

        for person in group_people:
            if rows_left <= 0:
                _draw_page_footer(c, page_num)
                page_num  += 1
                cursor_y   = new_page(is_first=False)
                cursor_y   = _draw_address_bar(c, bar_addr, cursor_y)
                cursor_y   = _draw_column_headers(c, cursor_y)
                rows_left  = _rows_available(is_first_page=False) - 1
                row_index  = 0

            fn, ln   = person.get("first_name", ""), person.get("last_name", "")
            addr     = person.get("address", "")
            bday_raw = person.get("birthday", "")
            bday     = _fmt_birthday(bday_raw)
            ph       = person.get("phone", "")
            grade    = _resolve_grade(person.get("grade", ""), bday_raw)
            apt      = _extract_apt(addr)
            addr_d   = _street_only(addr)
            attend   = person.get("attendance", "")
            is_v     = person.get("is_visitor", False)

            grade_warn = _is_minor(bday_raw) and not grade
            warn = [False, not fn, not ln, not bday, not ph,
                    grade_warn, False, False, _is_bad_address(addr)]

            cursor_y  = _draw_data_row(c, cursor_y,
                                       ["", fn, ln, bday, ph, grade, apt, attend, addr_d],
                                       row_index, warn, is_visitor=is_v)
            rows_left -= 1
            row_index += 1

        # Guarantee at least MIN_EMPTY_ROWS blank rows for walk-ins
        if rows_left < MIN_EMPTY_ROWS:
            _draw_page_footer(c, page_num)
            page_num  += 1
            cursor_y   = new_page(is_first=False)
            cursor_y   = _draw_address_bar(c, bar_addr, cursor_y)
            cursor_y   = _draw_column_headers(c, cursor_y)
            rows_left  = _rows_available(is_first_page=False) - 1
            row_index  = 0

        for _ in range(min(MIN_EMPTY_ROWS, rows_left)):
            cursor_y  = _draw_data_row(c, cursor_y,
                                       ["", "", "", "", "", "", "", "", bar_addr],
                                       row_index, [False] * 9)
            row_index += 1
            rows_left -= 1

    _draw_page_footer(c, page_num)
    c.save()
    return filename


def generate_simple_roster_pdf(location_name: str, subtitle: str,
                                attendees: list, filename: str = "Lista.pdf",
                                show_route: bool = False,
                                sunday_data: list = None) -> str:
    """Generate the clean alphabetical roster PDF used by bus drivers and Sunday
    school teachers.

    Attendees are sorted by last name then first name. No address grouping,
    no blank write-in rows. The visitor marker is drawn for people added to PCO
    within the last 7 days.

    When show_route=True the Asist. column is replaced with Ruta (showing only
    the route number), using the wider ED layout (Escuela Dominical format).
    If sunday_data is also provided, a compact attendance summary (per-Sunday
    counts and route totals) is drawn below the last attendee row.

    Returns the filename of the written PDF.
    """
    from collections import Counter

    col_widths = ED_COL_WIDTHS if show_route else SR_COL_WIDTHS
    headers    = ED_HEADERS    if show_route else SR_HEADERS

    visitor_count = sum(1 for p in attendees if p.get("is_visitor"))
    c      = rl_canvas.Canvas(filename, pagesize=landscape(letter))
    gen_dt = datetime.now()

    rows_per_page = int((PAGE_H - 2 * MARGIN - HEADER_H - COL_HDR_H - FOOTER_H) / ROW_H)

    sorted_attendees = sorted(
        attendees,
        key=lambda p: (p.get("last_name", "").lower(), p.get("first_name", "").lower()),
    )

    def new_page(is_first: bool) -> float:
        if not is_first:
            c.showPage()
        return _draw_page_header(c, location_name, subtitle, gen_dt, visitor_count)

    cursor_y  = new_page(is_first=True)
    cursor_y  = _draw_column_headers(c, cursor_y, col_widths, headers)
    rows_left = rows_per_page
    page_num  = 1
    row_index = 0

    for person in sorted_attendees:
        if rows_left <= 0:
            _draw_page_footer(c, page_num)
            page_num  += 1
            cursor_y   = new_page(is_first=False)
            cursor_y   = _draw_column_headers(c, cursor_y, col_widths, headers)
            rows_left  = rows_per_page
            row_index  = 0

        fn, ln   = person.get("first_name", ""), person.get("last_name", "")
        addr     = person.get("address", "")
        bday_raw = person.get("birthday", "")
        bday     = _fmt_birthday(bday_raw)
        ph       = person.get("phone", "")
        grade    = _resolve_grade(person.get("grade", ""), bday_raw)
        apt      = _extract_apt(addr)
        addr_d   = _street_only(addr)
        col8     = _extract_route_number(person.get("route", "")) if show_route else person.get("attendance", "")
        is_v     = person.get("is_visitor", False)

        grade_warn = _is_minor(bday_raw) and not grade
        warn = [False, not fn, not ln, not bday, not ph,
                grade_warn, False, False, _is_bad_address(addr)]

        cursor_y  = _draw_data_row(c, cursor_y,
                                   ["", fn, ln, bday, ph, grade, apt, col8, addr_d],
                                   row_index, warn, is_visitor=is_v,
                                   col_widths=col_widths)
        rows_left -= 1
        row_index += 1

    # Draw summary tables below the roster (Escuela Dominical only)
    if show_route and sunday_data:
        n_routes  = len(Counter(p.get("route", "") for p in attendees if p.get("route", "")))
        needed    = escuela_summary_height(len(sunday_data), n_routes)
        if cursor_y - MARGIN < needed:
            _draw_page_footer(c, page_num)
            page_num += 1
            cursor_y  = new_page(is_first=False)
        _draw_escuela_summary(c, cursor_y, attendees, sunday_data)

    _draw_page_footer(c, page_num)
    c.save()
    return filename
