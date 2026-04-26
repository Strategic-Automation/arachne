"""Long-term memory tools — Arachne agents can learn from past runs."""

import json
import time
from pathlib import Path

_MEMORY_DIR = Path.home() / ".local" / "share" / "arachne" / "memory"


def write_memory(entry: str, tags: list[str] | None = None, metadata: dict | None = None) -> str:
    """Append a memory entry for future retrieval."""
    _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": time.time(),
        "entry": entry,
        "tags": tags or [],
        "metadata": metadata or {},
    }
    lines_file = _MEMORY_DIR / "entries.jsonl"
    with open(lines_file, "a") as f:
        f.write(json.dumps(record) + "\n")
    return f"Memory entry saved ({len(tags or [])} tags)."


def search_memory(query: str, tag: str | None = None, limit: int = 5) -> str:
    """Search past memory entries for relevant lessons or context."""
    lines_file = _MEMORY_DIR / "entries.jsonl"
    if not lines_file.exists():
        return "No memory entries found."

    results = []
    with open(lines_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if tag and tag not in record.get("tags", []):
                continue

            q_lower = query.lower()
            entry_text = record.get("entry", "").lower()
            tags_text = " ".join(record.get("tags", [])).lower()
            meta_text = json.dumps(record.get("metadata", {})).lower()
            if q_lower in entry_text or q_lower in tags_text or q_lower in meta_text:
                results.append(record)
            if len(results) >= limit * 3:
                break

    results.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
    results = results[:limit]

    if not results:
        return f"No memory entries matching query '{query}'." + (f" with tag '{tag}'" if tag else "")

    lines = [f"Memory search results ({len(results)} found):"]
    for i, r in enumerate(results, 1):
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.get("timestamp", 0)))
        lines.append(f"\n--- Result {i} ({ts}) ---")
        lines.append(f"Tags: {', '.join(r.get('tags', [])) or '(none)'}")
        lines.append(r["entry"])
    return "\n".join(lines)


def clear_memory() -> str:
    """Clear all memory entries."""
    lines_file = _MEMORY_DIR / "entries.jsonl"
    if lines_file.exists():
        lines_file.unlink()
        return "All memory entries cleared."
    return "No memory entries to clear."
