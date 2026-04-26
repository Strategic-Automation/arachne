.PHONY: help lint format check test test-integration install-hooks

help:
	@echo "Arachne Development Helper"
	@echo ""
	@echo "Available targets:"
	@echo "  make help              Show this help message"
	@echo "  make lint              Run ruff check --fix + format"
	@echo "  make format            Run ruff format only"
	@echo "  make check             CI-safe validation (no auto-fix)"
	@echo "  make test              Run pytest with markers"
	@echo "  make test-integration  Live tests requiring API credentials"
	@echo "  make install-hooks     Install pre-commit hooks"

lint:
	uv run ruff check --fix .
	uv run ruff format .

format:
	uv run ruff format .

check:
	uv run ruff check .

test:
	uv run pytest

test-integration:
	uv run pytest -m integration

install-hooks:
	uv run pre-commit install
	uv run pre-commit autoupdate