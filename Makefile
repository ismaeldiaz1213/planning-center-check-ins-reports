.PHONY: backend-test frontend-test test lint preview build

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
