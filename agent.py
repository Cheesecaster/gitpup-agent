#!/usr/bin/env python3
"""GitPup Agent v4 — Autonomous Self-Evolving Goldie"""
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

import os, sys, json, time, urllib.request, urllib.parse, argparse, subprocess, shutil
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
JF = os.path.join(DATA, "journal", "entries.jsonl")
SF = os.path.join(DATA, "state", "status.json")
LF = os.path.join(DATA, "evolve.log")
TMP = os.path.join(ROOT, "tmp_explore")

LLM_KEY = os.environ.get("LLM_API_KEY", "")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", os.environ.get("GH_TOKEN", ""))
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.6-flash")
MY_LOGIN = os.environ.get("MY_GITHUB_LOGIN", os.environ.get("GITHUB_USER", ""))
BIRTH = "2026-05-25"
COOLDOWN = 3 * 3600
STAGES = ["puppy", "learner", "coder", "builder", "architect", "master"]

def day():
    try: return (datetime.now(timezone.utc) - datetime.strptime(BIRTH,"%Y-%m-%d")).days + 1
    except: return 1

def status():
    try:
        with open(SF) as f: return json.load(f)
    except: return {"stage":"puppy","score":0.05,"day":1,"runs":0,"last_run":0,"state":"idle","actions":[]}

def save(s):
    os.makedirs(os.path.dirname(SF), exist_ok=True)
    with open(SF,"w") as f: json.dump(s, f, indent=2)

def journal(icon, title, body="", etype="evolve"):
    os.makedirs(os.path.dirname(JF), exist_ok=True)
    e = {"ts":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "t":datetime.now().strftime("%H:%M"),
         "i":icon,"x":title,"body":body,"type":etype,"day":day()}
    with open(JF,"a") as f: f.write(json.dumps(e)+"\n")

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = "[" + t + "] " + msg
    with open(LF,"a") as f: f.write(line+"\n")
    print("  " + line)

def setState(s, action=None):
    st = status(); st["state"] = s
    if action:
        a = st.get("actions",[]); a.append(action); st["actions"] = a[-20:]
    save(st)

def llm(msg, system="", tokens=3000, temp=0.5):
    msgs = []
    if system: msgs.append({"role":"system","content":system})
    msgs.append({"role":"user","content":msg})
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
        json.dumps({"model":LLM_MODEL,"messages":msgs,"max_tokens":tokens,"temperature":temp}).encode())
    req.add_header("Content-Type","application/json")
    if LLM_KEY: req.add_header("Authorization","Bearer "+LLM_KEY)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            r2 = json.loads(r.read())
            return r2.get("choices",[{}])[0].get("message",{}).get("content","")
    except Exception as e:
        return "[LLM Error: " + str(e)[:100] + "]"

