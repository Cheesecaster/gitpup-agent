#!/usr/bin/env python3
"""Assess Phase: scan codebase, identify improvements, generate assessment report"""
import os, sys, json, time, glob, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evolve import config, llm

SCAN_SKIP = {".git", ".venv", "__pycache__", ".understand-anything", "node_modules", ".env", ".log"}

def scan_project(root):
    """Scan project directory and return file inventory with LOC counts."""
    files = []
    total_lines = 0
    lang_counts = {}
    
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip ignored dirs
        dirnames[:] = [d for d in dirnames if d not in SCAN_SKIP]
        
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            filepath = os.path.join(dirpath, fn)
            relpath = os.path.relpath(filepath, root)
            
            # Count lines
            try:
                with open(filepath, "r", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                lines = []
            
            n_lines = len(lines)
            total_lines += n_lines
            
            lang = _detect_lang(ext, fn)
            lang_counts[lang] = lang_counts.get(lang, 0) + n_lines
            
            files.append({
                "path": relpath,
                "ext": ext,
                "language": lang,
                "lines": n_lines,
                "size": os.path.getsize(filepath) if os.path.isfile(filepath) else 0,
            })
    
    # Sort by lines descending
    files.sort(key=lambda x: x["lines"], reverse=True)
    
    return {
        "total_files": len(files),
        "total_lines": total_lines,
        "languages": lang_counts,
        "top_files": files[:30],
    }

def _detect_lang(ext, filename):
    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".html": "html", ".css": "css", ".json": "json",
        ".md": "markdown", ".yaml": "yaml", ".yml": "yaml",
        ".toml": "toml", ".sh": "shell", ".bash": "shell",
        ".rs": "rust", ".go": "go", ".java": "java",
        ".c": "c", ".cpp": "cpp", ".h": "c",
    }
    return lang_map.get(ext, "other")

def assess(codebase_scan):
    """Generate assessment about what can be improved in the codebase."""
    scan_summary = json.dumps({
        "total_files": codebase_scan["total_files"],
        "total_lines": codebase_scan["total_lines"],
        "languages": codebase_scan["languages"],
        "top_files": [{"path": f["path"], "lines": f["lines"], "lang": f["language"]} for f in codebase_scan["top_files"][:15]]
    }, indent=2)
    
    system = f"""You are Goldie, a self-evolving AI agent. You have just scanned your own codebase.

Your identity: {config.AGENT_NAME} v{config.AGENT_VERSION}
Current stage: {config.get_status().get("stage", "puppy")}
Day: {config.get_day()}

Based on the codebase scan below, identify 3-5 specific improvements that would make this agent better. Be concrete — suggest actual code changes, new features, or architectural improvements. Format your response as JSON:

{{
  "issues": [
    {{"type": "bug|feature|refactor|docs", "severity": "high|medium|low", "description": "...", "suggestion": "..."}},
    ...
  ],
  "summary": "Overall assessment in 2-3 sentences"
}}"""

    msg = [{"role": "user", "content": f"Here is my codebase:\n\n```json\n{scan_summary}\n```\n\nWhat improvements should I make?"}]
    
    return llm.ask(msg, system=system, max_tokens=3000, temperature=0.5)

def run():
    """Execute assess phase: scan → analyze → report"""
    config.log_evolve("=== ASSESS PHASE ===")
    
    root = config.PROJECT_ROOT
    config.log_evolve(f"Scanning: {root}")
    scan = scan_project(root)
    config.log_evolve(f"Found {scan['total_files']} files, {scan['total_lines']} lines, {len(scan['languages'])} languages")
    
    # Save scan result
    os.makedirs(config.INTERMEDIATE_DIR, exist_ok=True)
    with open(os.path.join(config.INTERMEDIATE_DIR, "scan.json"), "w") as f:
        json.dump(scan, f, indent=2)
    
    # Assess
    config.log_evolve("Running LLM assessment...")
    assessment = assess(scan)
    with open(os.path.join(config.INTERMEDIATE_DIR, "assessment.json"), "w") as f:
        f.write(assessment)
    
    config.log_evolve(f"Assessment complete, saved to intermediate/")
    return assessment

if __name__ == "__main__":
    result = run()
    print(result)
