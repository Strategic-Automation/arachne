"""Tests for config.py."""

import pytest

from arachne.config import (
    CostSettings,
    LangfuseSettings,
    Settings,
)


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all env vars that pydantic-settings might load."""
    for var in (
        "LLM_BACKEND",
        "LLM_MODEL",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_TEMPERATURE",
        "LLM_MAX_TOKENS",
        "LANGFUSE_ENABLED",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
    ):
        monkeypatch.delenv(var, raising=False)


class TestLangfuseSettings:
    def test_defaults(self, monkeypatch):
        _clear_env(monkeypatch)
        lf = LangfuseSettings()
        assert lf.enabled is False

    def test_custom(self):
        lf = LangfuseSettings(enabled=True, public_key="test")
        assert lf.enabled is True

    def test_sample_rate_bounds(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LangfuseSettings(sample_rate=-0.1)
        with pytest.raises(ValidationError):
            LangfuseSettings(sample_rate=1.1)


class TestCostSettings:
    def test_defaults(self):
        c = CostSettings()
        assert c.default_max_usd == 10.0


class TestSettings:
    def test_defaults(self, monkeypatch):
        _clear_env(monkeypatch)
        s = Settings(_env_file=None)
        assert s.llm_backend == "openrouter"
        assert s.llm_model == "qwen/qwen3.6-plus:free"
        assert s.llm_temperature == 0.7
        assert s.llm_max_tokens == 16384

    def test_dspy_lm_kwargs(self, monkeypatch):
        _clear_env(monkeypatch)
        s = Settings(_env_file=None, llm_api_key="test-key", llm_model="google/gemma-3-12b-it")
        kwargs = s.dspy_lm_kwargs
        assert kwargs["api_key"] == "test-key"
        assert kwargs["model"] == "openrouter/google/gemma-3-12b-it"

    def test_dspy_lm_kwargs_no_key(self, monkeypatch):
        _clear_env(monkeypatch)
        s = Settings(_env_file=None, llm_api_key="")
        assert s.dspy_lm_kwargs["api_key"] is None

    def test_setup_dirs(self):
        s = Settings(_env_file=None)
        s.setup_dirs()
