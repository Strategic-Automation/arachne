"""Persistent Knowledge Store for Arachne."""

import time

from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    key: str
    value: str | dict
    source: str = "agent"
    timestamp: float = Field(default_factory=lambda: time.time())


class KnowledgeStore(BaseModel):
    """Stores facts, answers, and results across the agent's lifetime."""

    facts: list[KnowledgeEntry] = Field(default_factory=list)

    def add(self, key: str, value: str | dict, source: str = "agent") -> None:
        """Add a piece of knowledge."""
        # Remove duplicates based on content to prevent bloat
        existing = [e for e in self.facts if e.key == key and str(e.value) == str(value)]
        if existing:
            return
        self.facts.append(KnowledgeEntry(key=key, value=value, source=source))

    def get(self, key: str) -> str | dict | None:
        """Get the most recent value for a key."""
        for entry in reversed(self.facts):
            if entry.key == key:
                return entry.value
        return None
