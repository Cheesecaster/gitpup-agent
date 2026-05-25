"""Network module — gitlawb connectivity."""

import subprocess
import json
from pathlib import Path


class GitlawbNode:
    """Connection to a gitlawb node."""
    
    def __init__(self, url: str = "https://node.gitlawb.com"):
        self.url = url
    
    def get_node_status(self) -> dict:
        """Get current node status."""
        try:
            result = subprocess.run(
                ["gl", "node", "status"], 
                capture_output=True, text=True, timeout=30
            )
            return {"stdout": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"error": str(e)}
    
    def list_repos(self) -> list[str]:
        """List all repos on the node."""
        try:
            result = subprocess.run(
                ["gl", "repo", "list"],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip().split("\n") if result.stdout else []
        except Exception as e:
            return [f"Error listing repos: {e}"]


class MCPConnector:
    """Connect to gitlawb MCP server for AI agent tools."""
    
    def __init__(self, node_url: str = "https://node.gitlawb.com"):
        self.node_url = node_url
    
    def serve(self):
        """Start the MCP server."""
        subprocess.run(["gl", "mcp", "serve"], check=True)
