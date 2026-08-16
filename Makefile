.PHONY: backend-test frontend-test test lint preview build promote-checkin-locations promote-checkin

backend-test:
	cd backend && pytest

frontend-test:
	cd frontend && npm test

test: backend-test frontend-test

lint:
	cd backend && ruff check .
	cd frontend && npx tsc --noEmit

preview:
	cd backend && python preview.py

build:
	cd frontend && npm run build

# List exact Check-Ins location names (grade classes use inconsistent naming —
# always check this before promote-checkin rather than guessing).
#   make promote-checkin-locations [EVENT="Escuela Dominical"]
promote-checkin-locations:
	cd backend && python promote_checkins.py --list-locations $(if $(EVENT),--event "$(EVENT)",)

# Move one class up a grade in Check-Ins pre-select history. Run one class at a time
# so each can be verified before moving to the next.
#   make promote-checkin FROM="2nd Grade Boys" TO="3rd Grade Boys" DRY_RUN=1
#   make promote-checkin FROM="2nd Grade Boys" TO="3rd Grade Boys"
# Optional: WEEKS=2, TIME=10:00, MAX_AGE=20, EVENT="Escuela Dominical" (all shown are defaults)
promote-checkin:
	@if [ -z "$(FROM)" ] || [ -z "$(TO)" ]; then \
		echo "Usage: make promote-checkin FROM=\"2nd Grade Boys\" TO=\"3rd Grade Boys\" [WEEKS=2] [TIME=10:00] [MAX_AGE=20] [DRY_RUN=1]"; \
		echo "Run 'make promote-checkin-locations' first to see exact location names."; \
		exit 1; \
	fi
	cd backend && python promote_checkins.py \
		--from-location "$(FROM)" --to-location "$(TO)" \
		$(if $(EVENT),--event "$(EVENT)",) \
		$(if $(WEEKS),--weeks $(WEEKS),) \
		$(if $(TIME),--time "$(TIME)",) \
		$(if $(MAX_AGE),--max-age $(MAX_AGE),) \
		$(if $(DRY_RUN),--dry-run,)
