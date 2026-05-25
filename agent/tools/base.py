"""Agent tools: file I/O, execution, git operations, code analysis."""

import os
import subprocess
import tempfile
from pathlib import Path


class FileTool:
    """Read, write, patch files."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir).resolve()

    def read_file(self, path: str, max_lines: int = 500) -> str:
        """Read a file with line numbers."""
        full_path = self._resolve(path)
        if not full_path.exists():
            return f"Error: File not found: {path}"
        try:
            lines = full_path.read_text().split("\n")
            limited = lines[:max_lines]
            numbered = []
            for i, line in enumerate(limited, 1):
                numbered.append(f"{i:4d}| {line}")
            result = "\n".join(numbered)
            if len(lines) > max_lines:
                result += f"\n... ({len(lines) - max_lines} more lines)"
            return result
        except Exception as e:
            return f"Error reading {path}: {e}"

    def write_file(self, path: str, content: str) -> str:
        """Write a file (overwrites)."""
        full_path = self._resolve(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            full_path.write_text(content)
            return f"Written {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

    def patch_file(self, path: str, old_str: str, new_str: str) -> str:
        """Replace old_str with new_str in a file."""
        full_path = self._resolve(path)
        try:
            content = full_path.read_text()
            if old_str not in content:
                return f"Error: '{old_str[:50]}...' not found in {path}"
            new_content = content.replace(old_str, new_str, 1)
            full_path.write_text(new_content)
            return f"Patched {path}: replaced {len(old_str)} chars with {len(new_str)} chars"
        except Exception as e:
            return f"Error patching {path}: {e}"

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            if str(p.resolve()).startswith(str(self.base_dir)):
                return p.resolve()
            raise ValueError(f"Path outside base: {path}")
        return (self.base_dir / p).resolve()


class ExecutionTool:
    """Run shell commands safely."""

    def __init__(self, base_dir: str = ".", timeout: int = 60):
        self.base_dir = base_dir
        self.timeout = timeout
        self._blocked_commands = ["rm -rf /", ":(){:|:&};:", "wget", "curl", "nc"]

    def run(self, command: str) -> tuple[int, str, str]:
        """Run a command, return (exit_code, stdout, stderr)."""
        # Safety check
        for blocked in self._blocked_commands:
            if blocked in command.lower():
                return -1, "", f"Blocked command: {blocked}"

        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.base_dir,
        )
        try:
            stdout, stderr = proc.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            return -1, "", f"Command timed out after {self.timeout}s"

        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )


class GitTool:
    """Git operations for commits."""

    def __init__(self, base_dir: str = ".", author_name: str = "Evo Agent", author_email: str = "agent@evo.local"):
        self.base_dir = base_dir
        self.author_name = author_name
        self.author_email = author_email

    def status(self) -> str:
        """Get git status."""
        code, out, err = self._run("git status --short")
        return out if code == 0 else err

    def diff(self) -> str:
        """Get current diff."""
        code, out, err = self._run("git diff HEAD")
        return out if code == 0 else err

    def commit(self, message: str, paths: list[str] | None = None) -> str:
        """Stage files and commit."""
        if paths:
            for p in paths:
                self._run(f"git add {p}")
        else:
            self._run("git add -A")

        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = self.author_name
        env["GIT_AUTHOR_EMAIL"] = self.author_email
        env["GIT_COMMITTER_NAME"] = self.author_name
        env["GIT_COMMITTER_EMAIL"] = self.author_email

        code, out, err = self._run(f'git commit -m "{message}"', env=env)
        if code == 0:
            return f"Committed: {message}"
        return f"Commit failed: {err or out}"

    def push(self, remote: str = "origin", branch: str = "main") -> str:
        """Push to remote."""
        code, out, err = self._run(f"git push {remote} {branch}")
        if code == 0:
            return f"Pushed to {remote}/{branch}"
        return f"Push failed: {err or out}"

    def log(self, n: int = 10) -> str:
        """Get recent commits."""
        code, out, err = self._run(f"git log --oneline -{n}")
        return out if code == 0 else err

    def _run(self, cmd: str, env: dict | None = None) -> tuple[int, str, str]:
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=self.base_dir, env=env or os.environ.copy(),
        )
        stdout, stderr = proc.communicate(timeout=60)
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )


class TestTool:
    """Run tests and check if they pass."""

    def __init__(self, base_dir: str = ".", test_command: str = "python -m pytest -x"):
        self.base_dir = base_dir
        self.test_command = test_command

    def run_tests(self) -> tuple[bool, str]:
        """Run tests, return (passed, output)."""
        proc = subprocess.Popen(
            self.test_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.base_dir,
        )
        try:
            stdout, stderr = proc.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            return False, "Tests timed out after 120s"

        output = (stdout + stderr).decode("utf-8", errors="replace")
        return proc.returncode == 0, output
