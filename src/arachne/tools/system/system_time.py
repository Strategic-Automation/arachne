"""System time and date utilities for the agent."""

import datetime
from zoneinfo import ZoneInfo


def get_current_time(timezone_name: str = "UTC") -> str:
    """Get the current time and date in the specified timezone.

    Args:
        timezone_name: The IANA time zone string (e.g., "UTC", "Europe/London", "America/New_York").
                       Defaults to "UTC".

    Returns:
        A human-readable string with the current date and time.
    """
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        return f"Error: Invalid timezone '{timezone_name}'. Use IANA names like 'UTC' or 'Europe/London'."

    now = datetime.datetime.now(tz)
    return now.strftime("Current Date and Time: %A, %B %d, %Y at %I:%M:%S %p %Z")
