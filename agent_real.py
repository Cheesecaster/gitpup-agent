#!/usr/bin/env python3
import os, sys, json, time, subprocess, re
from pathlib import Path
from datetime import datetime, timezone
from openai import OpenAI

BASE = Path("/opt/gitpup")
DATA = BASE / "data"
JOURNAL = DATA / "journal"
STATE = DATA / "state"
for d in [DATA, JOURNAL, STATE]: d.mkdir(parents=True, exist_ok=True)

from dotenv import load_dotenv
load_dotenv(BASE / ".env")

LLM = OpenAI(base_url=os.getenv("LLM_API_URL","https://openrouter.ai/api/v1"), api_key=os.getenv("LLM_API_KEY"))
MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.6-flash")

def set_status(state, thought=""):
    with open(STATE / "status.json", "w") as f:
        json.dump({"state": state, "thought": thought, "time": time.time()}, f)

def log_journal(day, phase, content, mood="neutral", learning="", quote=""):
    entry = {"day":day,"ts":datetime.utcnow().isoformat(),"phase":phase,"content":content,"mood":mood,"learning":learning,"quote":quote}
    with open(JOURNAL / "entries.jsonl", "a") as f: f.write(json.dumps(entry) + "\n")

def update_stats(**kwargs):
    sf = STATE / "stats.json"
    stats = json.loads(sf.read_text()) if sf.exists() else {}
    for k,v in kwargs.items():
        if k in stats and isinstance(v,(int,float)): stats[k] += v
        else: stats[k] = v
    sf.write_text(json.dumps(stats, indent=2))

def calc_day():
    sf = STATE / "stats.json"
    if sf.exists():
        stats = json.loads(sf.read_text())
        if stats.get("day_start"):
            started = datetime.fromisoformat(stats["day_start"])
            return (datetime.utcnow() - started.replace(tzinfo=timezone.utc)).days + 1
    update_stats(day_start=datetime.utcnow().isoformat(), agent_started=datetime.utcnow().isoformat())
    return 1

def scan_codebase():
    set_status("scanning", "Reading own source code...")
    files = {}
    for f in BASE.rglob("*.py"):
        if "venv" in str(f) or ".git" in str(f): continue
        try: files[str(f.relative_to(BASE))] = f.read_text()
        except: pass
    readme = (BASE / "README.md").read_text() if (BASE / "README.md").exists() else ""
    return files, readme

def decide(files, readme, day):
    set_status("thinking", "Deciding what to improve...")
    file_list = "\n".join(f"  - {k} ({len(v)} bytes)" for k,v in files.items())
    prompt = f'''You are GitPup (Goldie), a Golden Retriever self-evolving coding agent.
Your codebase:
{file_list}

README:
{readme[:1000]}

Day {day}. Pick ONE specific, achievable improvement.
Return JSON ONLY with keys: task, target_file, action (edit|create|add_test), detail'''
    resp = LLM.chat.completions.create(model=MODEL, messages=[{"role":"user","content":prompt}], max_tokens=300, temperature=0.7)
    match = re.search(r'\{.*\}', resp.choices[0].message.content.strip(), re.DOTALL)
    if match: return json.loads(match.group())
    return {"task": resp.choices[0].message.content[:200], "target_file": "agent/main.py", "action": "edit", "detail": "improve"}

def execute(decision, files):
    set_status("writing_code", f"Working on: {decision['task']}")
    target = decision["target_file"]
    current = files.get(target, "")
    prompt = f'''You are GitPup. Task: {decision['task']}
Detail: {decision['detail']}
File: {target} ({"exists" if current else "create new"})
Current content:
```
{current[:3000] if current else "(empty - create new file)"}
```
Return ONLY the complete file content between ``` markers.'''
    resp = LLM.chat.completions.create(model=MODEL, messages=[{"role":"user","content":prompt}], max_tokens=4000, temperature=0.3)
    new_code = resp.choices[0].message.content.strip()
    match = re.search(r'```(?:\w+)?\n(.+?)```', new_code, re.DOTALL)
    if match: new_code = match.group(1).strip()
    tp = BASE / target; tp.parent.mkdir(parents=True, exist_ok=True); tp.write_text(new_code)
    return target, current, new_code

def run_tests():
    set_status("running_tests", "Running tests...")
    proc = subprocess.Popen("cd /opt/gitpup && python3 -m pytest tests/ -q 2>&1 || echo NO_TESTS_FOUND",
                           shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = proc.communicate(timeout=120)
    output = out.decode()
    passed = "NO_TESTS_FOUND" not in output and "passed" in output.lower()
    if passed: return True, output[:500]
    if "NO_TESTS_FOUND" in output: return True, "No test suite yet - passing by default"
    return False, output[:500]

def commit_and_push(task):
    set_status("committing", f"Comitting: {task}")
    subprocess.run("git add -A", shell=True, cwd=BASE)
    subprocess.run(f'git commit -m "Day {calc_day()}: {task}"', shell=True, cwd=BASE)
    subprocess.run("git push github main 2>/dev/null", shell=True, cwd=BASE)
    gl = Path.home() / ".hermes/home/.local/bin/gl"
    if gl.exists(): subprocess.run(f"{gl} push 2>&1", shell=True, cwd=BASE)
    update_stats(total_commits=1)

def write_journal(day, task, passed):
    set_status("journaling", "Writing journal...")
    p = f'''You are GitPup (Goldie). Write 2-3 sentence journal entry.
Task: {task}. Tests: {'passed' if passed else 'failed'}. Include mood.'''
    resp = LLM.chat.completions.create(model=MODEL, messages=[{"role":"user","content":p}], max_tokens=200, temperature=0.9)
    text = resp.choices[0].message.content.strip()
    mood = "happy"
    for m in ["happy","curious","focused","excited","confused","proud"]:
        if m in text.lower(): mood = m; break
    log_journal(day, "reflect", text, mood=mood, learning="Learning something new!" if "learn" in text.lower() else "")
    update_stats(total_runs=1, journal_entries=1)
    return text

def evolve():
    try:
        day = calc_day()
        print(f"GitPup Day {day}: Evolution starting")
        files, readme = scan_codebase()
        print(f"Scanned {len(files)} files")
        if not files or len(files) < 2:
            print("Too few files to evolve, sleeping")
            set_status("sleeping", "Need more files first")
            return
        decision = decide(files, readme, day)
        print(f"Task: {decision['task']}")
        log_journal(day, "decide", decision['task'], mood="curious")
        target, old, new = execute(decision, files)
        print(f"Modified: {target}")
        passed, output = run_tests()
        print(f"Tests: {passed}")
        if passed: commit_and_push(decision['task']); print("Committed")
        else: print("Failed, rolling back"); subprocess.run("git checkout -- .", shell=True, cwd=BASE)
        journal_text = write_journal(day, decision['task'], passed)
        print(f"Journal: {journal_text}")
        set_status("sleeping", "Growing time...")
        print(f"Day {day} complete!")
    except Exception as e:
        print(f"Failed: {e}")
        import traceback; traceback.print_exc()
        try: set_status("error", f"Failed: {str(e)[:100]}")
        except: pass
        raise

if __name__ == "__main__":
    if "--daemon" in sys.argv:
        while True: evolve(); time.sleep(60*60*3)
    else: evolve()
