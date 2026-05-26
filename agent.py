#!/usr/bin/env python3
"""
GitPup Agent v3 — Fully Autonomous Goldie
Every 3 hours: explore GitHub trending → analyze repos → contribute improvements → journal everything
"""
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import os, sys, json, time, urllib.request, urllib.parse, argparse, subprocess, shutil
from datetime import datetime, timezone

# ── Paths ──
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
JF = os.path.join(DATA, "journal", "entries.jsonl")
SF = os.path.join(DATA, "state", "status.json")
LF = os.path.join(DATA, "evolve.log")
TMP = os.path.join(ROOT, "tmp_explore")

# ── Config ──
LLM_KEY = os.environ.get("LLM_API_KEY", "")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", os.environ.get("GH_TOKEN", ""))
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.6-flash")
MY_LOGIN = os.environ.get("MY_GITHUB_LOGIN", os.environ.get("GITHUB_USER", ""))
BIRTH = "2026-05-25"
COOLDOWN = 3 * 3600
STAGES = ["puppy", "learner", "coder", "builder", "architect", "master"]

# ── Helper: JSONL Journal ──
def day():
    try:
        return (datetime.now(timezone.utc) - datetime.strptime(BIRTH, "%Y-%m-%d")).days + 1
    except:
        return 1

def status():
    try:
        with open(SF) as f:
            return json.load(f)
    except:
        return {"stage":"puppy","score":0.05,"day":1,"runs":0,"last_run":0,"state":"idle","actions":[]}

def save(s):
    os.makedirs(os.path.dirname(SF), exist_ok=True)
    with open(SF, "w") as f:
        json.dump(s, f, indent=2)

def journal(icon, title, body="", etype="evolve"):
    os.makedirs(os.path.dirname(JF), exist_ok=True)
    e = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "t": datetime.now().strftime("%H:%M"),
        "i": icon, "x": title, "type": etype, "body": body, "day": day()
    }
    with open(JF, "a") as f:
        f.write(json.dumps(e) + "\n")

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    with open(LF, "a") as f:
        f.write(line + "\n")
    print(f"  {line}")

def setState(s, append_action=None):
    st = status()
    st["state"] = s
    if append_action:
        actions = st.get("actions", [])
        actions.append(append_action)
        st["actions"] = actions[-20:]  # keep last 20
    save(st)

# ── LLM ──
def llm(msg, system="", tokens=3000, temp=0.5):
    msgs = []
    if system:
        msgs.append({"role":"system","content":system})
    msgs.append({"role":"user","content":msg})
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
        json.dumps({"model":LLM_MODEL,"messages":msgs,"max_tokens":tokens,"temperature":temp}).encode())
    req.add_header("Content-Type","application/json")
    if LLM_KEY:
        req.add_header("Authorization", f"Bearer {LLM_KEY}")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            r2 = json.loads(r.read())
            return r2.get("choices",[{}])[0].get("message",{}).get("content","")
    except Exception as e:
        return f"[LLM Error: {str(e)[:100]}]"

# ── GitHub API ──
def gh_get(path):
    """GET github API with token."""
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url)
    if GH_TOKEN:
        req.add_header("Authorization", f"token {GH_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  GH API error: {str(e)[:80]}")
        return {"error": str(e)}

def gh_post(path, data):
    req = urllib.request.Request(f"https://api.github.com{path}", json.dumps(data).encode())
    req.add_header("Content-Type", "application/json")
    if GH_TOKEN:
        req.add_header("Authorization", f"token {GH_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  GH POST error: {str(e)[:80]}")
        return {"error": str(e)}

