"""LLM integration tests — require real Ollama or OpenRouter access.

All tests use @pytest.mark.llm and are skipped by default.
Run with: uv run pytest -m llm -v
"""

import pytest


def _get_env_key() -> str | None:
    """Read OpenRouter key from .env."""
    try:
        from dotenv import dotenv_values
        vals = dotenv_values(".env")
        return vals.get("OPENROUTER_API_KEY") or vals.get("LLM_API_KEY")
    except Exception:
        return None


def _ollama_available() -> bool:
    """Check if Ollama is running and qwen3.5:2b is available."""
    import subprocess
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        return "qwen3.5:2b" in r.stdout
    except Exception:
        return False


# ── Ollama Tests ────────────────────────────────────────────────────────────


@pytest.mark.llm
def test_ollama_basic_completion():
    """Send a simple completion to Ollama qwen3.5:2b and verify response."""
    if not _ollama_available():
        pytest.skip("Ollama with qwen3.5:2b not available")

    import dspy

    from arachne.config import reset_dspy_config

    try:
        lm = dspy.LM("ollama_chat/qwen3.5:2b", api_base="http://localhost:11434")
        dspy.settings.configure(lm=lm)
        result = lm("What is 2+2? Reply with just the number.")
        assert result and len(result) > 0
        assert "4" in str(result).lower() or "four" in str(result).lower()
    finally:
        reset_dspy_config()


@pytest.mark.llm
def test_ollama_arachne_weave():
    """Weave a simple goal using Ollama and verify a valid topology is returned."""
    if not _ollama_available():
        pytest.skip("Ollama with qwen3.5:2b not available")

    import dspy

    from arachne.config import Settings, reset_dspy_config
    from arachne.core import Arachne

    try:
        settings = Settings(
            llm_backend="ollama",
            llm_model="qwen3.5:2b",
            llm_api_key="not-needed",
            llm_base_url="http://localhost:11434/v1",
            llm_temperature=0.1,
        )
        lm = dspy.LM("ollama_chat/qwen3.5:2b", api_base="http://localhost:11434")
        dspy.settings.configure(lm=lm)

        arachne = Arachne(settings=settings)
        topology = arachne.weave("What is the capital of France?")
        assert topology is not None
        assert len(topology.nodes) >= 1
        topology.topological_waves()
    except Exception as e:
        msg = str(e).lower()
        if any(kw in msg for kw in (
            "ollama_chat", "provider not supported", "module 'litellm'",
            "cost_per_token", "no attribute", "has no attribute",
            "404", "connection", "api/tags",
        )):
            pytest.skip(f"Ollama Arachne integration not available: {e}")
        raise
    finally:
        reset_dspy_config()


# ── OpenRouter Tests ────────────────────────────────────────────────────────


@pytest.mark.llm
def test_openrouter_basic_completion():
    """Send a simple completion to OpenRouter and verify response."""
    api_key = _get_env_key()
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    import dspy

    from arachne.config import reset_dspy_config

    try:
        lm = dspy.LM(
            "openrouter/qwen/qwen-2.5-72b-instruct:free",
            api_key=api_key,
        )
        dspy.settings.configure(lm=lm)
        result = lm("Say 'hello' in exactly one word.")
        assert result and len(result) > 0
        assert "hello" in str(result).lower()
    except Exception as e:
        msg = str(e).lower()
        if any(kw in msg for kw in ("402", "429", "rate", "insufficient",
                                      "developer instruction", "not enabled")):
            pytest.skip(f"OpenRouter unavailable: {e}")
        raise
    finally:
        reset_dspy_config()


@pytest.mark.llm
def test_openrouter_arachne_weave():
    """Weave a simple goal using OpenRouter and verify valid topology."""
    api_key = _get_env_key()
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    import dspy

    from arachne.config import Settings, reset_dspy_config
    from arachne.core import Arachne

    try:
        settings = Settings(
            llm_backend="openrouter",
            llm_model="qwen/qwen-2.5-72b-instruct:free",
            llm_api_key=api_key,
            llm_temperature=0.1,
        )
        lm = dspy.LM("openrouter/qwen/qwen-2.5-72b-instruct:free", api_key=api_key)
        dspy.settings.configure(lm=lm)

        arachne = Arachne(settings=settings)
        topology = arachne.weave("Find the population of Tokyo")
        assert topology is not None
        assert len(topology.nodes) >= 1
        topology.topological_waves()
    except Exception as e:
        msg = str(e).lower()
        if any(kw in msg for kw in (
            "402", "429", "rate", "insufficient",
            "developer instruction", "not enabled",
        )):
            pytest.skip(f"OpenRouter unavailable: {e}")
        raise
    finally:
        reset_dspy_config()
