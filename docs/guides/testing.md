---
type: guide
description: How to run tests, configure pytest, and write testable code
---

# Testing Guide

This guide covers running tests and configuring pytest for Arachne development.

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_config.py

# Run with verbose output
uv run pytest -v
```

## Test Configuration

Tests are configured in `pyproject.toml`. The project maintains >80% coverage.

## Writing Tests

- Use descriptive test names: `test_web_search_returns_empty_string_on_no_results`
- Mock external APIs and LLM calls
- Use `pytest.mark.asyncio` decorator for async tests

## Coverage Report

```bash
uv run pytest --cov=src/arachne --cov-report=term-missing
```

## Linting Tests

```bash
uv run ruff check tests/
uv run ruff format tests/
```