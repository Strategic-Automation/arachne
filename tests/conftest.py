"""Shared test fixtures and configuration."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Path:
    """Provide a temporary directory that cleans up after use."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture(autouse=True)
def dspy_settings(settings):
    """Configure DSPy with a mock LM for all tests."""
    import dspy

    class MockLM(dspy.LM):
        def __init__(self):
            super().__init__(model="test-model")
            self.history = []

        def __call__(self, prompt=None, **kwargs):
            self.history.append({"prompt": prompt, "kwargs": kwargs})
            return ["{}"]  # Return empty JSON string as a safe default for JSONAdapter

    lm = MockLM()
    dspy.settings.configure(lm=lm)
    yield


@pytest.fixture
def settings(tmp_path: Path):
    """Settings pointing to temporary directories."""
    from arachne.config import (
        CostSettings,
        LangfuseSettings,
        Settings,
    )

    return Settings(
        llm_backend="openrouter",
        llm_model="test-model",
        llm_api_key="test-key",
        llm_base_url="https://test.local/",
        llm_temperature=0.7,
        llm_max_tokens=1024,
        cost=CostSettings(default_max_usd=50.0, default_max_tokens=100_000),
        langfuse=LangfuseSettings(enabled=False),
    )
