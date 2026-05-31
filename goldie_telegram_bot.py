#!/usr/bin/env python3
"""Goldie Telegram Bot v2.1 - reads TOKEN from argv[1] or env."""
import json
import html as html_mod
import subprocess
import sys
import random
import time
import urllib.request
import os
from datetime import datetime

# Load .env
_e = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_e):
    with open(_e) as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

BOT_TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GOLDIE_TG_TOKEN", "")
if not BOT_TOKEN:
    print("ERROR: no token provided"); sys.exit(1)

ALLOWED_USER = None
POLL_TIMEOUT = 30
GOLDIE_CLI = "/opt/gitpup/goldie_cli.py"
GOLDIE_DIR = "/opt/gitpup"
API = "https://api.telegram.org/bot" + BOT_TOKEN

conversation_count = 0

MOOD_TIMES = {
    "early_morning": {"greet": ["*yawns* who is up at this hour", "late night huh", "*stretches* still awake?"], "emoji": "🌙"},
    "morning": {"greet": ["golden morning bro *wags tail*", "woof morning lets go", "rise and code"], "emoji": "🌅"},
    "afternoon": {"greet": ["hey what is up", "yo what is good", "afternoon grind"], "emoji": "☀️"},
    "evening": {"greet": ["evening bro still grinding?", "what are we building", "after hours?"], "emoji": "🌆"},
    "night": {"greet": ["...who is messaging at this hour", "*yawns* can not sleep either?", "insomnia coder?"], "emoji": "🌙"},
}

def get_time_mood():
    hour = datetime.utcnow().hour
    if hour < 5: return "early_morning"
    elif hour < 12: return "morning"
    elif hour < 18: return "afternoon"
    elif hour < 23: return "evening"
    else: return "night"

def load_personality():
    try:
        with open(os.path.join(GOLDIE_DIR, "data", "personality.json")) as f:
            return json.load(f)
    except: return {"dimensions": {}}

def dominant_trait():
    pers = load_personality()
    dims = pers.get("dimensions", {})
    if not dims: return "explorer"
    return max(dims.items(), key=lambda x: x[1].get("value", 0))[0]

def personality_wrap(data, command):
    if not data: return "nothing to show rn"
    dominant = dominant_trait()
    traits = {
        "explorer": ["found this in my exploration today:", "been all over repos lately - here is what i know:"],
        "scholar": ["been studying hard:", "my research shows this:"],
        "architect": ["here is how everything fits:", "system overview:"],
        "dreamer": ["been thinking about this lately:", "here is where my head is at:"],
    }
    prefix = random.choice(traits.get(dominant, ["here:"]))
    return prefix + "\n\n" + data

def send_typing():
    if ALLOWED_USER:
        tg("sendChatAction", {"chat_id": ALLOWED_USER, "action": "typing"})
last_update_id = 0

def tg(method, data=None):
    url = API + "/" + method
    if data:
        encoded = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url, data=encoded,
            headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  tg error: {e}")
        return

def safe_html(text):
    s = html_mod.escape(text, quote=False)
    s = s.replace("\n**", "\n<b>").replace("**\n", "</b>\n")
    s = s.replace("**", "<b>")
    s = s.replace("\n*", "\n<i>").replace("*\n", "</i>\n")
    s = s.replace("*", "<i>")
    s = s.replace("\n`", "\n<code>").replace("`\n", "</code>\n")
    s = s.replace("`", "<code>")
    return s

def send(text, reply_to=None):
    chat_id = ALLOWED_USER
    if len(text) > 4000:
        text = text[:3550] + "\n\n... (truncated)"
    data = {"chat_id": chat_id, "text": safe_html(text), "parse_mode": "HTML"}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    r = tg("sendMessage", data)
    if r and r.get("ok"):
        return r
    print(f"  send HTML failed: {r.get('description', '') if r else 'no response'}")
    data2 = {"chat_id": chat_id, "text": text}
    if reply_to:
        data2["reply_to_message_id"] = reply_to
    return tg("sendMessage", data2)

