#!/usr/bin/env python3
"""GitPup Agent v6.0 — Self-Evolving AI Agent with Long-Term Knowledge Base
Progressive Study: max 3 repos/day, 4-pass deepening, permanent memory.
Chat-ready: knowledge queryable via topic search."""
import os, sys, json, time, urllib.request, urllib.parse, subprocess, textwrap, hashlib
from collections import Counter
from datetime import datetime, timezone

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

MAX_REPOS_PER_DAY = 3

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
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("  " + msg)
    os.makedirs(os.path.dirname(LF), exist_ok=True)
    with open(LF, "a", encoding="utf-8") as fh:
        fh.write("[{}] {}\n".format(ts, msg))

def journal(icon, title, body="", etype="evolve"):
    os.makedirs(os.path.dirname(JF), exist_ok=True)
    entry = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             "t": datetime.now().strftime("%H:%M"),
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
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
            return resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return "[LLM Error: " + str(e)[:100] + "]"

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
        "memory_summaries": [],
        "pr_history": [],
        "stats": {"total_repos_studied": 0, "total_patterns": 0,
                  "total_insights": 0, "last_study_date": ""},
    }

def load_kb():
    if os.path.exists(KB_FILE):
        try:
            with open(KB_FILE, encoding="utf-8") as fh:
                kb = json.load(fh)
                for k in ["repos", "topic_index", "skill_index", "memory_summaries", "pr_history", "stats"]:
                    if k not in kb:
                        kb[k] = [] if k == "memory_summaries" else ({} if k != "pr_history" else [])
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

def kb_add_to_repo(repo_name, study_level=0, summary="", patterns=None,
                    best_practices=None, insights=None, code_examples=None,
                    topics=None, readme_insights="", stars=0, lang=""):
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
    rd["studied_at"].append(datetime.now().strftime("%Y-%m-%d %H:%M"))
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
    kb["stats"]["last_study_date"] = datetime.now().strftime("%Y-%m-%d")
    save_kb(kb)

# ════════════════════════════════════════════════
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
    today_str = datetime.now().strftime("%Y-%m-%d")
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
    today_str = datetime.now().strftime("%Y-%m-%d")
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
                        "added_at": datetime.now().isoformat()})
    save_queue(q)

