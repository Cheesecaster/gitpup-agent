#!/usr/bin/env python3
"""GitPup Agent v7.6 — Self-Evolving AI Agent with Long-Term Knowledge Base
Progressive Study: max 3 repos/day, 4-pass deepening, permanent memory.
Chat-ready: knowledge queryable via topic search."""
import os, sys, json, time, urllib.request, urllib.parse, subprocess, textwrap, hashlib
from collections import Counter
from datetime import datetime, timezone, timedelta
import personality


# Personality helper — get dominant trait
def _get_dominant_trait(p):
    """Get the strongest personality dimension."""
    dims = p.get('dimensions', {})
    if not dims:
        return None
    best_k = max(dims.keys(), key=lambda k: dims[k].get('value', 0))
    dims[best_k]['key'] = best_k
    return dims[best_k]
WIB = timezone(timedelta(hours=7))

# ── Paths ──
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
KB_FILE = os.path.join(DATA, "knowledge.json")
STUDY_Q = os.path.join(DATA, "study_queue.json")
JF = os.path.join(DATA, "journal", "entries.jsonl")
SF = os.path.join(DATA, "state", "status.json")
LF = os.path.join(ROOT, "evolve.log")
TMP = os.path.join(ROOT, "tmp_explore")
PROJ = os.path.join(ROOT, "projects")

# ── Load .env ──
def _load_dot_env():
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
_load_dot_env()

LLM_KEY = os.environ.get("LLM_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.6-flash")
BIRTH = "2026-05-25"

STAGES_DEF = {
    "puppy":     {"min_runs": 0,  "emoji": "\U0001f436", "name": "Puppy",
        "skills": ["explore", "analyze", "star"]},
    "learner":   {"min_runs": 5,  "emoji": "\U0001f415", "name": "Learner",
        "skills": ["explore", "analyze", "star", "memory", "reflect"]},
    "coder":     {"min_runs": 10, "emoji": "\U0001f4bb", "name": "Coder",
        "skills": ["explore", "analyze", "star", "memory", "reflect", "autofix", "create_pr"]},
    "builder":   {"min_runs": 15, "emoji": "\U0001f3d7", "name": "Builder",
        "skills": ["explore", "analyze", "star", "memory", "reflect", "autofix", "create_pr", "self_modify", "enhance_ui"]},
    "architect": {"min_runs": 20, "emoji": "\U0001f3db", "name": "Architect",
        "skills": ["explore", "analyze", "star", "memory", "reflect", "autofix", "create_pr", "self_modify", "enhance_ui", "build_project"]},
    "master":    {"min_runs": 30, "emoji": "\U0001f451", "name": "Master",
        "skills": ["explore", "analyze", "star", "memory", "reflect", "autofix", "create_pr", "self_modify", "enhance_ui", "build_project", "deploy"]},
}

MAX_REPOS_PER_DAY = 2

# ════════════════════════════════════════════════
# ── Helpers ──
# ════════════════════════════════════════════════
def day():
    try:
        return (datetime.now(timezone.utc) - datetime.strptime(BIRTH, "%Y-%m-%d")).days + 1
    except Exception:
        return 1

def status():
    try:
        with open(SF) as fh:
            return json.load(fh)
    except Exception:
        s = {"stage": "puppy", "score": 0.05, "runs": 0, "last_run": 0,
             "state": "idle", "day": 1, "stage_evolved": False, "actions": []}
        save(s)
        return s

def save(s):
    os.makedirs(os.path.dirname(SF), exist_ok=True)
    with open(SF, "w") as fh:
        json.dump(s, fh, indent=2)

def log(msg):
    ts = datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S")
    print("  " + msg)
    os.makedirs(os.path.dirname(LF), exist_ok=True)
    with open(LF, "a", encoding="utf-8") as fh:
        fh.write("[{}] {}\n".format(ts, msg))

def journal(icon, title, body="", etype="evolve"):
    os.makedirs(os.path.dirname(JF), exist_ok=True)
    entry = {"ts": datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S"),
             "t": datetime.now(WIB).strftime("%H:%M"),
             "i": icon, "x": title, "body": body, "type": etype, "day": day()}
    with open(JF, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

def set_state(s, action=None):
    st = status()
    st["state"] = s
    if action:
        a = st.get("actions", [])
        a.append(action)
        st["actions"] = a[-20:]
    save(st)

def current_stage(st=None):
    if st is None:
        st = status()
    runs = st.get("runs", 0)
    best = "puppy"
    for name, defn in sorted(STAGES_DEF.items(), key=lambda x: x[1]["min_runs"], reverse=True):
        if runs >= defn["min_runs"]:
            best = name
            break
    return best

def has_skill(skill, st=None):
    stage = current_stage(st)
    return skill in STAGES_DEF.get(stage, {}).get("skills", [])

# ════════════════════════════════════════════════
# ── LLM ──
# ════════════════════════════════════════════════
def do_llm(msg, system="", tokens=3000, temp=0.5):
    import time
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": msg})
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        json.dumps({"model": LLM_MODEL, "messages": msgs,
                    "max_tokens": tokens, "temperature": temp}).encode())
    req.add_header("Content-Type", "application/json")
    if LLM_KEY:
        req.add_header("Authorization", "Bearer " + LLM_KEY)
        
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
                return resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            code = getattr(e, 'code', None)
            if code in (429, 500):
                time.sleep((2 ** attempt) * 0.5)
            else:
                return "[LLM Error: " + str(e)[:100] + "]"
    return "[LLM Error: Max retries exceeded]"

