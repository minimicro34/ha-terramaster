PYTHON ?= python3.14
NODE ?= node

.PHONY: help compile format format-check lint typecheck test coverage card-test check clean

help:
	@echo "Targets: compile format format-check lint typecheck test coverage card-test check clean"

compile:
	$(PYTHON) -m compileall -q custom_components

format:
	$(PYTHON) -m ruff format .

format-check:
	$(PYTHON) -m ruff format --check .

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy custom_components/terramaster

test:
	$(PYTHON) -m pytest

coverage:
	$(PYTHON) -m pytest --cov=custom_components.terramaster --cov-report=term-missing --cov-report=xml --cov-fail-under=80

card-test:
	$(NODE) --check custom_components/terramaster/www/terramaster-card.js
	$(NODE) --test tests/js/*.test.cjs

check: lint typecheck coverage card-test

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -f .coverage coverage.xml coverage.json
