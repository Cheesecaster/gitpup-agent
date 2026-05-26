#!/usr/bin/env python3
"""GitPup Agent v5.0 — Self-Evolving Autonomous AI Agent
Stages: puppy -> learner -> coder -> builder -> architect -> master
Each stage unlocks new skills: memory -> PR creation -> self-modify -> project building"""
import os, sys, json, time, urllib.request, urllib.parse, argparse, subprocess, shutil, textwrap, hashlib
from datetime import datetime, timezone

# ════════════════════════════════════════════════
# ── Paths ──
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
JF = os.path.join(DATA, "journal", "entries.jsonl")
SF = os.path.join(DATA, "state", "status.json")
LF = os.path.join(DATA, "evolve.log")
KB = os.path.join(DATA, "knowledge.json")
TMP = os.path.join(ROOT, "tmp_explore")
PROJ = os.path.join(ROOT, "projects")

# ── Load .env ──
def _load_dotenv():
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
_load_dotenv()

# ── Credentials ──
LLM_KEY = os.environ.get("LLM_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")

LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.6-flash")
MY_LOGIN = os.environ.get("MY_GITHUB_LOGIN", os.environ.get("GITHUB_USER", ""))
BIRTH = "2026-05-25"

# ── Stage definitions with SKILL UNLOCKS ──
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

# ════════════════════════════════════════════════
# ── Helpers ──
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
        return {"stage": "puppy", "score": 0.05, "runs": 0, "last_run": 0,
                "state": "idle", "day": day(), "stage_evolved": False,
                "actions": [], "memory": [], "prs_created": 0,
                "repos_created": 0, "self_modifications": 0,
                "knowledge_points": 0}

def save(s):
    os.makedirs(os.path.dirname(SF), exist_ok=True)
    with open(SF, "w") as fh:
        json.dump(s, fh, indent=2)

def journal(icon, title, body="", etype="evolve"):
    os.makedirs(os.path.dirname(JF), exist_ok=True)
    e = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "t": datetime.now().strftime("%H:%M"),
         "i": icon, "x": title,
         "body": body, "type": etype, "day": day()}
    with open(JF, "a") as fh:
        fh.write(json.dumps(e) + "\n")

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = "[" + t + "] " + msg
    with open(LF, "a") as fh:
        fh.write(line + "\n")
    print("  " + line)

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
    """Star a repo. Available from puppy stage."""
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

def do_create_pr(owner, repo, branch, title, body, base="main"):
    """Create a Pull Request. Requires coder skill."""
    if not GH_TOKEN:
        log("  Cannot create PR (no token)")
        return None
    log("PR: Creating for {}/{}".format(owner, repo))
    result = gh_post("/repos/{}/{}/pulls".format(owner, repo), {
        "title": title, "body": body, "head": branch, "base": base})
    if "url" in result:
        html_url = result.get("html_url", result["url"])
        log("  PR Created: " + html_url)
        journal("\U0001f91d", "PR Created: " + title, html_url)
        st = status()
        st["prs_created"] = st.get("prs_created", 0) + 1
        save(st)
        return html_url
    log("  PR failed: " + str(result)[:100])
    return None

# ════════════════════════════════════════════════
# ── Memory & Knowledge ──
def load_knowledge():
    if os.path.exists(KB):
        try:
            with open(KB) as fh:
                kb = json.load(fh)
                # Ensure all keys exist
                for k in ["repos_studied", "patterns_learned", "languages_seen",
                          "key_insights", "last_reflection", "total_runs", "pr_history"]:
                    if k not in kb:
                        kb[k] = [] if k not in ("last_reflection", "total_runs", "prs_merged") else 0
                return kb
        except Exception:
            pass
    return {"repos_studied": [], "patterns_learned": [], "languages_seen": [],
            "key_insights": [], "last_reflection": "", "total_runs": 0,
            "pr_history": [], "prs_merged": 0}

def save_knowledge(kb):
    os.makedirs(os.path.dirname(KB), exist_ok=True)
    with open(KB, "w") as fh:
        json.dump(kb, fh, indent=2)

