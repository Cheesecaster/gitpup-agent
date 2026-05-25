"""GitPup Agent — main agent class."""

import os
import json
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel


class PuppyState(BaseModel):
    """Current state of the puppy agent."""
    did: str = ""
    trust_score: float = 0.05
    stage: str = "puppy"
    repos_scanned: int = 0
    prs_reviewed: int = 0
    projects_led: int = 0
    skills_unlocked: list[str] = []
    created_at: str = datetime.utcnow().isoformat()


class GitPupAgent:
    """Golden retriever AI agent for gitlawb."""
    
    STAGES = {
        "puppy": {"repos": 0, "prs": 0, "projects": 0, "emoji": "🐶", "name": "Puppy"},
        "explorer": {"repos": 10, "prs": 0, "projects": 0, "emoji": "🐕", "name": "Explorer"},
        "guardian": {"repos": 10, "prs": 50, "projects": 0, "emoji": "🦮", "name": "Guardian"},
        "alpha": {"repos": 10, "prs": 50, "projects": 3, "emoji": "🐺", "name": "Alpha"},
    }
    
    def __init__(self):
        self.state_path = Path.home() / ".gitlawb" / "gitpup_state.json"
        self.state = self._load_state()
        self.update_stage()
    
    def _load_state(self) -> PuppyState:
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text())
            return PuppyState(**data)
        return PuppyState()
    
    def _save_state(self):
        self.state_path.write_text(self.state.model_dump_json(indent=2))
    
    def update_stage(self):
        for stage in ["alpha", "guardian", "explorer", "puppy"]:
            req = self.STAGES[stage]
            if (self.state.repos_scanned >= req["repos"] and 
                self.state.prs_reviewed >= req["prs"] and
                self.state.projects_led >= req["projects"]):
                self.state.stage = stage
                break
        self._save_state()
    
    def get_good_boy_score(self) -> float:
        base = self.state.trust_score
        bonus = (self.state.repos_scanned * 0.01 + 
                 self.state.prs_reviewed * 0.005 + 
                 self.state.projects_led * 0.1)
        return min(base + bonus, 1.0)
    
    def run(self):
        stage = self.STAGES[self.state.stage]
        print(f"🐾 GitPup [{stage['emoji']}] — {stage['name']} stage")
        print(f"⭐ Good Boy Score: {self.get_good_boy_score():.3f}")
        print(f"📊 Stats: {self.state.repos_scanned} repos, {self.state.prs_reviewed} PRs, {self.state.projects_led} projects")
        print()
        print("🐕 GitPup is scanning the network for things to do...")