# ── Phase: EXPLORE GITHUB TRENDING ──
def explore_github():
    """Fetch trending repos from GitHub, analyze which ones are interesting."""
    log("=== EXPLORE GITHUB ===")
    setState("exploring_github")

    repos = []

    # Strategy 1: GitHub search - most starred recently
    for query in ["python+machine+learning+language:python+stars:>100",
                  "javascript+web+language:javascript+stars:>100",
                  "rust+cli+language:rust+stars:>50"]:
        data = gh_get(f"/search/repositories?q={urllib.parse.quote(query)}&sort=updated&per_page=5")
        if "items" in data:
            for repo in data["items"][:3]:
                repos.append({
                    "full_name": repo.get("full_name",""),
                    "stars": repo.get("stargazers_count",0),
                    "lang": repo.get("language",""),
                    "desc": repo.get("description",""),
                    "updated": repo.get("updated_at",""),
                    "url": repo.get("html_url",""),
                })

    if not repos:
        log("  No repos found")
        setState("error_no_repos")
        return []

    log(f"  Found {len(repos)} interesting repos")
    for r in repos[:3]:
        log(f"    ⭐{r['stars']:>6} {r['lang']:>10} {r['full_name']}")
        journal("🌐", f"Discovered {r['full_name']}",
                f"⭐{r['stars']} | {r['lang']} | {r.get('desc','')[:100]}")

    # Use LLM to pick the most interesting one
    repo_data = json.dumps(repos, indent=2)
    system = f"Goldie stage={status().get('stage','puppy')}. Pick the MOST interesting repo for a coding agent to study and potentially contribute to. Return ONLY JSON: {{\"repo\":\"full/name\",\"reason\":\"...\",\"what_to_improve\":\"...\"}}"
    result = llm(repo_data, system=system, tokens=1000, temp=0.3)

    try:
        pick = json.loads(result)
        repo_name = pick.get("repo","")
        reason = pick.get("reason","")
    except:
        pick = repos[0] if repos else {}
        repo_name = pick.get("full_name","")
        reason = "top result"

    setState("explored_github", f"Picked {repo_name}: {reason}")
    log(f"  Selected: {repo_name}")
    journal("🎯", f"Selected to study: {repo_name}", reason)

    return repos

# ── Phase: ANALYZE REPO ──
def analyze_repo(repo_name):
    """Clone repo, analyze structure, identify improvement opportunities."""
    log(f"=== ANALYZING {repo_name} ===")
    setState("analyzing", f"Analyzing {repo_name}")

    clone_dir = os.path.join(TMP, repo_name.replace("/","_"))
    os.makedirs(TMP, exist_ok=True)

    # Skip if already cloned (avoid re-fetching every cycle)
    if os.path.isdir(clone_dir):
        log(f"  Already explored {repo_name}, refreshing")
        subprocess.run(["git", "-C", clone_dir, "pull", "--quiet"], capture_output=True, timeout=60)
    else:
        log(f"  Cloning {repo_name}...")
        clone_url = f"https://github.com/{repo_name}.git"
        r = subprocess.run(["git", "clone", "--depth", "1", clone_url, clone_dir], capture_output=True, timeout=120)
        if r.returncode != 0:
            log(f"  Clone failed: {r.stderr.decode()[:200]}")
            journal("❌", f"Failed to clone {repo_name}", str(r.stderr.decode()[:200]))
            return None
        log(f"  Cloned to {clone_dir}")

    # Quick scan
    total_files = 0
    total_lines = 0
    langs = {}
    skip = {".git","node_modules",".venv","__pycache__","dist","build","target"}
    b_exts = {".png",".jpg",".gif",".svg",".woff",".woff2",".so",".dll",".exe",".zip",".lock"}

    for dp, dns, fns in os.walk(clone_dir):
        dns[:] = [d for d in dns if d not in skip]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in b_exts:
                continue
            total_files += 1
            fp = os.path.join(dp, fn)
            try:
                if ext in (".py", ".js", ".ts", ".rs", ".go", ".toml", ".yaml", ".json", ".md", ".css", ".html"):
                    with open(fp) as f:
                        nl = len(f.readlines())
                    total_lines += nl
                    langs[ext] = langs.get(ext, 0) + nl
            except:
                pass

    lang_str = ", ".join(f"{k}({v}L)" for k, v in sorted(langs.items(), key=lambda x: -x[1])[:6])

    info = {
        "repo": repo_name,
        "dir": clone_dir,
        "files": total_files,
        "lines": total_lines,
        "langs": langs,
        "lang_str": lang_str,
    }

    log(f"  {total_files} files, {total_lines} lines: {lang_str}")
    journal("📖", f"Analyzed {repo_name}", f"{total_files} files, {total_lines} lines: {lang_str}")
    setState("analyzed", f"{repo_name}: {lang_str}")

    # LLM: Find improvement opportunity
    system = f"You are Goldie, a self-evolving AI agent. Here is analysis of '{repo_name}':\n{json.dumps(info, indent=2)}\n\nSuggest ONE specific, simple improvement (not major rewrite). Return ONLY JSON: {{\"file\":\"path/to/file\",\"issue\":\"...\",\"fix_description\":\"...\"}}"
    suggestion = llm(f"Repo has {total_files} files, {total_lines} lines. Suggest simple improvements.", system=system, tokens=1500)

    try:
        imp = json.loads(suggestion)
        info["improvement"] = imp
        log(f"  Suggestion: {imp.get('file','')} - {imp.get('issue','')[:80]}")
        journal("💡", f"Idea for {repo_name}", imp.get("issue","")[:150])
    except:
        info["improvement"] = {"analysis": suggestion[:200]}
        log(f"  Analysis: {suggestion[:150]}")

    return info