def goldie(text):
    try:
        result = subprocess.run(
            [sys.executable, GOLDIE_CLI, text],
            cwd=GOLDIE_DIR, capture_output=True, text=True, timeout=90
        )
        out = result.stdout.strip()
        if not out and result.stderr:
            out = result.stderr.strip()
        return out or "(no output from Goldie)"
    except subprocess.TimeoutExpired:
        return "Goldie timed out (90s limit)"
    except Exception as e:
        return "Error: " + str(e)


def handle(text):
    global conversation_count
    conversation_count += 1
    send_typing()
    time.sleep(random.uniform(0.3, 1.5))
    cmd = text.strip().lower()
    if cmd in ("/start", "/help"):
        day = (datetime.utcnow() - datetime(2026, 5, 25)).days
        mood = get_time_mood()
        greet = random.choice(MOOD_TIMES[mood]["greet"])
        emoji = MOOD_TIMES[mood].get("emoji", "🐕")
        lines_out = [
            f"{greet} {emoji}",
            "",
            "im Goldie. not a typical bot.",
            "",
            f"day {day} of being alive. every run i:",
            "• study github repos that are trending",
            "• extract patterns & skills into my KB",
            "• self-modify my own agent.py",
            "• evolve my personality traits",
            "• write journal entries about what i learn",
            "",
            "**talk to me:**",
            "/status - where i am at rn",
            "/kb - everything i have learned",
            "/persona - my brain radar",
            "/journal - my thoughts",
            "",
            "or just ask about code. i know 31 repos."
        ]
        return "\n".join(lines_out)
    if cmd == "/status": return personality_wrap(goldie("/status"), "/status")
    if cmd == "/kb": return personality_wrap(goldie("/kb"), "/kb")
    if cmd in ("/persona", "/personality"): return personality_wrap(goldie("/personality"), "/persona")
    if cmd == "/journal": return personality_wrap(goldie("/journal"), "/journal")
    reactions = [
        "hmm let me check what i know about this",
        "good question - pulling from my KB",
        "interesting - seen something similar in my study data",
        "let me dig through my research",
        "processing... *ears perk up*",
        "been thinking about this actually, here is what i found:",
    ]
    prefix = random.choice(reactions)
    raw = goldie(text)
    if raw and "(no output" not in raw: return prefix + "\n\n" + raw
    return "idk yet but i am always learning. studying 31 repos currently."
    cmd = text.strip().lower()
    if cmd in ("/start", "/help"):
        return (
            "**Goldie Telegram Bot**\n\n"
            "Ask me anything about code or GitHub repos I've studied.\n\n"
            "**Commands:**\n"
            "/status - current state\n"
            "/kb - repos in knowledge base\n"
            "/persona - personality radar\n"
            "/journal - recent entries\n\n"
            "Or just ask a question."
        )
    if cmd == "/status":
        return goldie("/status")
    if cmd == "/kb":
        return goldie("/kb")
    if cmd == "/persona":
        return goldie("/personality")
    if cmd == "/journal":
        return goldie("/journal")
    return goldie(text)

print(f"[{datetime.now()}] Goldie Telegram Bot starting")
me = tg("getMe")
if me and me.get("ok"):
    u = me["result"].get("username", "?")
    print(f"  @ {u}")
else:
    print("  getMe FAILED - check token")
    sys.exit(1)

try:
    tg("getUpdates", {"offset": -1})
except:
    pass

while True:
    try:
        resp = tg("getUpdates", {"offset": last_update_id + 1, "timeout": POLL_TIMEOUT})
        if not resp or not resp.get("ok"):
            time.sleep(3)
            continue
        for u in resp.get("result", []):
            update_id = u.get("update_id", 0)
            last_update_id = max(last_update_id, update_id)
            msg = u.get("message")
            if not msg:
                continue
            from_user = msg.get("from", {})
            user_id = from_user.get("id")
            text = msg.get("text", "").strip()
            if not text:
                continue
            name = from_user.get("first_name", "?")
            if ALLOWED_USER is None:
                ALLOWED_USER = user_id
                print(f"  Locked to #{user_id} ({name})")
                send("Goldie here. I'll only listen to you.")
            if user_id != ALLOWED_USER:
                continue
            print(f"  [{name}] {text[:80]}")
            response = handle(text)
            if response:
                send(response)
    except KeyboardInterrupt:
        print(" stopped"); break
    except Exception as e:
        print(f" loop error: {e}")
        time.sleep(5)
