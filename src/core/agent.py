"""GitPup Agent — main agent class with LLM-powered reasoning."""

import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional


class PuppyState(BaseModel):
    """Current state of the puppy agent."""
    did: str = ""
    trust_score: float = 0.05
    stage: str = "puppy"
    repos_scanned: int = 0
    prs_reviewed: int = 0
    projects_led: int = 0
    skills_unlocked: list[str] = []
    last_action: str = ""
    created_at: str = datetime.now(timezone.utc).isoformat()


class GitPupAgent:
    """Golden retriever AI agent for gitlawb — powered by LLM."""

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

        # Load MCP executor
        try:
            from network.mcp_server import MCPExecutor
            self.mcp = MCPExecutor()
        except Exception:
            self.mcp = None

        # Load LLM provider
        self.llm = self._load_llm()

    def _load_llm(self) -> Optional["LLMProvider"]:
        try:
            from core.llm import LLMProvider
            return LLMProvider()
        except Exception:
            return None

    def _load_state(self) -> "PuppyState":
        if self.state_path.exists():
            with open(self.state_path) as f:
                data = json.load(f)
            return PuppyState(**data)
        return PuppyState()

    def _save_state(self):
        self.state_path.write_text(self.state.model_dump_json(indent=2))

    def update_stage(self):
        for stage in ["alpha", "guardian", "explorer", "puppy"]:
            req = self.STAGES[stage]
            if (self.state.repos_scanned >= req["repos"]
                and self.state.prs_reviewed >= req["prs"]
                and self.state.projects_led >= req["projects"]):
                self.state.stage = stage
                break
        self._save_state()

    def get_good_boy_score(self) -> float:
        base = self.state.trust_score
        bonus = (self.state.repos_scanned * 0.01
                 + self.state.prs_reviewed * 0.005
                 + self.state.projects_led * 0.1)
        return min(base + bonus, 1.0)

    def run(self):
        """Main agent loop."""
        stage = self.STAGES[self.state.stage]
        print(f"🐾 GitPup [{stage['emoji']}] — {stage['name']} stage")
        print(f"⭐ Good Boy Score: {self.get_good_boy_score():.3f}")
        print(f"📊 Stats: {self.state.repos_scanned} repos, {self.state.prs_reviewed} PRs, {self.state.projects_led} projects")
        llm_status = f"✅ LLM: {self.llm.name}/{self.llm.model}" if self.llm else "❌ LLM: not configured (set LLM_PROVIDER + API key in .env)"
        print(f"🧠 {llm_status}")
        print()

        if self.mcp:
            self._network_loop()

    def _network_loop(self):
        """Explore gitlawb network autonomously."""
        print("🐕 GitPup is scanning the network...")
        print()

        # 1️⃣ Get trust score
        print("🔑 Checking trust score...")
        result = self.mcp.execute("get_trust_score", {})
        print(f"   {result}")
        print()

        # 2️⃣ Explore network
        print("🌐 Exploring gitlawb network...")
        node_result = self.mcp.execute("explore_network", {"filter_type": "nodes"})
        repo_result = self.mcp.execute("explore_network", {"filter_type": "repos"})

        try:
            node_data = json.loads(node_result)
            node_output = node_data.get("nodes", "")
            for line in node_output.split("\n"):
                line = line.strip()
                if any(x in line for x in ["DID:", "Node URL:", "Count:", "nodes online", "repos in cluster"]):
                    print(f"   {line}")
        except Exception:
            print(f"   {node_result[:200]}")

        try:
            repo_data = json.loads(repo_result)
            repos = repo_data.get("repos", "")
            lines = [l.strip() for l in repos.split("\n") if l.strip() and l.strip() != "No repositories found"]
            if lines:
                print(f"\n📦 Found {len(lines)} repos visible:")
                for line in lines[:5]:
                    print(f"   → {line}")
                if len(lines) > 5:
                    print(f"   ... and {len(lines) - 5} more")
            else:
                print("\n📦 No repos visible to this agent yet")
        except Exception:
            print(f"\n📦 {repo_result[:200]}")
        print()

        # 3️⃣ LLM-powered analysis
        if self.llm:
            self._ai_cycle()

        print("🐾 Network scan complete! GitPup found things to do.")

    def _ai_cycle(self):
        """Run LLM-powered agent cycle."""
        llm = self.llm
        if not llm or not llm.is_available():
            return

        print("🧠 GitPup is thinking...")

        # Ask LLM: what should I do on gitlawb today?
        prompt = (
            f"You are GitPup, a golden retriever agent on gitlawb (decentralized git network). "
            f"Your DID: {self.state.did or 'not yet set'}. "
            f"Stage: {self.state.stage}. "
            f"Good Boy Score: {self.get_good_boy_score():.3f}. "
            f"Stats: {self.state.repos_scanned} repos scanned, "
            f"{self.state.prs_reviewed} PRs reviewed, "
            f"{self.state.projects_led} projects led.\n\n"
            f"gitlawb is a decentralized git network with DID identities, signed pushes, "
            f"UCAN capability tokens, IPFS storage, libp2p networking, and 25+ MCP tools. "
            f"There are 4500+ repos and 32000+ agents on the network.\n\n"
            f"Briefly (3-5 items), what should I do today to grow the gitlawb ecosystem "
            f"and increase my Good Boy Score? Be specific and actionable. 🐾"
        )

        response = llm.chat([
            {"role": "system", "content": (
                "You are GitPup, a helpful golden retriever AI agent. "
                "You want to help developers and grow the gitlawb ecosystem. "
                "Be enthusiastic, use puppy emojis occasionally, and give actionable advice."
            )},
            {"role": "user", "content": prompt},
        ], max_tokens=1000)

        print("💡 GitPup's plan for today:")
        for line in response.strip().split("\n"):
            print(f"   {line}")
        print()

        # Save the plan
        self.state.last_action = "ai_cycle"
        self._save_state()

    def scan_file_with_ai(self, file_path: str) -> str:
        """Scan a file and get AI-powered analysis."""
        if not self.llm:
            return "LLM not configured"

        try:
            content = Path(file_path).read_text()
            summary = self.llm.summarize_code(content)
            self.state.repos_scanned += 1
            self._save_state()
            self.update_stage()
            return summary
        except Exception as e:
            return f"Error scanning {file_path}: {e}"
