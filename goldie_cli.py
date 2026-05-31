#!/usr/bin/env python3
"""Goldie CLI v3.0 - Minimal CLI for Telegram bot commands."""
import json, os, sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
JF = os.path.join(DATA, "journal", "entries.jsonl")
SF = os.path.join(DATA, "state", "status.json")
LF = os.path.join(BASE, "data", "evolve.log")

BIRTH = "2026-05-25"

def day_count():
    birth = datetime.strptime(BIRTH, "%Y-%m-%d")
    today = datetime.utcnow()
    return max(1, (today - birth).days)

def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default or {}

def load_last_evolve(n=5):
    try:
        with open(LF) as f:
            lines = [l.strip() for l in f if l.strip()]
        return lines[-n:]
    except Exception:
        return ["No evolve log found"]

def cmd_status():
    st = load_json(SF, {"state": "idle"})
    stats = load_json(os.path.join(DATA, "state", "stats.json"), {})
    kb = load_json(os.path.join(DATA, "knowledge.json"), {})
    pers = load_json(os.path.join(DATA, "personality.json"), {})
    day = day_count()
    total_runs = stats.get("total_runs", pers.get("stats", {}).get("total_runs", 0))

    repos_studied = len(kb.get("repos", {}))
    patterns = kb.get("stats", {}).get("total_patterns", 0)
    skills = kb.get("stats", {}).get("total_skills_learned", 0)
    wisdom = len(load_json(os.path.join(DATA, "memory", "wisdom.json"), {}).get("items", []))

    evolve_lines = load_last_evolve(3)
    evolve_str = "\n".join("- " + e for e in evolve_lines)

    return (
        "**Goldie Status (Day %d)**\n\n"
        "**Stage:** %s\n"
        "**State:** %s\n"
        "**Total Runs:** %d\n\n"
        "**Knowledge Base:**\n"
        "- Repos studied: %d\n"
        "- Patterns extracted: %d\n"
        "- Skills learned: %d\n"
        "- Wisdom entries: %d\n\n"
        "**Last Runs:**\n%s"
        % (day, st.get("stage", "architect"), st.get("state", "idle"),
           total_runs, repos_studied, patterns, skills, wisdom, evolve_str)
    )

def cmd_personality():
    pers = load_json(os.path.join(DATA, "personality.json"), {})
    dims = pers.get("dimensions", {})
    stats = pers.get("stats", {})

    result = ["**Personality Radar**\n"]
    for dim, data in dims.items():
        val = data.get("value", 0)
        growth = data.get("growth_count", 0)
        bar = "#" * int(val * 10) + "." * (10 - int(val * 10))
        result.append("**%s:** [%s] %.2f (%d)" % (dim.capitalize(), bar, val, growth))

    result.append("\n**Stats:** %d runs, %d days active" % (
        stats.get("total_runs", 0), stats.get("days_active", 0)))
    return "\n".join(result)

def cmd_kb():
    kb = load_json(os.path.join(DATA, "knowledge.json"), {})
    repos = kb.get("repos", {})
    skills = kb.get("skills_memory", [])

    deep = []
    shallow = []
    for name, data in repos.items():
        level = data.get("study_level", 0)
        pats = len(data.get("patterns", []))
        ins = len(data.get("insights", []))
        if level >= 3:
            deep.append("- %s (L%d, %d patterns, %d insights)" % (name, level, pats, ins))
        else:
            shallow.append("- %s (L%d)" % (name, level))

    result = ["**Knowledge Base**\n"]
    result.append("**Total repos:** %d" % len(repos))
    result.append("**Skills in memory:** %d" % len(skills))
    result.append("**Relationships:** %d" % len(kb.get("relationships", [])))

    if deep:
        result.append("\n**Deep Study (L3+):**")
        result.extend(deep[:10])

    if shallow:
        result.append("\n**Surface Study:** (%d repos)" % len(shallow))
        for r in shallow[:5]:
            result.append(r)
        if len(shallow) > 5:
            result.append("- ... and %d more" % (len(shallow) - 5))

    return "\n".join(result)

def cmd_journal():
    entries = []
    try:
        with open(JF) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception:
        pass

    if not entries:
        return "**Journal**: No entries found."

    result = ["**Recent Journal**\n"]
    shown = 0
    for e in reversed(entries[-20:]):
        if shown >= 5:
            break
        body = (e.get("body") or "").strip()
        if len(body) < 20:
            continue
        ts = str(e.get("ts", "?"))[:16]
        icon = e.get("i", "?")
        title = str(e.get("x", ""))[:60]
        result.append("**%s %s** (%s)\n%s\n" % (icon, title, ts, body[:200]))
        shown += 1

    return "\n".join(result)

def cmd_chat(text):
    kb = load_json(os.path.join(DATA, "knowledge.json"), {})
    repos = list(kb.get("repos", {}).keys())
    if not repos:
        return "I haven't studied any repos yet."

    query = text.lower()
    matches = []
    for r in repos:
        rd = kb["repos"].get(r, {})
        if query in r.lower():
            matches.append("- %s (L%d)" % (r, rd.get("study_level", 0)))
        else:
            for p in rd.get("patterns", []) + rd.get("insights", []):
                if query in p.lower():
                    matches.append("- %s: %s" % (r, p[:80]))
                    break

    if matches:
        return "**Found in my KB:**\n\n" + "\n".join(matches[:10])
    else:
        deep_repos = [r for r in repos if kb["repos"].get(r, {}).get("study_level", 0) >= 3]
        return "I've studied %d repos but don't have specific knowledge about '%s'. My deep studies include: %s" % (
            len(repos), text[:50], ", ".join(deep_repos[:3]) if deep_repos else "none yet"
        )

def main():
    if len(sys.argv) < 2:
        print("Usage: goldie_cli.py <command> [text]")
        sys.exit(1)

    cmd = sys.argv[1].lower().strip("/")

    commands = {
        "status": cmd_status,
        "personality": cmd_personality,
        "kb": cmd_kb,
        "journal": cmd_journal,
    }

    if cmd in commands:
        print(commands[cmd]())
    else:
        print(cmd_chat(sys.argv[1]))

if __name__ == "__main__":
    main()
