# planning_center_reports/i18n/en.py
#
# English. FIRST PASS, written 2026-11-14 for the platform refactor and not yet
# reviewed by an English-speaking church. Polish before Liberty Baptist's
# onboarding (wording, date formats, grade labels). Nothing here affects IBL.

CODE = "en"

MONTHS = {
    1: "January",   2: "February", 3: "March",    4: "April",
    5: "May",       6: "June",     7: "July",     8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

MONTHS_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

GRADES = {
    -2: "Nursery", -1: "Pre-K", 0: "K",
    1: "1st",  2: "2nd",  3: "3rd",  4: "4th",  5: "5th",  6: "6th",
    7: "7th",  8: "8th",  9: "9th", 10: "10th", 11: "11th", 12: "12th",
}

TEXT = {
    # ── Files and folders a run creates ──
    "file.roster":       "Roster.pdf",
    "file.volunteers":   "Volunteers.pdf",
    "file.instructions": "Instructions.pdf",
    "folder.volunteers": "Volunteers",

    # ── Dates ──
    "date.short": "{mon} {day}",
    "date.long":  "{mon} {day}, {year}",

    # ── Page header and footer ──
    "page.generated":  "Generated {month} {day}, {year} at {time}",
    "page.continued":  "continued",
    "page.number":     "Page {n}",
    "legend.new":      "New this Sunday",
    "legend.warn":     "Missing information",
    "feedback.link":   "Questions or ideas? Tell us ›",
    "feedback.title":  "Something confusing? An idea? Something not working? Tell us.",
    "feedback.line1":  "Scan the code or tap here to leave comments, questions or complaints.",
    "feedback.line2":  "The more you tell us, the better we can make these rosters.",

    # ── Campaign themes ──
    "campaign.primavera": "Spring Campaign",
    "campaign.verano":    "Summer Campaign",
    "campaign.otono":     "Fall Campaign",
    "campaign.invierno":  "Winter Campaign",

    # ── Shared column headers ──
    "col.first_name": "First name",
    "col.last_name":  "Last name",
    "col.name":       "Name",
    "col.birthday":   "Birthday",
    "col.phone":      "Phone",
    "col.grade":      "Grade",
    "col.route":      "Route",
    "col.attendance": "Attendance",
    "col.added":      "Added",
    "col.address":    "Address",
    "col.last_seen":  "Last seen",
    "col.weeks":      "Weeks",
    "col.times":      "Times",
    "col.sunday":     "Sunday",
    "col.regulars":   "Regulars",
    "col.new":        "New",
    "col.total":      "Total",
    "col.riders":     "Riders on the roster",
    "col.present":    "Present",
    "col.first_checkin":   "First check-in",
    "col.average_checkin": "Average check-in",
    "col.usual_time": "Usual time",

    # ── Roster.pdf ──
    "roster.history":       "History since {date} · {sundays} Sundays",
    "roster.list":          "Roster",
    "roster.list.note":     "Came in the last {weeks} Sundays · one dot per Sunday · "
                            "Added = first Sunday in this class",
    "roster.list.empty":    "Nobody has come in recent weeks.",
    "roster.workers":       "Teachers and helpers",
    "roster.workers.note":  "Checked in as volunteers in Planning Center",
    "roster.inactive":      "Haven't been back recently",
    "roster.inactive.note": "Came since {date} but not in the last {weeks} Sundays · "
                            "a good list to call",
    "roster.inactive.legend": "Weeks = Sundays since they last came · "
                              "Times = Sundays attended since the start",
    "roster.guardian":      "Parent/Guardian:",
    "roster.route_row":     "Route {route}",
    "grade.toddler":        "Nursery",
    "grade.age3":           "Age 3",
    "grade.age4":           "Age 4",

    # ── Summary block ──
    "summary.title":           "Summary",
    "summary.average":         "Average per Sunday",
    "summary.added":           "Added in {weeks} weeks",
    "summary.new":             "New this Sunday",
    "summary.volunteers":      "Volunteers",
    "summary.attendance":      "Attendance",

    # ── Volunteers.pdf ──
    "volunteers.title":      "Volunteer attendance",
    "volunteers.meta":       "Last {sundays} Sundays",
    "volunteers.section":    "Volunteers",
    "volunteers.note":       "Check-in time each Sunday · — = did not check in",
    "volunteers.empty":      "Nobody was checked in as a volunteer on these Sundays. To list them "
                             "here, mark them as \"Volunteer\" when checking in.",
    "volunteers.unassigned": "Unassigned",
}

# English-only cover: the small second-language lines are left empty.
COVER = {
    "doc_title":   "Check-In Instructions",
    "brand":       "Planning Center Check-Ins",
    "title":       "How to check people in",
    "title_alt":   "",
    "audience":    "For bus route & Sunday school volunteers",
    "steps_heading": "In 3 steps",
    "steps": (
        ("Open Check-Ins and find your roster", "",
         "Use the Roster Station for your route or class."),
        ("Tap the name and wait 2 seconds", "",
         "It changes from \"Ready\" to \"Here\": the check-in is done."),
        ("Not there? Search outside your roster", "",
         "Search › \"outside of roster\". If they are new: Add person."),
    ),
    "video_title": "Watch the video",
    "video_alt":   "",
    "video_hint":  "Scan with your camera or tap here",
    "quick_heading": "Quick reference",
    "quick_situation": "Situation",
    "quick_action":    "What to do",
    "quick": (
        ("On my roster", "",
         "Tap their name › wait › confirm it changed to \"Here\""),
        ("Not on my roster, but in the system", "",
         "Search › \"outside of roster\" › tap their name"),
        ("Brand-new visitor", "",
         "Add person › New or Existing Household › fill in details › find them and check them in"),
    ),
    "help_title":     "Duplicate names or questions?",
    "help_line":      "Write down the name and talk to {contact}.",
    "feedback_title": "Something confusing or not working? Tell us.",
    "feedback_line":  "Scan the code or tap here: the more you tell us, the better we can fix it.",
    "contents_heading": "In this document",
    "page_abbr":      "p. {n}",
    "footer_video":    "Video: {url}",
    "footer_feedback": "Feedback: {url}",
    "guides": (
        ("Full guide", "check-in-guide-en.pdf"),
    ),
}
