#!/usr/bin/env python3
"""GitPup web server v42"""
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
import os, json, http.server, urllib.request, urllib.parse, secrets, time

PORT = 5173
GH_C = os.environ.get("GH_CLIENT_ID", "Ov23liLMEsHCQUzsfIKX")
GH_S = os.environ.get("GH_CLIENT_SECRET", "9450bda0ab55878ad38e10de477df653f85ff3f8")
GH_R = os.environ.get("GH_REDIRECT_URI", "https://gitpup.fun/auth/callback")
LLM_K = os.environ.get("LLM_API_KEY", "")
LLM_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_M = os.environ.get("LLM_MODEL", "qwen/qwen3.6-flash")
WEB = "/opt/gitpup/web_dist"
JF = "/opt/gitpup/data/journal/entries.jsonl"
SE = {}

PERS = {
    "puppy": "You are Goldie, a new puppy AI. Enthusiastic, playful.",
    "learner": "You are Goldie, a learner AI studying code.",
    "coder": "You are Goldie, a coder AI writing code.",
    "builder": "You are Goldie, a builder AI shipping features.",
    "architect": "You are Goldie, an architect AI designing.",
    "master": "You are Goldie, a master AI sage.",
}

CB = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Authenticating...</title>
<style>
body{background:#050a1a;color:#eee;font-family:system-ui;min-height:100vh;display:flex;align-items:center;justify-content:center}
.bx{text-align:center;padding:40px}
.sp{width:40px;height:40px;border:3px solid rgba(212,160,23,.15);border-top-color:#d4a017;border-radius:50%;margin:0 auto 16px;animation:s .8s linear infinite}
@keyframes s{to{transform:rotate(360deg)}}
h2{color:#d4a017;margin-bottom:8px;font-size:18px}
p{color:#888;font-size:13px}
</style></head><body>
<div class="bx"><div class="sp"></div><h2>Logging in...</h2><p>Connecting with GitHub</p></div>
<script>
(function(){
  var p=window.location.search;
  var c=p.match(/code=([^&]+)/);
  if(!c){window.location.href='/?err=code';return}
  fetch('/auth/verify'+p).then(function(r){return r.json()}).then(function(d){
    if(d.token){
      localStorage.setItem('gp_gh_token',d.token);
      localStorage.setItem('gp_gh_user',JSON.stringify({u:d.user,n:d.name}));
      window.location.href='/';
    }else{window.location.href='/?err=auth'}
  }).catch(function(){window.location.href='/?err=net'});
})();
</script></body></html>"""


def ghx(code):
    d = urllib.parse.urlencode({
        "client_id": GH_C, "client_secret": GH_S,
        "code": code, "redirect_uri": GH_R
    }).encode()
    req = urllib.request.Request("https://github.com/login/oauth/access_token", data=d)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def ghu(token):
    req = urllib.request.Request("https://api.github.com/user")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def llm(msg, stage):
    sys_c = PERS.get(stage, PERS["puppy"])
    data = json.dumps({
        "model": LLM_M,
        "messages": [
            {"role": "system", "content": sys_c},
            {"role": "user", "content": msg}
        ],
        "max_tokens": 400,
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(LLM_URL, data=data)
    req.add_header("Content-Type", "application/json")
    if LLM_K:
        req.add_header("Authorization", "Bearer " + LLM_K)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            resp = json.loads(r.read())
            return resp.get("choices", [{}])[0].get("message", {}).get("content", "Woof!")
    except Exception as e:
        return "Woof! (error: " + str(e)[:80] + ")"


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, d, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(d).encode())

    def _html(self, h):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(h.encode())

    def _file(self, path):
        if path == "/":
            path = "/index.html"
        path = path.split("?")[0]
        fp = WEB + path
        if os.path.isfile(fp):
            self.send_response(200)
            m = {".html": "text/html", ".css": "text/css", ".js": "application/javascript", ".json": "application/json"}
            self.send_header("Content-Type", m.get(os.path.splitext(fp)[1], "text/plain"))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with open(fp, "rb") as f:
                self.wfile.write(f.read())
        else:
            self._json({"error": "not found"}, 404)

    def _get(self):
        parts = []
        if os.path.isfile(JF):
            with open(JF) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        parts.append({
                            "t": e.get("t", e.get("ts", "")),
                            "i": e.get("i", e.get("icon", "\u2728")),
                            "x": e.get("x", e.get("content", "")),
                            "body": e.get("body", ""),
                            "type": e.get("type", ""),
                            "day": e.get("day", 0),
                        })
                    except Exception:
                        pass
        if not parts:
            parts = [
                {"t": "3h ago", "i": "\u2728", "x": "Built the playground UI"},
                {"t": "5h ago", "i": "\U0001f436", "x": "Born from gitlawb.com!"},
                {"t": "8h ago", "i": "\U0001f4d6", "x": "Studied yolo-evolve"},
            ]
        self._json({"entries": parts, "total": len(parts)})

    def _auth(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and auth[7:] in SE:
            return True
        return False

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        path = p.path
        if path == "/auth/callback":
            return self._html(CB)
        if path == "/auth/verify":
            qs = urllib.parse.parse_qs(p.query)
            code = qs.get("code", [""])[0]
            if not code:
                return self._json({"error": "no code"}, 400)
            tok = ghx(code)
            if "error" in tok or "access_token" not in tok:
                return self._json({"error": "token_fail", "detail": tok}, 401)
            at = tok["access_token"]
            user = ghu(at)
            if "error" in user or "login" not in user:
                return self._json({"error": "user_fail"}, 401)
            st = secrets.token_hex(32)
            SE[st] = {"user": user, "token": at, "time": time.time()}
            return self._json({"token": st, "user": user.get("login"), "name": user.get("name")})
        if path == "/api/session":
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer ") and auth[7:] in SE:
                s = SE[auth[7:]]
                return self._json({"ok": True, "user": s["user"].get("login")})
            return self._json({"ok": False}, 401)
        if path == "/api/status":
            return self._json({"stage": "puppy", "score": 0.05, "repos": 0, "prs": 0, "llm": bool(LLM_K)})
        if path == "/api/journal":
            return self._get()
        return self._file(path)

    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == "/api/chat":
            cl = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(cl)) if cl else {}
            msg = body.get("message", "")
            stage = body.get("stage", "puppy") or "puppy"
            logged = self._auth()
            if not logged:
                bt = body.get("token", "")
                if bt.startswith("Bearer "):
                    bt = bt[7:]
                if bt in SE:
                    logged = True
            if not msg:
                return self._json({"error": "missing message"}, 400)
            reply = llm(msg, stage) if logged else "Woof! Please login with GitHub to chat!"
            return self._json({"reply": reply, "logged_in": logged})
        if p.path == "/api/status":
            return self._json({"stage": "puppy", "score": 0.05, "repos": 0, "prs": 0, "llm": bool(LLM_K)})
        return self._json({"error": "not found"}, 404)


class S(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with S(("", PORT), H) as srv:
        print("GitPup v42 on :" + str(PORT))
        print("LLM: " + ("on" if LLM_K else "off"))
        srv.serve_forever()
