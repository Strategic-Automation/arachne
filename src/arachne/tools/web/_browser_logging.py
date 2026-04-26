"""Shared logging suppression for browser-use and its dependencies.

Call `suppress_browser_logs()` once at module import time in any tool that
uses browser_use, playwright, or related libraries.  CRITICAL level ensures
only truly catastrophic messages appear (rare).
"""

import logging

_NOISY_LOGGERS: list[str] = [
    # browser-use internals
    "browser_use",
    "browser_use.agent",
    "browser_use.browser",
    "browser_use.tools",
    "browser_use.dom",
    "browser_use.llm",
    "Agent",
    "BrowserSession",
    "bubus",
    # CDP / Chrome DevTools Protocol
    "cdp_use",
    "cdp_use.client",
    "cdp_use.cdp",
    "cdp_use.cdp.registry",
    # Networking
    "websockets",
    "websockets.client",
    "httpcore",
    "httpx",
    "urllib3",
    # Browser automation
    "playwright",
    "playwright.async_api",
    # Imaging
    "PIL",
    # Observability
    "langfuse",
]


def suppress_browser_logs() -> None:
    """Suppress all third-party logging from browser-use and its deps."""
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.CRITICAL)