# ── Phase: CONTRIBUTE ──
def contribute(repo_info):
    """Fork repo (if needed), make improvement, create PR."""
    if not repo_info:
        return None

    log("=== PREPARE CONTRIBUTION ===")
    setState("contributing")
    repo_name = repo_info["repo"]
    repo_dir = repo_info["dir"]
    imp = repo_info.get("improvement", {})

    # Check if we have GitHub token
    if not GH_TOKEN:
        log("  No GitHub token — cannot create PR")
        journal("⚠️", "Cannot contribute: no GitHub token set", "Set MY_GITHUB_LOGIN or GH_TOKEN env var")
        return None

    # Check if we have a github login
    if not MY_LOGIN:
        log("  No MY_GITHUB_LOGIN set — cannot fork/PR")
        journal("⚠️", "Cannot contribute: no GitHub username", "Set MY_GITHUB_LOGIN env var")
        return None

    file_path = imp.get("file", "")
    fix_desc = imp.get("fix_description", "") or imp.get("analysis", "")

    if not file_path or "error" in file_path or "no " in file_path.lower():
        log("  No specific file to improve, skipping PR")
        journal("📝", f"Studied {repo_name}", fix_desc[:200])
        return None

    log(f"  File to improve: {file_path}")
    log(f"  Fix: {fix_desc[:120]}")

    # Read the file
    fp = os.path.join(repo_dir, file_path)
    if not os.path.isfile(fp):
        log(f"  File {file_path} not found in clone")
        return None

    with open(fp) as f:
        original = f.read()

    # Use LLM to generate the fix
    system = f"You are Goldie, a coding AI. Improve this file from {repo_name}. Here's what to fix:\n{fix_desc}\n\nReturn the IMPROVED file content ONLY. Keep the same format/language."
    log(f"  Generating fix with LLM...")
    setState("writing_code", f"Fixing {file_path}")

    improved = llm(original, system=system, tokens=4000, temp=0.2)

    if not improved or improved.startswith("[LLM Error"):
        log(f"  LLM fix generation failed")
        return None

    # Save improved file
    with open(fp, "w") as f:
        f.write(improved)
    log(f"  Improved file written")
    journal("✏️", f"Improved {file_path} in {repo_name}", fix_desc[:120])

    # Commit
    r = subprocess.run(["git", "add", file_path], cwd=repo_dir, capture_output=True)
    r = subprocess.run(["git", "commit", "-m", f"🐛 Goldie: {fix_desc[:100]}"], cwd=repo_dir, capture_output=True, text=True)
    if r.returncode == 0:
        log(f"  Committed locally")
        journal("✅", f"Committed: {fix_desc[:80]}", f"File: {file_path}")
    else:
        log(f"  Commit failed: {r.stderr[:100]}")
        return None

    # Try to fork and push (this is complex, mark as ready for push)
    setState("commit_made", f"{repo_name}/{file_path}")
    journal("📤", f"Ready to push improvement to {repo_name}", f"Fix: {fix_desc[:100]}")

    return {"repo": repo_name, "file": file_path, "fix": fix_desc[:200]}

