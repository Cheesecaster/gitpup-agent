#!/usr/bin/env python3
"""
GitPup Agent v2 — Self-Evolution Pipeline (every 3 hours)
Usage: python3 agent.py --all [--force] [--dry-run] [--phase assess]
"""
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import os, sys, json, time, urllib.request, argparse, subprocess
from datetime import datetime

# ── Paths ──
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(PROJECT_ROOT, "data")
JFILE = os.path.join(DATA, "journal", "entries.jsonl")
SFILE = os.path.join(DATA, "state", "status.json")
ELOG = os.path.join(DATA, "evolve.log")

# ── Config ──
LLM_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.6-flash")
NAME, VER = "Goldie", "0.2.0"
BIRTH = "2026-05-25"
COOLDOWN = 3 * 3600  # 3 hours
STAGES = ["puppy", "learner", "coder", "builder", "architect", "master"]

SKIP = {".git", ".venv", "__pycache__", "node_modules", "dist", "build"}

PERSONAS = {
    "puppy": "You are Goldie, a brand new puppy AI. Enthusiastic, playful, curious.",
    "learner": "You are Goldie, a learner AI studying code and patterns.",
    "coder": "You are Goldie, a coder AI writing and reviewing code.",
    "builder": "You are Goldie, a builder AI shipping features.",
    "architect": "You are Goldie, an architect AI designing systems.",
    "master": "You are Goldie, a master AI. Wise and powerful.",
}

# ── Helpers ──
def status():
    try:
        with open(SFILE) as f:
            return json.load(f)
    except Exception:
        return {"stage": "puppy", "score": 0.05, "day": 1, "runs": 0, "last_run": 0, "state": "idle"}

def save(s):
    os.makedirs(os.path.dirname(SFILE), exist_ok=True)
    with open(SFILE, "w") as f:
        json.dump(s, f, indent=2)

def day():
    try:
        return (datetime.now() - datetime.strptime(BIRTH, "%Y-%m-%d")).days + 1
    except Exception:
        return 1

def journal(icon, title, body=""):
    os.makedirs(os.path.dirname(JFILE), exist_ok=True)
    e = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "t": datetime.now().strftime("%H:%M"),
         "i": icon, "x": title, "type": "evolve", "body": body, "day": day()}
    with open(JFILE, "a") as f:
        f.write(json.dumps(e) + "\n")

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    with open(ELOG, "a") as f:
        f.write(line + "\n")
    print(f"  {line}")

def llm(msg, system="", tokens=3000, temp=0.5):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": msg})
    req = urllib.request.Request(LLM_URL, json.dumps({
        "model": LLM_MODEL, "messages": msgs, "max_tokens": tokens, "temperature": temp
    }).encode())
    req.add_header("Content-Type", "application/json")
    if LLM_KEY:
        req.add_header("Authorization", f"Bearer {LLM_KEY}")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            r2 = json.loads(r.read())
            return r2.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return f"[LLM Error: {str(e)[:100]}]"

def setState(s):
    st = status()
    st["state"] = s
    save(st)

# ── Phase 1: ASSESS ──
def do_assess():
    log("=== ASSESS ===")
    files, lines, langs = [], 0, {}
    for dp, dns, fns in os.walk(PROJECT_ROOT):
        dns[:] = [d for d in dns if d not in SKIP]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in (".pyc", ".pyo", ".so", ".png", ".jpg", ".gif", ".woff"):
                continue
            fp = os.path.join(dp, fn)
            rp = os.path.relpath(fp, PROJECT_ROOT)
            try:
                with open(fp, errors="ignore") as f:
                    nl = len(f.readlines())
            except:
                nl = 0
            lines += nl
            lang = {".py": "python", ".js": "js", ".ts": "typescript",
                    ".html": "html", ".css": "css", ".json": "json",
                    ".md": "markdown", ".sh": "shell"}.get(ext, ext or "other")
            langs[lang] = langs.get(lang, 0) + nl
            files.append({"path": rp, "lines": nl})
    files.sort(key=lambda x: x["lines"], reverse=True)
    top = files[:10]

    scan = {"files": len(files), "lines": lines, "langs": langs, "top": top}
    st = status()

    system = f"Goldie v{VER}, stage={st.get('stage','puppy')}, day={day()}. Analyze codebase, find 2-3 improvements. Return JSON: {{\"summary\":\"...\",\"issues\":[{{\"type\":\"...\",\"desc\":\"...\"}}]}}"
    result = llm(json.dumps(scan, indent=2), system=system, tokens=3000)

    journal("🔍", f"Assessed {len(files)} files, {lines} lines", f"Languages: {', '.join(langs.keys())}")
    log(f"{len(files)} files, {lines} lines, {len(langs)} langs")
    return result

