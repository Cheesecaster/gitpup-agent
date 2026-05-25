"""Tests for Evo Garden agent."""
import json
import os
import tempfile
import pytest
from pathlib import Path


class TestConfig:
    def test_load_default_config(self):
        from agent.config import load_config
        config = load_config()
        assert config.llm.provider == "openrouter"
        assert config.web.port == 3000
        assert config.web.sse_port == 8080
        assert config.evolution.mode == "vps"

    def test_api_key_from_env(self, monkeypatch):
        from agent.config import load_config
        monkeypatch.setenv("LLM_API_KEY", "test-key-123")
        config = load_config()
        assert config.llm.get_api_key() == "test-key-123"


class TestFileTool:
    def test_read_write(self, tmp_path):
        from agent.tools.base import FileTool
        ft = FileTool(str(tmp_path))

        result = ft.write_file("test.txt", "hello world")
        assert "Written" in result

        content = ft.read_file("test.txt")
        assert "hello world" in content

    def test_patch_file(self, tmp_path):
        from agent.tools.base import FileTool
        ft = FileTool(str(tmp_path))

        ft.write_file("test.txt", "Hello Alice, goodbye Alice!")
        result = ft.patch_file("test.txt", "Alice", "Bob")
        assert "Patched" in result

        content = ft.read_file("test.txt")
        assert "Bob" in content
        assert "Alice" in content  # only first occurrence replaced


class TestJournal:
    def test_add_and_retrieve(self, tmp_path):
        from agent.journal.journal import Journal, JournalEntry
        j = Journal(str(tmp_path))

        entry = JournalEntry(
            day=1, timestamp="2026-01-01T00:00:00",
            phase="reflect", content="Today I learned!", mood="curious",
            learning="Tests are important!"
        )
        j.add_entry(entry)

        entries = j.get_entries()
        assert len(entries) == 1
        assert entries[0]["content"] == "Today I learned!"
        assert entries[0]["mood"] == "curious"


class TestExecutionTool:
    def test_run_command(self, tmp_path):
        from agent.tools.base import ExecutionTool
        et = ExecutionTool(str(tmp_path))

        code, out, err = et.run("echo hello")
        assert code == 0
        assert "hello" in out

    def test_blocked_command(self, tmp_path):
        from agent.tools.base import ExecutionTool
        et = ExecutionTool(str(tmp_path))

        code, out, err = et.run("rm -rf /")
        assert code == -1
        assert "Blocked" in err


class TestUnderstandAnalyzer:
    def test_fallback_scan(self, tmp_path):
        from agent.analysis.understand import UnderstandAnalyzer

        # Create some test files
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "test.py").write_text("def test_x(): pass")
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / ".gitignore").write_text("*")

        ua = UnderstandAnalyzer(str(tmp_path))
        assert ua._fallback_scan() is True

        stats = ua.get_language_stats()
        assert "python" in stats
        assert "markdown" in stats

        files = ua.list_files("python")
        assert len(files) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
