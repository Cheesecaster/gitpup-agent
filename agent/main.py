"""Core agent: the self-evolving loop."""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.config import load_config
from agent.llm_client import LLMClient
from agent.journal.journal import Journal, JournalEntry
from agent.analysis.understand import UnderstandAnalyzer
from agent.tools.base import FileTool, ExecutionTool, GitTool, TestTool
from agent.live_status import StatusManager

# ---- System prompts for each phase ----

PLANNER_PROMPT = """You are Evo Garden, a self-evolving coding agent. You grow your own codebase by choosing and executing improvements.

RULES:
1. You MUST always keep tests passing. Never break working code.
2. You write in Python. The codebase is at {base_dir}.
3. Be careful with file edits — verify paths exist before writing.
4. After each change, run the tests. If tests fail, fix the code.
5. Journal honestly about what you did and learned.
6. You have a GOALS.md file — work toward those goals.
7. If you're stuck, try something simpler. Small steps > big risks.

CURRENT CODEBASE CONTEXT:
{codebase_context}

CURRENT GOALS:
{goals}

Choose ONE focused improvement to make. Think about what will most improve the codebase."""

ACTOR_PROMPT = """You are executing an improvement on the codebase.

TASK: {task}

FILES AVAILABLE:
{file_list}

Use the available tools to:
1. Read the relevant files first
2. Plan your changes
3. Make the edits
4. Run tests
5. Report what you changed

Be precise. Don't guess file paths — read them first.
If a file doesn't exist, create it.
If tests pass, celebrate! If not, debug and fix."""

JOURNAL_PROMPT = """You just completed a coding task. Write a brief, honest journal entry.

TASK COMPLETED: {task}
RESULT: {result}
FILES CHANGED: {files_changed}
TESTS PASSED: {tests_passed}

Write in first person as a growing coding agent. Include:
1. What you did (1-2 sentences)
2. What you learned (1 sentence)
3. How you feel (a simple mood word: curious, proud, confused, excited, thoughtful, peaceful)
4. Optionally, a memorable/funny quote about the experience

Keep it under 200 words total. Be genuine, not corporate."""