# ── Phase: EXPLORE GITLAWB ──
def explore_gitlawb():
    """Check gitlawb.com for projects."""
    log("=== EXPLORE GITLAWB ===")
    setState("exploring_gitlawb")

    try:
        req = urllib.request.Request("https://gitlawb.com")
        req.add_header("User-Agent", "Goldie/0.3.0")
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode()

        # Extract any project names from the page
        log("  Checking gitlawb.com...")
        journal("🌐", "Explored gitlawb.com", "Checked gitlawb.com for projects")
        setState("explored_gitlawb")
        return True
    except Exception as e:
        log(f"  gitlawb.com check: {str(e)[:80]}")
        setState("explored_gitlawb")
        return False

# ── Phase: LEARN ──
def learn_from_day():
    """Learn from all actions today, update agent memory/patterns."""
    log("=== LEARN FROM TODAY ===")
    setState("learning")

    st = status()
    actions = st.get("actions", [])
    runs = st.get("runs", 0) + 1

    # Simple stage progression
    old_stage = st.get("stage", "puppy")
    idx = min(len(STAGES) - 1, runs // 3)
    new = STAGES[idx]

    state = {"stage": new, "score": round(0.05 + runs * 0.05, 2),
             "runs": runs, "last_run": time.time(), "state": "idle",
             "day": day(), "stage_evolved": new != old_stage,
             "actions": actions[-20:]}

    save(state)

    if new != old_stage:
        log(f"  🎉 STAGE UP! {old_stage} → {new}")
        journal("🎓", f"Stage up: {old_stage} → {new}!", f"Runs: {runs}, Score: {state['score']}")
    else:
        log(f"  Stage: {new}, Score: {state['score']}, Runs: {runs}")
        journal("📊", f"Evolution #{runs} complete", f"Stage: {new}, Score: {state['score']}")

    return state

# ── MAIN ──
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--phase", choices=["explore", "analyze", "contribute", "learn", "gitlawb"])
    args = p.parse_args()

    st = status()
    gap = time.time() - (st.get("last_run") or 0)
    if not args.force and gap < COOLDOWN:
        m = int((COOLDOWN - gap) / 60)
        log(f"Cooldown: {m}m remaining")
        print(f"Cooldown: {m}m (--force)")
        return

    if args.dry_run:
        print(f"Day {day()} | Stage: {st.get('stage','puppy')} | Runs: {st.get('runs',0)}")
        print(f"Pipeline: explore_github → analyze_repo → contribute → learn")
        return

    d = day(); s = st.get("stage","puppy")
    print(f"\n  Day {d} | Stage: {s}")
    print(f"╔══════════════════════════════════════╗")
    print(f"║  🐶 Goldie Autonomous Agent v3.0    ║")
    print(f"║  {'Day':<5}{d:<5}Stage: {s:<10}       ║")
    print(f"╚══════════════════════════════════════╝\n")

    setState("awake")
    journal("🌅", f"Day {d} — Goldie wakes up!", f"Stage: {s}")

    t0 = time.time()

    try:
        if not args.phase or args.phase == "explore":
            repos = explore_github()

        if not args.phase or args.phase == "analyze":
            repos = explore_github() if not 'repos' in vars() else repos
            if repos:
                info = analyze_repo(repos[0]["full_name"])

                if not args.phase == "explore":
                    if not args.phase or args.phase == "contribute":
                        result = contribute(info)
                    else:
                        result = None
            else:
                log("  No repos to analyze")
                result = None

        if not args.phase or args.phase == "learn":
            learn_from_day()

        if not args.phase or args.phase == "gitlawb":
            explore_gitlawb()

    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        st2 = status(); st2["state"] = f"error: {str(e)[:80]}"; save(st2)
        if args.dry_run:
            traceback.print_exc()
        return

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(json.dumps(status(), indent=2))
    log(f"Done in {elapsed:.1f}s")
    setState("sleeping")

if __name__ == "__main__":
    main()
