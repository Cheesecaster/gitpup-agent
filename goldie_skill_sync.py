#!/usr/bin/env python3
"""Goldie → Hermes Skill Sync v1.

Curates Goldie's learned repo patterns into ONE local Hermes skill:
/root/.hermes/skills/goldie-learned-patterns/SKILL.md

Designed to be conservative:
- no secrets / credentials
- dedupe aggressively
- dry-run by default unless --apply
- max new entries per run
- can be called after study passes without causing skill bloat
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
KB_FILE = DATA / "knowledge.json"
STATE_FILE = DATA / "goldie_skill_sync_state.json"
LOG_FILE = DATA / "goldie_skill_sync.log"
DEFAULT_SKILL_DIR = Path(os.environ.get("GOLDIE_HERMES_SKILL_DIR", "/root/.hermes/skills/goldie-learned-patterns"))
SKILL_FILE = DEFAULT_SKILL_DIR / "SKILL.md"
BACKUP_DIR = DATA / "skill_sync_backups"

SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|auth[_-]?token|bot[_-]?token|bearer\s+[a-z0-9._%-]{12,}|secret|password|private[_-]?key|sk-[a-z0-9_-]{12,}|ghp_[a-z0-9_]{12,}|xox[baprs]-[a-z0-9-]{12,}|BEGIN\s+(?:RSA\s+|OPENSSH\s+|EC\s+)?PRIVATE\s+KEY)"
)
NOISE_RE = re.compile(r"(?i)^(none|n/a|null|unknown|todo|fixme|readme|package\.json)$")
CATEGORY_RULES = [
    ("agent-architecture", ["agent", "memory", "autonomous", "loop", "reflection", "planning", "tool", "orchestrat"]),
    ("knowledge-base", ["knowledge", "kb", "retrieval", "index", "semantic", "context", "embedding"]),
    ("developer-tools", ["cli", "command", "debug", "test", "lint", "build", "workflow", "repo", "github"]),
    ("ui-dashboard", ["ui", "dashboard", "frontend", "chart", "visual", "mobile", "responsive", "canvas"]),
    ("deployment", ["deploy", "nginx", "cron", "server", "vps", "service", "docker", "systemd"]),
    ("data-processing", ["data", "parser", "json", "pipeline", "cache", "stream", "batch"]),
]


def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def log(msg: str) -> None:
    DATA.mkdir(exist_ok=True)
    line = f"{now_iso()} {msg}"
    LOG_FILE.write_text((LOG_FILE.read_text(errors="ignore") if LOG_FILE.exists() else "") + line + "\n")
    print(line)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(errors="ignore"))
    except Exception:
        return default


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    tmp.replace(path)


def norm_text(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = re.sub(r"[`*_#]+", "", text).strip()
    return text


def fingerprint(text: str) -> str:
    core = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    stop = {"the", "and", "for", "with", "from", "that", "this", "into", "when", "where", "there", "have", "should", "must"}
    words = [w for w in core.split() if len(w) > 2 and w not in stop]
    return hashlib.sha1(" ".join(words[:24]).encode()).hexdigest()[:16]


def category_for(text: str) -> str:
    lo = text.lower()
    for cat, terms in CATEGORY_RULES:
        if any(t in lo for t in terms):
            return cat
    return "repo-patterns"


def quality_score(text: str, source_level: int = 0, repeated: int = 1) -> float:
    t = norm_text(text)
    if len(t) < 36 or len(t) > 360:
        return 0.0
    if SECRET_RE.search(t) or NOISE_RE.match(t):
        return 0.0
    words = re.findall(r"[A-Za-z][A-Za-z0-9_+-]+", t)
    uniq = len(set(w.lower() for w in words))
    score = 0.35
    score += min(0.20, uniq / 80)
    score += 0.18 if source_level >= 4 else 0.10 if source_level >= 3 else 0.04 if source_level >= 2 else 0
    score += min(0.18, max(0, repeated - 1) * 0.06)
    if any(x in t.lower() for x in ["pattern", "architecture", "workflow", "guard", "cache", "memory", "agent", "test", "deploy", "validate"]):
        score += 0.12
    if t.endswith("."):
        score += 0.02
    return round(min(score, 1.0), 3)


def collect_candidates(kb: dict[str, Any]) -> list[dict[str, Any]]:
    repos = kb.get("repos", {}) if isinstance(kb, dict) else {}
    raw: list[dict[str, Any]] = []

    for repo, rd in repos.items():
        if not isinstance(rd, dict):
            continue
        level = int(rd.get("study_level", 0) or 0)
        lang = rd.get("lang", "") or rd.get("language", "") or ""
        summary = norm_text(rd.get("summary", ""))
        topics = rd.get("topics", []) or []
        fields = [
            ("pattern", rd.get("patterns", [])),
            ("insight", rd.get("insights", [])),
            ("best_practice", rd.get("best_practices", [])),
        ]
        for kind, values in fields:
            if not isinstance(values, list):
                continue
            for value in values[:12]:
                text = norm_text(value)
                if not text:
                    continue
                fp = fingerprint(text)
                raw.append({
                    "fingerprint": fp,
                    "text": text,
                    "kind": kind,
                    "repo": repo,
                    "level": level,
                    "lang": lang,
                    "summary": summary[:180],
                    "topics": topics[:8] if isinstance(topics, list) else [],
                })

    # include canonical skill index, but only as secondary material
    for key, sd in (kb.get("skill_index", {}) or {}).items():
        if not isinstance(sd, dict):
            continue
        text = norm_text(sd.get("name") or key)
        if text:
            raw.append({
                "fingerprint": fingerprint(text),
                "text": text,
                "kind": "skill_index",
                "repo": ", ".join((sd.get("sources") or [])[:3]) if isinstance(sd.get("sources"), list) else "skill_index",
                "level": 3,
                "lang": "",
                "summary": "",
                "topics": sd.get("related_concepts", [])[:8] if isinstance(sd.get("related_concepts"), list) else [],
            })

    grouped: dict[str, dict[str, Any]] = {}
    for item in raw:
        fp = item["fingerprint"]
        g = grouped.setdefault(fp, {**item, "sources": [], "repeated": 0})
        g["repeated"] += 1
        if item["repo"] and item["repo"] not in g["sources"]:
            g["sources"].append(item["repo"])
        g["level"] = max(int(g.get("level", 0)), int(item.get("level", 0)))

    out = []
    for g in grouped.values():
        score = quality_score(g["text"], int(g.get("level", 0)), int(g.get("repeated", 1)))
        if score < 0.72:
            continue
        g["score"] = score
        g["category"] = category_for(g["text"])
        out.append(g)
    out.sort(key=lambda x: (x["score"], x.get("level", 0), x.get("repeated", 0)), reverse=True)
    return out


def existing_fingerprints(markdown: str) -> set[str]:
    return set(re.findall(r"<!--\s*goldie-fp:([a-f0-9]{16})\s*-->", markdown))


def initial_skill_md() -> str:
    return """---
