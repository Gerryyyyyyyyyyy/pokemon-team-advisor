UV ?= uv

.PHONY: install lock format format-check lint type-check test coverage check run

install:
	$(UV) sync --locked

lock:
	$(UV) lock

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

format-check:
	$(UV) run ruff format --check .

lint:
	$(UV) run ruff check .

type-check:
	$(UV) run mypy

test:
	$(UV) run pytest

coverage:
	$(UV) run pytest --cov=pokemon_team_advisor --cov-report=term-missing

check: format-check lint type-check test

run:
	$(UV) run streamlit run src/pokemon_team_advisor/app.py
