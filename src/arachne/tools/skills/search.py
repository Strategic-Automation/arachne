"""Search skills."""

from arachne.skills import registry as skill_registry


def search_skills(query: str) -> str:
    """Search for behavioral skills matching a keyword."""
    results = skill_registry.search(query)
    if not results:
        return f"No skills found matching '{query}'. Try a broader category"

    output = [f"Found {len(results)} matching skills:"]
    for name, desc in results.items():
        output.append(f"- {name}: {desc}")

    return "\n".join(output)
