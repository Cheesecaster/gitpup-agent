#!/usr/bin/env python3
"""Goldie X OAuth web setup.

Serves a small HTTPS-proxied setup page where the owner can enter rotated X
OAuth2 credentials directly into gitpup.fun, without sending them through chat.
Stores secrets locally in /opt/gitpup/data/x_auth.json (gitignored data dir).
"""
import base64
import hashlib
import html
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
import http.server
import socketserver
from pathlib import Path

ROOT = Path('/opt/gitpup')
DATA = ROOT / 'data'
AUTH_FILE = DATA / 'x_auth.json'
PORT = int(os.environ.get('GOLDIE_X_AUTH_PORT', '5174'))
REDIRECT_URI = os.environ.get('GOLDIE_X_REDIRECT_URI', 'https://gitpup.fun/x-oauth/callback')
SCOPES = 'tweet.read tweet.write users.read offline.access like.read like.write follows.read'


def load_auth():
    try:
        return json.loads(AUTH_FILE.read_text())
    except Exception:
        return {}


def save_auth(data):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = AUTH_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2))
    os.chmod(tmp, 0o600)
    tmp.replace(AUTH_FILE)
    try:
        os.chmod(AUTH_FILE, 0o600)
    except Exception:
        pass


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def json_resp(h, data, status=200):
    h.send_response(status)
    h.send_header('Content-Type', 'application/json')
    h.send_header('Cache-Control', 'no-store')
    h.end_headers()
    h.wfile.write(json.dumps(data, ensure_ascii=False).encode())


def html_resp(h, body, status=200):
    h.send_response(status)
    h.send_header('Content-Type', 'text/html; charset=utf-8')
    h.send_header('Cache-Control', 'no-store')
    h.end_headers()
    h.wfile.write(body.encode())


def status_public():
    a = load_auth()
    tok = a.get('token', {})
    return {
        'configured': bool(a.get('client_id') and a.get('client_secret')),
        'authenticated': bool(tok.get('access_token')),
        'username': a.get('username') or '',
        'x_user': a.get('x_user') or {},
        'expires_at': tok.get('expires_at') or 0,
        'expires_in_seconds': max(0, int((tok.get('expires_at') or 0) - time.time())) if tok.get('expires_at') else 0,
    }


def form_page(msg=''):
    st = status_public()
    safe_user = html.escape(st.get('username') or '')
    banner = f'<div class="msg">{html.escape(msg)}</div>' if msg else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Goldie X Auth</title>
