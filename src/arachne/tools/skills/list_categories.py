"""List skill categories."""

from arachne.skills import registry as skill_registry


def list_skill_categories() -> str:
    """List high-level skill categories available in the library."""
    skills = skill_registry.list_available()
    categories = set()
    for s in skills:
        parts = s.split("/")
        if len(parts) > 1:
            categories.add(parts[0])

    if not categories:
        return "No hierarchical skill categories found."

    return "Available Categories: " + ", ".join(sorted(categories))
