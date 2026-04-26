import uuid
from collections.abc import Callable
from functools import wraps

import dspy

from arachne.config import Settings
from arachne.sessions.manager import active_session_path

SPILLOVER_THRESHOLD = 32000  # 32KB characters threshold (~8k tokens)


def with_spillover(tool_name: str, fn: Callable) -> Callable:
    """Wraps a tool function to intercept massive payloads and apply the pointer pattern.

    If fn is a dspy.Tool, it unwraps it to get the underlying function to preserve signature.
    """
    import asyncio
    import concurrent.futures

    actual_fn = fn
    if isinstance(fn, dspy.Tool):
        actual_fn = fn.func

    is_coro = asyncio.iscoroutinefunction(actual_fn)

    @wraps(actual_fn)
    def sync_wrapper(*args, **kwargs) -> str:
        # ReAct calls this synchronously. If we are in an event loop,
        # we must use a thread pool to run asyncio.run()
        if is_coro:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, actual_fn(*args, **kwargs))
                    result = future.result()
            else:
                result = asyncio.run(actual_fn(*args, **kwargs))
        else:
            result = actual_fn(*args, **kwargs)

        return _handle_spillover(tool_name, str(result))

    return sync_wrapper


def _handle_spillover(tool_name: str, result_str: str) -> str:
    """Detects large results, truncates dynamically, and writes real content to disk."""
    if len(result_str) > SPILLOVER_THRESHOLD:
        settings = Settings()

        # Use per-session spillover directory if a session is active
        sess_path = active_session_path.get()
        spillover_dir = sess_path / "spillover" if sess_path else settings.session.directory / "spillover"

        spillover_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{tool_name}_{uuid.uuid4().hex[:6]}.txt"
        filepath = spillover_dir / filename

        with open(filepath, "w", encoding="utf-8", errors="replace") as f:
            f.write(result_str)

        preview = result_str[:4000]
        pointer = (
            f"\n\n[Result from {tool_name}: {len(result_str)} chars — "
            f"too large for context window, full output saved to '{filepath}'. "
            f"Use read_file({filepath}) to read the full result if needed.]"
        )
        return preview + pointer

    return result_str
