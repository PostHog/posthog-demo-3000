SHELL := /bin/bash

.PHONY: help install env env-reset db run seed artifacts test lint clean check-env

help:
	@echo "Common targets:"
	@echo "  make install    - Install Python dependencies"
	@echo "  make env        - Create .env from example"
	@echo "  make check-env  - Verify .env has required PH_* values"
	@echo "  make db         - Initialize DB and dummy stats"
	@echo "  make run        - Check env, seed data, create artifacts, and run app"
	@echo "  make seed       - Seed PostHog historical data (uses PH_* env/.env)"
	@echo "  make artifacts  - Create PostHog demo artifacts (uses PH_* env/.env)"
	@echo "  make test       - Run tests"

install:
	uv sync

env:
	@if [ ! -f .env ]; then cp .env.example .env; fi

env-reset:
	cp .env.example .env

check-env:
	@grep -q "PH_HOST='https://<eu or us>.i.posthog.com'" .env && { echo "Please update PH_HOST in .env"; exit 1; } || true
	@grep -q "PH_PROJECT_KEY='<Project API key>'" .env && { echo "Please update PH_PROJECT_KEY in .env"; exit 1; } || true
	@grep -q "PH_PERSONAL_API_KEY='<Personal API key>'" .env && { echo "Please update PH_PERSONAL_API_KEY in .env"; exit 1; } || true
	@grep -q "PH_PROJECT_ID='<Project Id>'" .env && { echo "Please update PH_PROJECT_ID in .env"; exit 1; } || true

db:
	uv run python pop_db.py
	uv run python dummy_data.py

run: check-env db seed artifacts
	uv run python app.py

seed:
	uv run python scripts/seed_demo_data.py -d $${DAYS:-120} -i $${ITER:-300}

artifacts:
	uv run python scripts/create_posthog_artifacts.py

test:
	uv run pytest -q

clean:
	rm -f hogflix.sqlite
	rm -f .env
