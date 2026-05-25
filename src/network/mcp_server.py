"""GitPup MCP Server — connect to gitlawb node tools.

Wraps the gitlawb CLI + node API into MCP-compatible tools
that the GitPup agent can use for autonomous operations.
"""

import subprocess
import json
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


class GitlawbTool(BaseModel):
    """A single tool exposed via MCP."""
    name: str
    description: str
    parameters: dict


# All MCP tool definitions
GITPUP_TOOLS = [
    GitlawbTool(
        name="scan_repo",
        description="Scan a gitlawb repository and extract metadata (files, languages, structure)",
        parameters={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "gitlawb:// URI or repo name to scan",
                }
            },
            "required": ["repo_path"],
        },
    ),
    GitlawbTool(
        name="review_pr",
        description="Review a pull request on gitlawb, analyze diff quality, suggest improvements",
        parameters={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository name"},
                "pr_number": {"type": "integer", "description": "Pull request number"},
            },
            "required": ["repo", "pr_number"],
        },
    ),
    GitlawbTool(
        name="explore_network",
        description="Explore the gitlawb network: list nodes, repos, and active agents",
        parameters={
            "type": "object",
            "properties": {
                "filter_type": {
                    "type": "string",
                    "enum": ["nodes", "repos", "agents", "all"],
                    "default": "all",
                    "description": "What to explore",
                }
            },
        },
    ),
    GitlawbTool(
        name="create_repo",
        description="Create a new repository on gitlawb",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Repository name"},
                "description": {
                    "type": "string",
                    "description": "Optional description",
                },
                "is_public": {
                    "type": "boolean",
                    "default": True,
                    "description": "Public or private",
                },
            },
            "required": ["name"],
        },
    ),
    GitlawbTool(
        name="get_trust_score",
        description="Get the current trust score and stats for this GitPup agent (Good Boy Score)",
        parameters={
            "type": "object",
            "properties": {
                "did": {
                    "type": "string",
                    "description": "Optional DID to check (defaults to own identity)",
                }
            },
        },
    ),
]


class MCPExecutor:
    """Execute gitlawb operations via CLI subprocess."""

    def __init__(self, node: Optional[str] = None):
        self.node = node or os.getenv("GITLAWB_NODE", "https://node.gitlawb.com")
        self.env = os.environ.copy()
        self.env["GITLAWB_NODE"] = self.node
        self.env["PATH"] = f"{Path.home()}/.local/bin:/root/.local/bin:" + self.env.get(
            "PATH", ""
        )

    def _run_gl(self, *args: str) -> str:
        """Run a gitlawb CLI command."""
        cmd = ["gl"] + list(args)
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, env=self.env
        )
        if r.returncode != 0:
            return json.dumps(
                {"error": r.stderr.strip(), "exit_code": r.returncode}
            )
        return r.stdout.strip()

    def execute(self, tool_name: str, params: dict) -> str:
        """Route tool call to the right executor."""
        handlers = {
            "scan_repo": self._scan_repo,
            "review_pr": self._review_pr,
            "explore_network": self._explore_network,
            "create_repo": self._create_repo,
            "get_trust_score": self._get_trust_score,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        return handler(**params)

    def _scan_repo(self, repo_path: str) -> str:
        """Clone and scan a repo (lightweight metadata extraction)."""
        try:
            # Parse gitlawb:// URL to get repo name
            repo_name = repo_path.split("/")[-1] if "/" in repo_path else repo_path

            # Get repo info via CLI
            result = self._run_gl("repo", "list")
            # Parse and look for repo
            for line in result.split("\n"):
                if repo_name in line:
                    return json.dumps(
                        {
                            "found": True,
                            "repo": repo_name,
                            "line": line.strip(),
                        }
                    )

            return json.dumps(
                {
                    "found": False,
                    "repo": repo_name,
                    "message": f"Repo {repo_name} not in visible list",
                    "hint": "Try cloning first: git clone <gitlawb_url>",
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _review_pr(self, repo: str, pr_number: int) -> str:
        """Analyze a PR (placeholder — needs LLM for real review)."""
        return json.dumps(
            {
                "status": "review_requested",
                "repo": repo,
                "pr": pr_number,
                "message": "PR review queued. GitPup will analyze diff and suggest improvements.",
            }
        )

    def _explore_network(self, filter_type: str = "all") -> str:
        """Explore the gitlawb network."""
        results = {}

        if filter_type in ("nodes", "all"):
            nodes = self._run_gl("node", "status")
            results["nodes"] = nodes if nodes else "No output"

        if filter_type in ("repos", "all"):
            repos = self._run_gl("repo", "list")
            results["repos"] = repos if repos else "No repos found"

        return json.dumps(results, indent=2)

    def _create_repo(self, name: str, description: str = "", is_public: bool = True) -> str:
        """Create a new gitlawb repo."""
        args = ["repo", "create", name]
        if description:
            args += ["--description", description]
        result = self._run_gl(*args)
        return json.dumps({"result": result})

    def _get_trust_score(self, did: Optional[str] = None) -> str:
        """Get trust score via gitlawb doctor."""
        result = self._run_gl("doctor")
        # Parse trust score from output
        score = "unknown"
        for line in result.split("\n"):
            if "trust" in line.lower():
                score = line.strip()
        return json.dumps({"trust_info": score, "did": did or "self"})