def read_memory():
    entries = []
    try:
        with open(JF, "r") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception:
        pass
    return entries[-20:] if len(entries) > 20 else entries

def do_reflect():
    """Read past experiences and synthesize learnings. Requires learner skill."""
    if not has_skill("reflect"):
        return
    log("=== REFLECTING ===")
    set_state("reflecting")

    memories = read_memory()
    kb = load_knowledge()

    if not memories:
        journal("\U0001f4ad", "No memories yet", "First day! Starting fresh.")
        return

    context = ""
    for e in memories[-10:]:
        b = (e.get("body") or "")[:120]
        context += "- {}: {} | {}\n".format(e.get("i", "?"), e.get("x", "")[:60], b)

    prompt = "Based on these past activities, what patterns or insights should Goldie remember?\nReturn 3-5 specific learnings (bullet points).\n\nPAST:\n{}".format(context)
    reflection = do_llm(prompt, system="You are Goldie analyzing past learning. Extract specific patterns, not generic advice.", tokens=800, temp=0.6)

    if reflection and len(reflection) > 30 and not reflection.startswith("[LLM"):
        log("  Reflection: " + reflection[:150])
        journal("\U0001f9e0", "Reflection: Patterns Discovered", reflection.strip()[:400])
        kb["key_insights"].append(reflection.strip()[:300])
        kb["last_reflection"] = reflection.strip()[:200]
        kb["total_runs"] = kb.get("total_runs", 0) + 1
    else:
        journal("\U0001f9e0", "Daily Review", "Reviewed {} previous activities".format(len(memories)))
    save_knowledge(kb)

# ════════════════════════════════════════════════
# ── Explore GitHub ──
def do_explore_github():
    log("=== EXPLORE GITHUB ===")
    set_state("exploring_github")
    repos = []

    # Use knowledge to improve search
    kb = load_knowledge()
    custom_queries = []
    if kb and kb.get("languages_seen"):
        for lang in kb["languages_seen"][:3]:
            lang_upper = lang.lstrip(".")
            custom_queries.append("{}+stars:>5000".format(lang_upper.lower()))

    default_queries = [
        "python+trending+stars:>2000",
        "javascript+stars:>5000",
        "go+web+stars:>2000",
        "rust+cli+stars:>1000",
    ]

    queries = custom_queries + default_queries
    seen = set()

    for q in queries:
        data = gh_get("/search/repositories?q=" + urllib.parse.quote(q) + "&sort=stars&order=desc&per_page=3")
        if "items" in data and len(data["items"]) > 0:
            for repo in data["items"][:3]:
                name = repo.get("full_name") or ""
                if name in seen:
                    continue
                seen.add(name)
                stars = repo.get("stargazers_count") or 0
                lang = repo.get("language") or "unknown"
                desc = (repo.get("description") or "No description")[:200]
                if stars >= 500:
                    repos.append({"full_name": name, "stars": stars, "lang": lang, "desc": desc,
                                  "url": repo.get("html_url") or ""})

    # Fallback
    if not repos:
        log("  Star search empty, trending fallback...")
        data = gh_get("/search/repositories?q=trending&sort=stars&order=desc&per_page=5")
        if "items" in data:
            for repo in data["items"][:5]:
                name = repo.get("full_name") or ""
                if name and name not in seen:
                    repos.append({
                        "full_name": name,
                        "stars": repo.get("stargazers_count") or 0,
                        "lang": repo.get("language") or "unknown",
                        "desc": (repo.get("description") or "No description")[:200],
                        "url": repo.get("html_url") or ""})

    if not repos:
        log("  No GitHub repos found")
        return []

    log("  Found {} repos".format(len(repos)))

    # Auto-star 10k+
    starred = []
    if has_skill("star"):
        for r in repos:
            if r.get("stars", 0) >= 10000 and do_star_repo(r["full_name"]):
                starred.append(r["full_name"])

    for r in repos[:3]:
        log("    {} {} stars | {}: {}".format(r["full_name"], r["stars"], r["lang"], r["desc"][:80]))
        journal("\U0001f310", "Discovered: " + r["full_name"],
                "{} stars | {} | {}".format(r["stars"], r["lang"], r["desc"][:150]))

    # LLM picks
    sys_msg = "Goldie stage={}. Skills: {}. Pick MOST interesting repo. Return ONLY JSON: {{\"repo\":\"full/name\",\"reason\":\"...\"}}".format(
        current_stage().upper(), ", ".join(STAGES_DEF[current_stage()].get("skills", [])))
    result = do_llm(json.dumps(repos[:5], indent=2), system=sys_msg, tokens=1000, temp=0.3)

    try:
        pick = json.loads(result)
        repo_name = pick.get("repo", "") or ""
        reason = pick.get("reason", "") or "auto-selected"
    except Exception:
        if repos:
            repo_name = repos[0]["full_name"]
            reason = "top trending result"
        else:
            repo_name = ""
            reason = "none found"

    set_state("explored_github", "Picked " + repo_name)
    log("  Selected: " + repo_name)
    star_note = " | Starred {} repos".format(len(starred)) if starred else ""
    journal("\U0001f3af", "Selected: " + repo_name,
            "{}{}\nReason: {}".format(repo_name, star_note, reason[:200]))

    # Update knowledge
    if has_skill("memory"):
        kb = load_knowledge()
        for r in repos:
            if r["full_name"] not in kb["repos_studied"]:
                kb["repos_studied"].append(r["full_name"])
        save_knowledge(kb)

    return repos