<style>
body{{margin:0;min-height:100dvh;background:#090a0f;color:#f4efe4;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;display:grid;place-items:center;padding:22px}}
.card{{width:min(680px,100%);background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:22px;padding:24px;box-shadow:0 30px 90px rgba(0,0,0,.38)}}
h1{{margin:0 0 8px;font-size:28px}}p{{color:#b8b2a7;line-height:1.55}}label{{display:block;margin:14px 0 7px;color:#d9d0bf;font-size:14px}}input{{box-sizing:border-box;width:100%;border:1px solid rgba(255,255,255,.18);background:#11131a;color:#fff;border-radius:14px;padding:13px 14px;font-size:15px}}button,a.btn{{display:inline-flex;align-items:center;justify-content:center;margin-top:18px;background:#f5c45c;color:#17120a;border:0;border-radius:999px;padding:13px 18px;font-weight:800;text-decoration:none;cursor:pointer}}.muted{{font-size:13px;color:#8f8a80}}.ok{{color:#7ee787}}.bad{{color:#ffb86b}}.msg{{background:#131b25;border:1px solid #2c415f;border-radius:14px;padding:12px 14px;margin:14px 0;color:#dbeafe}}code{{background:#151821;padding:2px 6px;border-radius:7px}}.row{{display:flex;gap:8px;flex-wrap:wrap}}.status{{background:#0d1017;border-radius:14px;padding:12px;margin:14px 0}}</style>
</head><body><main class="card">
<h1>Goldie X Auth</h1>
<p>Paste your <b>rotated</b> X OAuth2 Client ID + Client Secret here. This page writes them directly on the VPS; they do not go through Telegram/chat.</p>
{banner}
<div class="status">
<div>Status: <b class="{'ok' if st['authenticated'] else 'bad'}">{'authenticated' if st['authenticated'] else 'not authenticated'}</b></div>
<div>Username: <code>{html.escape(st.get('username') or '-')}</code></div>
<div>Token expires in: <code>{st.get('expires_in_seconds',0)}s</code></div>
</div>
<form method="post" action="/x-auth/setup" autocomplete="off">
<label>Goldie X username, without @</label><input name="username" value="{safe_user}" placeholder="goldiepup" required>
<label>New OAuth2 Client ID</label><input name="client_id" placeholder="paste client id" required>
<label>New OAuth2 Client Secret</label><input name="client_secret" type="password" placeholder="paste client secret" required>
<button type="submit">Save & login to X</button>
</form>
<p class="muted">X app settings required: callback URL <code>{REDIRECT_URI}</code>, app type <code>Web app / automated app / bot</code>, permission <code>Read and write</code>.</p>
<div class="row"><a class="btn" href="/x-auth/status">status json</a><a class="btn" href="/">back</a></div>
</main></body></html>'''


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ('/x-auth', '/x-auth/', '/x-auth/status', '/x-oauth/callback'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path in ('/x-auth', '/x-auth/'):
            return html_resp(self, form_page())
        if p.path == '/x-auth/status':
            return json_resp(self, status_public())
        if p.path == '/x-oauth/callback':
            qs = urllib.parse.parse_qs(p.query)
            code = qs.get('code', [''])[0]
            state = qs.get('state', [''])[0]
            if not code:
                return html_resp(self, form_page('Missing OAuth code from X.'), 400)
            a = load_auth()
            pending = a.get('pending', {})
            if not pending or state != pending.get('state'):
                return html_resp(self, form_page('OAuth state mismatch. Please restart login.'), 400)
            try:
                token = self.exchange_code(a, code, pending.get('code_verifier'))
                token['expires_at'] = int(time.time()) + int(token.get('expires_in', 7200)) - 90
                a['token'] = token
                a.pop('pending', None)
                save_auth(a)
                # best-effort whoami
                try:
                    me = api_get('/2/users/me')
                    a = load_auth(); a['x_user'] = me.get('data', {}); save_auth(a)
                except Exception:
                    pass
                return html_resp(self, '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Goldie X Connected</title><style>body{background:#090a0f;color:#f4efe4;font-family:system-ui;display:grid;place-items:center;min-height:100dvh;padding:24px}.card{max-width:560px;background:#11131a;border:1px solid #2b3040;border-radius:20px;padding:24px}a{color:#f5c45c}</style></head><body><div class="card"><h1>Goldie X connected ✅</h1><p>OAuth token is saved on the VPS. Goldie can now publish through the autonomous social loop.</p><p><a href="/x-auth">Back to status</a></p></div></body></html>''')
            except Exception as e:
                return html_resp(self, form_page('OAuth exchange failed: ' + str(e)[:180]), 500)
        return html_resp(self, 'not found', 404)

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if p != '/x-auth/setup':
            return json_resp(self, {'error': 'not found'}, 404)
        n = int(self.headers.get('Content-Length') or 0)
        if n > 20000:
            return html_resp(self, form_page('Payload too large.'), 400)
        raw = self.rfile.read(n).decode('utf-8', 'replace')
        data = urllib.parse.parse_qs(raw)
        username = (data.get('username', [''])[0] or '').strip().lstrip('@')
        client_id = (data.get('client_id', [''])[0] or '').strip()
        client_secret = (data.get('client_secret', [''])[0] or '').strip()
        if not username or not client_id or not client_secret:
            return html_resp(self, form_page('Missing username/client id/client secret.'), 400)
        code_verifier = b64url(secrets.token_bytes(64))
        challenge = b64url(hashlib.sha256(code_verifier.encode()).digest())
        state = b64url(secrets.token_bytes(24))
        auth = {
            'username': username,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': REDIRECT_URI,
            'scope': SCOPES,
            'created_at': int(time.time()),
            'pending': {'state': state, 'code_verifier': code_verifier, 'created_at': int(time.time())},
        }
        save_auth(auth)
        params = urllib.parse.urlencode({
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': REDIRECT_URI,
            'scope': SCOPES,
            'state': state,
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        })
        self.send_response(302)
        self.send_header('Location', 'https://twitter.com/i/oauth2/authorize?' + params)
        self.end_headers()

    def exchange_code(self, auth, code, verifier):
        data = urllib.parse.urlencode({
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': auth.get('redirect_uri') or REDIRECT_URI,
            'code_verifier': verifier,
        }).encode()
        req = urllib.request.Request('https://api.x.com/2/oauth2/token', data=data, method='POST')
        basic = base64.b64encode((auth['client_id'] + ':' + auth['client_secret']).encode()).decode()
        req.add_header('Authorization', 'Basic ' + basic)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read())


def refresh_token(auth=None):
    auth = auth or load_auth()
    tok = auth.get('token', {})
    if not tok.get('refresh_token'):
        raise RuntimeError('missing refresh token')
    data = urllib.parse.urlencode({'grant_type': 'refresh_token', 'refresh_token': tok['refresh_token']}).encode()
    req = urllib.request.Request('https://api.x.com/2/oauth2/token', data=data, method='POST')
    basic = base64.b64encode((auth['client_id'] + ':' + auth['client_secret']).encode()).decode()
    req.add_header('Authorization', 'Basic ' + basic)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urllib.request.urlopen(req, timeout=25) as r:
        nt = json.loads(r.read())
    nt['expires_at'] = int(time.time()) + int(nt.get('expires_in', 7200)) - 90
    auth['token'] = nt
    save_auth(auth)
    return nt


def access_token():
    auth = load_auth()
    tok = auth.get('token', {})
    if not tok.get('access_token'):
        raise RuntimeError('not authenticated')
    if tok.get('expires_at') and tok['expires_at'] <= time.time() + 120:
        tok = refresh_token(auth)
    return tok['access_token']


def api_request(method, path, payload=None):
    url = 'https://api.x.com' + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', 'Bearer ' + access_token())
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def api_get(path):
    return api_request('GET', path)


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    with socketserver.TCPServer(('127.0.0.1', PORT), Handler) as httpd:
        print(f'Goldie X auth web listening on 127.0.0.1:{PORT}', flush=True)
        httpd.serve_forever()


if __name__ == '__main__':
    main()
