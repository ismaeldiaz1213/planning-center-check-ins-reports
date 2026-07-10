# Sample Data & Previews

`preview.py` generates PDFs using mock attendees — no Planning Center credentials,
no Google Drive, no service account needed.

---

## Basic usage

Run from the `backend/` directory:

```bash
python preview.py
```

Output goes to `backend/previews/`. Files are named by type and theme,
e.g. `previews/primavera_direcciones.pdf`.

---

## Flags

| Flag | Values | Description |
|------|--------|-------------|
| `--theme` | `primavera`, `verano`, `otono`, `invierno` | Apply a campaign colour scheme |
| `--type` | `rutas`, `escuela`, `direcciones` | Generate only one PDF type |
| `--open` | — | Open the generated PDFs in your system PDF viewer after generating |

### Examples

```bash
# All themes × all PDF types
python preview.py

# One theme, all types
python preview.py --theme primavera

# Only address PDFs (Direcciones) with autumn theme
python preview.py --type direcciones --theme otono

# Sunday school rosters only, open immediately
python preview.py --type escuela --open

# Quick single-file check
python preview.py --type rutas --theme invierno --open
```

---

## What the mock data covers

`MOCK_ATTENDEES` at the top of `preview.py` is a list of `Attendee` objects that exercises
all the edge cases the PDF generators handle:

| Edge case | How it's covered |
|-----------|-----------------|
| Missing phone | One attendee has no phone number → yellow highlight |
| Missing birthday | One attendee has no birthday → yellow highlight |
| Missing grade | One minor has no grade set → yellow highlight |
| Address-only / city-only address | One entry with a partial address → yellow highlight |
| Toddler (under 5) | Age auto-resolves to Nursery / 3 años / 4 años |
| New visitor (added within 7 days) | `is_new_visitor=True` → gold dot or soccer ball |
| Helper / bus worker | `is_helper=True` → appears on Sunday school roster, blank Ruta column |
| Multi-location | Multiple `location_name` values → separate PDFs per location |
| Attendance rate | `attendance_rate="3/5"` on some records |

---

## Editing mock data

To test a specific scenario, edit `MOCK_ATTENDEES` near the top of `preview.py`:

```python
MOCK_ATTENDEES = [
    Attendee(
        first_name="Juan",
        last_name="García",
        phone="713-555-0101",
        birthday="01/15/2015",
        grade="4th",
        address="123 Main St Apt 4A, Houston, TX 77001",
        location_name="Ruta 1 - Bus",
        route="1",
        attendance_rate="5/5",
        is_new_visitor=False,
        is_helper=False,
    ),
    # Add more entries here...
]
```

After editing, run `python preview.py --open` to see the result immediately.

---

## Previews directory

Generated files in `backend/previews/` are ignored by git (see `.gitignore`).
You can safely generate as many preview files as you want without cluttering the repo.