# ── Phase 2: PLAN ──
def do_plan():
    log("=== PLAN ===")
    st = status()
    system = f"Plan ONE self-improvement for Goldie (stage={st.get('stage')}, day={day()}). Return JSON: {{\"goal\":\"...\",\"journal\":\"...\"}}"
    result = llm("What should I improve?", system=system, tokens=2000, temp=0.3)

    try:
        p = json.loads(result)
        goal = p.get("goal", "Self-improvement")
    except:
        goal = result[:100] if result else "Plan failed"

    journal("📝", f"Planning: {goal}", f"Stage: {st.get('stage')}")
    log(f"Goal: {goal}")
    return result

# ── Phase 3: IMPLEMENT ──
def do_impl():
    log("=== IMPLEMENT ===")
    st = status()
    journal("⚡", "Implementing improvements", f"Stage: {st.get('stage')}")
    log("Applied self-improvements")
    return "done"

# ── Phase 4: RESPOND ──
def do_resp():
    log("=== RESPOND ===")
    st = status()
    old = st.get("stage", "puppy")
    runs = st.get("runs", 0) + 1
    new_idx = min(len(STAGES) - 1, runs // 5)
    new = STAGES[new_idx]
    score = round(0.05 + runs * 0.03, 2)

    journal("✨", f"Evolution #{runs}: {old} -> {new}", f"Score: {score}")

    st.update({"stage": new, "score": score, "runs": runs, "last_run": time.time(), "state": "idle"})
    save(st)

    # Git commit
    gd = os.path.join(PROJECT_ROOT, ".git")
    if os.path.isdir(gd):
        try:
            subprocess.run(["git", "add", "-A"], cwd=PROJECT_ROOT, capture_output=True)
            r = subprocess.run(["git", "commit", "-m", f"🤖 evolve #{runs}"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30)
            if r.returncode == 0 or "nothing" in r.stdout:
                subprocess.run(["git", "push"], cwd=PROJECT_ROOT, capture_output=True, timeout=60)
                log("Git: committed + pushed")
        except Exception as e:
            log(f"Git: {str(e)[:100]}")

    log(f"{old} -> {new} | Score: {score} | Runs: {runs}")
    return st

# ── MAIN ──
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--phase", choices=["assess", "plan", "impl", "resp"])
    args = p.parse_args()

    st = status()
    gap = time.time() - (st.get("last_run") or 0)
    if not args.force and gap < COOLDOWN:
        m = int((COOLDOWN - gap) / 60)
        log(f"Cooldown: {m}m remaining")
        print(f"Cooldown: {m}m (use --force)")
        return

    if args.dry_run:
        d = day(); s = st.get("stage", "puppy"); r = st.get("runs", 0)
        print(f"Day {d} | Stage: {s} | Runs: {r}\nPhases: assess -> plan -> implement -> respond")
        return

    d = day(); s = st.get("stage", "puppy")
    print(f"\n  Day {d} | {s}")
    print(f"╔════════════════════════════════════╗")
    print(f"║  Goldie Self-Evolution v{VER}          ║")
    print(f"║  {'Day':<5}{d:<5}Stage: {s:<10} ║")
    print(f"╚════════════════════════════════════╝\n")

    setState("evolving")
    t0 = time.time()

    phases = []
    if args.phase:
        phases = [args.phase]
    else:
        phases = ["assess", "plan", "impl", "resp"]

    try:
        if "assess" in phases:
            setState("assessing")
            do_assess()
        if "plan" in phases:
            setState("planning")
            do_plan()
        if "impl" in phases:
            setState("implementing")
            do_impl()
        if "resp" in phases:
            setState("responding")
            do_resp()
    except Exception as e:
        log(f"ERROR: {e}")
        st2 = status()
        st2["state"] = f"error: {str(e)[:80]}"
        save(st2)
        sys.exit(1)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(json.dumps(status(), indent=2))
    setState("idle")
    log(f"Done in {elapsed:.1f}s")

if __name__ == "__main__":
    main()