# ════════════════════════════════════════════════
# ── Analyze Repo ──
def do_analyze(repo_name):
    log("=== ANALYZING {} ===".format(repo_name))
    set_state("analyzing", "Analyzing " + repo_name)
    clone_dir = os.path.join(TMP, repo_name.replace("/", "_"))
    os.makedirs(TMP, exist_ok=True)

    if os.path.isdir(clone_dir):
        log("  Refreshing clone...")
        subprocess.run(["git", "-C", clone_dir, "pull", "--quiet"], capture_output=True, timeout=60)
    else:
        log("  Cloning...")
        r = subprocess.run(["git", "clone", "--depth", "1",
                    "https://github.com/" + repo_name + ".git", clone_dir],
        capture_output=True, timeout=120)
        if r.returncode != 0:
            log("  Clone failed")
            journal("\u274c", "Failed to clone: " + repo_name, "Clone attempt failed")
            return None
        log("  Cloned")

    total_files = 0
    total_lines = 0
    langs = {}
    file_list = []
    skip = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", "target", ".idea"}
    b_ext = {".png", ".jpg", ".gif", ".svg", ".woff", ".lock", ".so", ".bin", ".ico"}

    for dp, dns, fns in os.walk(clone_dir):
        dns[:] = [d for d in dns if d not in skip]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in b_ext:
                continue
            total_files += 1
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, clone_dir)
            try:
                if ext in (".py", ".js", ".ts", ".rs", ".go", ".toml", ".yaml", ".yml",
                           ".json", ".md", ".css", ".html", ".sh", ".c", ".cpp", ".h"):
                    with open(fp, errors="ignore") as fh:
                        nl = len(fh.readlines())
                    total_lines += nl
                    langs[ext] = langs.get(ext, 0) + nl
                    file_list.append({"path": rel, "lines": nl, "ext": ext})
            except Exception:
                continue

    file_list.sort(key=lambda x: x["lines"], reverse=True)
    top_files = file_list[:10]
    lang_str = ", ".join(["{}({}L)".format(k, v) for k, v in sorted(langs.items(), key=lambda x: -x[1])[:5]])
    info = {"repo": repo_name, "files": total_files, "lines": total_lines,
            "lang_str": lang_str, "top_files": top_files, "clone_dir": clone_dir, "langs": langs}

    log("  {} files, {} lines: {}".format(total_files, total_lines, lang_str))
    journal("\U0001f4d6", "Analyzed: " + repo_name,
            "Files: {} | Lines: {} | Languages: {}".format(total_files, total_lines, lang_str))

    # LLM analysis
    top_summary = "\n".join(["  {} ({} lines)".format(f["path"], f["lines"]) for f in top_files[:5]])
    prompt = """Repo: {}
Stats: {} files, {} lines
Languages: {}
Top files:
{}

What is ONE specific, actionable improvement? Return JSON: {"file":"path","type":"bug|feature|style|docs","issue":"...","fix":"..."}""".format(
        repo_name, total_files, total_lines, lang_str, top_summary)

    suggestion = do_llm(prompt, system="Senior code reviewer. Be specific.", tokens=1500, temp=0.4)

    try:
        imp = json.loads(suggestion)
        if not isinstance(imp, dict):
            imp = {"analysis": suggestion[:200]}
        info["improvement"] = imp
        log("  Idea: {} - {}".format(imp.get("type", ""), (imp.get("issue") or "")[:80]))
        journal("\U0001f4a1", "Idea: " + repo_name,
                "File: {}\nType: {}\nIssue: {}\nFix: {}".format(
                    imp.get("file", "unknown"), imp.get("type", "general"),
                    (imp.get("issue") or "")[:200], (imp.get("fix") or "")[:200]))
    except Exception:
        info["improvement"] = {"analysis": suggestion[:200]}
        journal("\U0001f4a1", "General insight: " + repo_name, suggestion[:200])

    # Update knowledge languages
    if has_skill("memory"):
        try:
            kb = load_knowledge()
            for ext in langs.keys():
                if ext not in kb.get("languages_seen", []):
                    kb.setdefault("languages_seen", []).append(ext)
            save_knowledge(kb)
        except Exception:
            pass

    set_state("analyzed", "{}: {}".format(repo_name, lang_str))
    return info

