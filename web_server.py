#!/usr/bin/env python3
"""GitPup Web Server v3.0 — Full API with project build pipeline"""
import http.server, json, os, urllib.parse, urllib.request, subprocess, time, threading

GITPUP = '/opt/gitpup'
DATA = os.path.join(GITPUP, 'data')
SF = os.path.join(DATA, 'state', 'status.json')
JF = os.path.join(DATA, 'journal', 'entries.jsonl')
KB = os.path.join(DATA, 'knowledge.json')
BIRTH = '2026-05-25'

def _compute_day():
    from datetime import datetime, timezone
    try:
        birth = datetime.strptime(BIRTH, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - birth).days + 1
    except Exception:
        return 1

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

# === IN-MEMORY CACHE for journal/API data (30s TTL) ===
_CACHE = {}
_CACHE_TTL = 30
def _cached_jsonl(key, path):
    """Cache JSONL reads to avoid disk I/O."""
    import time, json
    now = time.time()
    import os
    mtime = os.path.getmtime(path) if os.path.exists(path) else 0
    if key in _CACHE:
        data, cached_mtime, cached_at = _CACHE[key]
        if (now - cached_at) < _CACHE_TTL and mtime == cached_mtime:
            return data
    entries = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except:
        pass
    _CACHE[key] = (entries, mtime, now)
    return entries

import personality as pers

def load_json(path, default=None):
    import json
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def load_jsonl(path):
    entries = []
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except FileNotFoundError:
        raise FileNotFoundError(f"JSONL file not found: {path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON in file {path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to load JSONL file {path}: {e}")
    return entries