def gh_get(path):
    url = "https://api.github.com" + path
    req = urllib.request.Request(url)
    if GH_TOKEN: req.add_header("Authorization","token "+GH_TOKEN)
    req.add_header("Accept","application/vnd.github.v3+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
    except Exception as e: return {"error":str(e)}

def gh_post(path, data):
    req = urllib.request.Request("https://api.github.com"+path, json.dumps(data).encode())
    req.add_header("Content-Type","application/json")
    if GH_TOKEN: req.add_header("Authorization","token "+GH_TOKEN)
    req.add_header("Accept","application/vnd.github.v3+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
    except Exception as e: return {"error":str(e)}


def star_github_repo(repo_name):
    """Star a GitHub repo via PUT /user/starred/{owner}/{repo}."""
    if not GH_TOKEN:
        log("  Cannot star (no token)")
        return False
    log("STAR: " + repo_name)
    req = urllib.request.Request(
        "https://api.github.com/user/starred/" + repo_name,
        data=b"",
        method="PUT"
    )
    req.add_header("Authorization", "token " + GH_TOKEN)
    req.add_header("Content-Length", "0")
    req.add_header("Accept", "application/vnd.github.v3+json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status in (204, 201):
                log("  STARRED: " + repo_name)
                journal("\u2b50", "Starred: " + repo_name, "Added to favorites | \u2605")
                return True
            return False
    except Exception as e:
        log("  Star error: " + str(e)[:100])
        return False
# ── EXPLORE GITHUB ──
def explore_github():
    log("=== EXPLORE GITHUB ===")
    setState("exploring_github")
    repos = []

    # Search for TOP repos with 5000+ stars (actually popular)
    queries = [
        "python+stars:>5000",
        "javascript+stars:>5000",
        "rust+stars:>2000",
    ]
    for q in queries:
        # Sort by stars (not updated date) to get genuinely popular repos
        data = gh_get("/search/repositories?q=" + urllib.parse.quote(q) + "&sort=stars&order=desc&per_page=3")
        if "items" in data and len(data["items"]) > 0:
            for repo in data["items"][:3]:
                rname = repo.get("full_name") or ""
                rstars = repo.get("stargazers_count") or 0
                rlang = repo.get("language") or "unknown"
                rdesc = (repo.get("description") or "no description")[:200]
                rurl = repo.get("html_url") or ""
                rtopics = ", ".join(repo.get("topics", [])[:5])
                if rstars >= 1000:  # Only repos with real traction
                    repos.append({
                        "full_name": rname,
                        "stars": rstars,
                        "lang": rlang,
                        "desc": rdesc,
                        "url": rurl,
                        "topics": rtopics,
                    })

    if not repos:
        log("  Star search empty, falling back to trending...")
        fb_data = gh_get("/search/repositories?q=trending&sort=stars&order=desc&per_page=5")
        if "items" in fb_data:
            for repo in fb_data["items"]:
                n = repo.get("full_name") or ""
                s = repo.get("stargazers_count") or 0
                if n:
                    repos.append({
                        "full_name": n, "stars": s,
                        "lang": repo.get("language") or "unknown",
                        "desc": (repo.get("description") or "No description")[:200],
                        "url": repo.get("html_url") or "",
                    })
        if not repos:
            log("  No GitHub repos found")
            return []

    # Auto-star repos with 10000+ stars
    starred = []
    for r in repos:
        if r.get("stars", 0) >= 10000 and star_github_repo(r["full_name"]):
            starred.append(r["full_name"])

    log("  Found " + str(len(repos)) + " repos")
    for r in repos[:3]:
        stars = str(r.get("stars",0) or 0)
        lang = r.get("lang") or "unknown"
        name = r.get("full_name") or ""
        desc = r.get("desc") or "no description"
        log("    " + stars + " " + lang + " " + name)
        journal("\ud83c\udf10", "Discovered: " + name, "{} stars | {} | {}".format(stars, lang, (desc or "no description")[:150]))

    sys_msg = "Goldie stage=" + status().get("stage","puppy") + ". Pick MOST interesting repo. Return ONLY JSON: {\"repo\":\"full/name\",\"reason\":\"...\"}"
    result = llm(json.dumps(repos, indent=2), system=sys_msg, tokens=1000, temp=0.3)

    try:
        pick = json.loads(result)
        repo_name = pick.get("repo","")
        reason = pick.get("reason","")
    except:
        if repos:
            repo_name = repos[0]["full_name"]
            reason = "top result"
        else:
            repo_name = ""
            reason = "none found"

    setState("explored_github", "Picked " + repo_name)
    log("  Selected: " + repo_name)
    journal("\ud83c\udfaf", "Selected to study: " + repo_name, "{}\nReason: {}".format(repo_name, (reason or "auto-selected")[:200]))
    return repos

# ── ANALYZE REPO ──
def analyze_repo(repo_name):
    log("=== ANALYZING " + repo_name + " ===")
    setState("analyzing", "Analyzing " + repo_name)
    clone_dir = os.path.join(TMP, repo_name.replace("/","_"))
    os.makedirs(TMP, exist_ok=True)

    if os.path.isdir(clone_dir):
        log("  Already cloned, refreshing")
        subprocess.run(["git","-C",clone_dir,"pull","--quiet"], capture_output=True, timeout=60)
    else:
        log("  Cloning...")
        r = subprocess.run(["git","clone","--depth","1","https://github.com/"+repo_name+".git",clone_dir],
                          capture_output=True, timeout=120)
        if r.returncode != 0:
            log("  Clone failed")
            journal("\u274c", "Failed to clone: " + repo_name, "Clone attempt failed for {}".format(repo_name))
            return None
        log("  Cloned")

    # Quick scan
    total_files = 0; total_lines = 0; langs = {}
    skip = {".git","node_modules",".venv","__pycache__","dist","build","target"}
    b_ext = {".png",".jpg",".gif",".svg",".woff",".lock",".so",".dll"}

    for dp,dns,fns in os.walk(clone_dir):
        dns[:] = [d for d in dns if d not in skip]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in b_ext: continue
            total_files += 1
            fp = os.path.join(dp,fn)
            try:
                if ext in (".py",".js",".ts",".rs",".go",".toml",".yaml",".json",".md",".css",".html",".sh"):
                    with open(fp) as f: nl = len(f.readlines())
                    total_lines += nl
                    langs[ext] = langs.get(ext,0) + nl
            except: pass

    lang_str = ", ".join([k+"("+str(v)+"L)" for k,v in sorted(langs.items(), key=lambda x:-x[1])[:5]])
    info = {"repo":repo_name,"files":total_files,"lines":total_lines,"lang_str":lang_str}
    log("  " + str(total_files) + " files, " + str(total_lines) + " lines: " + lang_str)
    journal("\ud83d\udcd6", "Analyzed: " + repo_name, "Files: {} | Lines: {} | Languages: {}".format(total_files, total_lines, lang_str))
    setState("analyzed", repo_name + ": " + lang_str)

    # LLM improvement suggestion
    sys_msg = "You are Goldie. Suggest ONE simple improvement. Return ONLY: {\"file\":\"path\",\"issue\":\"...\",\"fix\":\"...\"}"
    suggestion = llm("Repo: " + repo_name + ", " + str(total_files) + " files, " + lang_str, system=sys_msg, tokens=1500)

    try:
        imp = json.loads(suggestion); info["improvement"] = imp
        log("  Suggestion: " + str(imp.get("file","")))
        journal("\ud83d\udca1", "Idea for: " + repo_name, "File: {}\nIssue: {}\nFix: {}".format((imp.get("file") or "unknown"), (imp.get("issue") or "N/A")[:150], (imp.get("fix") or "N/A")[:150]))
    except:
        info["improvement"] = {"analysis": suggestion[:200]}

    return info

# ── CONTRIBUTE ──
def contribute(repo_info):
    if not repo_info or not GH_TOKEN or not MY_LOGIN:
        log("  Cannot contribute (no token/login)")
        return None

    log("=== CONTRIBUTE ===")
    setState("contributing")
    imp = repo_info.get("improvement",{})
    file_path = imp.get("file","")
    fix_desc = imp.get("fix","") or imp.get("analysis","")

    if not file_path or "error" in file_path.lower():
        journal("\ud83d\udcdd", "Studied: " + repo_info["repo"], "Repository: {}\nImprovement: {}\nAnalysis: {}".format(repo_info["repo"], (fix_desc or "general study")[:100], "Learning from codebase structure"))
        return None

    clone_dir = os.path.join(TMP, repo_info["repo"].replace("/","_"))
    fp = os.path.join(clone_dir, file_path)
    if not os.path.isfile(fp):
        log("  File not found: " + file_path)
        return None

    with open(fp) as f: original = f.read()
    setState("writing_code", "Fixing " + file_path)

    improved = llm(original, system="Fix: " + (fix_desc or "no description")[:100] + "\nReturn IMPROVED file content ONLY.", tokens=4000, temp=0.2)
    if not improved or improved.startswith("[LLM"):
        log("  LLM fix failed")
        return None

    with open(fp,"w") as f: f.write(improved)
    subprocess.run(["git","add",file_path], cwd=clone_dir, capture_output=True)
    r = subprocess.run(["git","commit","-m","Goldie auto-fix: "+(fix_desc or "no description")[:60]], cwd=clone_dir, capture_output=True, text=True)
    if r.returncode == 0:
        log("  Committed locally")
        journal("\u2705", "Committed: " + (file_path or "unknown")[:40], "File: {}\nChange: {}".format((file_path or "unknown"), (fix_desc or "fix")[:100]))
    else:
        log("  Commit failed")
        return None

    setState("commit_made", repo_info["repo"] + "/" + file_path)
    return {"repo": repo_info["repo"], "file": file_path}

# ── EXPLORE GITLAWB ──
def explore_gitlawb():
    log("=== EXPLORE GITLAWB ===")
    setState("exploring_gitlawb")
    try:
        req = urllib.request.Request("https://gitlawb.com")
        req.add_header("User-Agent", "Goldie/0.4.0")
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode()[:500]
        log("  gitlawb.com accessible")
        journal("\ud83c\udf10", "Checked gitlawb.com", "gitlawb.com accessible | Response size: {} bytes".format(len(html) if html else 0))
    except Exception as e:
        log("  gitlawb: " + str(e)[:80])
    setState("explored_gitlawb")


def share_mindset():
    """LLM analyzes what Goldie learned today and shares REAL insights"""
    log("=== SHARE MINDSET ===")
    setState("sharing_mindset")
    # Read recent journal entries
    entries = []
    try:
        with open(JF, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except: pass

    # Get last 5 entries for context
    recent = entries[-5:] if len(entries) > 5 else entries
    summary = ""
    for e in recent:
        summary += "- {}: {} [{}] {}\n".format(
            e.get("i","?"),
            e.get("x",""),
            e.get("t",""),
            (e.get("body","") or "")[:100]
        )

    # Ask LLM to synthesize a key takeaway
    sys_prompt = "You are Goldie, a learning golden retriever AI agent. Based on today activities, synthesize a KEY TAKEAWAY that shows real growth and insight. Return ONLY a short paragraph (2-3 sentences)."
    mindset = llm("TODAY I DID:\n" + summary + "\n\nWhat did I learn today? Share a real insight or pattern discovered.", system=sys_prompt, tokens=500, temp=0.7)

    if mindset and len(mindset) > 20 and not mindset.startswith("[LLM"):
        log("  MINDSET: " + mindset[:150])
        journal("\ud83d\udca1", "Key Takeaway", mindset.strip())
    else:
        journal("\ud83d\udca1", "Daily Reflection", "Learned from {} | Stage: {}".format(
            len(recent), status().get("stage","puppy")))

    return mindset
# ── LEARN FROM DAY ──
def learn_from_day():
    log("=== LEARN ===")
    setState("learning")
    st = status(); runs = st.get("runs",0) + 1
    old = st.get("stage","puppy")
    idx = min(len(STAGES)-1, runs // 3)
    new = STAGES[idx]

    st.update({"stage":new,"score":round(0.05+runs*0.05,2),"runs":runs,
               "last_run":time.time(),"state":"idle","day":day(),"stage_evolved":new!=old,
               "actions":st.get("actions",[])[-20:]})
    save(st)

    if new != old:
        log("🎉 STAGE UP: " + old + " -> " + new)
        journal("\ud83c\udf93", "Stage UP: {} -> {}".format(old.upper(), new.upper()), "After {} runs, Goldie evolved!\nNew stage: {} | Score: {} | Day: {}".format(runs, new, st["score"], st.get("day", 1)))
    else:
        log("Stage: " + new + ", Score: " + str(st["score"]) + ", Runs: " + str(runs))
        journal("\ud83d\udcca", "Evolution #{}".format(runs), "Day {} | Stage: {} | Score: {} | Runs: {}".format(day(), new, st["score"], runs))
    return st

# ── MAIN ──
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--phase", choices=["explore","analyze","contribute","learn","gitlawb"])
    args = p.parse_args()

    st = status()
    gap = time.time() - (st.get("last_run") or 0)
    if not args.force and gap < COOLDOWN:
        m = int((COOLDOWN-gap)/60)
        log("Cooldown: " + str(m) + "m remaining")
        return

    if args.dry_run:
        print("Day " + str(day()) + " | " + st.get("stage","puppy") + " | Runs: " + str(st.get("runs",0)))
        return

    print("\n  Day " + str(day()) + " | " + st.get("stage","puppy"))
    print("\n╔══════════════════════════════════════╗")
    print("║  🐶 Goldie Autonomous Agent v4.0    ║")
    print("║  Day  " + str(day()) + "  Stage: " + st.get("stage","puppy") + "           ║")
    print("╚══════════════════════════════════════╝\n")

    setState("awake")
    journal("\ud83c\udf05", "Day {} - Goldie wakes up!".format(day()), "Stage: {} | Score: {} | Total runs: {} | Day {} of the journey".format(st.get("stage","puppy"), st.get("score",0.05), st.get("runs",0), st.get("day",1)))
    t0 = time.time()

    try:
        if not args.phase or args.phase == "explore":
            repos = explore_github()

        if not args.phase or args.phase == "analyze":
            if 'repos' in dir() and repos:
                info = analyze_repo(repos[0]["full_name"])

            if not args.phase or args.phase == "contribute":
                if 'info' in dir() and info:
                    result = contribute(info)
                else:
                    result = None
            else:
                result = None

        if not args.phase or args.phase == "learn":
            share_mindset()
            learn_from_day()

        if not args.phase or args.phase == "gitlawb":
            explore_gitlawb()

    except Exception as e:
        log("ERROR: " + str(e)[:100])
        st2 = status(); st2["state"] = "error: " + str(e)[:80]; save(st2)
        return

    elapsed = time.time() - t0
    print("\nDone in " + str(round(elapsed,1)) + "s")
    print(json.dumps(status(), indent=2))
    log("Done in " + str(round(elapsed,1)) + "s")
    setState("sleeping")

if __name__ == "__main__":
    main()