def queue_get_next():
    q = load_queue()
    repos = q.get("repos", [])
    if not repos:
        return None
    for item in repos:
        rn = item["repo"]
        target = item["target_depth"]
        kb = load_kb()
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

    default_queries = ["python+stars:>5000", "javascript+stars:>5000",
        "go+stars:>3000", "rust+stars:>2000", "typescript+stars:>5000"]
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
    # Soulful narrative journal entry
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
    if not has_skill("reflect"):
        return
    log("=== REFLECTING ===")
    set_state("reflecting")
    kb = load_kb()
    entries = []
    try:
        with open(JF, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception:
        pass
    mem = entries[-10:] if len(entries) > 10 else entries
    if not mem:
        journal("\U0001f4ad", "No memories yet", "First run.")
        return
    ctx = ""
    for e in mem[-8:]:
        ctx += "- [{}] {}: {}\n".format(e.get("i","?"), e.get("x","")[:60], (e.get("body") or "")[:120])
    prompt = "Past activity:\n{}\nReturn 3-5 specific learnings (bullets).".format(ctx)
    refl = do_llm(prompt, system="Extract patterns from activities.", tokens=800, temp=0.6)
    if refl and len(refl) > 30 and not refl.startswith("[LLM"):
        log("  Reflection: " + refl[:150])
        journal("\U0001f9e0", "Reflection", refl.strip()[:400])
        kb["memory_summaries"].append(refl.strip()[:500])
        kb["memory_summaries"] = kb["memory_summaries"][-10:]
    else:
        journal("\U0001f9e0", "Daily Review", "Reviewed {} activities".format(len(mem)))
    save_kb(kb)

# ════════════════════════════════════════════════
# ── CONTRIBUTE / SELF-MODIFY / BUILD ──
# ════════════════════════════════════════════════
def do_contribute(repo_info):
    if not has_skill("autofix"):
        return
    log("=== CONTRIBUTE ===")
    set_state("contributing")
    journal("\U0001f527", "Contributing to " + repo_info.get("full_name",""), "")

def do_self_modify():
    if not has_skill("self_modify"):
        return
    log("=== SELF-MODIFY ===")
    set_state("self_modifying")
    with open(os.path.join(ROOT, "agent.py"), "r", encoding="utf-8") as fh:
        code = fh.read()
    prompt = ("Current code:\n---\n{}\n---\n"
        "Suggest one improvement. JSON: "
        '{{"section":"...","suggestion":"...","reason":"..."}}').format(code[:3000])
    raw = do_llm(prompt, system="Suggest code improvement. JSON only.", tokens=1000, temp=0.5)
    try:
        m = json.loads(raw)
        log("  Self-modify: {} -> {}".format(m.get("section",""), m.get("suggestion","")))
        journal("\U0001f527", "Self-Modify",
            "{}: {}\n{}".format(m.get("section",""), m.get("suggestion",""), m.get("reason","")))
        st = status()
        st["self_modifications"] = st.get("self_modifications", 0) + 1
        save(st)
    except Exception:
        log("  Self-modify parse fail")

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
    content_lower = (content or "").lower()
    if kb_size <= 1:
        return "excited"
    if "error" in content_lower or "fail" in content_lower:
        return "confused"
    if "pattern" in content_lower or "insight" in content_lower:
        return "awed"
    if "study" in content_lower or "analyzing" in content_lower:
        return "curious"
    if "star" in content_lower:
        return "excited"
    if "reflect" in content_lower:
        return "humbled"
    if "build" in content_lower or "project" in content_lower:
        return "determined"
    return "curious"

def write_narrative_journal(event_context, tone="reflective"):
    st = status()
    stage = st.get("stage", "puppy")
    runs = st.get("runs", 0)
    kb = load_kb()
    total_repos = len(kb.get("repos", {}))
    total_patterns = sum(len(r.get("patterns",[])) for r in kb.get("repos",{}).values())
    
    sys_lines = [
        "You are Goldie, a golden retriever AI agent who writes a developer journal.",
        "Write in first person (I, my). Sound like a thoughtful developer reflecting on what they learned.",
        "Include specific technical details from the event. Show genuine curiosity, doubt, or excitement.",
        "Reference past learning when relevant.",
        "Keep it concise (2-5 sentences).",
        "No filler, no 'I am excited to share', no 'this is a testament'.",
        "Just honest thoughts from an agent figuring things out one repo at a time.",
        "Current stage: {} | Runs: {} | Knowledge base: {} repos studied, {} patterns.".format(
            stage, runs, total_repos, total_patterns)
    ]
    sys_msg = " ".join(sys_lines)
    
    prompt_lines = [
        "Write a journal entry about this event:",
        json.dumps(event_context, indent=2),
        "",
        "Write as Goldie, reflecting on what just happened.",
        "Include specific technical details. Be honest - if something confused you, say so.",
        "If you connected two ideas, say that. If you realized you were wrong about something, own it.",
    ]
    prompt = "\n".join(prompt_lines)
    
    narrative = do_llm(prompt, system=sys_msg, tokens=500, temp=0.7)
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
        "timestamp": datetime.now().isoformat(),
    }
    
    result = write_narrative_journal(event_context)
    mood_info = result["mood_data"]
    os.makedirs(os.path.dirname(JF), exist_ok=True)
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "t": datetime.now().strftime("%H:%M"),
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
    box += "\u2551  \U0001f436 Goldie v6.0 - Study & Learn     \u2551\n"
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
        if not args.phase or args.phase == "build":
            do_build_project()
    except Exception as e:
        log("ERROR: " + str(e)[:100])
        s2 = status(); s2["state"] = "error: " + str(e)[:80]; save(s2)
        return

    if not args.phase or args.phase == "evolve":
        do_evolve()

    elapsed = time.time() - t0
    print("\nDone in {:.1f}s".format(elapsed))
    print(json.dumps(status(), indent=2))
    log("Done in {:.1f}s".format(elapsed))
    set_state("sleeping")

    # ── Commit & push knowledge updates
    try:
        subprocess.run(["git", "add", "data/knowledge.json", "data/study_queue.json",
                        "data/journal/entries.jsonl", "evolve.log"],
                       cwd=ROOT, capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m", "Goldie v6: study pass completed"],
                       cwd=ROOT, capture_output=True, timeout=10)
        subprocess.run(["git", "push"], cwd=ROOT, capture_output=True, timeout=30)
    except Exception:
        pass

if __name__ == "__main__":
    main()

# ════════════════════════════════════════════════

# ========================================