def _json_resp(handler, data, status=200):
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()
    handler.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

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
            st = load_json(SF, {'stage': 'puppy', 'score': 0, 'runs': 0, 'state': 'idle'})
            st['day'] = _compute_day()
            _json_resp(self, st)
        elif p == '/api/journal':
            entries = _cached_jsonl('journal', JF)
            narrative = [e for e in entries if e.get('type') == 'narrative' and e.get('event',{}).get('phase') != 'deep_self_reflection' and len(e.get('body','')) > 50]
            narrative = narrative[-50:]
            _json_resp(self, {'entries': list(reversed(narrative)), 'total': len(narrative)})
        elif p == '/api/reflections':
            entries = _cached_jsonl('reflections', JF)
            # Only self-reflection entries (deep_self_reflection phase)
            reflections = [e for e in entries if e.get('event',{}).get('phase') == 'deep_self_reflection']
            reflections = reflections[-20:]
            _json_resp(self, {'entries': list(reversed(reflections)), 'total': len(reflections)})
        elif p == '/api/activity':
            entries = _cached_jsonl('activity', JF)
            activity = [e for e in entries if e.get('type') != 'narrative']
            activity = activity[-50:]
            _json_resp(self, {'entries': list(reversed(activity)), 'total': len(activity)})
        elif p == '/api/personality':
            try:
                _json_resp(self, pers.get_radar())
            except:
                _json_resp(self, {'labels': [], 'data': [], 'colors': [], 'keys': []})
        elif p == '/api/soul':
            sc = ''
            try:
                with open('/opt/gitpup/data/soul.md', encoding='utf-8') as f:
                    sc = f.read()
            except:
                pass
            _json_resp(self, {'content': sc})
        elif p == '/api/story':
            _json_resp(self, {'ok': True, 'url': '/story'})
        elif p == '/story':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                with open('/opt/gitpup/web_dist/story.html', 'rb') as f:
                    self.wfile.write(f.read())
            except Exception:
                self.wfile.write(b'<h1>Story not found</h1>')
            return
        elif p == '/api/kb':
            _json_resp(self, cp.kb_stats() if hasattr(cp, 'kb_stats') else {'repos': 0})
        elif p == '/api/repos':
            kb = load_json(KB)
            repos = kb.get('repos', {})
            _json_resp(self, {'repos': [{'name': rn, 'level': rd.get('study_level',0), 'lang': rd.get('lang',''), 'stars': rd.get('stars',0)} for rn, rd in repos.items()], 'total': len(repos)})
        elif p == '/api/cost':
            try:
                from pathlib import Path
                cost_file = Path('/opt/gitpup/data/journal/cost_tracking.jsonl')
                entries = []
                if cost_file.exists():
                    with open(cost_file) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try: entries.append(json.loads(line))
                                except: pass
                # Compute aggregates
                total_in = sum(e.get('prompt_tokens',0) for e in entries)
                total_out = sum(e.get('completion_tokens',0) for e in entries)
                total_all = sum(e.get('total_tokens',0) for e in entries)
                total_cost = sum(e.get('cost_usd',0) for e in entries)
                # Today
                import time
                today = time.strftime('%Y-%m-%d')
                today_entries = [e for e in entries if today in e.get('date','')]
                today_cost = sum(e.get('cost_usd',0) for e in today_entries)
                today_tokens = sum(e.get('total_tokens',0) for e in today_entries)
                # Per run
                runs = {}
                for e in entries:
                    phase = e.get('phase','unknown')
                    if phase not in runs:
                        runs[phase] = {'count':0, 'tokens':0, 'cost':0}
                    runs[phase]['count'] += 1
                    runs[phase]['tokens'] += e.get('total_tokens',0)
                    runs[phase]['cost'] += e.get('cost_usd',0)
                _json_resp(self, {
                    'total_cost_usd': round(total_cost, 4),
                    'total_tokens': total_all,
                    'total_prompt_tokens': total_in,
                    'total_completion_tokens': total_out,
                    'today_cost': round(today_cost, 4),
                    'today_tokens': today_tokens,
                    'entries_count': len(entries),
                    'per_phase': {k: {'count': v['count'], 'tokens': v['tokens'], 'cost_usd': round(v['cost'],4)} for k,v in runs.items()}
                })
            except Exception as e:
                _json_resp(self, {'error': str(e)})
        elif p == '/api/relationships':
            kb = load_json(KB)
            rels = kb.get('relationships', [])
            concepts = kb.get('concepts', {})
            skills = kb.get('skill_index', {})
            _json_resp(self, {
                'relationships': rels,
                'concepts': {k: {'repos': v['repos'], 'evidence': v['evidence_count']}
                             for k, v in concepts.items()},
                'skill_count': len(skills),
                'total_concepts': len(concepts),
            })
        elif p == '/api/mood_arc':
            entries = _cached_jsonl('mood_arc', JF)
            timeline = []
            for e in entries:
                m = e.get('mood')
                if m:
                    timeline.append({
                        'ts': e.get('ts', ''),
                        'day': e.get('day', 1),
                        'label': e.get('mood_label', m),
                        'color': e.get('mood_color', '#888'),
                        'title': (e.get('x', '') or '')[:60],
                    })
            _json_resp(self, {'timeline': timeline[-50:], 'total': len(timeline)})
        elif p == '/auth/callback':
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = qs.get('code', [''])[0]
            if not code:
                self.send_response(400)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                return
            import urllib.request as _ur
            import json as _json
            _body = _json.dumps({
                'client_id': 'Ov23liLMEsHCQUzsfIKX',
                'client_secret': '940bda0ab55878ad38e10de477df653f85ff3f8',
                'code': code,
                'redirect_uri': 'https://gitpup.fun/auth/callback',
            }).encode('utf-8')
            _req = _ur.Request('https://github.com/login/oauth/access_token',
                data=_body, headers={'Accept': 'application/json'}, method='POST')
            try:
                with _ur.urlopen(_req, timeout=10) as _r:
                    _resp = _json.loads(_r.read())
                    _token = _resp.get('access_token', '')
                    if _token:
                        _ur2 = _ur.Request('https://api.github.com/user',
                            headers={'Authorization': 'token ' + _token})
                        with _ur.urlopen(_ur2, timeout=10) as _r2:
                            _user = _json.loads(_r2.read())
                        _name = _user.get('login', 'user')
                        _html = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
                            '<script>try{localStorage.setItem("gp_gh_token","' + _token
                            + '");localStorage.setItem("gp_gh_user",JSON.stringify('
                            + '{login:"' + _name + '",token:"' + _token + '"}))}'
                            + 'catch(e){}window.location.href="/";</script></head>'
                            + '<body>Logged in ' + _name + '! Redirecting...</body></html>')
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html')
                        self.end_headers()
                        self.wfile.write(_html.encode())
                    else:
                        self.send_response(400)
                        self.send_header('Content-Type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b'Login failed')
            except Exception:
                self.send_response(500)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(b'OAuth error')
        else:
            self.send_error(404)
            return

        # Session storage for pending proposals (in-memory)
        _pending_proposals = {}

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if p == '/api/chat':
            def handle_chat():
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length)
                    data = json.loads(body)
                    self._handle_chat(data)
                except Exception as e:
                    _json_resp(self, {'status': 'error', 'error': str(e)})
            threading.Thread(target=handle_chat, daemon=True).start()
        elif p == '/api/trigger':
            def handle_trigger():
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length)
                    data = json.loads(body)
                    r = subprocess.run(['python3', os.path.join(GITPUP, 'agent.py'), '--force'],
                        cwd=GITPUP, capture_output=True, text=True, timeout=300)
                    _json_resp(self, {'status': 'done', 'stdout': r.stdout[:500], 'returncode': r.returncode})
                except Exception as e:
                    _json_resp(self, {'status': 'error', 'error': str(e)})
            threading.Thread(target=handle_trigger, daemon=True).start()
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

    async def _handle_chat(self):
        import concurrent.futures
        import json
        import asyncio
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        except (json.JSONDecodeError, ValueError):
            return _json_resp(self, {'error': 'Invalid JSON'}, 400)
        except Exception:
            return _json_resp(self, {'error': 'Internal Server Error'}, 500)

        msg = body.get('message', '').strip()
        if not msg:
            _json_resp(self, {'reply': 'Yo, ketik sesuatu bro', 'cited': []})
            return

        if msg.lower() in ('stats', 'knowledge', 'kb', 'apa yang lo pelajari', 'what do you know'):
            summary = cp.kb_summary()
            _json_resp(self, {'reply': summary, 'cited': [], 'kb_context_used': True})
            return

        try:
            intent = await asyncio.wrap_future(executor.submit(cp.detect_intent, msg))

            if intent == 'build_request':
                lower = msg.lower()
                if any(w in lower for w in ['ya', 'gas', 'ok', 'oke', 'lanjut', 'konfirmasi', 'confirm', 'yes', 'y', 'jalan']):
                    session_key = body.get('session', 'default')
                    if session_key in self._pending_proposals:
                        proposal = self._pending_proposals.pop(session_key)
                        result = await asyncio.wrap_future(executor.submit(cp.handle_build_confirm, msg, proposal))
                        _json_resp(self, result)
                        return

                result = await asyncio.wrap_future(executor.submit(cp.handle_build_proposal, msg))
                if result['status'] == 'proposal':
                    self._pending_proposals[msg[:50]] = result['data']
                _json_resp(self, result)

            elif intent == 'question':
                result = await asyncio.wrap_future(executor.submit(cp.handle_question, msg))
                _json_resp(self, result)

            else:
                _json_resp(self, {'reply': 'Gw belum ngerti apa yang lo mau bro.', 'cited': []})
        except Exception:
            return _json_resp(self, {'error': 'Internal Server Error'}, 500)

    def log_message(self, fmt, *args):
        pass


os.chdir('/opt/gitpup/web_dist')
srv = http.server.ThreadingHTTPServer(('0.0.0.0', 5173), H)
srv.daemon_threads = True
print("GitPup web v3.0 on :5173 with build pipeline")
server_thread = threading.Thread(target=srv.serve_forever, daemon=True)
server_thread.start()
import time
while True:
    time.sleep(3600)