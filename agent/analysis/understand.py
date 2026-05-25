"""Understand-Anything integration: codebase scanning & analysis."""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional


class UnderstandAnalyzer:
    """Lightweight interface to Understand-Anything knowledge graph."""

    def __init__(self, base_dir: str = ".", graph_path: Optional[str] = None):
        self.base_dir = Path(base_dir).resolve()
        self.graph_path = Path(graph_path) if graph_path else self.base_dir / ".understand-anything" / "knowledge-graph.json"
        self._graph: Optional[dict] = None

    def scan(self) -> bool:
        """Run Understand-Anything scanner on the project.
        Returns True if scan completed successfully."""
        try:
            # Try running understand-anything CLI if installed
            result = subprocess.run(
                ["understand-anything", "scan", "--output", str(self.graph_path.parent)],
                cwd=str(self.base_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                self._load_graph()
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: build a simple codebase structure ourselves
        return self._fallback_scan()

    def _fallback_scan(self) -> bool:
        """Simple fallback: list files, detect languages, build basic graph."""
        nodes = []
        for root, dirs, files in os.walk(self.base_dir):
            # Skip hidden dirs and common ignores
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv")]

            for f in files:
                path = Path(root) / f
                rel = path.relative_to(self.base_dir)
                ext = path.suffix
                lang = self._ext_to_lang(ext)
                if lang:
                    nodes.append({
                        "id": str(rel),
                        "type": "file",
                        "language": lang,
                        "path": str(rel),
                        "loc": 0,  # will populate if we read
                    })

        graph = {
            "version": "1",
            "nodes": nodes,
            "edges": [],
            "metadata": {
                "total_files": len(nodes),
                "languages": list(set(n["language"] for n in nodes)),
            }
        }

        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.graph_path, "w") as f:
            json.dump(graph, f, indent=2)

        self._graph = graph
        return True

    def _ext_to_lang(self, ext: str) -> str:
        mapping = {
            ".py": "python",
            ".rs": "rust",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".go": "go",
            ".rb": "ruby",
            ".md": "markdown",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".html": "html",
            ".css": "css",
            ".sh": "shell",
        }
        return mapping.get(ext.lower(), "")

    def get_graph(self) -> Optional[dict]:
        """Get the loaded knowledge graph."""
        if self._graph is None:
            self._load_graph()
        return self._graph

    def _load_graph(self):
        if self.graph_path.exists():
            with open(self.graph_path) as f:
                self._graph = json.load(f)

    def get_file_summary(self, path: str) -> Optional[dict]:
        """Get info about a specific file from the graph."""
        if self._graph is None:
            self._load_graph()
        if self._graph is None:
            return None

        for node in self._graph.get("nodes", []):
            if node.get("path") == path:
                return node
        return None

    def get_language_stats(self) -> dict:
        """Get file count per language."""
        if self._graph is None:
            self._load_graph()
        if self._graph is None:
            return {}

        lang_counts = {}
        for node in self._graph.get("nodes", []):
            lang = node.get("language", "unknown")
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        return lang_counts

    def list_files(self, language: Optional[str] = None, limit: int = 50) -> list[str]:
        """List files from the graph, optionally filtered by language."""
        if self._graph is None:
            self._load_graph()
        if self._graph is None:
            return []

        files = []
        for node in self._graph.get("nodes", []):
            if language and node.get("language") != language:
                continue
            files.append(node.get("path", ""))
            if len(files) >= limit:
                break
        return files
