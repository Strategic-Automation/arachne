"""Shared utilities for Arachne.

Keep this module small — only genuinely cross-cutting helpers belong here.
"""

import hashlib


def goal_hash(goal: str, length: int = 16) -> str:
    """Return a canonical short hash for a goal string.

    Used as the topology cache filename stem and for display IDs in the CLI.
    Normalises the goal before hashing so minor formatting differences
    (trailing punctuation, extra spaces, case) produce the same hash.

    Args:
        goal: The raw goal string.
        length: Number of hex characters to return (default 16).

    Returns:
        A hex string of the requested length.
    """
    clean = goal.lower().strip().rstrip(".").replace("  ", " ")
    return hashlib.sha256(clean.encode()).hexdigest()[:length]
