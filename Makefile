.PHONY: help dev install test lint format clean run

help:
	@echo "Commands:"
	@echo "  dev       Install dev dependencies and pre-commit hooks"
	@echo "  install   Install production dependencies"
	@echo "  test      Run tests with coverage"
	@echo "  lint      Check code style"
	@echo "  format    Auto-fix code style"
	@echo "  clean     Remove build artifacts"
	@echo "  run       Start development server"

dev:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	.venv/bin/pre-commit install

install:
	pip install -e .

PYTHON := .venv/bin/python

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check . --exclude .venv

format:
	$(PYTHON) -m ruff format . --exclude .venv
	$(PYTHON) -m ruff check --fix . --exclude .venv

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +

run:
	$(PYTHON) run.py

coverage:
	$(PYTHON) -m pytest --cov-report=html
	open htmlcov/index.html
