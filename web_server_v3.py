#!/usr/bin/env python3
"""GitPup Web Server v3.0 — Full API with project build pipeline"""
import http.server, json, os, urllib.parse, urllib.request, subprocess, time

GITPUP = '/opt/gitpup'
DATA = os.path.join(GITPUP, 'data')
SF = os.path.join(DATA, 'state', 'status.json')
JF = os.path.join(DATA, 'journal', 'entries.jsonl')
KB = os.path.join(DATA, 'knowledge.json')

# Load .env
_ep = os.path.join(GITPUP, '.env')
if os.path.exists(_ep):
    with open(_ep) as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith('#') and '=' in _l:
                _k, _v = _l.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

import chat_pipeline as cp

def load_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default or {}

def load_jsonl(path):
    entries = []
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except Exception:
        pass
    return entries

def _json_resp(handler, data, status=200):
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()
    handler.wfile.write(json.dumps(data, ensure_ascii=False).encode())

class H(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p == '/api/status':
            _json_resp(self, load_json(SF, {'stage': 'puppy', 'score': 0, 'runs': 0, 'state': 'idle', 'day': 1}))
        elif p == '/api/journal':
            entries = load_jsonl(JF)[-50:]
            _json_resp(self, {'entries': entries, 'total': len(entries)})
        elif p == '/api/kb':
            _json_resp(self, cp.kb_stats() if hasattr(cp, 'kb_stats') else {'repos': 0})
        elif p == '/api/repos':
            kb = load_json(KB)
            repos = kb.get('repos', {})
            _json_resp(self, {'repos': [{'name': rn, 'level': rd.get('study_level',0), 'lang': rd.get('lang',''), 'stars': rd.get('stars',0)} for rn, rd in repos.items()], 'total': len(repos)})
        else:
            super().do_GET()

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if p == '/api/chat':
            self._handle_chat()
        elif p == '/api/trigger':
            try:
                r = subprocess.run(['python3', os.path.join(GITPUP, 'agent.py'), '--force'],
                    cwd=GITPUP, capture_output=True, text=True, timeout=300)
                _json_resp(self, {'status': 'done', 'stdout': r.stdout[:500], 'returncode': r.returncode})
            except Exception as e:
                _json_resp(self, {'status': 'error', 'error': str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_chat(self):
        n = int(self.headers.get('Content-Length', 0))
        try:
            data = json.loads(self.rfile.read(n))
        except:
            _json_resp(self, {'error': 'invalid JSON'}, 400)
            return

        msg = data.get('message', '').strip()
        if not msg:
            _json_resp(self, {'reply': 'Yo, ketik sesuatu bro', 'cited': []})
            return

        # Stats/kb query
        if msg.lower() in ('stats', 'knowledge', 'kb', 'apa yang lo pelajari', 'what do you know'):
            s = cp.kb_stats()
            reply = "Knowledge base gw:\n* {} repos | {} patterns | {} insights\n".format(
                s['total_repos'], s['total_patterns'], s['total_insights'])
            reply += "* Topics: {}\n".format(', '.join(s['topics'][:8]))
            if s['repos']:
                for r in s['repos'][:5]:
                    reply += "- {} (level {}/4, {})\n".format(r['name'], r['level'], r['stars'])
            _json_resp(self, {'reply': reply, 'cited': [], 'stats': s})
            return

        intent = cp.detect_intent(msg)

        if intent == 'build_request':
            # Check if this is a confirm message
            lower = msg.lower()
            if any(w in lower for w in ['ya', 'gas', 'ok', 'oke', 'lanjut', 'konfirmasi', 'confirm', 'yes', 'y', 'jalan']):
                # Check for pending proposal in conversation state
                session_key = data.get('session', 'default')
                if session_key in _pending_proposals:
                    proposal = _pending_proposals.pop(session_key)
                    result = cp.handle_build_confirm(msg, proposal)
                    _json_resp(self, result)
                    return

            # Generate proposal
            result = cp.handle_build_proposal(msg)
            if result['status'] == 'proposal':
                _pending_proposals[msg[:50]] = result['data']
            _json_resp(self, result)

        elif intent == 'question':
            result = cp.handle_question(msg)
            _json_resp(self, result)

        else:
            _json_resp(self, {'reply': 'Gw belum ngerti apa yang lo mau bro.', 'cited': []})

    def log_message(self, fmt, *args):
        pass

# Session storage for pending proposals (in-memory)
_pending_proposals = {}

os.chdir('/opt/gitpup/web_dist')
srv = http.server.HTTPServer(('0.0.0.0', 5173), H)
print("GitPup web v3.0 on :5173 with build pipeline")
srv.serve_forever()
