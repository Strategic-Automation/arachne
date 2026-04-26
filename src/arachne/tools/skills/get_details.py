"""Get skill details."""

from arachne.skills import registry as skill_registry


def get_skill_details(name: str) -> str:
    """Retrieve the full protocol/instructions for a specific skill."""
    content = skill_registry.get(name)
    if not content:
        return f"Skill '{name}' not found. Use search_skills to find valid names."
    return content
