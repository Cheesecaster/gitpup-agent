"""GitPup CLI Agent — Phase Configuration & Evolution Pipeline"""
import os, sys, json, time
# Try to load dotenv for LLM config
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass

# ── Constants ──
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
JOURNAL_FILE = os.path.join(DATA_DIR, "journal", "entries.jsonl")
STATUS_FILE = os.path.join(DATA_DIR, "state", "status.json")
EVOLVE_LOG = os.path.join(DATA_DIR, "evolve.log")
SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")
AGENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents")
INTERMEDIATE_DIR = os.path.join(PROJECT_ROOT, ".understand-anything", "intermediate")

# ── LLM Config ──
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openrouter")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.6-flash")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_URL = "https://openrouter.ai/api/v1/chat/completions"

# ── Identity ──
AGENT_NAME = "Goldie"
AGENT_VERSION = "0.1.0"

# ── Pipeline Config ──
MAX_PLAN_TOKENS = 2000
MAX_IMPL_TOKENS = 4000
RESPONSE_TIMEOUT = 60  # seconds per LLM call
EVOLVE_COOLDOWN = 8 * 3600  # 8 hours between runs
BIRTH_DATE = "2026-05-25"

# ── Status tracking ──
def get_status():
    if os.path.isfile(STATUS_FILE):
        with open(STATUS_FILE) as f:
            return json.load(f)
    return {"stage": "puppy", "score": 0.05, "day": 1, "runs": 0, "last_run": None}

def save_status(status):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)

def get_day():
    try:
        from datetime import datetime
        birth = datetime.strptime(BIRTH_DATE, "%Y-%m-%d")
        now = datetime.now()
        return (now - birth).days + 1
    except Exception:
        return 1

def write_journal(entry_type, title, body="", icon="✨"):
    os.makedirs(os.path.dirname(JOURNAL_FILE), exist_ok=True)
    entry = {
        "t": time.strftime("%Y-%m-%d %H:%M:%S"),
        "i": icon,
        "x": title,
        "type": entry_type,
        "body": body,
        "day": get_day(),
    }
    with open(JOURNAL_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def log_evolve(msg):
    with open(EVOLVE_LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
