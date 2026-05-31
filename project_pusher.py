#!/usr/bin/env python3
"""Goldie Project Pusher — Creates GitHub repos and pushes built projects."""
import os, json, subprocess, urllib.request, urllib.error, re
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(ROOT, ".env")
TOKEN = ""
USER = ""
MAX_PROJECTS_PER_WEEK = 2
PUSH_HISTORY = os.path.join(ROOT, "data", "project_push_history.json")

def _load_env():
    global TOKEN, USER
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k in ("GITHUB_TOKEN", "GH_TOKEN"):
                    TOKEN = v
                elif k in ("GITHUB_USER", "MY_GITHUB_LOGIN"):
                    USER = v
_load_env()

def _gh(path, method="GET", data=None):
    url = "https://api.github.com" + path
    hdr = {"Authorization": "token " + TOKEN, "Accept": "application/vnd.github.v3+json", "User-Agent": "Goldie-Agent/1.0"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=hdr, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:300], "status": e.code}, e.code

def _log(msg):
    lp = os.path.join(ROOT, "evolve.log")
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(lp, "a") as f:
        f.write("[{}] [project_pusher] {}\n".format(ts, msg))

def safe_name(n):
    s = re.sub(r'[^a-zA-Z0-9._-]', '-', n).strip('-')
    return s if s else "goldie-project"

def push_project_to_github(project_name, project_dir, description="", language="python"):
    """Full pipeline: quota -> create repo -> README -> git push."""
    _log("=== PUSH PROJECT: {} ===".format(project_name))

    if not TOKEN:
        return {"success": False, "repo_url": "", "message": "No GitHub token", "reason": "no_token"}
    if not USER:
        return {"success": False, "repo_url": "", "message": "No GitHub user", "reason": "no_user"}

    # Quota check
    if os.path.exists(PUSH_HISTORY):
        try:
            hist = json.load(open(PUSH_HISTORY))
        except:
            hist = []
        cutoff = datetime.utcnow().timestamp() - (7 * 86400)
        recent = [p for p in hist if p.get("timestamp", 0) >= cutoff]
        if len(recent) >= MAX_PROJECTS_PER_WEEK:
            return {"success": False, "repo_url": "", "message": "Quota: {}/week".format(len(recent)), "reason": "quota"}
    else:
        hist = []

    # Create repo via GitHub API
    sname = safe_name(project_name)
    chk, code = _gh("/repos/{}/{}".format(USER, sname))
    if code == 200:
        return {"success": False, "repo_url": "", "message": "Repo exists: {}/{}".format(USER, sname), "reason": "exists"}

    payload = {"name": sname, "description": "Built by Goldie, an autonomous AI agent. " + description, "private": False, "auto_init": False}
    result, code = _gh("/user/repos", method="POST", data=payload)
    if code not in (200, 201, 202) or "html_url" not in result:
        return {"success": False, "repo_url": "", "message": result.get("error", "create failed"), "reason": "create_failed"}

    repo_url = result["html_url"]
    _log("Created: {} -> {}".format(sname, repo_url))

    # Create README if missing
    rpath = os.path.join(project_dir, "README.md")
    if not os.path.exists(rpath):
        ld = language.capitalize() if language else "Python"
        readme = "# {}\n\n{}\n\n".format(sname, description or "A project built by Goldie, an autonomous AI agent.")
        readme += "> Built by Goldie, an autonomous AI agent. Details: [gitpup.fun](https://gitpup.fun)\n\n"
        readme += "## About Goldie\n\n"
        readme += "Goldie is not a chatbot -- he's an autonomous agent who:\n"
        readme += "- Studies trending GitHub repos to learn patterns and best practices\n"
        readme += "- Contributes PRs to trending open-source projects\n"
        readme += "- Maintains a living personality that evolves over time\n"
        readme += "- Keeps a journal of his entire learning journey\n\n"
        readme += "Watch Goldie live: https://gitpup.fun\n"
        readme += "Read Goldie's story: https://gitpup.fun/story\n"
        readme += "Chat with Goldie: Telegram @goldiepupbot\n\n"
        readme += "*Built autonomously on {}*\n".format(datetime.utcnow().strftime("%d %b %Y"))
        with open(rpath, "w") as f:
            f.write(readme)

    # Git init + push
    os.makedirs(os.path.dirname(PUSH_HISTORY), exist_ok=True)
    auth_url = "https://{}:{}@github.com/{}/{}.git".format(USER, TOKEN, USER, sname)

    cmds = [
        (["git", "init"], "git init"),
        (["git", "remote", "add", "origin", auth_url], "git remote"),
        (["git", "add", "-A"], "git add"),
        (["git", "config", "user.email", "goldie@gitpup.fun"], "git config email"),
        (["git", "config", "user.name", "Goldie"], "git config name"),
    ]
    for cmd, label in cmds:
        r = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, timeout=30)
        if r.returncode != 0 and label != "git init":
            return {"success": False, "repo_url": repo_url, "message": "{}: {}".format(label, r.stderr[:200]), "reason": "git_fail"}

    cmt = "Initial commit: {}\n\nBuilt by Goldie, an autonomous AI agent.\nLearn more: https://gitpup.fun".format(sname)
    r = subprocess.run(["git", "commit", "-m", cmt], cwd=project_dir, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return {"success": False, "repo_url": repo_url, "message": "commit: " + r.stderr[:200], "reason": "commit_fail"}

    # Push main then master as fallback
    for branch in ["main", "master"]:
        r = subprocess.run(["git", "push", "-u", "origin", branch], cwd=project_dir, capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            # Record success
            hist.append({"repo": sname, "url": repo_url, "description": description, "timestamp": datetime.utcnow().timestamp(), "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")})
            with open(PUSH_HISTORY, "w") as f:
                json.dump(hist, f, indent=2)
            msg = "{}/{} (branch: {})".format(USER, sname, branch)
            _log("SUCCESS: " + msg)
            return {"success": True, "repo_url": repo_url, "message": msg, "reason": "ok"}

    return {"success": False, "repo_url": repo_url, "message": "push failed", "reason": "push_failed"}
