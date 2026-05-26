#!/usr/bin/env python3
"""Understand-Anything Integration — codebase analysis pipeline for GitPup"""
import os, sys, json, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from evolve import config, llm

SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".understand-anything", "dist", "build"}
SKIP_EXTS = {".pyc", ".pyo", ".so", ".dll", ".exe", ".zip", ".tar", ".gz", ".png", ".jpg", ".gif", ".woff", ".woff2"}


def scan_tree(root):
    """Build a tree representation of the project."""
    tree = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, root)
        tree[rel] = []
        for fn in filenames:
            if os.path.splitext(fn)[1] not in SKIP_EXTS:
                tree[rel].append(fn)
    return tree


def code_tree_string(root, max_depth=4, prefix=""):
    """Build a string tree for LLM context."""
    lines = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, root)
        depth = rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames.clear()
            continue
        indent = "  " * depth
        lines.append(f"{indent}📁 {os.path.basename(dirpath)}/")
        for fn in sorted(filenames)[:20]:
            ext = os.path.splitext(fn)[1]
            if ext not in SKIP_EXTS:
                lines.append(f"{indent}  📄 {fn}")
    return "\n".join(lines)


def understand_codebase():
    """LLM-analyze the codebase tree and produce knowledge graph."""
    config.log_evolve("=== Understand-Anything Analysis ===")
    root = config.PROJECT_ROOT
    tree_str = code_tree_string(root, max_depth=3)

    system = f"""You are Goldie analyzing your own codebase. Produce a structured knowledge graph:

{{
  "architecture": "high-level description of the system architecture",
  "modules": [
    {{"name": "...", "purpose": "...", "files": ["..."], "imports": ["..."]}},
    ...
  ],
  "entry_points": ["main.py", "start.py", ...],
  "data_flow": "how data flows between components",
  "key_patterns": ["pattern 1", "pattern 2", ...],
  "dependencies": {{...}},
  "strengths": ["..."],
  "weaknesses": ["..."]
}}"""

    msg = [{"role": "user", "content": f"Here is my codebase structure:\n\n{tree_str}\n\nAnalyze and produce the knowledge graph."}]
    result = llm.ask(msg, system=system, max_tokens=4000, temperature=0.3)

    # Save to intermediate
    os.makedirs(config.INTERMEDIATE_DIR, exist_ok=True)
    kg_path = os.path.join(config.INTERMEDIATE_DIR, "knowledge-graph.json")
    try:
        # Try to extract JSON from LLM response
        kg = json.loads(result)
    except (json.JSONDecodeError, ValueError):
        # If not valid JSON, wrap it
        kg = {"raw_analysis": result, "architecture": result[:500]}

    with open(kg_path, "w") as f:
        json.dumpkg(kg, f, indent=2)

    config.log_evolve(f"Knowledge graph saved to {kg_path}")
    return kg


if __name__ == "__main__":
    result = understand_codebase()
    print(json.dumps(result, indent=2))
