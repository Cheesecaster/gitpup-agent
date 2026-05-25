"""Evo Garden MCP Server — exposes agent tools via MCP protocol.

Add to Hermes config (~/.hermes/config.yaml):
  mcp_servers:
    evo_garden:
      command: "python"
      args: ["-m", "agent.mcp_server"]
      env:
        LLM_API_KEY: "your-key"

Exposed tools:
  evo_garden_status    - Get live agent status
  evo_garden_chat      - Chat with the agent
  evo_garden_journal   - Read journal entries
  evo_garden_goals     - Read current goals
  evo_garden_stats     - Get cumulative stats
  evo_garden_codebase  - Get codebase analysis info
  evo_garden_evolve    - Trigger manual evolution cycle
"""

import json
import os
import sys
import asyncio
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


class EvoGardenState:
    """Shared state for the MCP server."""

    def __init__(self):
        try:
            self.config = get_config()
        except Exception:
            self.config = load_config()

        # Lazy init to avoid import loops in __init__
        self._status_mgr = None
        self._journal = None

    @property
    def status_mgr(self):
        if self._status_mgr is None:
            from agent.live_status import StatusManager
            self._status_mgr = StatusManager()
        return self._status_mgr

    @property
    def journal(self):
        if self._journal is None:
            from agent.journal.journal import Journal
            self._journal = Journal("data/journal")
        return self._journal


@asynccontextmanager
async def server_lifespan(srv: Server):
    """Initialize shared state on startup."""
    try:
        state = EvoGardenState()
    except Exception:
        state = EvoGardenState()
    yield {"state": state}


server = Server("evo-garden", lifespan=server_lifespan)


def _get_tools() -> list[Tool]:
    return [
        Tool(
            name="evo_garden_status",
            description="Get the current live status of the Evo Garden agent. Shows what it's doing right now (sleeping, thinking, writing code, running tests, etc), current task, mood, and last update time.",
            inputSchema={
                "type": "object", "properties": {}, "required": [],
            },
        ),
        Tool(
            name="evo_garden_chat",
            description="Send a message to the Evo Garden agent and get a response. The agent can answer questions about its codebase, goals, evolution, or just chat conversationally.",
            inputSchema={
                "type": "object",
                "properties": {"message": {"type": "string", "description": "The message to send to the agent"}},
                "required": ["message"],
            },
        ),
        Tool(
            name="evo_garden_journal",
            description="Read journal entries from the Evo Garden agent. Each entry reflects on what the agent did, learned, and how it felt. Optional filters for mood.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of entries (default: 10, max: 50)", "default": 10},
                    "mood": {"type": "string", "description": "Filter by mood: peaceful, curious, excited, confused, proud, thoughtful"},
                },
                "required": [],
            },
        ),
        Tool(
            name="evo_garden_goals",
            description="Read the current goals that the Evo Garden agent is working toward.",
            inputSchema={
                "type": "object", "properties": {}, "required": [],
            },
        ),
        Tool(
            name="evo_garden_stats",
            description="Get cumulative statistics: total runs, commits, cost, tokens used, journal entries, and mood distribution.",
            inputSchema={
                "type": "object", "properties": {}, "required": [],
            },
        ),
        Tool(
            name="evo_garden_codebase",
            description="Get information about the Evo Garden codebase: languages, file list, module structure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "Filter by language (python, rust, typescript, etc)"},
                    "detail": {"type": "string", "description": "Level of detail: 'summary' (default), 'files', 'stats'", "default": "summary"},
                },
                "required": [],
            },
        ),
        Tool(
            name="evo_garden_evolve",
            description="Manually trigger the Evo Garden agent to run one evolution cycle: scan codebase, decide improvement, write code, test, and journal.",
            inputSchema={
                "type": "object",
                "properties": {"force": {"type": "boolean", "description": "Force run even if agent is currently busy", "default": False}},
                "required": [],
            },
        ),
    ]