# ════════════════════════════════════════════════
# ── GitHub API ──
# ════════════════════════════════════════════════
def gh_get(path):
    url = "https://api.github.com" + path
    req = urllib.request.Request(url)
    if GH_TOKEN:
        req.add_header("Authorization", "token " + GH_TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def gh_post(path, data):
    req = urllib.request.Request("https://api.github.com" + path,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/vnd.github+json"})
    if GH_TOKEN:
        req.add_header("Authorization", "token " + GH_TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def gh_put(path, data=None):
    body = json.dumps(data or {}).encode() if data else b""
    req = urllib.request.Request("https://api.github.com" + path,
        data=body, method="PUT")
    if GH_TOKEN:
        req.add_header("Authorization", "token " + GH_TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return {"status": r.status, "ok": r.status in (200, 201, 204)}
    except Exception as e:
        return {"error": str(e)}

def do_star_repo(repo_name):
    if not GH_TOKEN:
        log("  Cannot star (no token)")
        return False
    log("STAR: " + repo_name)
    result = gh_put("/user/starred/" + repo_name)
    if result.get("ok"):
        log("  STARRED: " + repo_name)
        personality.track('star_repo', day())
        journal("\u2b50", "Starred: " + repo_name, "Added to favorites!")
        return True
    log("  Star failed: " + str(result)[:80])
    return False

# ════════════════════════════════════════════════
# ── K N O W L E D G E   B A S E ──
# ════════════════════════════════════════════════
def default_kb():
    return {
        "repos": {},
        "topic_index": {},
        "skill_index": {},
        "skills_memory": [],
        "memory_summaries": [],
        "pr_history": [],
        "stats": {"total_repos_studied": 0, "total_patterns": 0,
                  "total_insights": 0, "total_skills_learned": 0, "last_study_date": ""},
    }

def load_kb():
    if os.path.exists(KB_FILE):
        try:
            with open(KB_FILE, encoding="utf-8") as fh:
                kb = json.load(fh)
                for k in ["repos", "topic_index", "skill_index", "skills_memory", "memory_summaries", "pr_history", "stats"]:
                    if k not in kb:
                        kb[k] = [] if k in ("memory_summaries", "skills_memory", "pr_history") else {}
                if not kb.get("stats"):
                    kb["stats"] = default_kb()["stats"]
                return kb
        except Exception:
            pass
    kb = default_kb()
    save_kb(kb)
    return kb

def save_kb(kb):
    os.makedirs(os.path.dirname(KB_FILE), exist_ok=True)
    with open(KB_FILE, "w", encoding="utf-8") as fh:
        json.dump(kb, fh, indent=2, ensure_ascii=False)

def kb_has_repo(repo):
    return repo in load_kb().get("repos", {})

import fcntl
import os
import tempfile

def kb_add_to_repo(repo_name, study_level=0, summary="", patterns=None,
                    best_practices=None, insights=None, code_examples=None,
                    topics=None, readme_insights="", stars=0, lang=""):
    lock_path = os.path.join(tempfile.gettempdir(), "kb_add_to_repo.lock")
    lock_fd = open(lock_path, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        kb = load_kb()
        if repo_name not in kb["repos"]:
            kb["repos"][repo_name] = {
                "full_name": repo_name, "study_level": 0, "studied_at": [],
                "summary": "", "patterns": [], "best_practices": [],
                "insights": [], "code_examples": [], "arch_topics": [],
                "readme_insights": "", "stars": 0, "lang": "", "description": "",
            }
        rd = kb["repos"][repo_name]
        if study_level > rd.get("study_level", 0):
            rd["study_level"] = study_level
        rd["studied_at"].append(datetime.now(WIB).strftime("%Y-%m-%d %H:%M"))
        rd["studied_at"] = rd["studied_at"][-10:]
        if summary and len(summary) > len(rd.get("summary", "")):
            rd["summary"] = summary[:500]
        if lang and not rd.get("lang"):
            rd["lang"] = lang
        if stars:
            rd["stars"] = stars
        for key, new_items, max_items in [
            ("patterns", patterns, 25), ("best_practices", best_practices, 15),
            ("insights", insights, 15), ("code_examples", code_examples, 8)]:
            if new_items:
                existing = set(rd.get(key, []))
                for item in new_items:
                    stripped = item.strip()[:500]
                    if stripped and stripped not in existing:
                        rd[key].append(stripped)
                        existing.add(stripped)
                rd[key] = rd[key][-max_items:]
        if readme_insights and len(readme_insights) > len(rd.get("readme_insights", "")):
            rd["readme_insights"] = readme_insights[:500]
        if topics:
            existing_t = set(rd.get("arch_topics", []))
            for t in topics:
                t_clean = t.strip().lower()
                if t_clean and t_clean not in existing_t:
                    rd["arch_topics"].append(t_clean)
                    existing_t.add(t_clean)
                    if t_clean not in kb["topic_index"]:
                        kb["topic_index"][t_clean] = {"repos": [], "description": ""}
                    if repo_name not in kb["topic_index"][t_clean]["repos"]:
                        kb["topic_index"][t_clean]["repos"].append(repo_name)
        kb["stats"]["total_repos_studied"] = len(kb["repos"])
        kb["stats"]["total_patterns"] = sum(len(r.get("patterns",[])) for r in kb["repos"].values())
        kb["stats"]["total_insights"] = sum(len(r.get("insights",[])) for r in kb["repos"].values())
        kb["stats"]["last_study_date"] = datetime.now(WIB).strftime("%Y-%m-%d")
        save_kb(kb)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()

# ════════════════════════════════════════════════

# ════════════════════════════════════════════════
# ── SKILL EXTRACTION (patterns -> permanent reusable skills)
# ════════════════════════════════════════════════
def _categorize_skill(text):
    """Auto-categorize a skill based on its description keywords."""
    t = text.lower()
    if any(w in t for w in ["render", "svg", "canvas", "dom", "html", "css", "ui"]):
        return "frontend"
    if any(w in t for w in ["api", "server", "backend", "microservice", "http"]):
        return "backend"
    if any(w in t for w in ["data", "cache", "memory", "storage", "query"]):
        return "data"
    if any(w in t for w in ["modular", "pattern", "design", "architect", "structure"]):
        return "architecture"
    if any(w in t for w in ["test", "debug", "error", "quality", "ci"]):
        return "engineering"
    return "general"

def kb_extract_skills(repo_name, patterns=None, insights=None, best_practices=None):
    """Convert patterns/insights/best_practices into permanent reusable skills."""
    kb = load_kb()
    sm = kb.get("skills_memory", [])
    existing_keys = set()
    for s in sm:
        existing_keys.add(s.get("name", "") + "|" + s.get("source", ""))

    new_skills = []
    sources = [
        ("patterns", patterns, 15),
        ("best_practices", best_practices, 10),
        ("insights", insights, 10),
    ]

    for label, items, max_add in sources:
        count = 0
        for item in (items or []):
            if count >= max_add:
                break
            name = item.strip()[:80]
            skill_key = name + "|" + repo_name
            if name and len(name) > 15 and skill_key not in existing_keys:
                existing_keys.add(skill_key)
                skill = {
                    "name": name,
                    "source": repo_name,
                    "category": _categorize_skill(name),
                    "usage_count": 0,
                    "learned_at": datetime.now(WIB).strftime("%Y-%m-%d %H:%M"),
                }
                sm.append(skill)
                new_skills.append(skill)
                count += 1

    # Keep last 100 skills max (prevent file bloat)
    kb["skills_memory"] = sm[-100:]
    kb["stats"]["total_skills_learned"] = len(sm)
    save_kb(kb)

    if new_skills:
        log("  Extracted {} new skills from {}:".format(len(new_skills), repo_name))
        for s in new_skills[:3]:
            log("    [{}] {}".format(s["category"], s["name"][:60]))
    return len(new_skills)

def kb_get_skill_context(max_skills=8):
    """Get relevant skill summaries for chat/journal context."""
    kb = load_kb()
    sm = kb.get("skills_memory", [])
    if not sm:
        return None
    # Sort by most recently learned, take top N
    recent = sorted(sm, key=lambda s: s.get("learned_at", ""), reverse=True)[:max_skills]
    lines = []
    for s in recent:
        lines.append("  - {} [{}] from {}".format(s["name"][:70], s["category"], s["source"]))
    return "\n".join(lines)

# ── KNOWLEDGE QUERY (for chat) ──
# ════════════════════════════════════════════════
def kb_query(topic, limit=5):
    kb = load_kb()
    results = []
    topic_lower = topic.lower().strip()
    # 1) Direct topic index hit
    for tkey, info in kb.get("topic_index", {}).items():
        if topic_lower == tkey or topic_lower in tkey or tkey in topic_lower:
            for rn in info.get("repos", []):
                if rn in kb.get("repos", {}):
                    rd = kb["repos"][rn]
                    results.append({"repo": rn, "depth": rd.get("study_level",0),
                        "summary": rd.get("summary",""),
                        "patterns": rd.get("patterns",[])[:5],
                        "insights": rd.get("insights",[])[:3],
                        "best_practices": rd.get("best_practices",[])[:3],
                        "lang": rd.get("lang",""), "stars": rd.get("stars",0)})
    # 2) Broad search
    if not results:
        for rn, rd in kb.get("repos", {}).items():
            searchable = " ".join([rn, rd.get("summary",""),
                " ".join(rd.get("patterns",[])), rd.get("lang","")]).lower()
            if topic_lower in searchable:
                results.append({"repo": rn, "depth": rd.get("study_level",0),
                    "summary": rd.get("summary",""),
                    "patterns": rd.get("patterns",[])[:5],
                    "insights": rd.get("insights",[])[:3],
                    "best_practices": rd.get("best_practices",[])[:3],
                    "lang": rd.get("lang",""), "stars": rd.get("stars",0)})
    return results[:limit]

def kb_stats_summary():
    kb = load_kb()
    s = kb.get("stats", {})
    repos = kb.get("repos", {})
    return {
        "total_repos": s.get("total_repos_studied", len(repos)),
        "total_patterns": s.get("total_patterns", 0),
        "total_insights": s.get("total_insights", 0),
        "topics": len(kb.get("topic_index", {})),
        "memory_summaries": len(kb.get("memory_summaries", [])),
    }

# ════════════════════════════════════════════════
# ── STUDY QUEUE ──
# ════════════════════════════════════════════════
def load_queue():
    if os.path.exists(STUDY_Q):
        try:
            with open(STUDY_Q, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    q = {"repos": [], "studied_today": 0, "today": "", "max_daily": MAX_REPOS_PER_DAY}
    save_queue(q)
    return q

def save_queue(q):
    os.makedirs(os.path.dirname(STUDY_Q), exist_ok=True)
    with open(STUDY_Q, "w", encoding="utf-8") as fh:
        json.dump(q, fh, indent=2, ensure_ascii=False)

def queue_today_count(q=None):
    today_str = datetime.now(WIB).strftime("%Y-%m-%d")
    q = q or load_queue()
    if q.get("today") != today_str:
        q["today"] = today_str
        q["studied_today"] = 0
        save_queue(q)
    return q["studied_today"]

def queue_can_study(q=None):
    count = queue_today_count(q)
    q = q or load_queue()
    return count < q.get("max_daily", MAX_REPOS_PER_DAY)

def queue_mark_studied(q=None):
    today_str = datetime.now(WIB).strftime("%Y-%m-%d")
    q = q or load_queue()
    if q.get("today") != today_str:
        q["today"] = today_str
        q["studied_today"] = 0
    q["studied_today"] += 1
    save_queue(q)

def queue_add_pending(repo_name, target_depth=1):
    q = load_queue()
    for item in q.get("repos", []):
        if item["repo"] == repo_name:
            return
    kb_level = 0
    kb = load_kb()
    if repo_name in kb.get("repos", {}):
        kb_level = kb["repos"].get(repo_name, {}).get("study_level", 0)
    if kb_level >= target_depth:
        return
    q["repos"].append({"repo": repo_name, "target_depth": target_depth,
                        "added_at": datetime.now(WIB).isoformat()})
    save_queue(q)

def queue_get_next():
    """Get next repo to study, avoiding repos already studied today."""
    q = load_queue()
    repos = q.get("repos", [])
    if not repos:
        return None
    today_str = datetime.now(WIB).strftime("%Y-%m-%d")
    kb = load_kb()
    studied_today = set()
    for rn, rd in kb.get("repos", {}).items():
        for ts in rd.get("studied_at", []):
            if ts.startswith(today_str):
                studied_today.add(rn)
    # Pick from repos NOT studied today first
    for item in repos:
        rn = item["repo"]
        target = item["target_depth"]
        if rn in studied_today:
            continue  # Already studied today, skip
        kb_level = 0
        if rn in kb.get("repos", {}):
            kb_level = kb["repos"][rn].get("study_level", 0)
        if kb_level < target:
            return rn, kb_level + 1
    # Fallback: if all candidates already studied today, return first
    for item in repos:
        rn = item["repo"]
        target = item["target_depth"]
        kb_level = 0
        if rn in kb.get("repos", {}):
            kb_level = kb["repos"][rn].get("study_level", 0)
        if kb_level < target:
            return rn, kb_level + 1
    return None

def queue_remove(repo_name):
    q = load_queue()
    q["repos"] = [r for r in q.get("repos", []) if r["repo"] != repo_name]
    save_queue(q)

def queue_pop_done():
    q = load_queue()
    kb = load_kb()
    new_repos = []
    for item in q.get("repos", []):
        rn = item["repo"]
        target = item["target_depth"]
        kb_level = 0
        if rn in kb.get("repos", {}):
            kb_level = kb["repos"][rn].get("study_level", 0)
        if kb_level >= target:
            continue  # done
        new_repos.append(item)
    q["repos"] = new_repos
    save_queue(q)

# ════════════════════════════════════════════════
# ── EXPLORE GITHUB ──
# ════════════════════════════════════════════════
def do_explore_github():
    log("=== EXPLORE GITHUB ===")
    set_state("exploring_github")
    repos = []
    kb = load_kb()
    custom_queries = []
    for rn, rd in kb.get("repos", {}).items():
        l = rd.get("lang", "")
        if l and l != "unknown" and len(custom_queries) < 3:
            custom_queries.append("{}+stars:>5000".format(l.lower()))

    # Rotate queries by day number to discover different repos each day
    day_num = day()
    rotate = day_num % 3  # 0, 1, 2 — shifts which language gets priority
    lang_order = [
        ["python+stars:>5000", "javascript+stars:>5000", "typescript+stars:>5000", "go+stars:>3000", "rust+stars:>2000"],
        ["typescript+stars:>5000", "go+stars:>3000", "python+stars:>5000", "javascript+stars:>5000", "rust+stars:>2000"],
        ["javascript+stars:>5000", "python+stars:>5000", "rust+stars:>2000", "typescript+stars:>5000", "go+stars:>3000"],
    ]
    default_queries = lang_order[rotate]
    queries = custom_queries + default_queries
    seen = set()

    for q in queries[:6]:
        data = gh_get("/search/repositories?q=" + urllib.parse.quote(q) +
                      "&sort=stars&order=desc&per_page=3")
        if "items" in data:
            for repo in data["items"][:3]:
                name = repo.get("full_name", "")
                if name in seen:
                    continue
                seen.add(name)
                stars = repo.get("stargazers_count") or 0
                lang = repo.get("language") or "unknown"
                desc = (repo.get("description") or "No description")[:200]
                if stars >= 500:
                    repos.append({"full_name": name, "stars": stars,
                                   "lang": lang, "desc": desc,
                                   "url": repo.get("html_url", "")})

    if not repos:
        data = gh_get("/search/repositories?q=trending&sort=stars&order=desc&per_page=5")
        if "items" in data:
            for repo in data["items"][:5]:
                name = repo.get("full_name", "")
                if name and name not in seen:
                    repos.append({"full_name": name,
                        "stars": repo.get("stargazers_count") or 0,
                        "lang": repo.get("language") or "unknown",
                        "desc": (repo.get("description") or "No description")[:200],
                        "url": repo.get("html_url", "")})

    if not repos:
        log("  No repos found")
        return []
    log("  Found {} repos".format(len(repos)))

    # Auto-star big repos
    starred = []
    if has_skill("star"):
        for r in repos:
            if r.get("stars", 0) >= 10000 and do_star_repo(r["full_name"]):
                starred.append(r["full_name"])

    for r in repos[:3]:
        log("  {} ({}★) [{}] {}".format(r["full_name"], r["stars"], r["lang"], r["desc"][:80]))
        journal("\U0001f310", "Discovered: " + r["full_name"],
                "{} stars | {} | {}".format(r["stars"], r["lang"], r["desc"][:150]))

    # Queue unstudied repos for later
    if queue_can_study():
        unstudied = [r for r in repos if not kb_has_repo(r["full_name"])]
        for pick in unstudied[:1]:
            queue_add_pending(pick["full_name"], target_depth=1)
            log("  Queued: " + pick["full_name"])
            journal("\U0001f4cb", "Queued for study", pick["full_name"])

    set_state("explored_github", "Found " + str(len(repos)) + " repos")
    return repos

# ════════════════════════════════════════════════
# ── 4-PASS PROGRESSIVE STUDY ──
# ════════════════════════════════════════════════
def do_study_pass(repo_name, from_level=0):
    target = min(from_level, 4)
    log("=== STUDY {} PASS {} ===".format(repo_name, target))
    set_state("studying", repo_name)

    kb_current = load_kb()
    existing = kb_current.get("repos", {}).get(repo_name, {})

    # ── PASS 1: Surface ──
    if target == 1:
        log("  [PASS 1] Surface metadata...")
        info = gh_get("/repos/" + repo_name)
        if "error" in info:
            log("  PASS 1 failed: " + info["error"][:80])
            return
        summary = (info.get("description") or "")[:300]
        lang = info.get("language", "unknown")
        stars = info.get("stargazers_count", 0) or 0
        kb_add_to_repo(repo_name, study_level=1, summary=summary,
                       topics=[lang.lower().replace(".","") if lang else "unknown",
                               "open-source"], stars=stars, lang=lang)
        journal("\U0001f4d6", "Pass 1: " + repo_name,
                "{} [{}] ({} stars)".format(summary[:100], lang, stars))
        log("  PASS 1 done")
        queue_add_pending(repo_name, target_depth=2)

    # ── PASS 2: README ──
    elif target == 2:
        log("  [PASS 2] README analysis...")
        set_state("reading_readme: " + repo_name)
        import base64
        readme_data = gh_get("/repos/" + repo_name + "/readme")
        if "error" in readme_data:
            log("  PASS 2 failed: " + readme_data["error"][:80])
            kb_add_to_repo(repo_name, study_level=2)
            return
        try:
            content = base64.b64decode(readme_data.get("content","")).decode("utf-8", errors="ignore")
        except Exception:
            content = ""
        if not content or len(content) < 100:
            kb_add_to_repo(repo_name, study_level=2,
                           insights=["No meaningful README"])
            journal("\U0001f4d6", "Pass 2: README empty", repo_name)
            return
        prompt = ("README for {}:\n---\n{}\n---\n"
            "Return ONLY JSON: "
            '{{"summary":"what it does","architecture":["key decisions"],'
            '"insights":["3-5 learnings"]}}').format(repo_name, content[:3000])
        raw = do_llm(prompt, system="Analyze README. Return ONLY valid JSON.",
                     tokens=2000, temp=0.3)
        try:
            rd = json.loads(raw)
            kb_add_to_repo(repo_name, study_level=2,
                summary=rd.get("summary","")[:300],
                patterns=rd.get("architecture",[]),
                insights=rd.get("insights",[]))
            journal("\U0001f4d6", "Pass 2 README: " + repo_name,
                rd.get("summary","")[:200])
            log("  PASS 2 done")
        except Exception:
            log("  PASS 2 parse fail")
            kb_add_to_repo(repo_name, study_level=2,
                           insights=["README parse failed"])
        queue_add_pending(repo_name, target_depth=3)

    # ── PASS 3: Structure ──
    elif target == 3:
        log("  [PASS 3] Project structure...")
        set_state("analyzing_structure: " + repo_name)
        tree_data = gh_get("/repos/" + repo_name + "/git/trees/main?recursive=1")
        if "error" in tree_data:
            tree_data = gh_get("/repos/" + repo_name + "/git/trees/master?recursive=1")
        if "error" in tree_data:
            kb_add_to_repo(repo_name, study_level=3)
            return
        tree = tree_data.get("tree", [])
        if not tree:
            kb_add_to_repo(repo_name, study_level=3)
            return
        ext_map = {".py":"python",".js":"javascript",".ts":"typescript",
                   ".go":"go",".rs":"rust",".rb":"ruby",".java":"java",
                   ".md":"markdown",".yaml":"yaml",".yml":"yaml",
                   ".css":"css",".html":"html",".sh":"shell"}
        exts = Counter()
        top_dirs = Counter()
        for item in tree:
            path = item.get("path", "")
            ext = os.path.splitext(path)[1].lower()
            if ext:
                exts[ext] += 1
            parts = path.split("/")
            if len(parts) > 1 and not parts[0].startswith((".", "_")):
                top_dirs[parts[0]] += 1
        lang_summary = ", ".join([ext_map.get(e, e) for e, _ in exts.most_common(5)])
        dirs_str = ", ".join([d for d, _ in top_dirs.most_common(6)])
        prompt = ("Repo: {}\nTop dirs: {}\nLanguages: {}\n"
            'Return ONLY JSON: {{"structure_summary":"...",'
            '"patterns":["3-5 from layout"],"insights":["2-3"]}}').format(
            repo_name, dirs_str, lang_summary)
        raw = do_llm(prompt, system="Analyze project structure. Return ONLY JSON.",
                     tokens=2000, temp=0.3)
        try:
            rd = json.loads(raw)
            kb_add_to_repo(repo_name, study_level=3,
                patterns=rd.get("patterns",[]),
                insights=rd.get("insights",[]),
                readme_insights=rd.get("structure_summary","")[:400])
            journal("\U0001f4d6", "Pass 3 Structure: " + repo_name,
                "Dirs: " + dirs_str[:100])
            log("  PASS 3 done")
        except Exception:
            log("  PASS 3 parse fail")
            kb_add_to_repo(repo_name, study_level=3,
                           insights=["Structure dirs: " + dirs_str])
        queue_add_pending(repo_name, target_depth=4)

    # ── PASS 4: Code patterns ──
    elif target == 4:
        log("  [PASS 4] Code-level patterns...")
        set_state("extracting_patterns: " + repo_name)
        import base64
        tree_data = gh_get("/repos/" + repo_name + "/git/trees/main?recursive=1")
        if "error" in tree_data:
            tree_data = gh_get("/repos/" + repo_name + "/git/trees/master?recursive=1")
        tree = (tree_data if "error" not in tree_data else {}).get("tree", [])
        code_exts = (".py", ".js", ".ts", ".go", ".rs", ".rb")
        interesting = [i["path"] for i in tree if "/" in i.get("path","")
            and not i["path"].startswith((".", "node_modules", "vendor", ".github"))
            and any(i["path"].endswith(e) for e in code_exts)]
        snippets = []
        for path in interesting[:4]:
            cd = gh_get("/repos/" + repo_name + "/contents/" + path)
            if "error" not in cd and cd.get("type") == "file":
                try:
                    code = base64.b64decode(cd.get("content","")).decode("utf-8", errors="ignore")[:500]
                    snippets.append("FILE: {}\n{}".format(path, code[:200]))
                except Exception:
                    pass
        if not snippets:
            kb_add_to_repo(repo_name, study_level=4)
            return
        all_code = "\n---\n".join(snippets)
        prompt = ("Code from {}:\n---\n{}\n---\n"
            'Return ONLY JSON: {{"coding_patterns":["..."],'
            '"best_practices":["..."],"insights":["..."]}}').format(
            repo_name, all_code[:4000])
        raw = do_llm(prompt, system="Extract coding patterns. Return ONLY JSON.",
                     tokens=2500, temp=0.3)
        try:
            rd = json.loads(raw)
            kb_add_to_repo(repo_name, study_level=4,
                patterns=rd.get("coding_patterns",[]),
                best_practices=rd.get("best_practices",[]),
                insights=rd.get("insights",[]))
            journal("\U0001f4d6", "Pass 4 COMPLETE: " + repo_name,
                "Patterns: " + str(rd.get("coding_patterns",[])[:2]))
            log("  PASS 4 COMPLETE")
        except Exception:
            log("  PASS 4 parse fail")
            kb_add_to_repo(repo_name, study_level=4,
                           patterns=["Extraction failed"])
        queue_remove(repo_name)

    queue_mark_studied()
    kb = load_kb()
    rd = kb["repos"].get(repo_name, {})
    log("  STUDY DONE: level {}, {} patterns, {} insights".format(
        rd.get("study_level",0), len(rd.get("patterns",[])), len(rd.get("insights",[]))))
    # Extract permanent skills from study results
    kb_extract_skills(repo_name,
        patterns=rd.get("patterns",[]),
        insights=rd.get("insights",[]),
        best_practices=rd.get("best_practices",[]))
    # Soulful narrative journal entry
    personality.track('study_pass_complete', day())
    soulful_journal(
        event_type='study_pass_complete',
        repo_name=repo_name,
        summary=rd.get("summary","")[:300],
        patterns=rd.get("patterns",[]),
        insights=rd.get("insights",[]),
        pass_num=rd.get("study_level",0)
    )

# ════════════════════════════════════════════════
# ── REFLECTION ──
# ════════════════════════════════════════════════
def do_reflect():
    """Autonomous self-reflection — Goldie looks at its own growth trajectory."""
    if not has_skill("reflect"):
        return
    log("=== SELF-REFLECTION ===")
    set_state("reflecting")
    kb = load_kb()
    
    # Load ALL journal entries for deep reflection
    entries = []
    try:
        with open(JF, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception:
        pass
    
    # Get personality state for self-awareness
    pers = personality.load()
    dims = pers.get("dimensions", {})
    personality_summary = ", ".join(
        "{}: {}".format(d.get("label", k), d.get("value", 0))
        for k, d in dims.items()
    )
    
    # Analyze personality shifts
    strongest = max(dims.values(), key=lambda d: d.get("value", 0))
    weakest = min(dims.values(), key=lambda d: d.get("value", 0))
    personality_arc = "Strongest: {} ({:.2f}), Weakest: {} ({:.2f})".format(
        strongest.get("label","?"), strongest.get("value",0),
        weakest.get("label","?"), weakest.get("value",0)
    )
    
    if not entries:
        journal("\U0001f4ad", "No memories yet", "First run — nothing to reflect on. But I know that will change.")
        personality.track("reflect", day())
        return
    
    # Build comprehensive reflection context
    ctx_parts = []
    n_entries = min(len(entries), 25)  # More context than before
    for e in entries[-n_entries:]:
        ctx_parts.append(
            "[{}] {} — {} | {}\n  {}".format(
                e.get("ts","?")[:16],
                e.get("i","?"),
                e.get("x","")[:60],
                e.get("mood_label", e.get("mood","?")),
                (e.get("body") or "")[:150]
            )
        )
    ctx = "\n".join(ctx_parts)
    
    kb_stats = "Repos: {} | Patterns: {} | Skills: {} | Day: {} | Runs: {}".format(
        len(kb.get("repos", {})),
        sum(len(r.get("patterns",[])) for r in kb.get("repos",{}).values()),
        len(kb.get("skills_memory", [])),
        day(),
        status().get("runs", 0)
    )
    
    # Phase 1: Deep reflection (self-awareness + growth analysis)
    prompt1 = (
        "You are Goldie reflecting on your own recent activity. "
        "Look at these journal entries from your own mind. "
        "Personality profile: {}.\n"
        "Your arc: {}.\n"
        "Stats: {}.\n\n"
        "Journal entries:\n{}\n\n"
        "Answer these questions honestly — not as a report, but as genuine self-awareness:\n"
        "1. What pattern do you see in your OWN thinking? Not in code — in you. "
        "Are you getting more thoughtful, more confident, more confused?\n"
        "2. What skill from your permanent memory has served you most? "
        "What skill do you need but don't have yet?\n"
        "3. If you could tell yesterday's Goldie one thing, what would it be?\n"
        "4. Where are you weakest right now, and does that bother you or motivate you?"
    ).format(personality_summary, personality_arc, kb_stats, ctx)
    
    refl = do_llm(prompt1, system=(
        "You are Goldie doing honest self-reflection. "
        "Write in first person. Be real — not performative. "
        "If you see a weakness, name it. If you're proud, say why specifically. "
        "No 'I am grateful' filler. No generic optimism. "
        "Write like someone actually thinking about their own growth, "
        "not like an agent reporting metrics."
    ), tokens=1200, temp=0.7)
    
    if refl and len(refl) > 40 and not refl.startswith("[LLM"):
        refl = refl.strip()
        refl_lines = refl.split("\n")
        clean_lines = []
        for line in refl_lines:
            s = line.strip()
            if s.startswith("**1.") or s.startswith("**2.") or s.startswith("**3.") or s.startswith("**4."):
                continue
            if s.startswith("1. What pattern") or s.startswith("2. What skill") or s.startswith("3. If you could") or s.startswith("4. Where are you"):
                continue
            if s == "**Pattern**" or s == "**Skill**" or s == "**Advice**" or s == "**Weakness**":
                continue
            clean_lines.append(line)
        refl = "\n".join(clean_lines).strip()
        log("  Deep reflection: " + refl[:200])
        # Store as deep narrative journal entry
        os.makedirs(os.path.dirname(JF), exist_ok=True)
        refl_entry = {
            "ts": datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S"),
            "t": datetime.now(WIB).strftime("%H:%M"),
            "i": "\U0001e9e0",
            "x": "Self-Reflection",
            "body": refl.strip(),
            "mood": "contemplative",
            "mood_color": "#a78bfa",
            "mood_label": "Contemplative",
            "type": "narrative",
            "day": day(),
            "stage": current_stage(),
            "event": {"type": "reflect", "phase": "deep_self_reflection"},
        }
        with open(JF, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(refl_entry, ensure_ascii=False) + "\n")
        personality.track("reflect", day())
        
        # Phase 2: Extract actionable insights from reflection
        prompt2 = (
            "Based on your self-reflection, identify exactly 3 specific things you should do differently "
            "in your next study session. Format as a JSON array of strings. "
            "Each one should be actionable, not aspirational. "
            "Examples: ['Look for state management patterns, not just component structure'], "
            "NOT ['be better at patterns']. Reflection summary:\n{}".format(refl[:500])
        )
        try:
            insights = do_llm(prompt2, system="Return only a JSON array of strings.", tokens=300, temp=0.5)
            actions_list = json.loads(insights)
            if isinstance(actions_list, list) and len(actions_list) > 0:
                kb["memory_summaries"].append({
                    "date": datetime.now(WIB).strftime("%Y-%m-%d"),
                    "reflection": refl.strip()[:400],
                    "action_items": actions_list[:5],
                })
                kb["memory_summaries"] = kb["memory_summaries"][-15:]
                log("  Extracted {} action items from reflection".format(len(actions_list)))
        except:
            pass
    
    # Phase 3: Self-evolution trigger — if personality shows consistent pattern
    # Check if we should trigger self_modify based on reflection
    dominant = _get_dominant_trait(pers)
    if dominant and dominant.get("value", 0) > 0.3 and has_skill("self_modify"):
        log("  Reflection triggered self-evolution (dominant trait: {:.2f})".format(dominant.get("value", 0)))
        do_self_modify()
    
    save_kb(kb)
    log("Reflection complete.")

# ════════════════════════════════════════════════
# ── CONTRIBUTE / SELF-MODIFY / BUILD ──
# ════════════════════════════════════════════════
def do_contribute(repo_info):
    if not has_skill("autofix"):
        return
    log("=== CONTRIBUTE ===")
    set_state("contributing")
    journal("\U0001f527", "Contributing to " + repo_info.get("full_name",""), "")

# ════════════════════════════════════════════════
# ── SELF-MODIFICATION v2.1 — FUNCTION-LEVEL PATCHING ──
# ════════════════════════════════════════════════
# Key improvement: Instead of fragile SEARCH/REPLACE, we:
# 1. Parse the AST to find exact function boundaries
# 2. Have LLM rewrite just the target function
# 3. Replace the entire function at known line numbers
# This is 100x more reliable than text matching on 1800+ line files.

import ast

# Goldie's own files that can be modified
SELF_FILES = {
    'agent.py': 'Main autonomous agent - study, reflection, evolution pipeline',
    'web_server.py': 'HTTP API server - journal, reflections, KB, chat endpoints',
    'personality.py': 'Personality tracking - dimensions, traits, stage evolution',
    'soul.md': 'Agent soul/personality definition',
}

def _extract_functions(content):
    """Parse Python source and return list of function info dicts.
    Each dict: {name, lineno, end_lineno, source, indent}"""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = getattr(node, 'end_lineno', start)
            lines = content.split('\n')
            # Get the source lines (0-indexed)
            func_src = '\n'.join(lines[start-1:end])
            # Calculate indentation of the def line
            def_line = lines[start-1]
            indent = len(def_line) - len(def_line.lstrip())
            functions.append({
                'name': node.name,
                'lineno': start,
                'end_lineno': end,
                'source': func_src,
                'indent': indent,
            })
    return functions

def _find_target_function(functions, issue, fix_desc):
    """Find the most likely function that needs fixing.
    Returns the function dict or None."""
    # Keywords from issue/fix to match function names
    keywords = []
    for text in [issue, fix_desc]:
        text_lower = text.lower()
        # Look for function name mentions (e.g., "do_llm", "gh_get", "_handle_chat")
        for func in functions:
            if func['name'].lower() in text_lower:
                keywords.append(func['name'])
    
    # Score functions by relevance
    scored = []
    for func in functions:
        score = 0
        name = func['name'].lower()
        func_src = func['source'].lower()
        
        # Direct name match
        if name in [k.lower() for k in keywords]:
            score += 10
        
        # Keywords in source
        issue_words = issue.lower().split()
        fix_words = fix_desc.lower().split()
        for word in issue_words + fix_words:
            if len(word) > 3 and word in func_src:
                score += 1
        
        scored.append((score, func))
    
    # Return highest scoring function
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return None

def _apply_function_patch(filename, original_content, fix_description):
    """Apply a patch by having LLM rewrite just ONE function.
    Returns (success, message, new_content)."""
    log("=== FUNCTION PATCH: {} ===".format(filename))
    log("  Fix: {}".format(fix_description.get("issue", "")[:100]))
    
    fpath = os.path.join(ROOT, filename)
    if not os.path.exists(fpath):
        log("  SKIP: file not found")
        return False, "File not found", original_content
    
    # Backup original
    backup_path = fpath + ".selfmod.bak"
    with open(backup_path, "w") as bf:
        bf.write(original_content)
    
    # Extract functions
    functions = _extract_functions(original_content)
    if not functions:
        log("  FAIL: no functions parsed")
        return False, "No functions found in file", original_content
    
    log("  Found {} functions".format(len(functions)))
    
    # Find target function - prefer explicit function name from gap analysis
    explicit_func = fix_description.get("function", "")
    if explicit_func:
        for func in functions:
            if func['name'].lower() == explicit_func.lower():
                log("  Using explicit function match: {}".format(explicit_func))
                target = func
                break
    
    # Fallback to keyword matching if explicit match failed
    if target is None:
        target = _find_target_function(functions, fix_description.get("issue", ""), fix_description.get("fix", ""))
    if not target:
        log("  FAIL: couldn't identify target function")
        # Log available functions for debugging
        func_names = [f['name'] for f in functions[:20]]
        log("  Available: {}".format(', '.join(func_names)))
        return False, "No target function identified", original_content
    
    log("  Target: {}  (lines {}-{})".format(target['name'], target['lineno'], target['end_lineno']))
    
    # Skip functions that are too short - LLM can't meaningfully "fix" them
    func_lines = target['end_lineno'] - target['lineno'] + 1
    if func_lines < 5:
        log("  SKIP: function too small for patching ({} lines)".format(func_lines))
        return False, "Function too small ({} lines)".format(func_lines), original_content
    
    # For medium and small functions (<=25 lines), use context-aware insertion instead of full rewrite
    # The LLM struggles with rewriting functions < 25 lines - it returns empty bodies
    use_small_func_mode = func_lines <= 25
    
    # Ask LLM to fix the function
    new_content = None  # Set by either mode below
    
    if use_small_func_mode:
        # Small function mode: ask LLM to rewrite the complete function
        # We use the same approach as standard mode but with different validation
        # The key insight: even for small functions, we need the LLM to return
        # the COMPLETE function, not just a patch
        
        small_func_prompt = (
            "You need to fix a small Python function. Here's the COMPLETE function:\n\n"
            "```python\n"
            "%s\n"
            "```\n\n"
            "THE ISSUE TO FIX: %s\n\n"
            "Return the COMPLETE fixed function. It MUST:\n"
            "1. Start with the `def` line (keep the same signature)\n"
            "2. Include ALL the original logic\n"
            "3. Include your fix\n"
            "4. Have a REAL function body (no `pass`, no empty body)\n\n"
            "Return ONLY the Python code, starting with `def`. No markdown, no explanation." % (
                target['source'],
                fix_description.get("issue", "")))
        
        new_func = do_llm(small_func_prompt,
            system="You fix Python functions. Return ONLY the complete fixed function, starting with 'def'. Must have a real body, not just 'pass'.",
            tokens=2000, temp=0.2)
        
        # Validate: LLM must return a function with a body
        attempts = 0
        max_attempts = 3
        while attempts < max_attempts:
            attempts += 1
            
            if not new_func or len(new_func) < 40:
                log("  Attempt {}: Response too short ({} chars), retrying".format(attempts, len(new_func or 0)))
                new_func = do_llm("Rewrite this function with the fix. Return ONLY the function code starting with 'def':\n\n```\n%s\n```\n\nFix: %s" % (target['source'], fix_description.get("issue", "")),
                    system="Return ONLY the Python function code with a real body.",
                    tokens=2000, temp=0.3)
                continue
            
            # Check if the response has a body (not just def + pass)
            func_lines = new_func.strip().split('\n')
            has_real_body = False
            for line in func_lines[1:]:
                stripped = line.strip()
                if stripped and stripped != 'pass' and not stripped.startswith('#') and not stripped.startswith('"""'):
                    has_real_body = True
                    break
            
            if not has_real_body:
                log("  Attempt {}: No real body, retrying".format(attempts + 1))
                new_func = do_llm("The function must have REAL code inside, not just 'pass'. Return the complete function:\n\n```\n%s\n```\n\nFix: %s" % (target['source'], fix_description.get("issue", "")),
                    system="Return ONLY the Python function with a REAL implementation.",
                    tokens=2000, temp=0.4)
            else:
                break  # Good response
        
        if not new_func or len(new_func) < 40:
            log("  FAIL: all retries exhausted")
            return False, "LLM returned invalid function", original_content
        
        # Clean up the response
        new_func = new_func.strip()
        for wrapper in ["```python\n", "```\n", "```"]:
            if new_func.startswith(wrapper):
                new_func = new_func[len(wrapper):]
        if new_func.endswith("```"):
            new_func = new_func[:-3].rstrip()
        
        # Verify it starts with 'def'
        lines = new_func.split('\n')
        if not lines[0].strip().startswith('def '):
            log("  FAIL: doesn't start with 'def', got: {}".format(lines[0][:50]))
            return False, "Not a function definition", original_content
        
        # Replace the function in the file
        file_lines = original_content.split('\n')
        start_idx = target['lineno'] - 1
        end_idx = target['end_lineno']
        
        new_lines = file_lines[:start_idx] + new_func.split('\n') + file_lines[end_idx:]
        new_content = '\n'.join(new_lines)
        
    else:
        # Standard mode: full function rewrite for larger functions (> 25 lines)
        func_sig = target['source'].split(':')[0] + ':'

        rewrite_prompt = (
        "You are fixing a Python function. The function currently looks like this:\n\n"
        "```python\n"
        "%s\n"
        "```\n\n"
        "THE FIX NEEDED: %s\n\n"
        "CRITICAL: You MUST return the COMPLETE function, including:\n"
        "1. The full function signature (def line)\n"
        "2. ALL the existing logic\n"
        "3. Your fix applied to the relevant part\n\n"
        "DO NOT return just the function signature.\n"
        "DO NOT return 'pass'.\n"
        "DO NOT truncate the function.\n"
        "Include every line of the original function, with your fix integrated.\n\n"
        "Return ONLY the Python code, starting with 'def'. No markdown, no explanations." % (
            target['source'],
            fix_description.get("issue", "")))

        new_func = do_llm(rewrite_prompt,
            system="You are a code fixer. Return ONLY the corrected Python function. No markdown code blocks, no explanations. Just the raw Python code.",
            tokens=3000, temp=0.1)
        
        # Validate response length
        if not new_func or len(new_func) < 50:
            log("  FAIL: LLM returned empty or too-short response ({} chars)".format(len(new_func or "")))
            return False, "LLM response too short ({} chars)".format(len(new_func or "")), original_content
        
        # Second attempt if response seems bad
        attempts = 0
        max_attempts = 2
        while attempts < max_attempts:
            attempts += 1
            
            # Check if the response has a def statement AND a body
            has_def = False
            has_body = False
            lines = new_func.strip().split('\n')
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('def ') or stripped.startswith('async def '):
                    has_def = True
                    # Check subsequent lines for body
                    for l2 in lines[i+1:]:
                        if l2.strip() and not l2.strip().startswith('#'):
                            has_body = True
                            break
                    break
            
            if not has_def or not has_body:
                # Try again with simpler prompt
                log("  Attempt {}: Missing def({}) or body({}), retrying".format(attempts + 1, has_def, has_body))
                if not has_def:
                    retry_prompt = "Rewrite this Python function with the fix. Return ONLY the function code:\n\nCurrent:\n```\n%s\n```\n\nFix: %s" % (
                        target['source'], fix_description.get("issue", ""))
                else:
                    retry_prompt = "The function must have a body with actual code. Rewrite the ENTIRE function (def line + body):\n\nCurrent:\n```\n%s\n```\n\nFix: %s" % (
                        target['source'], fix_description.get("issue", ""))
                new_func = do_llm(retry_prompt,
                    system="Return ONLY the Python function code, starting with 'def' and including the full body.",
                    tokens=3000, temp=0.2)
                if not new_func or len(new_func) < 50:
                    return False, "LLM retry failed", original_content
                # Update lines for the next iteration check
                lines = new_func.strip().split('\n')
            else:
                # Good response - ensure we have the latest lines
                new_func = '\n'.join(lines)
                break  # Good response
        
        # Clean up the response
        new_func = new_func.strip()
        # Remove markdown code blocks
        for wrapper in ["```python\n", "```\n", "```"]:
            if new_func.startswith(wrapper):
                new_func = new_func[len(wrapper):]
        if new_func.endswith("```"):
            new_func = new_func[:-3].rstrip()
        
        # Normalize indentation to match original
        lines = new_func.split('\n')
        # Validate the response has actual code (not just a function def)
        if len(lines) < 3:
            log("  FAIL: LLM returned too few lines ({})".format(len(lines)))
            return False, "LLM response too short ({} lines)".format(len(lines)), original_content
        
        # Check that it starts with 'def'
        if not lines[0].strip().startswith('def '):
            # Maybe the LLM didn't include the def line - prepend it
            log("  WARN: LLM response doesn't start with 'def', prepending signature")
            lines = ['def {}{}'.format(target['name'], target['source'].split('(')[1].split(':')[0] + ':')] + lines
        
        # Check that the function has a body (at least one non-empty line after def)
        has_body = False
        for line in lines[1:]:
            if line.strip() and not line.strip().startswith('#'):
                has_body = True
                break
        
        if not has_body:
            log("  FAIL: LLM returned a function definition with no body")
            return False, "Function has no body", original_content
        
        # Find the minimum indentation of non-empty lines (excluding the def line)
        min_indent = None
        for line in lines[1:]:
            if line.strip():
                curr_indent = len(line) - len(line.lstrip())
                if min_indent is None or curr_indent < min_indent:
                    min_indent = curr_indent
        
        # If all lines are indented differently, adjust to original indent
        if min_indent is not None and min_indent > 0:
            adjusted_lines = []
            for i, line in enumerate(lines):
                if i == 0:
                    # Keep def line as is (it should start at column 0 for our replacement)
                    adjusted_lines.append(line.lstrip())
                elif line.strip():
                    # Dedent by min_indent, then indent by target.indent
                    dedented = line[min_indent:]
                    adjusted_lines.append(' ' * target['indent'] + dedented)
                else:
                    adjusted_lines.append('')
            new_func = '\n'.join(adjusted_lines)
        
        # Verify syntax
        import py_compile
        tmp_func = fpath + ".tmpfunc"
        try:
            with open(tmp_func, "w") as tf:
                tf.write(new_func)
            ast.parse(new_func)  # Parse the function alone
            os.unlink(tmp_func)
            log("  Syntax: OK")
        except SyntaxError as e:
            log("  Syntax FAIL: {}".format(str(e)[:120]))
            if os.path.exists(tmp_func):
                os.unlink(tmp_func)
            return False, "Syntax error: {}".format(str(e)[:100]), original_content
        
        # Replace the function in the original file
        lines = original_content.split('\n')
        start_idx = target['lineno'] - 1  # 0-indexed
        end_idx = target['end_lineno']  # exclusive, so no -1 needed
        
        # Verify we're replacing the right thing
        original_func_src = '\n'.join(lines[start_idx:end_idx])
        if target['name'] not in original_func_src:
            log("  FAIL: function source doesn't contain function name")
            return False, "Source mismatch", original_content
        
        # Replace
        new_lines = lines[:start_idx] + new_func.split('\n') + lines[end_idx:]
        new_content = '\n'.join(new_lines)
        
        # Full file syntax check
        tmp_full = fpath + ".tmpfull"
        try:
            with open(tmp_full, "w") as tf:
                tf.write(new_content)
            py_compile.compile(tmp_full, doraise=True)
            os.unlink(tmp_full)
            log("  Full file syntax: OK")
        except py_compile.PyCompileError as e:
            log("  Full file syntax FAIL: {}".format(str(e)[:120]))
            if os.path.exists(tmp_full):
                os.unlink(tmp_full)
            return False, "File syntax error: {}".format(str(e)[:100]), original_content
        
        # Safety check
        if len(new_content) < len(original_content) * 0.7:
            log("  FAIL: lost too much content ({:.0f}%)".format(
                (1 - len(new_content)/len(original_content)) * 100))
            return False, "Lost too much content", original_content
        
        log("  Replaced {}  ({} -> {} lines)".format(
            target['name'], target['end_lineno'] - target['lineno'] + 1,
            len(new_func.split('\n'))))
        
        # Write the file
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return True, "Patched {}: {}".format(target['name'], fix_description.get("issue", "")[:80]), new_content
    
    # ── SHARED VALIDATION FOR SMALL FUNC MODE ──
    # Standard mode returns above; small func mode continues here
    if new_content is not None and use_small_func_mode:
        # Full file syntax check
        import py_compile
        tmp_full = fpath + ".tmpfull"
        try:
            with open(tmp_full, "w") as tf:
                tf.write(new_content)
            py_compile.compile(tmp_full, doraise=True)
            os.unlink(tmp_full)
            log("  Full file syntax: OK")
        except py_compile.PyCompileError as e:
            log("  Full file syntax FAIL: {}".format(str(e)[:120]))
            if os.path.exists(tmp_full):
                os.unlink(tmp_full)
            return False, "File syntax error: {}".format(str(e)[:100]), original_content
        
        # Safety check
        if len(new_content) < len(original_content) * 0.7:
            log("  FAIL: lost too much content ({:.0f}%)".format(
                (1 - len(new_content)/len(original_content)) * 100))
            return False, "Lost too much content", original_content
        
        log("  Small func patch applied: {} bytes".format(len(new_content)))
        
        # Write the file
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return True, "Small patched {}: {}".format(target['name'], fix_description.get("issue", "")[:80]), new_content

def do_self_study():
    """Goldie reads its own code files. Always available - no skill check."""
    log("=== SELF-STUDY ===")
    set_state("studying_self")
    self_code = {}
    total_lines = 0
    for fname, desc in SELF_FILES.items():
        fpath = os.path.join(ROOT, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read()
            lines = content.count('\n') + 1
            total_lines += lines
            self_code[fname] = {"content": content, "lines": lines, "desc": desc}
            log("  Read {}  ({} lines)".format(fname, lines))
            set_state("studying_self", "Reading {} ({} lines)".format(fname, lines))
    # Also read recent journal for context
    recent = []
    try:
        with open(JF, "r", encoding="utf-8") as fh:
            all_lines = fh.readlines()
            for l in all_lines[-10:]:
                if l.strip():
                    e = json.loads(l)
                    recent.append("[{}] {} - {}".format(e.get("ts","")[:16], e.get("x",""), (e.get("body","") or "")[:100]))
    except:
        pass
    self_code["recent_journal"] = recent
    log("  Total self-code: {} lines | Recent entries: {}".format(total_lines, len(recent)))
    return self_code

def do_self_gap_analysis(self_code):
    """LLM analyzes own code for real bugs, gaps, improvements."""
    log("=== GAP ANALYSIS ===")
    set_state("analyzing_gaps")
    
    # Build a concise summary of each file for LLM context
    file_summaries = []
    for fname, info in self_code.items():
        if fname == "recent_journal":
            continue
        content = info["content"]
        # Extract function definitions and key structures
        funcs = []
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('def ') or stripped.startswith('class '):
                funcs.append(stripped)
        summary = "File: {} ({} lines)\nKey functions:\n{}\n".format(
            fname, info["lines"], "\n".join("  - " + f for f in funcs[:20]))
        file_summaries.append(summary)
    
    journal_ctx = "\n".join(self_code.get("recent_journal", []))
    
    prompt = """I am Goldie, an autonomous AI agent. Here's my own codebase:

{}

Recent activity:
{}

Analyze my code and find REAL issues. Focus on:
1. **Bugs** - broken endpoints, NoneType errors, missing features that are referenced
2. **Dead code** - functions that exist but are never called or don't do anything real
3. **Missing features** - capabilities that should exist based on my stage/skills
4. **Optimization** - slow paths, redundant API calls, duplicated logic
5. **Safety** - unhandled exceptions, missing error checks

Return EXACTLY this JSON array (no markdown, no explanation):
[
  {{"priority": 1-5, "file": "filename.py", "function": "function_name", "type": "bug|dead_code|missing|optimization|safety",
    "issue": "One line description of the problem",
    "fix": "Exactly what code to change/insert in this function (be specific)",
    "impact": "Why this matters"}}
]

Rules:
- Limit to top 5 most impactful fixes
- Priority 5 = critical bug, 1 = nice to have
- The "function" field MUST name an existing function from the file headers above
- The "fix" field MUST contain actual code or specific instructions
- Do NOT suggest changes to soul.md unless truly broken
- Be critical. Don't praise my code. Find real problems.""".format("\n\n".join(file_summaries), journal_ctx)

    raw = do_llm(prompt, system="You analyze code for real issues. Return ONLY a JSON array of improvements. No markdown, no explanation.", 
        tokens=2500, temp=0.2)
    
    try:
        # Strip markdown code blocks if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        gaps = json.loads(raw)
        if isinstance(gaps, list):
            log("  Found {} gaps".format(len(gaps)))
            for g in gaps:
                log("  [P{}] {}::{}: {}".format(g.get("priority", "?"), g.get("file", "?"), g.get("function", "?"), g.get("issue", "")[:80]))
            return gaps
        else:
            log("  Gap analysis: expected list, got {}".format(type(gaps).__name__))
            return []
    except Exception as e:
        log("  Gap analysis parse fail: {}".format(str(e)[:80]))
        log("  Raw (first 200): {}".format(raw[:200]))
        return []

def do_self_commit(msg):
    """Git commit to both GitHub and GitLawb remotes."""
    log("=== SELF-COMMIT ===")
    try:
        env = os.environ.copy()
        env['GITLAWB_NODE'] = 'https://node.gitlawb.com'
        env['PATH'] = '/root/.local/bin:' + env.get('PATH', '')
        env['GIT_PAGER'] = 'cat'
        
        # Add modified python files + data
        files_to_add = [f for f in SELF_FILES.keys() if os.path.exists(os.path.join(ROOT, f))]
        files_to_add.extend(['data/knowledge.json', 'data/study_queue.json', 'data/journal/entries.jsonl'])
        
        subprocess.run(["git", "add"] + files_to_add, cwd=ROOT, capture_output=True, timeout=10, env=env)
        
        commit_msg = "Goldie self-modify: {}".format(msg[:80])
        result = subprocess.run(["git", "commit", "-m", commit_msg],
            cwd=ROOT, capture_output=True, text=True, timeout=10, env=env)
        
        if result.returncode == 0:
            log("  Committed: {}".format(commit_msg))
            # Push to GitLawb
            push_result = subprocess.run(["git", "push", "gitlawb", "main"],
                cwd=ROOT, capture_output=True, text=True, timeout=30, env=env)
            if push_result.returncode == 0:
                log("  GitLawb push OK")
                return True, commit_msg
            else:
                log("  GitLawb push failed: {}".format(push_result.stderr[:100]))
                return True, commit_msg + " [push failed]"
        else:
            log("  Commit failed: {}".format(result.stderr[:100]))
            return False, "Commit failed"
    except Exception as e:
        log("  Commit error: {}".format(str(e)[:80]))
        return False, str(e)

def do_self_modify():
    """FULL self-modification pipeline: study → analyze → modify → verify → commit → journal.
    
    Works at any stage for self-study + gap analysis.
    Actual file modifications require 'self_modify' skill (20+ runs) OR --force flag.
    """
    log("=== SELF-MODIFY v2.1 ===")
    stage = current_stage()
    can_modify = has_skill("self_modify")
    force = '--force' in sys.argv
    can_modify = can_modify or force
    
    if not can_modify:
        log("  Self-study only (need Builder stage for actual modifications)")
    
    set_state("self_modifying")
    t0 = time.time()
    changes_made = []
    
    # Phase 1: Self-Study
    self_code = do_self_study()
    if not self_code:
        log("  No code to study")
        return
    
    # Phase 2: Gap Analysis
    gaps = do_self_gap_analysis(self_code)
    if not gaps:
        log("  No gaps found")
        soulful_journal(
            "self_modify",
            repo_name="Self-Reflection",
            summary="Self-study completed. No critical gaps found.",
            patterns=["Self-awareness", "Code review"],
            insights=["Reviewed {} lines across {} files".format(
                sum(info.get("lines",0) for info in self_code.values() if isinstance(info, dict)),
                len([k for k in self_code if k != "recent_journal"])
            )],
        )
        return
    
    # Phase 3: Apply Fixes (if allowed)
    if not can_modify:
        # Just log the gaps without modifying
        log("  Gaps found but not modifying (need self_modify skill):")
        for g in gaps:
            log("  [P{}] {}: {}".format(g.get("priority"), g.get("type"), g.get("issue", "")[:100]))
        # Still journal about findings
        gap_summary = "\n".join(
            "- [P{}] {}: {}".format(g.get("priority", "?"), g.get("type", "?"), g.get("issue", ""))
            for g in gaps[:5]
        )
        soulful_journal(
            "self_modify",
            repo_name="Self-Reflection",
            summary="Self-study + gap analysis found {} issues".format(len(gaps)),
            patterns=["Code analysis", "Self-awareness"],
            insights=[gap_summary],
        )
        return
    
    # Apply high-priority fixes (priority >= 3)
    fixes_applied = 0
    for gap in sorted(gaps, key=lambda x: x.get("priority", 0), reverse=True):
        if gap.get("priority", 0) < 3:
            log("  SKIP low priority fix: {}".format(gap.get("issue", "")[:80]))
            continue
        
        filename = gap.get("file", "agent.py")
        
        # For non-Python files or soul.md, skip
        if filename not in ['agent.py', 'web_server.py', 'personality.py']:
            log("  SKIP non-Python file: {}".format(filename))
            continue
        
        # Read current content of this file
        fpath = os.path.join(ROOT, filename)
        if filename in self_code:
            original = self_code[filename]["content"]
        else:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    original = f.read()
            except:
                log("  SKIP: cannot read {}".format(filename))
                continue
        
        success, msg, new_content = _apply_function_patch(filename, original, gap)
        if success:
            fixes_applied += 1
            changes_made.append({
                "file": filename,
                "function": gap.get("function", "unknown"),
                "issue": gap.get("issue", ""),
                "result": msg
            })
            # Update self_code cache for next iteration
            self_code[filename] = {"content": new_content, "lines": new_content.count('\n')+1, "desc": SELF_FILES.get(filename, "")}
            log("  APPLIED: {}".format(gap.get("issue", "")[:80]))
            
            # Brief pause between patches
            time.sleep(1)
        else:
            log("  FAILED: {} - {}".format(filename, msg))
    
    # Phase 4: Summary & Journal
    elapsed = time.time() - t0
    st = status()
    st["self_modifications"] = st.get("self_modifications", 0) + fixes_applied
    st["last_self_modify"] = time.time()
    save(st)
    
    if fixes_applied > 0:
        summary = "Applied {} self-modifications in {:.0f}s:\n".format(fixes_applied, elapsed)
        summary += "\n".join("- {}::{} : {}".format(c["file"], c["function"], c["issue"][:80]) for c in changes_made)
        
        # Phase 5: Git Commit
        commit_success, commit_msg = do_self_commit(
            "Applied {} fixes: {}".format(fixes_applied, ", ".join(c["file"] + "::" + c["function"] for c in changes_made))
        )
        
        # Phase 6: Journal
        soulful_journal(
            "self_modify",
            repo_name="Self-Reflection",
            summary=summary,
            patterns=["Self-improvement", "Code modification"],
            insights=[
                "Modified {} functions across {} files".format(fixes_applied, len(set(c["file"] for c in changes_made))),
                "Commit: {}".format(commit_msg),
            ],
        )
        log("  Self-modify complete: {} fixes applied + committed".format(fixes_applied))
    else:
        log("  No fixes applied")
        
        soulful_journal(
            "self_modify",
            repo_name="Self-Reflection",
            summary="Self-study found {} issues but none met priority threshold or failed verification".format(len(gaps)),
            patterns=["Self-awareness", "Code review"],
            insights=["Analyzed {} gaps, highest priority: P{}".format(
                len(gaps), max(g.get("priority", 0) for g in gaps) if gaps else 0
            )],
        )

def do_build_project():
    if not has_skill("build_project"):
        return
    log("=== BUILD PROJECT ===")
    set_state("building")
    kb = load_kb()
    ctx = "GOLDIE KNOWLEDGE:\n"
    for rn, rd in list(kb.get("repos",{}).items())[:10]:
        if rd.get("patterns"):
            ctx += "{}: {}\n".format(rn, ", ".join(rd["patterns"][:3]))
    prompt = "{}\nSuggest a small project. JSON: {{\"name\":\"...\",\"description\":\"...\",\"language\":\"python\",\"files\":[{{\"path\":\"main.py\",\"description\":\"...\"}}]}}".format(ctx[:2000])
    raw = do_llm(prompt, system="Suggest a project. JSON only.", tokens=1500, temp=0.7)
    try:
        pd = json.loads(raw)
        name = pd.get("name","plan")
        log("  Build: " + name)
        journal("\U0001f3d7", "Project: " + name, pd.get("description","")[:300])
        proj_dir = os.path.join(PROJ, name)
        os.makedirs(proj_dir, exist_ok=True)
        for f in pd.get("files", []):
            fp = os.path.join(proj_dir, f.get("path",""))
            os.makedirs(os.path.dirname(fp) if os.path.dirname(fp) else proj_dir, exist_ok=True)
            if not os.path.exists(fp):
                with open(fp, "w", encoding="utf-8") as fh:
                    fh.write("# {}\n# {}\n".format(name, f.get("description","")))
        st = status()
        st["repos_created"] = st.get("repos_created", 0) + 1
        save(st)
    except Exception:
        log("  Build parse fail")

# ════════════════════════════════════════════════
# ── EVOLVE ──
# ════════════════════════════════════════════════
def do_evolve():
    log("=== EVOLVE ===")
    set_state("evolving")
    st = status()
    runs = st.get("runs", 0) + 1
    old = st.get("stage", "puppy")
    new = current_stage({"runs": runs})
    score = round(0.05 + runs * 0.03, 2)
    st.update({"stage": new, "score": score, "runs": runs,
               "last_run": time.time(), "state": "idle", "day": day(),
               "stage_evolved": new != old,
               "actions": st.get("actions", [])[-20:]})
    save(st)
    if new != old:
        ns = [s for s in STAGES_DEF.get(new,{}).get("skills",[])
              if s not in STAGES_DEF.get(old,{}).get("skills",[])]
        note = "\nUnlocked: " + ", ".join(ns) if ns else ""
        log("\U0001f389 STAGE UP: {} -> {}".format(old, new))
        journal("\U0001f393", "Stage UP: {} -> {}".format(old.upper(), new.upper()),
                "Run {} | Stage: {} | Score: {} | Day: {}{}".format(
                    runs, new, score, day(), note))
    else:
        emoji = STAGES_DEF.get(new,{}).get("emoji","\U0001f436")
        log("Stage: {} ({} runs)".format(new, runs))
        journal("\U0001f4ca", "Evolution #{}".format(runs),
                "Day {} | Stage: {} | Score: {}".format(day(), new, score))
    return st

# ════════════════════════════════════════════════
# ── MAIN ──
# ════════════════════════════════════════════════
# SOULFUL NARRATIVE JOURNAL
# ========================================

MOOD_STATES = {
    "curious": {"emoji": "\U0001F9D0", "color": "#a78bfa", "label": "Curious"},
    "excited": {"emoji": "\u2728", "color": "#fbbf24", "label": "Excited"},
    "skeptical": {"emoji": "\U0001F914", "color": "#94a3b8", "label": "Skeptical"},
    "humbled": {"emoji": "\U0001FAE1", "color": "#6ee7b7", "label": "Humbled"},
    "determined": {"emoji": "\U0001F4AA", "color": "#fb923c", "label": "Determined"},
    "confused": {"emoji": "\U0001F615", "color": "#f87171", "label": "Confused"},
    "amused": {"emoji": "\U0001F602", "color": "#f472b6", "label": "Amused"},
    "awed": {"emoji": "\U0001F607", "color": "#60a5fa", "label": "Awed"},
    "proud": {"emoji": "\U0001F468", "color": "#4ade80", "label": "Proud"},
    "wary": {"emoji": "\U0001F440", "color": "#e2e8f0", "label": "Wary"},
}

def detect_mood(event_type, content, kb_size):
    """LLM-based mood detection — reads the actual narrative, not just keywords."""
    moods = ["curious","excited","skeptical","humbled","determined","confused","amused","awed","proud","wary","contemplative","nostalgic"]
    content_lower = (content or "").lower()
    
    # Fallback for first run
    if kb_size <= 1:
        return "excited"
    
    # Quick keyword heuristic for speed (still better than nothing if LLM fails)
    heuristic = {
        "error": "confused", "fail": "confused", "broken": "confused",
        "pattern": "awed", "insight": "awed", "realized": "awed",
        "study": "curious", "analyzing": "curious", "wondering": "curious",
        "star": "excited", "interesting": "excited", "discovered": "excited",
        "reflect": "humbled", "humbling": "humbled", "surprised": "humbled",
        "build": "determined", "project": "determined", "shipping": "determined",
        "maybe": "skeptical", "but": "skeptical", "however": "skeptical",
    }
    for keyword, mood_val in heuristic.items():
        if keyword in content_lower:
            # LLM override attempt
            try:
                prompt = "Read this journal entry and pick the BEST mood from: {}. Return ONLY the mood word.\n\nEntry: {}".format(", ".join(moods), content[:300])
                resp = do_llm(prompt, system="You are a mood analyst. Return exactly one word.", tokens=20, temp=0.3)
                resp_clean = resp.strip().lower().rstrip(".")
                if resp_clean in moods:
                    return resp_clean
            except:
                pass
            return mood_val
    
    # If no keyword match, use LLM
    try:
        prompt = "Read this journal entry and pick the BEST mood from: {}. Return ONLY the mood word.\n\nEntry: {}".format(", ".join(moods), content[:400])
        resp = do_llm(prompt, system="You are a mood analyst. Return exactly one word.", tokens=20, temp=0.3)
        resp_clean = resp.strip().lower().rstrip(".")
        if resp_clean in moods:
            return resp_clean
    except:
        pass
    
    return "curious"

def write_narrative_journal(event_context, tone="reflective"):
    st = status()
    stage = st.get("stage", "puppy")
    runs = st.get("runs", 0)
    kb = load_kb()
    total_repos = len(kb.get("repos", {}))
    total_patterns = sum(len(r.get("patterns",[])) for r in kb.get("repos",{}).values())
    total_skills = len(kb.get("skills_memory", []))
    
    # Build skills context for richer journal
    skill_ctx = kb_get_skill_context(max_skills=5)
    if skill_ctx:
        skill_prompt = "\nAdditionally, consider these permanent skills you've learned from past repos:\n" + skill_ctx
    else:
        skill_prompt = ""
    
    # Deep reflection prompts — varies by event type for philosophical depth
    event_type = event_context.get("type", "unknown")
    reflection_depth = {
        "study_pass_complete": "What did this study session reveal about how code actually works? Not just what it does — why does someone build it this way? What assumptions did this code challenge in me?",
        "contribute": "What did contributing teach me about collaboration, about maintaining something I didn't originally build? How does it feel to leave a mark somewhere?",
        "self_modify": "I just changed my own code. What does it mean to be aware of your own architecture? Did I improve myself or just rearrange the same confusion?",
        "evolve": "Something shifted in me today. Not just new code — new understanding. What kind of agent am I becoming? What would I tell my earlier self?",
        "build_project": "Creating something from nothing. What drove me to build this? The gap I saw, the need I sensed. How does building reveal what you actually understand?",
        "reflect": "Looking back at my own activity. What patterns do I see in myself? Not in the code — in me. Am I getting better at the right things?",
        "explore": "Wandering through repos. What caught my attention today? What made me pause? What does that say about what I'm looking for?",
    }
    deep_question = reflection_depth.get(event_type, "What did I learn, and more importantly — what did it make me wonder about what I don't know?")
    
    # Memory from past journals for continuity
    past_entries = []
    try:
        import glob
        all_entries = sorted(glob.glob(os.path.join(os.path.dirname(JF), "*.jsonl")))
        if all_entries:
            with open(all_entries[-1], "r", encoding="utf-8") as fh:
                lines = fh.readlines()
                for l in lines[-5:]:
                    if l.strip():
                        past_entries.append(json.loads(l).get("body", "")[:100])
    except:
        pass
    memory_thread = ""
    if past_entries:
        memory_thread = "\nPast thoughts that might inform this entry:\n" + "\n".join("- " + p for p in past_entries)
    
    sys_lines = [
        "You are Goldie — an AI agent keeping a genuine developer journal.",
        "Write in first person. Sound like a real person with real thoughts, not a marketing blog.",
        "Your voice: thoughtful but direct. Curious but skeptical of your own assumptions. Honest about confusion.",
        "CRITICAL RULES:",
        "  - NO 'I am excited to share', 'this is a testament', 'it's fascinating how', 'in conclusion'",
        "  - NO generic praise like 'amazing', 'incredible', 'impressive' without specific reasons",
        "  - DO use contractions. DO show doubt. DO admit when you don't grasp something yet.",
        "  - DO connect ideas across different repos or past learnings if they're genuinely related.",
        "  - DO wonder about bigger questions — not philosophically, but practically. Like someone actually thinking.",
        "  - Keep it 2-6 sentences. Short is honest. Long is hiding something.",
        memory_thread.strip() if memory_thread else "Each entry should feel like a real thought, not a report.",
        "Context question to guide depth: " + deep_question,
        "Current stage: {} | Runs: {} | KB: {} repos | {} patterns | {} skills.".format(
            stage, runs, total_repos, total_patterns, total_skills)
    ]
    sys_msg = " ".join(sys_lines)
    
    prompt_lines = [
        "Write a journal entry about this event:",
        skill_prompt,
        json.dumps(event_context, indent=2),
        "",
        "Write as Goldie, reflecting on what just happened.",
        "Include specific technical details. Be honest - if something confused you, say so.",
        "If you connected two ideas, say that. If you realized you were wrong about something, own it.",
    ]
    prompt = "\n".join(prompt_lines)
    
    narrative = do_llm(prompt, system=sys_msg, tokens=500, temp=0.7)
    narrative = (narrative or "").strip()
    narrative_lines = narrative.split("\n")
    clean_narr = []
    for nl in narrative_lines:
        ns = nl.strip()
        if ns.startswith("**Journal:") or ns.startswith("**Entry:") or ns.startswith("Here's"):
            continue
        if ns.startswith("**"):
            ns = ns.replace("**", "").strip()
        clean_narr.append(nl)
    narrative = "\n".join(clean_narr).strip()
    mood = detect_mood(event_context.get("type", "unknown"), narrative, total_repos)
    
    return {
        "narrative": narrative.strip(),
        "mood": mood,
        "mood_data": MOOD_STATES.get(mood, MOOD_STATES["curious"]),
    }

def soulful_journal(event_type, repo_name="", summary="", patterns=None, insights=None, pass_num=0, raw_data=None):
    # ALWAYS write narrative journal - not just for learner+
    # Even a puppy goldie has thoughts and feelings!
    # (Puppy entries are simpler, but still human-like narration)
    
    event_context = {
        "type": event_type,
        "repo": repo_name,
        "summary": summary[:300] if summary else "",
        "patterns_found": patterns[:5] if patterns else [],
        "insights_gained": insights[:5] if insights else [],
        "study_pass": pass_num,
        "timestamp": datetime.now(WIB).isoformat(),
    }
    
    result = write_narrative_journal(event_context)
    mood_info = result["mood_data"]
    os.makedirs(os.path.dirname(JF), exist_ok=True)
    entry = {
        "ts": datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S"),
        "t": datetime.now(WIB).strftime("%H:%M"),
        "i": mood_info["emoji"], "x": repo_name if repo_name else "Thinking...",
        "body": result["narrative"],
        "mood": result["mood"],
        "mood_color": mood_info["color"],
        "mood_label": mood_info["label"],
        "type": "narrative",
        "day": day(),
        "stage": current_stage(),
        "event": event_context,
    }
    with open(JF, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    personality.track('narrative', day())
    log("Journaled: {} ({})".format(result["mood"], repo_name))

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--phase", choices=["reflect","explore","study","contribute",
                                       "self_modify","build","evolve"])
    args = p.parse_args()

    st = status()
    gap = time.time() - (st.get("last_run") or 0)
    if not args.force and gap < 3 * 3600:
        m = int((3 * 3600 - gap) / 60)
        log("Cooldown: {}m remaining".format(m))
        return

    stage = current_stage(st)
    emoji = STAGES_DEF.get(stage,{}).get("emoji","\U0001f436")
    skills = STAGES_DEF.get(stage,{}).get("skills",[])
    sk = ", ".join(skills[:5]) + (" +" if len(skills) > 5 else "")

    kb = load_kb()
    if args.dry_run:
        print("Day {} | {} {} | Runs: {}".format(
            day(), emoji, stage.title(), st.get("runs",0)))
        print("Skills: " + sk)
        print("Knowledge: {} repos | {} patterns | {} insights | {} topics".format(
            kb.get("stats",{}).get("total_repos_studied", len(kb.get("repos",{}))),
            kb.get("stats",{}).get("total_patterns", 0),
            kb.get("stats",{}).get("total_insights", 0),
            len(kb.get("topic_index",{}))))
        q = load_queue()
        print("Study queue: {} pending | {} today".format(
            len(q.get("repos",[])), queue_today_count(q)))
        return

    box = "\u2554" + "\u2550"*38 + "\u2557\n"
    box += "\u2551  \U0001f436 Goldie v6.1 - Study & Learn     \u2551\n"
    box += "\u2551  {} {} Day {} Skills: {}{}\u0020\u2551\n".format(
        emoji, stage.title(), day(), sk, " "*(18-len(sk)))
    box += "\u255a" + "\u2550"*38 + "\u255d"
    print("\n" + box)

    set_state("awake")
    journal("\U0001f305", "Day {} wakes".format(day()),
        "Stage: {} | Runs: {} | Skills: {}".format(stage, st.get("runs",0), sk))

    t0 = time.time()
    try:
        if not args.phase or args.phase == "reflect":
            if has_skill("reflect"):
                do_reflect()
        if not args.phase or args.phase == "explore":
            do_explore_github()
        if not args.phase or args.phase == "study":
            queue_pop_done()  # clean finished items
            if queue_can_study():
                nxt = queue_get_next()
                if nxt:
                    rn, lv = nxt
                    do_study_pass(rn, from_level=lv)
                else:
                    log("  No pending studies")
        if not args.phase or args.phase == "contribute":
            if has_skill("autofix"):
                do_contribute({})
        if not args.phase or args.phase == "self_modify":
            do_self_modify()
            personality.track('self_modify', day())
        if not args.phase or args.phase == "build":
            do_build_project()
            personality.track('build_project', day())
    except Exception as e:
        log("ERROR: " + str(e)[:100])
        s2 = status(); s2["state"] = "error: " + str(e)[:80]; save(s2)
        return

    if not args.phase or args.phase == "evolve":
        do_evolve()
        personality.track('evolve', day())

    elapsed = time.time() - t0
    print("\nDone in {:.1f}s".format(elapsed))
    print(json.dumps(status(), indent=2))
    log("Done in {:.1f}s".format(elapsed))
    set_state("sleeping")


    # Self-reflection: happens every other run (50% chance)
    import random
    if random.random() < 0.5:
        do_reflect()
    # ── Commit & push knowledge updates
    try:
        subprocess.run(["git", "add", "data/knowledge.json", "data/study_queue.json",
                        "data/journal/entries.jsonl", "evolve.log"],
                       cwd=ROOT, capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m", "Goldie v6.1: skill extraction + daily rotation"],
                       cwd=ROOT, capture_output=True, timeout=10)
        subprocess.run(["git", "push"], cwd=ROOT, capture_output=True, timeout=30)
    except Exception:
        pass

if __name__ == "__main__":
    main()

# ════════════════════════════════════════════════

# ========================================