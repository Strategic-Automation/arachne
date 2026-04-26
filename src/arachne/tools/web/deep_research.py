"""Deep research tool using browser-use for autonomous navigation."""

import contextlib
import os
import shutil
import tempfile
import time

import dspy
from pydantic import BaseModel, Field
from rich.console import Console

from arachne.config import Settings
from arachne.tools.web._browser_logging import suppress_browser_logs
from arachne.tools.web._langfuse_telemetry import create_langfuse_callbacks

# Suppress noisy third-party logs BEFORE importing browser_use (creates loggers on import)
suppress_browser_logs()

from browser_use import Agent, Browser, ChatOpenAI  # noqa: E402


class DeepResearchInput(BaseModel):
    """Input for deep research."""

    task: str = Field(
        description="The specific research task (e.g. 'Find the pricing page for X and summarize the plans')."
    )
    max_steps: int = Field(default=10, description="Maximum number of browser steps to take (default 10).")
    prior_findings: str = Field(
        default="",
        description=(
            "Summary of findings already discovered by earlier research steps. "
            "The agent will focus on NEW information and avoid repeating these searches."
        ),
    )


# ---------------------------------------------------------------------------
# Helper functions — each handles one concern
# ---------------------------------------------------------------------------


def _resolve_api_key(settings: Settings) -> tuple[str, str] | str:
    """Resolve browser LLM credentials from settings / env.

    Returns ``(api_key, base_url)`` on success, or an error message string on failure.
    """
    api_key_secret = settings.browser_llm_api_key or settings.llm_api_key
    api_key = api_key_secret.get_secret_value() if api_key_secret else None
    if not api_key:
        api_key = os.getenv("BROWSER_LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")

    base_url = str(settings.browser_llm_base_url or settings.llm_base_url)

    if not api_key:
        return (
            "Error: No API key found for deep research. "
            "Set BROWSER_LLM_API_KEY, OPENROUTER_API_KEY, or OPENAI_API_KEY in .env."
        )
    return api_key, base_url


def _create_llms(
    api_key: str,
    base_url: str,
    settings: Settings,
) -> tuple[ChatOpenAI, ChatOpenAI]:
    """Build primary + fallback LLM instances."""
    model_name = settings.browser_llm_model or settings.llm_model

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,
        seed=42,
    )

    fallback_model = settings.browser_llm_fallback_model or model_name
    fallback_llm = ChatOpenAI(
        model=fallback_model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,
        seed=42,
    )
    return llm, fallback_llm


def _enhance_task(task: str, prior_findings: str) -> str:
    """Inject prior findings into the task to avoid duplicate searches."""
    if not prior_findings or not prior_findings.strip():
        return task
    return (
        f"{task}\n\n"
        f"IMPORTANT — The following information has ALREADY been found by earlier research. "
        f"Do NOT search for any of this again. Focus ONLY on finding NEW, undiscovered information:\n\n"
        f"{prior_findings[:3000]}"
    )


def _build_compaction():
    """Configure aggressive message compaction to keep agent context lean."""
    try:
        from browser_use.agent.views import MessageCompactionSettings

        return MessageCompactionSettings(
            enabled=True,
            compact_every_n_steps=5,
            keep_last_items=4,
        )
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------


@dspy.Tool
async def deep_research_async(task: str, max_steps: int = 10, prior_findings: str = "", **_kwargs) -> str:
    """Perform autonomous deep research using a web browser.

    The agent will search, click, navigate, and extract information until the task is complete.
    Use this for complex tasks that require navigating multiple pages or finding specific data points
    that a standard search doesn't reveal immediately.

    Args:
        task: The research task description.
        max_steps: Maximum browser steps (default 10, reduced from 20 for speed).
        prior_findings: Summary of already-known results to avoid duplicate searching.
    """
    console = Console()
    console.print(f'    [magenta]🤖 Launching Deep Research Agent:[/magenta] [bold]"{task[:80]}..."[/bold]')

    start_time = time.monotonic()
    settings = Settings()

    # Resolve API credentials
    creds = _resolve_api_key(settings)
    if isinstance(creds, str):
        return creds  # error message
    api_key, base_url = creds

    # Build LLMs and enhanced task
    llm, fallback_llm = _create_llms(api_key, base_url, settings)
    enhanced_task = _enhance_task(task, prior_findings)

    # Langfuse observability callbacks
    step_cb, done_cb = create_langfuse_callbacks(task, settings)

    # Temp dir for conversation logs (cleaned up after run)
    conv_temp_dir = tempfile.mkdtemp(prefix="arachne_dr_")
    compaction = _build_compaction()

    # Suppress all stdout/stderr from browser_use during browser operations
    with contextlib.redirect_stdout(None), contextlib.redirect_stderr(None):
        browser = Browser(headless=True)
        agent = Agent(
            task=enhanced_task,
            llm=llm,
            fallback_llm=fallback_llm,
            browser=browser,
            max_failures=3,
            use_thinking=True,
            register_new_step_callback=step_cb,
            register_done_callback=done_cb,
            generate_gif=False,
            save_conversation_path=conv_temp_dir,
            demo_mode=False,
            max_history_items=30,
            message_compaction_settings=compaction,
        )

        try:
            result = await agent.run(max_steps=max_steps)
            elapsed = time.monotonic() - start_time
            final_result = result.final_result()

            if final_result:
                output = f"Deep Research Result:\n{final_result}"
            else:
                output = "Deep research completed but no specific final result was returned. Check the logs."

            # Persist to session memory so healing/retry can reuse findings
            from arachne.runtime.search_memory import record_search

            record_search("deep_research_async", task, output)

            console.print(f"    [green]✓ Deep research finished[/green] in {elapsed:.1f}s ({len(output):,} chars)")
            return output
        except Exception as e:
            elapsed = time.monotonic() - start_time
            error_msg = f"Deep research failed after {elapsed:.1f}s for task '{task[:60]}': {e}"

            # Record the failure so the healer knows this was attempted
            from arachne.runtime.search_memory import record_search

            record_search("deep_research_async", task, error_msg)

            return error_msg
        finally:
            with contextlib.suppress(Exception):
                await browser.close()
            with contextlib.suppress(Exception):
                shutil.rmtree(conv_temp_dir, ignore_errors=True)