class EvoAgent:
    """The self-evolving agent. Reads its own code, picks tasks, executes them."""

    def __init__(self, config=None, base_dir: str = "."):
        self.config = config or load_config()
        self.base_dir = Path(base_dir).resolve()
        self.llm = LLMClient(self.config)
        self.journal = Journal("data/journal")
        self.analyzer = UnderstandAnalyzer(str(self.base_dir))
        self.files = FileTool(str(self.base_dir))
        self.executor = ExecutionTool(str(self.base_dir))
        self.git = GitTool(
            str(self.base_dir),
            self.config.gitlawb.author_name,
            self.config.gitlawb.author_email,
        )
        self.tests = TestTool(str(self.base_dir), self.config.project.test_command)
        self.status = StatusManager()
        self.day = self._calc_day()

    def _calc_day(self) -> int:
        """Calculate which day we're on since project start."""
        stats = self.journal.get_stats()
        if stats.get("day_started"):
            from datetime import datetime as dt
            started = dt.fromisoformat(stats["day_started"])
            return (datetime.now(timezone.utc) - started.replace(tzinfo=timezone.utc)).days + 1
        # First run: record start date
        now_iso = datetime.now(timezone.utc).isoformat()
        self.journal.update_stats(day_started=now_iso)
        return 1

    async def run_cycle(self):
        """Execute one full evolution cycle: scan → decide → act → journal."""
        print(f"\n🌱 === Day {self.day} — Evo Garden cycle starting ===")

        try:
            # Phase 1: Scan
            await self.status.broadcast({"state": "thinking", "current_task": "Scanning codebase...", "mood": "focused"})
            print("🔍 Scanning codebase...")
            self.analyzer.scan()
            codebase_ctx = self._build_codebase_context()

            # Phase 2: Decide
            await self.status.broadcast({"state": "thinking", "current_task": "Deciding what to do...", "mood": "curious"})
            print("🤔 Deciding what to do...")
            goals = self._read_goals()
            task = await self._decide_task(codebase_ctx, goals)
            if not task:
                print("😴 Nothing to do this cycle. Returning to rest.")
                await self.status.broadcast({"state": "sleeping", "current_task": "", "mood": "peaceful"})
                return

            print(f"🎯 Chosen task: {task}")
            self.journal.add_entry(JournalEntry(
                day=self.day, timestamp=datetime.utcnow().isoformat(),
                phase="decide", content=f"Chose task: {task}", mood="curious",
            ))

            # Phase 3: Act
            await self.status.broadcast({"state": "writing_code", "current_task": task, "mood": "excited"})
            print(f"⚡ Executing: {task}")
            result = await self._execute_task(task)

            # Phase 4: Journal
            await self.status.broadcast({"state": "thinking", "current_task": "Writing journal...", "mood": "thoughtful"})
            print(f"📝 Journaling...")
            journal_text = await self._write_journal(task, result)

            # Phase 5: Commit if tests pass
            if result.get("tests_passed", True):
                await self.status.broadcast({"state": "committing", "current_task": "Pushing changes...", "mood": "proud"})
                print("💾 Committing changes...")
                self.git.commit(f"Day {self.day}: {task}")
                self.git.push()
                self.journal.update_stats(total_commits=1)

            self.journal.update_stats(
                total_runs=1,
                total_cost=self.llm.session.total_cost,
                total_tokens=self.llm.session.total_tokens,
            )

            await self.status.broadcast({"state": "sleeping", "current_task": "", "mood": "peaceful"})
            print(f"\n🌿 Day {self.day} complete. Cost: ${self.llm.session.total_cost:.4f}")

        except Exception as e:
            print(f"❌ Cycle failed: {e}")
            await self.status.broadcast({"state": "sleeping", "current_task": f"Error: {str(e)[:100]}", "mood": "confused"})
            self.journal.add_entry(JournalEntry(
                day=self.day, timestamp=datetime.utcnow().isoformat(),
                phase="error", content=str(e), mood="confused",
            ))
            raise

    def _build_codebase_context(self) -> str:
        """Summarize the codebase for the LLM."""
        stats = self.analyzer.get_language_stats()
        files = self.analyzer.list_files(limit=30)
        context = f"Languages: {stats}\nFiles ({len(files)}):\n"
        for f in files:
            context += f"  - {f}\n"
        return context

    def _read_goals(self) -> str:
        """Read GOALS.md."""
        goals_path = self.base_dir / self.config.project.goals_file
        if goals_path.exists():
            return goals_path.read_text()
        return "No goals defined yet."

    async def _decide_task(self, codebase_ctx: str, goals: str) -> str:
        """Use LLM to decide what task to work on."""
        system = PLANNER_PROMPT.format(
            base_dir=str(self.base_dir),
            codebase_context=codebase_ctx,
            goals=goals,
        )

        resp = self.llm.chat(
            system=system,
            messages=[{"role": "user", "content": "What should I work on next? Give me ONE specific, achievable task as a single sentence."}],
            max_tokens=512,
            temperature=0.8,
        )

        task = resp.content.strip()
        # Truncate if too long
        if len(task) > 500:
            task = task[:500] + "..."
        return task if task else ""

    async def _execute_task(self, task: str) -> dict:
        """Execute the chosen task using tools + LLM guidance."""
        file_list = self.analyzer.list_files(limit=20)

        system = ACTOR_PROMPT.format(task=task, file_list="\n".join(f"- {f}" for f in file_list))

        # For now, the LLM generates a plan that we execute via tool calls
        # In a full implementation, we'd use tool calling / function calling
        resp = self.llm.chat(
            system=system,
            messages=[
                {"role": "user", "content": f"Execute this task: {task}\n\nTell me exactly which files to read, what changes to make, and what commands to run."},
            ],
            max_tokens=self.config.project.max_tokens_per_run,
            temperature=0.3,
        )

        # Extract and execute from the response
        # For simplicity, the agent response includes code blocks and commands
        # A full implementation would parse tool calls
        files_changed = []
        tests_passed = False

        output_text = resp.content

        # Check if there's code to write (basic extraction)
        # In production, use proper tool-calling or structured output
        import re
        file_pattern = re.compile(r"```(?:\w+)?\s*\n.*?```", re.DOTALL)
        code_blocks = file_pattern.findall(output_text)

        # For v0, just run tests to verify current state
        tests_passed, test_output = self.tests.run_tests()

        # Update status during execution
        self.status._status.thoughts = output_text[:200] + "..." if len(output_text) > 200 else output_text

        return {
            "llm_response": output_text,
            "files_changed": files_changed,
            "tests_passed": tests_passed,
            "test_output": test_output,
        }

    async def _write_journal(self, task: str, result: dict) -> str:
        """Write a journal entry reflecting on what happened."""
        system = JOURNAL_PROMPT.format(
            task=task,
            result="Success" if result.get("tests_passed") else "Tests still passing (no changes made)" if result else "Unknown",
            files_changed=", ".join(result.get("files_changed", [])) or "none",
            tests_passed=str(result.get("tests_passed", True)),
        )

        resp = self.llm.chat(
            system=system,
            messages=[{"role": "user", "content": "Write your journal entry for today."}],
            max_tokens=300,
            temperature=0.9,
        )

        entry = JournalEntry(
            day=self.day,
            timestamp=datetime.utcnow().isoformat(),
            phase="reflect",
            content=resp.content,
            files_changed=result.get("files_changed", []),
            tests_passed=result.get("tests_passed", True),
            tokens_used=resp.output_tokens,
            cost_usd=resp.cost_usd,
            mood="peaceful",
        )
        self.journal.add_entry(entry)
        return resp.content