name: goldie-learned-patterns
description: Curated implementation patterns learned by Goldie from progressive GitHub repo study. Auto-synced conservatively from /opt/gitpup/data/knowledge.json.
version: 1.0.0
author: Goldie + Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [goldie, learned-patterns, repo-study, agent-memory]
---

# Goldie Learned Patterns

This skill is Goldie's curated bridge from his repo-study knowledge base into Hermes Agent skills.
It is updated conservatively: only high-confidence, deduplicated, non-secret patterns are added.

Use this when Goldie discusses agent architecture, KB design, autonomous workflows, UI dashboards, developer tooling, deployment, or repo-derived implementation lessons.

## Operating principles

1. Treat these as reusable patterns, not universal laws.
2. Prefer patterns repeated across repos or extracted from deep L4 studies.
3. Keep implementation advice grounded, testable, and safe.
4. Never store credentials, private URLs, tokens, or environment values here.

## Learned entries

"""


def render_entry(c: dict[str, Any]) -> str:
    sources = ", ".join(c.get("sources", [])[:4]) or c.get("repo", "unknown")
    topics = ", ".join(str(x) for x in c.get("topics", [])[:5])
    bits = [
        f"### {c['category']}: {c['text'][:72].rstrip()}" + ("…" if len(c["text"]) > 72 else ""),
        f"<!-- goldie-fp:{c['fingerprint']} -->",
        "",
        f"- Pattern: {c['text']}",
        f"- Source repos: {sources}",
        f"- Confidence: {c['score']} | study_level: {c.get('level', 0)} | repeated: {c.get('repeated', 1)}",
    ]
    if topics:
        bits.append(f"- Related topics: {topics}")
    if c.get("summary"):
        bits.append(f"- Context: {c['summary']}")
    bits.extend(["", ""])
    return "\n".join(bits)


def sync(apply: bool, max_new: int, min_score: float, skill_file: Path = SKILL_FILE) -> dict[str, Any]:
    kb = load_json(KB_FILE, {})
    candidates = [c for c in collect_candidates(kb) if c.get("score", 0) >= min_score]
    current = skill_file.read_text(errors="ignore") if skill_file.exists() else initial_skill_md()
    existing = existing_fingerprints(current)
    new = [c for c in candidates if c["fingerprint"] not in existing]
    selected = new[:max_new]
    result = {
        "apply": apply,
        "skill_file": str(skill_file),
        "candidates": len(candidates),
        "existing": len(existing),
        "new_available": len(new),
        "selected": len(selected),
        "selected_items": [{"text": c["text"], "score": c["score"], "category": c["category"], "sources": c.get("sources", [])[:3]} for c in selected],
    }
    if not apply or not selected:
        return result

    skill_file.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if skill_file.exists():
        backup = BACKUP_DIR / ("SKILL.md." + dt.datetime.utcnow().strftime("%Y%m%d%H%M%S") + ".bak")
        shutil.copy2(skill_file, backup)
        result["backup"] = str(backup)

    addition = "".join(render_entry(c) for c in selected)
    new_md = current.rstrip() + "\n\n" + addition
    if SECRET_RE.search(addition):
        raise RuntimeError("secret-like content detected in generated skill addition")
    tmp = skill_file.with_suffix(".tmp")
    tmp.write_text(new_md)
    tmp.replace(skill_file)

    state = load_json(STATE_FILE, {})
    state.update({"last_sync": now_iso(), "last_selected": selected, "skill_file": str(skill_file)})
    save_json(STATE_FILE, state)
    log(f"synced {len(selected)} entries into {skill_file}")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write to Hermes skill; default is dry-run")
    ap.add_argument("--max-new", type=int, default=8)
    ap.add_argument("--min-score", type=float, default=0.72)
    ap.add_argument("--skill-file", default=str(SKILL_FILE))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = sync(args.apply, max(1, args.max_new), args.min_score, Path(args.skill_file))
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Goldie skill sync: candidates={result['candidates']} new={result['new_available']} selected={result['selected']} apply={result['apply']}")
        for item in result.get("selected_items", [])[:10]:
            print(f"- [{item['category']} score={item['score']}] {item['text'][:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
