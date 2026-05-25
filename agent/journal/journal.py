"""Journal system: records agent reflections, mood, and activity."""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class JournalEntry:
    day: int
    timestamp: str
    phase: str  # "scan", "decide", "act", "reflect", "sleep"
    content: str
    files_changed: list[str] = field(default_factory=list)
    tests_passed: bool = True
    tokens_used: int = 0
    cost_usd: float = 0.0
    mood: str = "neutral"  # neutral, curious, proud, confused, excited, thoughtful
    learning: str = ""
    quote: str = ""  # self-aware / funny moment


class Journal:
    """Handles reading/writing journal entries."""

    def __init__(self, data_dir: str = "data/journal"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def entries_path(self) -> Path:
        return self.data_dir / "entries.jsonl"

    @property
    def stats_path(self) -> Path:
        return self.data_dir / "stats.json"

    def add_entry(self, entry: JournalEntry):
        """Append an entry to the journal log."""
        with open(self.entries_path, "a") as f:
            f.write(json.dumps(entry.__dict__) + "\n")

    def get_entries(self, limit: int = 100) -> list[dict]:
        """Get recent journal entries."""
        if not self.entries_path.exists():
            return []
        entries = []
        with open(self.entries_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries[-limit:]

    def get_stats(self) -> dict:
        """Get cumulative stats."""
        if not self.stats_path.exists():
            return {"total_runs": 0, "total_commits": 0, "total_cost": 0.0, "total_tokens": 0, "day_started": None}

        with open(self.stats_path) as f:
            return json.load(f)

    def update_stats(self, **kwargs):
        """Update cumulative stats."""
        stats = self.get_stats()
        for key, value in kwargs.items():
            if key in stats and isinstance(value, (int, float)):
                stats[key] += value
            else:
                stats[key] = value

        with open(self.stats_path, "w") as f:
            json.dump(stats, f, indent=2)

    def get_mood_distribution(self) -> dict:
        """Get count of each mood."""
        entries = self.get_entries(limit=1000)
        moods = {}
        for e in entries:
            mood = e.get("mood", "neutral")
            moods[mood] = moods.get(mood, 0) + 1
        return moods

    def get_top_quotes(self, limit: int = 10) -> list[str]:
        """Get entries with non-empty quotes."""
        entries = self.get_entries(limit=1000)
        quotes = [e for e in entries if e.get("quote")]
        return quotes[:limit]
