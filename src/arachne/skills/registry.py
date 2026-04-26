"""Skills registry — loads and injects markdown behavioral guidelines into nodes."""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_SKILL_DIRS: list[Path] = []
_METADATA_CACHE: dict[str, dict[str, Any]] = {}


def initialize(skill_dirs: list[str | Path]) -> None:
    """Register directories to scan for .md skill files. First one is the custom save target."""
    global _SKILL_DIRS
    _SKILL_DIRS = [Path(d) for d in skill_dirs]
    for d in _SKILL_DIRS:
        d.mkdir(parents=True, exist_ok=True)
    _refresh_cache()


def _refresh_cache() -> None:
    """Scan all directories and cache skill metadata for discovery."""
    global _METADATA_CACHE
    _METADATA_CACHE = {}
    # Strictly exclude common non-skill files
    excluded_names = {
        "DESCRIPTION.MD",
        "README.MD",
        "CHANGELOG.MD",
        "LICENSE.MD",
        "CONTRIBUTING.MD",
        "REFERENCE.MD",
    }

    for folder in _SKILL_DIRS:
        if not folder.exists():
            continue
        # Recursively find all .md files
        for item in folder.rglob("*.md"):
            name_upper = item.name.upper()
            if item.name.startswith("_") or name_upper in excluded_names:
                continue

            # Determine relative path as hierarchical name
            # Support BOTH folder/skill/SKILL.md and folder/skill.md
            if name_upper == "SKILL.MD":
                rel_path = item.parent.relative_to(folder)
            else:
                rel_path = item.relative_to(folder).with_suffix("")

            name = str(rel_path).replace("\\", "/")
            if not name or name == ".":
                continue

            try:
                content = item.read_text(encoding="utf-8")
                meta, _ = _parse_metadata(content)
                _METADATA_CACHE[name] = {
                    "path": item,
                    "description": meta.get("description", ""),
                    "metadata": meta,
                }
            except Exception as e:
                logger.warning("Failed to parse skill at %s: %s", item, e)


def _parse_metadata(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from a markdown string."""
    if not content.startswith("---"):
        return {}, content

    match = re.search(r"^---[\s\S]*?\n---", content)
    if not match:
        return {}, content

    yaml_block = match.group(0).strip("-").strip()
    body = content[match.end() :].strip()

    try:
        meta = yaml.safe_load(yaml_block)
        if isinstance(meta, dict):
            return meta, body
    except Exception:
        pass
    return {}, content


def get(name: str) -> str | None:
    """Get the content of a skill by hierarchical name."""
    # 1. Check cache first
    entry = _METADATA_CACHE.get(name)
    if entry:
        path = entry["path"]
        if path.exists():
            return path.read_text(encoding="utf-8").strip()

    # 2. Fallback scan if cache missed (e.g. newly added file)
    for folder in _SKILL_DIRS:
        # Try exact hierarchical path matches
        # Pattern A: path/to/skill.md
        candidate_a = folder / f"{name}.md"
        if candidate_a.exists():
            return candidate_a.read_text(encoding="utf-8").strip()

        # Pattern B: path/to/skill/SKILL.md
        candidate_b = folder / name / "SKILL.md"
        if candidate_b.exists():
            return candidate_b.read_text(encoding="utf-8").strip()

        # Pattern C: sanitize snake_case in path components (backward compat)
        safe_name = name.replace("-", "_")
        candidate_c = folder / f"{safe_name}.md"
        if candidate_c.exists():
            return candidate_c.read_text(encoding="utf-8").strip()

    return None


def list_available(with_descriptions: bool = False) -> list[str] | dict[str, str]:
    """List all skill names (relative paths)."""
    if not _METADATA_CACHE:
        _refresh_cache()

    if with_descriptions:
        return {name: info["description"] for name, info in _METADATA_CACHE.items()}
    return sorted(_METADATA_CACHE.keys())


def search(query: str) -> dict[str, str]:
    """Search for skills matching a query string in name or description.

    Returns:
        Dictionary of {skill_name: description}
    """
    if not _METADATA_CACHE:
        _refresh_cache()

    query = query.lower()
    results = {}
    for name, info in _METADATA_CACHE.items():
        if query in name.lower() or query in info["description"].lower():
            results[name] = info["description"]
    return results


def get_metadata(name: str) -> dict[str, Any] | None:
    """Get full metadata for a specific skill."""
    if not _METADATA_CACHE:
        _refresh_cache()
    return _METADATA_CACHE.get(name)


def exists(name: str) -> bool:
    """Check if a skill with this name already exists."""
    return name in _METADATA_CACHE or get(name) is not None


def save(name: str, content: str) -> Path:
    """Persist a new skill in the custom directory. Supports nested names."""
    custom_dir = _SKILL_DIRS[-1] if _SKILL_DIRS else Path("skills")
    # If name is 'research/results', save to skills/research/results.md
    target = custom_dir / f"{name}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _refresh_cache()
    return target