def _handle_tool_call(name: str, arguments: dict, state: EvoGardenState) -> str:
    """Execute a tool call. Pure sync, no async operations."""
    if name == "evo_garden_status":
        return json.dumps(state.status_mgr._status.to_dict(), indent=2)

    elif name == "evo_garden_chat":
        msg = arguments.get("message", "")
        if not msg:
            return "Error: message cannot be empty"
        try:
            from agent.llm_client import LLMClient

            llm = LLMClient(state.config)
            entries = state.journal.get_entries(limit=3)
            context = ""
            if entries:
                lines = []
                for e in entries:
                    lines.append(f"[Day {e['day']} ({e.get('mood', 'neutral')})] {e['content'][:150]}...")
                context = "Recent journal:\n" + "\n".join(lines)
            else:
                context = "No journal entries yet."

            resp = llm.chat(
                system=f"You are Evo Garden, a self-evolving coding agent. Be friendly and honest.\n\n{context}",
                messages=[{"role": "user", "content": msg}],
                max_tokens=512,
                temperature=0.7,
            )
            state.status_mgr.add_chat_message("user", msg)
            state.status_mgr.add_chat_message("assistant", resp.content)
            return resp.content
        except Exception as e:
            return f"Error chatting: {e}"

    elif name == "evo_garden_journal":
        limit = min(arguments.get("limit", 10), 50)
        mood_filter = arguments.get("mood")
        entries = state.journal.get_entries(limit=limit)
        if mood_filter:
            entries = [e for e in entries if e.get("mood") == mood_filter]
        if not entries:
            return "No journal entries yet. The garden hasn't started growing!"
        return json.dumps(entries, indent=2)

    elif name == "evo_garden_goals":
        from pathlib import Path
        goals_path = Path(state.config.project.goals_file)
        if goals_path.exists():
            return goals_path.read_text()
        return "Goals file not found. No goals set yet."

    elif name == "evo_garden_stats":
        stats = state.journal.get_stats()
        entries = state.journal.get_entries(limit=1000)
        moods = {}
        for e in entries:
            mood = e.get("mood", "neutral")
            moods[mood] = moods.get(mood, 0) + 1
        stats["mood_distribution"] = moods
        stats["total_entries"] = len(entries)
        return json.dumps(stats, indent=2)

    elif name == "evo_garden_codebase":
        from agent.analysis.understand import UnderstandAnalyzer
        ua = UnderstandAnalyzer(".")
        ua.scan()
        detail = arguments.get("detail", "summary")
        lang = arguments.get("language")

        if detail == "files":
            files = ua.list_files(lang, limit=100)
            return "\n".join(f"- {f}" for f in files) if files else "No files found."
        elif detail == "stats":
            lang_stats = ua.get_language_stats()
            total = sum(v for v in lang_stats.values()) if isinstance(lang_stats, dict) else 0
            return json.dumps({"total_files": total, "languages": lang_stats, "graph_path": str(ua.graph_path)}, indent=2)
        else:
            lang_stats = ua.get_language_stats()
            file_count = sum(v for v in lang_stats.values()) if isinstance(lang_stats, dict) else 0
            return json.dumps({"total_files": file_count, "languages": lang_stats}, indent=2)

    elif name == "evo_garden_evolve":
        try:
            from agent.main import EvoAgent
            agent = EvoAgent(base_dir=".")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(agent.run_cycle())
                return "Evolution cycle completed successfully."
            finally:
                loop.close()
        except Exception as e:
            return f"Evolution cycle failed: {e}"

    else:
        return f"Unknown tool: {name}"


# ── Register Tools ──

@server.list_tools()
async def list_tools():
    return _get_tools()


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    ctx = server.request_context
    state = ctx.lifespan_context.get("state", EvoGardenState())
    try:
        result = _handle_tool_call(name, arguments, state)
        return [TextContent(type="text", text=str(result))]
    except Exception as e:
        tb = traceback.format_exc()
        return [TextContent(type="text", text=f"Error executing {name}: {e}\n{tb}")]


# ── Entry Point ──

async def main():
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, initialization_timeout=60)


if __name__ == "__main__":
    asyncio.run(main())
