"""OllamaManager -- handles local model existence checks and automatic pulling."""

import json
import logging
import time

import requests
from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, SpinnerColumn, TextColumn, TransferSpeedColumn

from arachne.config import Settings

logger = logging.getLogger(__name__)


def check_model_exists(settings: Settings) -> bool:
    """Check if the configured LLM model exists in the local Ollama instance."""
    base_url = settings.llm_base_url.rstrip("/")
    # litellm/ollama expects the raw name for the /api/tags check
    model_name = settings.llm_model

    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])

        # Check for both exact match and 'latest' tag normalization
        names = [m["name"] for m in models]
        return model_name in names or (":" not in model_name and f"{model_name}:latest" in names)
    except Exception as e:
        logger.warning(f"Failed to check Ollama models: {e}")
        return True  # Fallback: assume it exists to avoid blocking on transient API errors


def pull_model(settings: Settings) -> None:
    """Pull the missing model from Ollama with progress feedback."""
    console = Console()
    base_url = settings.llm_base_url.rstrip("/")
    model_name = settings.llm_model

    console.print(f"\n[bold cyan]Ollama[/bold cyan]: Model '[bold]{model_name}[/bold]' not found locally. Pulling...")

    try:
        # Start the pull request with streaming
        response = requests.post(
            f"{base_url}/api/pull",
            json={"name": model_name},
            stream=True,
            timeout=10,  # Initial connection timeout
        )
        response.raise_for_status()

        total_size = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Pulling {model_name}...", total=None)

            start_time = time.monotonic()
            dynamic_timeout = 600  # Default 10 minutes floor

            for line in response.iter_lines():
                if not line:
                    continue

                data = json.loads(line)
                status = data.get("status", "")

                # Extract total size to set dynamic timeout once it becomes available
                if "total" in data and total_size == 0:
                    total_size = data["total"]
                    progress.update(task, total=total_size)

                    # Formula: (GB * 120s) + 60s buffer
                    size_gb = total_size / (1024**3)
                    dynamic_timeout = int((size_gb * 120) + 60)
                    logger.info(f"Ollama pull: detected size {size_gb:.2f}GB. Setting timeout to {dynamic_timeout}s")

                completed = data.get("completed", 0)
                if completed:
                    progress.update(task, completed=completed, description=f"{status}")
                else:
                    progress.update(task, description=f"{status}")

                # Enforce dynamic timeout
                if time.monotonic() - start_time > dynamic_timeout:
                    raise TimeoutError(f"Ollama pull timed out after {dynamic_timeout}s for {model_name}")

        console.print(f"[green]✓[/green] Model '{model_name}' successfully pulled.")

    except Exception as e:
        console.print(f"[red]Error pulling model:[/red] {e}")
        console.print("[yellow]Hint: You can try pulling it manually via 'ollama pull {model_name}'[/yellow]")
        raise RuntimeError(f"Failed to provision LLM model: {e}") from e


def ensure_model_exists(settings: Settings) -> None:
    """Utility entry point: check and pull if missing."""
    if not check_model_exists(settings):
        pull_model(settings)