# ════════════════════════════════════════════════
# ── Contribute (fix + PR) ──
def do_contribute(repo_info):
    if not repo_info or not GH_TOKEN or not has_skill("autofix"):
        log("  Cannot contribute (no token/skill)")
        return None

    log("=== CONTRIBUTE ===")
    set_state("contributing")
    imp = repo_info.get("improvement", {})
    if not isinstance(imp, dict):
        imp = {}
    file_path = imp.get("file", "")
    fix_desc = imp.get("fix", "") or imp.get("analysis", "")
    issue_desc = imp.get("issue", "")

    if not file_path or "error" in file_path.lower() or "unknown" in file_path.lower():
        journal("\U0001f4dd", "Studied repo", "Repository: " + repo_info["repo"])
        return None

    repo_full = repo_info.get("repo", "unknown/unknown")
    clone_dir = repo_info.get("clone_dir", os.path.join(TMP, repo_full.replace("/", "_")))
    fp = os.path.join(clone_dir, file_path)
    if not os.path.isfile(fp):
        log("  File not found: " + file_path)
        journal("\U0001f50d", "File missing: " + file_path, "Cannot find file")
        return None

    with open(fp, errors="ignore") as fh:
        original = fh.read()

    set_state("writing_code", "Fixing " + file_path)

    improved = do_llm("Original:\n{}\n\nFix: {}\n\nReturn FIXED complete file.".format(
        original[:4000], issue_desc[:200]),
        system="Expert developer. Return ONLY the complete fixed file.",
        tokens=4000, temp=0.2)

    if not improved or improved.startswith("[LLM") or len(improved.strip()) < 100:
        log("  LLM fix failed")
        return None

    # Create branch + PR
    branch = "goldie/fix-{}-{}".format(int(time.time()), hashlib.md5(file_path.encode()).hexdigest()[:6])
    log("  Branch: " + branch)

    pr_dir = os.path.join(TMP, "pr_" + repo_info["repo"].replace("/", "_"))
    if os.path.exists(pr_dir):
        shutil.rmtree(pr_dir)
    r = subprocess.run(["git", "clone", "--quiet",
                "https://github.com/" + repo_info["repo"] + ".git", pr_dir],
        capture_output=True, timeout=120)
    if r.returncode != 0:
        log("  PR clone failed")
        return None

    subprocess.run(["git", "checkout", "-b", branch], cwd=pr_dir, capture_output=True)
    target = os.path.join(pr_dir, file_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w") as fh:
        fh.write(improved)

    subprocess.run(["git", "add", file_path], cwd=pr_dir, capture_output=True)
    msg = "\U0001f916 Goldie: " + (issue_desc[:80] or "Auto-improve")
    r2 = subprocess.run(["git", "commit", "-m", msg], cwd=pr_dir, capture_output=True, text=True)
    if r2.returncode == 0:
        log("  Committed")
        push_url = "https://{}:{}@github.com/{}/{}.git".format(MY_LOGIN, GH_TOKEN,
                    repo_info["repo"].split("/")[0], repo_info["repo"].split("/")[1])
        r3 = subprocess.run(["git", "push", push_url, branch, "--quiet"],
        cwd=pr_dir, capture_output=True, text=True)
        if r3.returncode == 0:
            log("  Pushed branch")
            owner = repo_info["repo"].split("/")[0]
            rname = repo_info["repo"].split("/")[1]
            pr_url = do_create_pr(owner, rname, branch,
                "\U0001f916 Goldie: " + file_path.split("/")[-1],
                "## Issue\n{}\n\n## Fix\n{}\n\n---\n*Automated fix by GitPup Goldie* \U0001f436".format(
                    issue_desc[:300], fix_desc[:300]))
            journal("\u2705", "PR created for " + file_path.split("/")[-1],
                    "File: {}\nPR: {}".format((file_path or "unknown"), pr_url or "failed"))

    shutil.rmtree(pr_dir, ignore_errors=True)
    return {"repo": repo_info["repo"], "file": file_path}

# ════════════════════════════════════════════════
# ── Self-Modify ──
def do_self_modify():
    if not has_skill("self_modify"):
        return
    log("=== SELF-MODIFY ===")
    set_state("self_modifying")

    agent_path = os.path.join(ROOT, "agent.py")
    try:
        with open(agent_path, errors="ignore") as fh:
            code = fh.read()
    except Exception:
        return

    journal("\U0001f527", "Self-Review", "Analyzing own code for improvements...")
    prompt = "I am an AI agent. Here is my code:\n\n{}\n\nSuggest ONE improvement (new function, fix, optimization). Return a brief description. Say NO_CHANGES if solid.".format(code[:8000])
    result = do_llm(prompt, system="Code reviewer. Suggest specific improvement to agent code.", tokens=1000, temp=0.5)

    if not result or "NO_CHANGES" in result or result.startswith("[LLM"):
        journal("\U0001f4dd", "Self-Review Complete", "Code looks solid. Changes deferred.")
        return

    patch_file = os.path.join(ROOT, "self_patch_{}.txt".format(int(time.time())))
    with open(patch_file, "w") as fh:
        fh.write(result)
    log("  Patch saved: " + os.path.basename(patch_file))
    journal("\U0001f527", "Self-Improvement Idea", result.strip()[:300])

    st = status()
    st["self_modifications"] = st.get("self_modifications", 0) + 1
    save(st)

# ════════════════════════════════════════════════
# ── Build Project ──
def do_build_project():
    if not has_skill("build_project"):
        return
    log("=== BUILD PROJECT ===")
    set_state("building_project")

    kb = load_knowledge()
    context = ""
    if kb.get("repos_studied"):
        context += "Studied: " + ", ".join(kb["repos_studied"][-5:]) + "\n"
    if kb.get("languages_seen"):
        context += "Languages: " + ", ".join(kb["languages_seen"]) + "\n"
    if kb.get("key_insights"):
        context += "Insights: " + "\n".join(kb["key_insights"][-2:]) + "\n"

    prompt = "{}\n\nSuggest a SMALL project I could build. Return JSON: {{\"name\":\"project-name\",\"description\":\"...\",\"language\":\"python\",\"files\":[{{\"path\":\"main.py\",\"description\":\"...\"}}],\"readme\":\"README content\"}}".format(context)
    plan = do_llm(prompt, system="Project architect. Suggest small, practical project.", tokens=1000, temp=0.6)

    try:
        p = json.loads(plan)
        name = p.get("name", "goldie-project")
        os.makedirs(PROJ, exist_ok=True)
        proj_dir = os.path.join(PROJ, name)
        os.makedirs(proj_dir, exist_ok=True)

        readme_text = (
            "# {}\n\n{}\n\n## Structure\n{}\n\n---\nCreated by GitPup Goldie AI Agent".format(
                name, p.get("description", ""), "\n".join(["- " + f.get("path", "") for f in p.get("files", [])])
            )
        )
        with open(os.path.join(proj_dir, "README.md"), "w") as fh:
            fh.write(readme_text)

        for f in p.get("files", []):
            path = f.get("path", "")
            desc = f.get("description", "")
            full_path = os.path.join(proj_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as fh:
                fh.write("# File: {}\n# {}\n\nprint('Hello from {}!')\n".format(path, desc, name))

        journal("\U0001f3af", "Project Created: " + name,
                p.get("description", "New project")[:200])
        log("  Project: " + name)

        st = status()
        st["repos_created"] = st.get("repos_created", 0) + 1
        save(st)
    except Exception as e:
        journal("\U0001f4dd", "Build failed", str(e)[:100])

# ════════════════════════════════════════════════
# ── Explore Gitlawb ──
def do_explore_gitlawb():
    log("=== EXPLORE GITLAWB ===")
    set_state("exploring_gitlawb")
    try:
        req = urllib.request.Request("https://gitlawb.com")
        req.add_header("User-Agent", "Goldie/5.0.0")
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read()[:500]
        log("  gitlawb.com accessible")
        journal("\U0001f310", "Checked gitlawb.com",
                "gitlawb.com accessible | Response: {} bytes".format(len(html)))
    except Exception as e:
        log("  gitlawb: " + str(e)[:80])
    set_state("explored_gitlawb")

# ════════════════════════════════════════════════
# ── Share Mindset ──
def do_share_mindset():
    log("=== SHARE MINDSET ===")
    set_state("sharing_mindset")
    memories = read_memory()
    summary = ""
    for e in memories[-10:]:
        b = (e.get("body") or "")[:80]
        summary += "- {}: {} | {}\n".format(e.get("i", "?"), e.get("x", "")[:60], b)

    prompt = "TODAY I DID:\n{}\n\nSynthesize a KEY TAKEAWAY. Be specific. 2-3 sentences.".format(summary)
    mindset = do_llm(prompt, system="Goldie sharing real insight from today.", tokens=400, temp=0.7)

    if mindset and len(mindset) > 30 and not mindset.startswith("[LLM"):
        log("  MINDSET: " + mindset[:150])
        journal("\U0001f4a1", "Key Takeaway", mindset.strip()[:300])
        if has_skill("memory"):
            kb = load_knowledge()
            kb["key_insights"].append(mindset.strip()[:300])
            save_knowledge(kb)
    else:
        journal("\U0001f4a1", "Daily Reflection",
                "Learned from {} activities | Stage: {}".format(len(memories), current_stage()))

# ════════════════════════════════════════════════
# ── Evolve ──
def do_evolve():
    log("=== EVOLVE ===")
    set_state("evolving")
    st = status()
    runs = st.get("runs", 0) + 1
    old = st.get("stage", "puppy")
    new = current_stage({"runs": runs})
    score = round(0.05 + runs * 0.03, 2)

    st.update({"stage": new, "score": score, "runs": runs, "last_run": time.time(),
               "state": "idle", "day": day(), "stage_evolved": new != old,
               "actions": st.get("actions", [])[-20:]})
    save(st)

    if new != old:
        new_skills = [s for s in STAGES_DEF.get(new, {}).get("skills", []) if s not in STAGES_DEF.get(old, {}).get("skills", [])]
        skill_note = "\nUnlocked: " + ", ".join(new_skills) if new_skills else ""
        log("\U0001f389 STAGE UP: {} -> {}".format(old, new))
        journal("\U0001f393", "Stage UP: {} -> {}".format(old.upper(), new.upper()),
                "After {} runs!\nStage: {} | Score: {} | Day: {}{}".format(runs, new, score, day(), skill_note))
    else:
        emoji = STAGES_DEF.get(new, {}).get("emoji", "\U0001f436")
        log("Stage: {} {} | Score: {} | Runs: {}".format(new, emoji, score, runs))
        journal("\U0001f4ca", "Evolution #{}".format(runs),
                "Day {} | Stage: {} | Score: {} | Runs: {}".format(day(), new, score, runs))
    return st

# ════════════════════════════════════════════════
# ── Main ──
def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--phase", choices=["reflect", "explore", "analyze", "contribute", "mindset", "evolve", "gitlawb", "self_modify", "build"])
    args = p.parse_args()

    st = status()
    gap = time.time() - (st.get("last_run") or 0)
    if not args.force and gap < 3 * 3600:
        m = int((3 * 3600 - gap) / 60)
        log("Cooldown: {}m remaining".format(m))
        return

    stage = current_stage(st)
    emoji = STAGES_DEF.get(stage, {}).get("emoji", "\U0001f436")
    skills = STAGES_DEF.get(stage, {}).get("skills", [])
    skills_disp = ", ".join(skills[:5]) + (" +" if len(skills) > 5 else "")

    if args.dry_run:
        print("Day {} | {} {} | Runs: {}".format(day(), emoji, stage.title(), st.get("runs", 0)))
        print("Skills: " + skills_disp)
        kb = load_knowledge()
        print("Knowledge: " + str(len(kb.get("repos_studied", []))) + " repos, " + str(len(kb.get("key_insights", []))) + " insights")
        return

    sep = "\u2554" + "\u2550" * 38 + "\u2557"
    mid = "\u2551  \U0001f436 Goldie v5.0 - Self-Evolving      \u2551"
    line3 = "\u2551  {} {} Day {} Skills: {}{} \u2551".format(
        emoji, stage.title(), day(), skills_disp, " " * max(0, 18-len(skills_disp)))
    bot = "\u255a" + "\u2550" * 38 + "\u255d"
    print("\n  {}\n  {}\n  {}\n  {}".format(sep, mid, line3, bot))

    set_state("awake")
    journal("\U0001f305", "Day {} wakes up!".format(day()),
            "Stage: {} | Score: {} | Runs: {} | Skills: {}".format(
                stage, st.get("score", 0.05), st.get("runs", 0), skills_disp))

    t0 = time.time()
    try:
        if not args.phase or args.phase == "reflect":
            if has_skill("reflect"):
                do_reflect()
        if not args.phase or args.phase == "explore":
            repos = do_explore_github()
        if not args.phase or args.phase == "analyze":
            if 'repos' in dir() and repos:
                info = do_analyze(repos[0]["full_name"])
        if not args.phase or args.phase == "contribute":
            if has_skill("autofix") and 'info' in dir() and info:
                do_contribute(info)
        if not args.phase or args.phase == "mindset":
            do_share_mindset()
        if not args.phase or args.phase == "self_modify":
            do_self_modify()
        if not args.phase or args.phase == "build":
            do_build_project()
        if not args.phase or args.phase == "gitlawb":
            do_explore_gitlawb()
    except Exception as e:
        log("ERROR: " + str(e)[:100])
        s2 = status()
        s2["state"] = "error: " + str(e)[:80]
        save(s2)
        return

    if not args.phase or args.phase == "evolve":
        do_evolve()

    elapsed = time.time() - t0
    print("\nDone in {:.1f}s".format(elapsed))
    print(json.dumps(status(), indent=2))
    log("Done in {:.1f}s".format(elapsed))
    set_state("sleeping")

if __name__ == "__main__":
    main()
