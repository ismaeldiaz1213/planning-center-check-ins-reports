# planning_center_reports/i18n/es.py
#
# Spanish. These are IBL's PDFs word for word: the golden tests
# (tests/golden/) fail if any string here changes.

CODE = "es"

MONTHS = {
    1: "enero",      2: "febrero",  3: "marzo",      4: "abril",
    5: "mayo",       6: "junio",    7: "julio",      8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

MONTHS_ABBR = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

GRADES = {
    -2: "Nursery", -1: "Pre-K", 0: "Kinder",
    1: "1°",  2: "2°",  3: "3°",  4: "4°",  5: "5°",  6: "6°",
    7: "7°",  8: "8°",  9: "9°", 10: "10°", 11: "11°", 12: "12°",
}

TEXT = {
    # ── Files and folders a run creates ──
    "file.roster":       "Roster.pdf",
    "file.volunteers":   "Voluntarios.pdf",
    "file.instructions": "Instrucciones.pdf",
    "folder.volunteers": "Voluntarios",

    # ── Dates ──
    "date.short": "{mon} {day}",
    "date.long":  "{day} {mon_lower} {year}",

    # ── Page header and footer ──
    "page.generated":  "Generado el {day} de {month} de {year} a las {time}",
    "page.continued":  "continuación",
    "page.number":     "Página {n}",
    "legend.new":      "Nuevo este domingo",
    "legend.warn":     "Falta información",
    "feedback.link":   "¿Dudas o ideas? Cuéntanos ›",
    "feedback.title":  "¿Algo confuso? ¿Una idea? ¿Algo que no funciona? Cuéntanos.",
    "feedback.line1":  "Escanea el código o toca aquí para dejar tus comentarios, dudas o quejas.",
    "feedback.line2":  "Entre más nos digas, mejor podemos hacer estas listas.  "
                       "·  Scan or tap to share feedback.",

    # ── Campaign themes ──
    "campaign.primavera": "Campaña de Primavera",
    "campaign.verano":    "Campaña de Verano",
    "campaign.otono":     "Campaña de Otoño",
    "campaign.invierno":  "Campaña de Invierno",

    # ── Shared column headers ──
    "col.first_name": "Nombre",
    "col.last_name":  "Apellido",
    "col.name":       "Nombre",
    "col.birthday":   "Cumpleaños",
    "col.phone":      "Teléfono",
    "col.grade":      "Grado",
    "col.route":      "Ruta",
    "col.attendance": "Asistencia",
    "col.added":      "Agregado",
    "col.address":    "Dirección",
    "col.last_seen":  "Última vez",
    "col.weeks":      "Semanas",
    "col.times":      "Veces",
    "col.sunday":     "Domingo",
    "col.regulars":   "Regulares",
    "col.new":        "Nuevos",
    "col.total":      "Total",
    "col.riders":     "Niños en la lista",
    "col.present":    "Presentes",
    "col.first_checkin":   "Primer check-in",
    "col.average_checkin": "Check-in promedio",
    "col.usual_time": "Hora usual",

    # ── Roster.pdf ──
    "roster.history":       "Historial desde {date} · {sundays} domingos",
    "roster.list":          "Lista",
    "roster.list.note":     "Vinieron en los últimos {weeks} domingos · un punto por domingo · "
                            "Agregado = primer domingo en esta clase",
    "roster.list.empty":    "Nadie ha venido en las últimas semanas.",
    "roster.workers":       "Maestros y ayudantes",
    "roster.workers.note":  "Registrados como voluntarios en Planning Center",
    "roster.inactive":      "Hace tiempo que no viene",
    "roster.inactive.note": "Vinieron desde {date} pero no en los últimos {weeks} domingos · "
                            "buena lista para llamar",
    "roster.inactive.legend": "Semanas = domingos desde la última vez · "
                              "Veces = domingos que vino desde el inicio",
    "roster.guardian":      "Padre/Tutor:",
    "roster.route_row":     "Ruta {route}",
    "grade.toddler":        "Nursery",
    "grade.age3":           "3 años",
    "grade.age4":           "4 años",

    # ── Summary block ──
    "summary.title":           "Resumen",
    "summary.average":         "Promedio por domingo",
    "summary.added":           "Agregados en {weeks} semanas",
    "summary.new":             "Nuevos este domingo",
    "summary.volunteers":      "Voluntarios",
    "summary.attendance":      "Asistencia",

    # ── Voluntarios.pdf ──
    "volunteers.title":      "Asistencia de voluntarios",
    "volunteers.meta":       "Últimos {sundays} domingos",
    "volunteers.section":    "Voluntarios",
    "volunteers.note":       "Hora de check-in cada domingo · — = no hizo check-in",
    "volunteers.empty":      "Nadie fue registrado como voluntario en estos domingos. Para que "
                             "aparezcan aquí, márcalos como \"Volunteer\" al hacer check-in.",
    "volunteers.unassigned": "Sin asignar",
}

# The instructions cover is bilingual on purpose: IBL's volunteers read either
# language. "main" lines are large, "alt" lines are the small second language.
COVER = {
    "doc_title":   "Instrucciones de Check-In",
    "brand":       "Planning Center Check-Ins",
    "title":       "Cómo registrar asistencia",
    "title_alt":   "How to check people in",
    "audience":    "Para voluntarios de Rutas y Escuela Dominical  ·  "
                   "For bus route & Sunday school volunteers",
    "steps_heading": "En 3 pasos  ·  In 3 steps",
    "steps": (
        ("Abre Check-Ins y busca tu lista",
         "Open Check-Ins and find your roster",
         "Usa la estación de lista (Roster Station) de tu ruta o clase."),
        ("Toca el nombre y espera 2 segundos",
         "Tap the name and wait 2 seconds",
         "Pasa de \"Ready\" a \"Here\": el check-in está listo."),
        ("¿No aparece? Búscalo afuera de tu lista",
         "Not there? Search outside your roster",
         "Search › \"outside of roster\". Si es nuevo: Add person."),
    ),
    "video_title": "Mira el video",
    "video_alt":   "Watch the video",
    "video_hint":  "Escanea con la cámara o toca aquí",
    "quick_heading": "Resumen rápido  ·  Quick reference",
    "quick_situation": "Situación · Situation",
    "quick_action":    "Qué hacer · What to do",
    "quick": (
        ("Está en mi lista", "On my roster",
         "Toca su nombre › espera › confirma que pasó a \"Here\""),
        ("No está en mi lista, pero sí en el sistema", "Not on my roster, but in the system",
         "Search › \"outside of roster\" › toca su nombre"),
        ("Persona completamente nueva", "Brand-new visitor",
         "Add person › New o Existing Household › llena datos › búscala y regístrala"),
    ),
    "help_title":     "¿Nombres duplicados o dudas?",
    "help_line":      "Anota el nombre y habla con {contact}.",
    "feedback_title": "¿Algo confuso o que no funciona? Cuéntanos.",
    "feedback_line":  "Escanea el código o toca aquí: entre más nos digas, mejor lo arreglamos.",
    "contents_heading": "En este documento  ·  In this document",
    "page_abbr":      "pág. {n}",
    "footer_video":    "Video: {url}",
    "footer_feedback": "Comentarios: {url}",
    # (label in the table of contents, file under assets/guides/)
    "guides": (
        ("Guía completa en español", "guia-check-in-es.pdf"),
        ("Full guide in English", "check-in-guide-en.pdf"),
    ),
}
