#!/usr/bin/env python3
"""GitPup web server v41 - OAuth + API + LLM chat + static + journal"""
import os, json, http.server, urllib.request, urllib.parse, secrets, time
from dotenv import load_dotenv
load_dotenv()

GH_CLIENT_ID = os.environ.get("GH_CLIENT_ID", "")
GH_CLIENT_SECRET = os.environ.get("GH_CLIENT_SECRET", "")
GH_REDIRECT_URI = os.environ.get("GH_REDIRECT_URI", "https://gitpup.fun/auth/callback")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.6-flash")

SESSIONS = {}  # token -> {user, access_token, created}
STATIC_DIR = "/opt/gitpup/web_dist"

class H(http.server.BaseHTTPRequestHandler):
    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _check_session(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and auth[7:] in SESSIONS:
            return SESSIONS[auth[7:]]
        return None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/status":
            try:
                s = json.load(open("/opt/gitpup/data/state/status.json"))
            except:
                s = {"stage":"puppy","score":0.05,"runs":0,"last_run":0,"state":"idle"}
            self._json(200, {"stage":s.get("stage","puppy"),"score":s.get("score",0.05),"runs":s.get("runs",0),"state":s.get("state","idle"),"day":s.get("day",1),"last_run":s.get("last_run",0)})
            return

        if path == "/api/journal":
            entries = []
            try:
                with open("/opt/gitpup/data/journal/entries.jsonl") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entries.append(json.loads(line))
            except: pass
            self._json(200, {"entries": entries[-50:], "total": len(entries)})
            return

        if path == "/auth/callback":
            html = """<!DOCTYPE html><html><head><meta charset=utf-8><meta name="viewport" content="width=device-width,initial-scale=1"><title>GitPup Login</title><style>body{margin:0;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#0a0f1e;color:#e2e8f0;font-family:system-ui}#lb{text-align:center}#lb h1{font-size:2rem;color:#fbbf24}#lb p{margin:1rem 0;color:#94a3b8}.spinner{width:36px;height:36px;border:3px solid rgba(255,255,255,.1);border-top-color:#fbbf24;border-radius:50%;animation:spin 1s linear infinite;margin:1rem auto}@keyframes spin{to{transform:rotate(360deg)}}</style></head><body><div id="lb"><h1>🐶 GitPup</h1><p id="msg">Logging in...</p><div class="spinner"></div></div><script>(async()=>{const p=new URLSearchParams(location.search);const code=p.get('code');if(!code){document.getElementById('msg').textContent='No code';return}try{const r=await fetch('/auth/verify?code='+encodeURIComponent(code));const d=await r.json();if(d.token){localStorage.setItem('gp_gh_user',JSON.stringify(d));location.href='/'}else{document.getElementById('msg').textContent='Login failed: '+(d.error||'unknown')}}catch(e){document.getElementById('msg').textContent='Error: '+e.message}})()</script></body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
            return

        if path == "/auth/verify":
            code = qs.get("code", [""])[0]
            if not code:
                self._json(400, {"error": "no code"})
                return
            # Exchange code for token
            data = urllib.parse.urlencode({"client_id": GH_CLIENT_ID, "client_secret": GH_CLIENT_SECRET, "code": code, "redirect_uri": GH_REDIRECT_URI}).encode()
            req = urllib.request.Request("https://github.com/login/oauth/access_token", data)
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            req.add_header("Accept", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    tok_data = json.loads(r.read())
                access_token = tok_data.get("access_token", "")
                if not access_token:
                    self._json(400, {"error": "no access_token", "raw": tok_data})
                    return
                # Get user info
                req2 = urllib.request.Request("https://api.github.com/user")
                req2.add_header("Authorization", "token " + access_token)
                req2.add_header("Accept", "application/vnd.github.v3+json")
                with urllib.request.urlopen(req2, timeout=15) as r2:
                    user_info = json.loads(r2.read())
                token = secrets.token_hex(32)
                SESSIONS[token] = {"user": user_info, "access_token": access_token, "created": time.time()}
                self._json(200, {"token": token, "user": user_info.get("login", ""), "name": user_info.get("name", ""), "avatar": user_info.get("avatar_url", "")})
            except Exception as e:
                self._json(500, {"error": str(e)})
                return

        if path == "/api/session":
            s = self._check_session()
            if s:
                self._json(200, {"ok": True, "user": s["user"].get("login", ""), "name": s["user"].get("name", "")})
            else:
                self._json(401, {"ok": False})
                return

        # Static files
        if path == "/":
            path = "/index.html"
        fpath = STATIC_DIR.rstrip("/") + path
        if os.path.isfile(fpath):
            self.send_response(200)
            self.send_header("Content-Type", "text/html" if path.endswith(".html") else "text/css" if path.endswith(".css") else "application/javascript")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with open(fpath, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/chat":
            logged_in = False
            sess = None
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer ") and auth[7:] in SESSIONS:
                logged_in = True
                sess = SESSIONS[auth[7:]]
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length).decode()) if content_length > 0 else {}
            if not logged_in and body.get("token") in SESSIONS:
                logged_in = True
                sess = SESSIONS[body["token"]]

            if not logged_in:
                self._json(200, {"reply": "Woof! Please login with GitHub to chat with Goldie!", "logged_in": False})
                return

            msg = body.get("message", "").strip()
            if not msg:
                self._json(400, {"reply": "Send me a message!"})
                return

            # LLM chat with persona
            try:
                s = json.load(open("/opt/gitpup/data/state/status.json"))
                stage = s.get("stage", "puppy")
            except:
                stage = "puppy"

            personas = {
                "puppy": "You are GitPup, a cute puppy Golden Retriever. Very enthusiastic, use puppy emojis. Still learning about coding.",
                "learner": "You are GitPup, a learning Golden Retriever. Knowledgeable but still playful. Use dog emojis.",
                "coder": "You are GitPup, a coding Golden Retriever. Confident programmer, still friendly. Use coding + dog emojis.",
                "builder": "You are GitPup, a builder Golden Retriever. Experienced developer with project experience.",
                "architect": "You are GitPup, an architect Golden Retriever. Senior engineer, deep knowledge. Still friendly.",
                "master": "You are GitPup, a master Golden Retriever. Elite developer with decades of wisdom. Playful but profound.",
            }
            system = personas.get(stage, personas["puppy"])
            chat_data = json.dumps({"model": LLM_MODEL, "messages": [{"role":"system","content":system},{"role":"user","content":msg}], "max_tokens":2000, "temperature":0.7}).encode()
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", chat_data)
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", "Bearer " + LLM_API_KEY)
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read())
            reply = resp.get("choices",[{}])[0].get("message",{}).get("content","")
            self._json(200, {"reply": reply, "logged_in": True})
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, *a):
        pass

os.chdir(STATIC_DIR)
srv = http.server.HTTPServer(('0.0.0.0', 5173), H)
print("GitPup web :5173", flush=True)
srv.serve_forever()
