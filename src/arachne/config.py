"""Core config -- pydantic-settings based."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class LangfuseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANGFUSE_", extra="ignore")
    enabled: bool = False
    public_key: str | None = ""
    secret_key: SecretStr = SecretStr("")
    host: str = "https://cloud.langfuse.com"
    sample_rate: float = Field(1.0, ge=0.0, le=1.0)

    @classmethod
    def from_flat_env(cls) -> LangfuseSettings:
        import os

        def _get_bool(key: str, default: bool) -> bool:
            val = os.environ.get(key)
            if val is None:
                return default
            return val.lower() in ("true", "1", "yes")

        return cls(
            enabled=_get_bool("LANGFUSE_ENABLED", False),
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=SecretStr(os.environ.get("LANGFUSE_SECRET_KEY", "")),
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )


class CostSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARACHNE_COST_", extra="ignore")
    default_max_usd: float = 10.0
    default_max_tokens: int = 500_000


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARACHNE_MCP_", extra="ignore")
    enabled: bool = True
    servers: dict[str, Any] = Field(default_factory=dict)


class SessionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARACHNE_SESSION_", extra="ignore")
    directory: Path = Path.home() / ".local" / "share" / "arachne" / "sessions"


class SkillSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARACHNE_SKILL_", extra="ignore")
    directory: Path = Path.home() / ".local" / "share" / "arachne" / "skills"


class ToolSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARACHNE_TOOL_", extra="ignore")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    llm_backend: str = "openrouter"
    llm_model: str = "qwen/qwen3.6-plus:free"
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = "https://openrouter.ai/api/v1/"
    llm_temperature: float = Field(0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = 16384
    llm_context_limit: int = Field(131072, description="Mandatory limit for total tokens (input + output)")
    llm_stability_floor: int = Field(4096, description="Headroom reserved for model output to prevent truncation")
    llm_max_output: int | None = Field(None, description="Physical model limit for completion tokens (if known)")
    llm_cache: bool = Field(
        False, description="Enable DSPy on-disk LM response cache. Off by default to prevent stale cache hits."
    )
    node_timeout: int = Field(300, description="Default timeout for individual node execution in seconds")

    # RLM (Recursive Language Model) settings
    rlm_sub_llm_model: str | None = Field(
        None,
        description="Model for RLM sub-LLM calls. Defaults to main llm_model if not set.",
    )
    rlm_require_deno: bool = Field(
        True,
        description="If True, prevent RLM nodes from executing when Deno is not installed",
    )

    # Browser-specific LLM settings (decoupled from main model)
    browser_llm_model: str | None = Field(
        None,
        description="Dedicated model for browser-based agents (e.g. browser-use). Falls back to llm_model if None.",
    )
    browser_llm_api_key: SecretStr | None = Field(
        None,
        description="API key for browser LLM. Falls back to llm_api_key if None.",
    )
    browser_llm_base_url: str | None = Field(
        None,
        description="Base URL for browser LLM. Falls back to llm_base_url if None.",
    )
    browser_llm_backend: str | None = Field(
        None,
        description="Backend provider for browser LLM. Falls back to llm_backend if None.",
    )
    browser_llm_temperature: float = Field(
        0.3,
        ge=0.0,
        le=2.0,
        description="Temperature for browser-based LLM calls (deep research, etc.). Lower than main LLM for more deterministic outputs.",
    )
    browser_llm_fallback_model: str | None = Field(
        None,
        description="Separate fallback model for JSON parsing failures. Falls back to browser_llm_model if None.",
    )

    # Web Search API Keys
    jina_api_key: SecretStr | None = Field(
        None,
        description="API key for Jina Search (s.jina.ai). Required for full results.",
    )
    serpapi_api_key: str | None = Field(
        None,
        description="API key for SerpApi (Google search results).",
    )

    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings.from_flat_env)
    cost: CostSettings = Field(default_factory=CostSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    skill: SkillSettings = Field(default_factory=SkillSettings)
    tool: ToolSettings = Field(default_factory=ToolSettings)

    weave_temperature: float = Field(0.1, ge=0.0, le=2.0)
    weave_n: int = Field(2, ge=1, le=10)
    weave_threshold: float = Field(0.5, ge=0.0, le=1.0)

    # Weaver BootstrapFewShot compiler settings (used by `arachne compile-weaver`)
    weaver_teacher_model: str | None = Field(
        "deepseek/deepseek-v4-flash",
        description="Teacher model for bootstrapping demos. Defaults to deepseek/deepseek-v4-flash.",
    )
    weaver_max_demos: int = Field(
        4, ge=1, le=16, description="Maximum number of bootstrapped demonstrations for the weaver."
    )

    @property
    def dspy_lm_kwargs(self) -> dict:
        key = self.llm_api_key.get_secret_value()
        model = self.llm_model

        # Ensure model is prefixed with provider for litellm compatibility
        if self.llm_backend and not model.startswith(f"{self.llm_backend}/"):
            model = f"{self.llm_backend}/{model}"

        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": key or None,
            "api_base": self.llm_base_url or None,
            "max_tokens": self.llm_max_tokens,
            "temperature": self.llm_temperature,
            "cache": self.llm_cache,
        }

        if self.llm_backend == "openrouter":
            kwargs["extra_body"] = {"plugins": [{"id": "context-compression"}]}

        return kwargs

    def setup_langfuse(self: Settings) -> None:
        """Initialize Langfuse observability if keys are present."""
        import os

        lf = self.langfuse
        if not lf.enabled:
            return

        os.environ["LANGFUSE_SECRET_KEY"] = lf.secret_key.get_secret_value()
        os.environ["LANGFUSE_PUBLIC_KEY"] = lf.public_key
        os.environ["LANGFUSE_BASE_URL"] = lf.host

        try:
            from langfuse import get_client
            from openinference.instrumentation.dspy import DSPyInstrumentor

            if hasattr(DSPyInstrumentor, "_is_instrumented_by_arachne"):
                return

            get_client()

            DSPyInstrumentor().instrument()
            DSPyInstrumentor._is_instrumented_by_arachne = True

            import atexit

            atexit.register(get_client().flush)
        except Exception:
            logger.debug("Langfuse instrumentation skipped (library not installed or misconfigured)", exc_info=True)

    def setup_dirs(self) -> None:
        """Create required directories."""
        pass

    def ensure_ready(self) -> None:
        """Complete all provisioning, directory setup, and model checks."""
        # 1. Setup Langfuse if enabled
        self.setup_langfuse()

        # 2. Setup Ollama model check
        if self.llm_backend == "ollama":
            from arachne.runtime.ollama_manager import ensure_model_exists

            ensure_model_exists(self)

    @classmethod
    def from_yaml(cls, yaml_path: Settings | str | Path | None = None) -> Settings:
        if yaml_path is not None:
            yaml_path = Path(yaml_path)
        else:
            cwd_yaml = Path.cwd() / "arachne.yaml"
            user_yaml = Path.home() / ".arachne" / "config.yaml"
            yaml_path = cwd_yaml if cwd_yaml.exists() else (user_yaml if user_yaml.exists() else None)

        # Base settings loaded from .env/environment (pydantic-settings auto-loads .env)
        settings = cls()

        if yaml_path is None or not yaml_path.exists():
            return settings

        data: dict[str, Any] = yaml.safe_load(yaml_path.read_text()) or {}

        import os

        from dotenv import dotenv_values

        env_vars = {k.lower(): v for k, v in os.environ.items()}
        dotenv_vars = {k.lower(): v for k, v in dotenv_values(".env").items()}

        # Warn about conflicts: YAML values that are also set in env/.env are ignored
        _conflict_fields = []
        for field in cls.model_fields:
            if field in data and field in env_vars:
                _conflict_fields.append(field)
        if _conflict_fields:
            import warnings

            warnings.warn(
                f"Configuration conflict: These fields are set in both {yaml_path} and environment/.env. "
                f"Environment variables take precedence: {_conflict_fields}. "
                f"Consider moving non-secret values to {yaml_path} and keep .env for secrets/overrides only.",
                stacklevel=2,
            )

        # Merge YAML data only if not already set by environment variables or .env.
        # This ensures .env/os.environ takes precedence.
        for field in cls.model_fields:
            if (
                field in data
                and field not in ("langfuse", "cost", "mcp", "session", "skill", "tool")
                and field not in env_vars
                and field not in dotenv_vars
            ):
                setattr(settings, field, data[field])

        # Handle nested settings (merging instead of overwriting)
        if "langfuse" in data and isinstance(data["langfuse"], dict):
            lf_data = data["langfuse"]
            for k, v in lf_data.items():
                env_key = f"langfuse_{k.lower()}"
                if env_key not in env_vars and env_key not in dotenv_vars and v is not None:
                    setattr(settings.langfuse, k, v)

        # Special case: reload from environment just in case to ensure absolute priority
        settings.langfuse = LangfuseSettings.from_flat_env() if "LANGFUSE_ENABLED" in os.environ else settings.langfuse

        return settings

    def to_yaml(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump(mode="json")
        data["llm_api_key"] = "[REDACTED]"
        if "langfuse" in data and isinstance(data["langfuse"], dict):
            data["langfuse"]["secret_key"] = "[REDACTED]"
        with p.open("w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def get_context_limit(model_name: str, settings: Settings) -> tuple[int, str]:
    """Auto-detect context limit from model name or litellm mapping."""
    import os

    import litellm

    # 0. Check for explicit environment variable override
    if os.environ.get("ARACHNE_LLM_CONTEXT_LIMIT"):
        return int(os.environ["ARACHNE_LLM_CONTEXT_LIMIT"]), "Environment Override"

    try:
        clean_name = model_name
        if "/" in model_name:
            parts = model_name.split("/")
            if len(parts) > 2:
                clean_name = "/".join(parts[1:])

        limit = litellm.get_max_tokens(clean_name)
        if not limit and "/" in model_name:
            limit = litellm.get_max_tokens(model_name)

        if limit and isinstance(limit, int):
            return limit, "LiteLLM Mapping"
    except Exception:
        pass

    m = model_name.lower()

    if any(keyword in m for keyword in ["128k", "131k", "nitro", "oss-20b", "qwen", "llama-3.1", "gpt-4-turbo"]):
        return 131072, "Heuristic Keyword"

    if "64k" in m:
        return 65536, "Heuristic Keyword"
    if "32k" in m:
        return 32768, "Heuristic Keyword"

    if "16k" in m or "gpt-3.5-turbo-0125" in m:
        return 16384, "Heuristic Keyword"

    if "8k" in m or "llama-3" in m:
        return 8192, "Heuristic Keyword"

    return settings.llm_context_limit, "Config Default"


def get_model_limits(model_name: str, settings: Settings) -> Any:
    """Resolve full ModelLimits (context window + max output + capabilities) for a given model/backend."""
    from arachne.runtime.token_manager import ModelLimits, fetch_ollama_limits, fetch_openrouter_limits

    # 1. Start with configured/detected context limit
    ctx_limit, ctx_source = get_context_limit(model_name, settings)
    limits = ModelLimits(
        context_window=ctx_limit,
        max_output=settings.llm_max_output or 4096,
        stability_floor=settings.llm_stability_floor,
        source=ctx_source,
    )

    # 2. Attempt high-fidelity detection based on backend
    detected = None
    if settings.llm_backend == "openrouter":
        detected = fetch_openrouter_limits(model_name)
        if detected:
            limits.source = "API (OpenRouter)"
    elif settings.llm_backend == "ollama":
        detected = fetch_ollama_limits(model_name, settings.llm_base_url)
        if detected:
            limits.source = "API (Ollama)"

    if detected:
        # Patch limits with detected values if they are more specific
        limits.context_window = detected.context_window
        if detected.max_output:
            limits.max_output = detected.max_output
        if detected.supports_function_calling is not None:
            limits.supports_function_calling = detected.supports_function_calling
        if detected.supports_structured_output is not None:
            limits.supports_structured_output = detected.supports_structured_output

    return limits


def check_deno_installed() -> bool:
    """Check if Deno is installed and available in PATH."""
    import shutil

    return shutil.which("deno") is not None


def get_rlm_sub_lm_kwargs(settings: Settings) -> dict[str, Any]:
    """Get LM kwargs configured for RLM sub-LLM. Uses rlm_sub_llm_model if set, otherwise falls back to main llm_model."""
    key = settings.llm_api_key.get_secret_value()
    model = settings.rlm_sub_llm_model or settings.llm_model

    # Ensure model is prefixed with provider
    if settings.llm_backend and not model.startswith(f"{settings.llm_backend}/"):
        model = f"{settings.llm_backend}/{model}"

    return {
        "model": model,
        "api_key": key or None,
        "api_base": settings.llm_base_url or None,
        "max_tokens": 4096,
        "temperature": settings.llm_temperature,
        "cache": settings.llm_cache,
    }


# ---------------------------------------------------------------------------
# Centralized DSPy configuration
# ---------------------------------------------------------------------------
# Tracks whether dspy.configure() has been called in this process,
# preventing the dual-configure race between CLI and core.
_DSPY_CONFIGURED: bool = False


def configure_dspy(settings: Settings) -> Any:
    """Configure DSPy exactly once per process.

    This is the *only* place that should call ``dspy.configure()``.
    Both the CLI and ``Arachne.__init__()`` must delegate here so that
    adapter / LM settings are applied consistently.

    Returns the resolved ``ModelLimits`` for caller convenience.
    """
    import dspy

    global _DSPY_CONFIGURED
    if _DSPY_CONFIGURED:
        logger.debug("dspy.configure() already called — skipping")
        return get_model_limits(settings.llm_model, settings)

    limits = get_model_limits(settings.llm_model, settings)

    lm = dspy.LM(**settings.dspy_lm_kwargs)

    adapter: dspy.Adapter
    if limits.supports_function_calling:
        adapter = dspy.ChatAdapter(use_native_function_calling=True)
    else:
        adapter = dspy.ChatAdapter()

    dspy.configure(
        lm=lm,
        adapter=adapter,
        allow_tool_async_sync_conversion=True,
    )

    _DSPY_CONFIGURED = True
    logger.debug(
        "DSPy configured: model=%s, adapter=%s, function_calling=%s",
        settings.llm_model,
        type(adapter).__name__,
        limits.supports_function_calling,
    )
    return limits


def reset_dspy_config() -> None:
    """Allow re-configuration (useful in tests)."""
    global _DSPY_CONFIGURED
    _DSPY_CONFIGURED = False
