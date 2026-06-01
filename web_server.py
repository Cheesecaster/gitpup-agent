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

_env_model = os.environ.get('LLM_MODEL', '')
_env_provider = os.environ.get('LLM_PROVIDER', '')
_env_base_url = os.environ.get('LLM_BASE_URL', '')

import chat_pipeline as cp


# === IN-MEMORY CACHE for journal/API data (30s TTL) ===
_CACHE = {}
_CACHE_TTL = 30
def _cached_jsonl(key, path):
    """Cache JSONL reads to avoid disk I/O."""
    import time, json
    import os
    now = time.time()
    canonical_path = os.path.abspath(path)
    cache_key = (key, canonical_path)

    try:
        stat_result = os.stat(canonical_path)
        file_signature = (stat_result.st_mtime_ns, stat_result.st_size, stat_result.st_ino)
    except OSError:
        file_signature = None

    if cache_key in _CACHE:
        data, cached_signature, cached_at = _CACHE[cache_key]
        if (now - cached_at) < _CACHE_TTL and cached_signature == file_signature:
            return data

    entries = []
    try:
        with open(canonical_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except:
        pass
    _CACHE[cache_key] = (entries, file_signature, now)
    return entries

import personality as pers

def load_json(path, default=None):
    import json
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
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
    if p not in {
        '/api/status', '/api/journal', '/api/reflections', '/api/config', '/api/activity',
        '/api/personality', '/api/soul', '/api/story', '/story', '/api/kb', '/api/repos',
        '/api/cost', '/api/x_queue', '/api/x_queue/clear', '/api/relationships', '/api/mood_arc',
        '/auth/callback'
    }:
        self.send_error(404)
        return

    if p == '/api/status':
        st = load_json(SF, {'stage': 'puppy', 'score': 0, 'runs': 0, 'state': 'idle'})
        st['day'] = _compute_day()
        st['llm_provider'] = _env_provider or 'openrouter'
        if _env_model:
            st['llm_model'] = _env_model
        elif _env_provider == 'custom':
            st['llm_model'] = 'gpt-4o'
        else:
            st['llm_model'] = 'unknown'
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
    elif p == '/api/config':
        _json_resp(self, {'provider': _env_provider or 'openrouter', 'model': _env_model or 'unknown', 'llm_base_url': _env_base_url or '', 'ok': True})
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
    elif p == '/api/x_queue':
        qf = os.path.join(DATA, 'x_queue.jsonl')
        posts = []
        if os.path.exists(qf):
            with open(qf) as f:
                for ln in f:
                    ln = ln.strip()
                    if ln:
                        try: posts.append(json.loads(ln))
                        except: pass
        _json_resp(self, {'posts': posts, 'count': len(posts)})
    elif p == '/api/x_queue/clear':
        qf = os.path.join(DATA, 'x_queue.jsonl')
        if os.path.exists(qf):
            open(qf, 'w').close()
        _json_resp(self, {'cleared': True})

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

    def _parse_json_payload():
        raw_length = self.headers.get('Content-Length')
        try:
            content_length = int(raw_length) if raw_length is not None else 0
        except (TypeError, ValueError) as e:
            raise ValueError("Invalid Content-Length header") from e

        if content_length < 0:
            raise ValueError("Invalid Content-Length header")

        body = self.rfile.read(content_length)
        try:
            if isinstance(body, (bytes, bytearray)):
                body = body.decode('utf-8')
            return json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as e:
            raise ValueError("Invalid JSON payload") from e

    if p == '/api/chat':
        def handle_chat():
            try:
                data = _parse_json_payload()
                if not isinstance(data, dict):
                    raise ValueError("Invalid JSON payload: expected object")
                import asyncio
                asyncio.run(self._handle_chat(data))
            except (KeyError, TypeError, ValueError) as e:
                _json_resp(self, {'status': 'error', 'error': str(e)}, 400)
            except Exception as e:
                _json_resp(self, {'status': 'error', 'error': str(e)}, 500)
        threading.Thread(target=handle_chat, daemon=True).start()
    elif p == '/api/trigger':
        def handle_trigger():
            try:
                data = _parse_json_payload()
                if not isinstance(data, dict):
                    raise ValueError("Invalid JSON payload: expected object")
                r = subprocess.run(['python3', os.path.join(GITPUP, 'agent.py'), '--force'],
                    cwd=GITPUP, capture_output=True, text=True, timeout=300)
                _json_resp(self, {'status': 'done', 'stdout': r.stdout[:500], 'returncode': r.returncode})
            except (KeyError, TypeError, ValueError) as e:
                _json_resp(self, {'status': 'error', 'error': str(e)}, 400)
            except Exception as e:
                _json_resp(self, {'status': 'error', 'error': str(e)}, 500)
        threading.Thread(target=handle_trigger, daemon=True).start()
    else:
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

async def _handle_chat(self, body=None):
    import concurrent.futures
    import json
    import asyncio
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    if body is None:
        try:
            raw_length = self.headers.get('Content-Length', 0)
            content_length = int(raw_length)
            if content_length < 0:
                raise ValueError("Invalid Content-Length header")
            body = self.rfile.read(content_length)
            if isinstance(body, (bytes, bytearray)):
                body = body.decode('utf-8')
            body = json.loads(body)
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            return _json_resp(self, {'error': 'Invalid JSON'}, 400)
        except Exception:
            return _json_resp(self, {'error': 'Internal Server Error'}, 500)
    elif not isinstance(body, dict):
        return _json_resp(self, {'error': 'Invalid JSON'}, 400)

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
    return


# === PUBLIC CHAT OVERRIDES ===
# Keep public static serving, but route API calls explicitly. Chat is public; no GitHub token required.
_CHAT_RATE = {}
_CHAT_CONTEXT = {}
_IMAGE_RATE = {}
_SONG_RATE = {}

def _client_ip(handler):
    return handler.headers.get('X-Forwarded-For', '').split(',')[0].strip() or handler.client_address[0]

def _rate_ok(handler, user_key='anonymous', limit=5, window=60):
    """Strict public chat limiter: max 5 chats/min per IP AND per user/session."""
    import time
    import threading

    lock = globals().setdefault('_CHAT_RATE_LOCK', threading.Lock())
    ip = _client_ip(handler)
    safe_user = ''.join(ch for ch in str(user_key or 'anonymous') if ch.isalnum() or ch in ('_', '-', ':'))[:80] or 'anonymous'
    keys = ['ip:' + ip, 'user:' + safe_user]
    now = time.time()

    with lock:
        # prune stale entries to avoid unbounded memory growth
        for seen in list(_CHAT_RATE):
            active_hits = [t for t in _CHAT_RATE.get(seen, []) if now - t < window]
            if active_hits:
                _CHAT_RATE[seen] = active_hits
            else:
                del _CHAT_RATE[seen]

        for key in keys:
            hits = [t for t in _CHAT_RATE.get(key, []) if now - t < window]
            if len(hits) >= limit:
                _CHAT_RATE[key] = hits
                return False

        for key in keys:
            hits = [t for t in _CHAT_RATE.get(key, []) if now - t < window]
            hits.append(now)
            _CHAT_RATE[key] = hits
        return True


def _image_rate_ok(handler, user_key='anonymous', limit=1, window=300):
    """Image generation/edit limiter: max 1 image/min per IP AND per user/session."""
    import time, threading
    lock = globals().setdefault('_IMAGE_RATE_LOCK', threading.Lock())
    ip = _client_ip(handler)
    safe_user = ''.join(ch for ch in str(user_key or 'anonymous') if ch.isalnum() or ch in ('_', '-', ':'))[:80] or 'anonymous'
    keys = ['ip:' + ip, 'user:' + safe_user]
    now = time.time()
    with lock:
        for seen in list(_IMAGE_RATE):
            active = [t for t in _IMAGE_RATE.get(seen, []) if now - t < window]
            if active: _IMAGE_RATE[seen] = active
            else: del _IMAGE_RATE[seen]
        for key in keys:
            hits = [t for t in _IMAGE_RATE.get(key, []) if now - t < window]
            if len(hits) >= limit:
                _IMAGE_RATE[key] = hits
                return False
        for key in keys:
            hits = [t for t in _IMAGE_RATE.get(key, []) if now - t < window]
            hits.append(now)
            _IMAGE_RATE[key] = hits
        return True

def _image_rate_refund(handler, user_key='anonymous'):
    """Refund image limiter when provider fails before producing an image."""
    import threading
    lock = globals().setdefault('_IMAGE_RATE_LOCK', threading.Lock())
    ip = _client_ip(handler)
    safe_user = ''.join(ch for ch in str(user_key or 'anonymous') if ch.isalnum() or ch in ('_', '-', ':'))[:80] or 'anonymous'
    keys = ['ip:' + ip, 'user:' + safe_user]
    with lock:
        for key in keys:
            hits = _IMAGE_RATE.get(key, [])
            if hits:
                hits.pop()
            if hits:
                _IMAGE_RATE[key] = hits
            else:
                _IMAGE_RATE.pop(key, None)


def _load_env_file_once():
    envp = '/opt/gitpup/.env'
    try:
        with open(envp, encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k,v=line.split('=',1)
                    os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass

def _extract_openrouter_image(resp):
    import base64, urllib.request
    msg = (resp.get('choices') or [{}])[0].get('message') or {}
    # OpenRouter image models commonly return message.images[].image_url.url
    for img in msg.get('images') or []:
        url = (img.get('image_url') or {}).get('url') or img.get('url') or ''
        if url.startswith('data:image'):
            return base64.b64decode(url.split(',',1)[1])
        if url.startswith('http'):
            req = urllib.request.Request(url, headers={'User-Agent':'GoldieImage/1.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
    # Some routes return base64/json in content
    content = msg.get('content') or ''
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                url = ((part.get('image_url') or {}).get('url') or part.get('url') or '')
                if url.startswith('data:image'):
                    return base64.b64decode(url.split(',',1)[1])
                if url.startswith('http'):
                    req = urllib.request.Request(url, headers={'User-Agent':'GoldieImage/1.0'})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        return r.read()
    if isinstance(content, str) and 'data:image' in content:
        import re
        m = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', content)
        if m:
            return base64.b64decode(m.group(1))
    return None

def _compress_image_max(raw, out_path, max_bytes=800*1024):
    """Write image <= max_bytes. Uses Pillow when available; otherwise writes raw if already small."""
    import os, io
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if len(raw) <= max_bytes:
        with open(out_path, 'wb') as f: f.write(raw)
        return out_path, len(raw)
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert('RGB')
        # progressively resize + lower JPEG quality until <=800KB
        scale = 1.0
        for quality in [88,82,76,70,64,58,52,46,40,35,30,25,20]:
            w,h = im.size
            im2 = im.resize((max(256,int(w*scale)), max(256,int(h*scale)))) if scale < 1.0 else im
            buf = io.BytesIO()
            im2.save(buf, format='JPEG', quality=quality, optimize=True, progressive=True)
            if buf.tell() <= max_bytes:
                out_path = out_path.rsplit('.',1)[0] + '.jpg'
                with open(out_path,'wb') as f: f.write(buf.getvalue())
                return out_path, buf.tell()
            scale *= 0.86
        out_path = out_path.rsplit('.',1)[0] + '.jpg'
        buf = io.BytesIO(); im.resize((512,512)).save(buf, format='JPEG', quality=20, optimize=True)
        with open(out_path,'wb') as f: f.write(buf.getvalue()[:max_bytes])
        return out_path, min(buf.tell(), max_bytes)
    except Exception as e:
        raise RuntimeError('image output exceeded 800KB and Pillow compression unavailable: ' + str(e)[:120])


def _song_rate_ok(handler, user_key='anonymous', limit=1, window=14400):
    import time, threading
    lock = globals().setdefault('_SONG_RATE_LOCK', threading.Lock())
    ip = _client_ip(handler)
    safe_user = ''.join(ch for ch in str(user_key or 'anonymous') if ch.isalnum() or ch in ('_', '-', ':'))[:80] or 'anonymous'
    keys = ['ip:' + ip, 'user:' + safe_user]
    now = time.time()
    with lock:
        for seen in list(_SONG_RATE):
            active = [t for t in _SONG_RATE.get(seen, []) if now - t < window]
            if active: _SONG_RATE[seen] = active
            else: del _SONG_RATE[seen]
        for key in keys:
            hits = [t for t in _SONG_RATE.get(key, []) if now - t < window]
            if len(hits) >= limit:
                _SONG_RATE[key] = hits
                return False
        for key in keys:
            hits = [t for t in _SONG_RATE.get(key, []) if now - t < window]
            hits.append(now); _SONG_RATE[key] = hits
        return True

def _song_rate_refund(handler, user_key='anonymous'):
    import threading
    lock = globals().setdefault('_SONG_RATE_LOCK', threading.Lock())
    ip = _client_ip(handler)
    safe_user = ''.join(ch for ch in str(user_key or 'anonymous') if ch.isalnum() or ch in ('_', '-', ':'))[:80] or 'anonymous'
    with lock:
        for key in ['ip:' + ip, 'user:' + safe_user]:
            hits = _SONG_RATE.get(key, [])
            if hits: hits.pop()
            if hits: _SONG_RATE[key] = hits
            else: _SONG_RATE.pop(key, None)


def _handle_image(self, data):
    import time, json, urllib.request, base64, os
    user_key = data.get('session') or data.get('user') or 'anonymous'
    if not _image_rate_ok(self, user_key=user_key, limit=1, window=300):
        return _json_resp(self, {'status':'error','error':'image_rate_limited','reply':'Image rate limit exceeded. Please wait a moment — maximum 1 image every 5 minutes per user/IP.','limit':'1/5 minutes'}, 429)
    prompt = (data.get('prompt') or data.get('message') or '').strip()
    if not prompt:
        return _json_resp(self, {'status':'error','error':'missing_prompt','reply':'Please enter an image prompt.'}, 400)
    if len(prompt) > 1500:
        prompt = prompt[:1500]
    _load_env_file_once()
    key = os.environ.get('OPENROUTER_API_KEY','')
    if not key:
        return _json_resp(self, {'status':'error','error':'missing_openrouter_key'}, 500)
    primary_model = os.environ.get('IMAGE_MODEL','x-ai/grok-imagine-image-quality')
    fallback_model = os.environ.get('IMAGE_FALLBACK_MODEL','')
    models_to_try = []
    for m in [primary_model, fallback_model]:
        if m and m not in models_to_try:
            models_to_try.append(m)
    image_data = data.get('image') or data.get('image_base64') or ''
    # OpenRouter Grok Imagine docs expect plain string content + modalities:["image"] for generation.
    if image_data:
        if image_data.startswith('data:image'):
            image_url = image_data
        else:
            image_url = 'data:image/png;base64,' + image_data
        content = [{'type':'text','text':prompt}, {'type':'image_url','image_url':{'url': image_url}}]
    else:
        content = prompt
    last_error = ''
    raw = None
    resp = None
    used_model = None
    for model in models_to_try:
        payload = {
            'model': model,
            'messages': [{'role':'user','content': content}],
            'modalities': ['image']
        }
        req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions', data=json.dumps(payload).encode('utf-8'), method='POST')
        req.add_header('Content-Type','application/json')
        req.add_header('Authorization','Bearer ' + key)
        req.add_header('HTTP-Referer','https://gitpup.fun')
        req.add_header('X-Title','Goldie Image Chat')
        req.add_header('User-Agent','GoldieImage/1.0')
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.loads(r.read())
            raw = _extract_openrouter_image(resp)
            if raw:
                used_model = model
                break
            text = ((resp.get('choices') or [{}])[0].get('message') or {}).get('content','')
            last_error = text[:500] or 'Image model did not return an image.'
        except Exception as e:
            last_error = str(e)[:300]
            # Try fallback when primary model is not routed/available.
            continue
    if not raw:
        _image_rate_refund(self, user_key)
        return _json_resp(self, {'status':'error','error':last_error or 'no_image_returned','reply':'Image model did not return an image.'}, 502)
    try:
        fname = 'goldie_%d.png' % int(time.time()*1000)
        out = '/opt/gitpup/web_dist/generated/' + fname
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'wb') as f:
            f.write(raw)
        size = os.path.getsize(out)
        url = '/generated/' + os.path.basename(out)
        _append_chat_context(self, user_key, 'user', '[image prompt] ' + prompt)
        _append_chat_context(self, user_key, 'assistant', '[generated image] ' + url)
        return _json_resp(self, {'status':'ok','reply':'Image generated.','image_url':url,'size_bytes':size,'model':used_model,'requested_model':primary_model,'fallback_model':fallback_model,'limit':'1/5 minutes','output_size':'model_default'})
    except Exception as e:
        return _json_resp(self, {'status':'error','error':str(e)[:300],'reply':'Image generation failed: ' + str(e)[:180]}, 500)



def _handle_song(self, data):
    import os, json, urllib.request, base64, time
    user_key = data.get('session') or data.get('user') or 'anonymous'
    if not _song_rate_ok(self, user_key=user_key, limit=1, window=14400):
        return _json_resp(self, {'status':'error','error':'song_rate_limited','reply':'Song rate limit exceeded. Please wait — maximum 1 song every 4 hours per user/IP.','limit':'1/4 hours'}, 429)
    prompt = (data.get('prompt') or data.get('message') or '').strip()
    if not prompt:
        _song_rate_refund(self, user_key)
        return _json_resp(self, {'status':'error','error':'missing_prompt','reply':'Please enter a song prompt.'}, 400)
    if len(prompt) > 1200: prompt = prompt[:1200]
    _load_env_file_once()
    key = os.environ.get('OPENROUTER_API_KEY','')
    model = os.environ.get('SONG_MODEL','google/lyria-3-pro-preview')
    if not key:
        _song_rate_refund(self, user_key)
        return _json_resp(self, {'status':'error','error':'missing_openrouter_key'}, 500)
    full_prompt = 'Create music/audio from this prompt. Return audio only. Prompt: ' + prompt
    payload = {'model': model, 'stream': True, 'messages':[{'role':'user','content': full_prompt}], 'modalities':['audio']}
    req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions', data=json.dumps(payload).encode('utf-8'), method='POST')
    for k,v in {'Content-Type':'application/json','Authorization':'Bearer '+key,'HTTP-Referer':'https://gitpup.fun','X-Title':'Goldie Song Chat','User-Agent':'GoldieSong/1.0'}.items(): req.add_header(k,v)
    audio_b64 = None; used_model = model; err = ''
    try:
        with urllib.request.urlopen(req, timeout=480) as r:
            for line in r:
                txt=line.decode('utf-8','replace').strip()
                if not txt or not txt.startswith('data: '): continue
                dat=txt[6:]
                if dat == '[DONE]': break
                try:
                    obj=json.loads(dat)
                    used_model = obj.get('model') or used_model
                    delta=(obj.get('choices') or [{}])[0].get('delta') or {}
                    aud=delta.get('audio') or {}
                    if isinstance(aud, dict) and aud.get('data'):
                        audio_b64 = aud.get('data')
                except Exception as e:
                    err = str(e)[:180]
    except Exception as e:
        err = str(e)[:300]
    if not audio_b64:
        _song_rate_refund(self, user_key)
        return _json_resp(self, {'status':'error','error':err or 'no_audio_returned','reply':'Song model did not return audio.'}, 502)
    try:
        raw = base64.b64decode(audio_b64)
        os.makedirs('/opt/gitpup/web_dist/generated', exist_ok=True)
        fname='goldie_song_%d.mp3' % int(time.time()*1000)
        out='/opt/gitpup/web_dist/generated/'+fname
        with open(out,'wb') as f: f.write(raw)
        url='/generated/'+fname
        _append_chat_context(self, user_key, 'user', '[song prompt] '+prompt)
        _append_chat_context(self, user_key, 'assistant', '[generated song] '+url)
        return _json_resp(self, {'status':'ok','reply':'Song generated.','audio_url':url,'size_bytes':os.path.getsize(out),'model':used_model,'requested_model':model,'limit':'1/4 hours'})
    except Exception as e:
        _song_rate_refund(self, user_key)
        return _json_resp(self, {'status':'error','error':str(e)[:300],'reply':'Song generation failed.'}, 500)


def _public_do_GET(self):
    p = urllib.parse.urlparse(self.path).path
    normalized_p = p.rstrip('/')
    if normalized_p == '':
        normalized_p = '/'

    if (normalized_p == '/api' or
            normalized_p.startswith('/api/') or
            normalized_p == '/story' or
            normalized_p == '/auth/callback' or
            normalized_p == '/status'):
        return do_GET(self)
    return http.server.SimpleHTTPRequestHandler.do_GET(self)


CHAT_HISTORY_FILE = os.path.join(DATA, 'chat_history.json')

def _history_key(handler, user_key):
    ip = _client_ip(handler)
    safe_user = ''.join(ch for ch in str(user_key or 'anonymous') if ch.isalnum() or ch in ('_', '-', ':'))[:80] or 'anonymous'
    return ip + '|' + safe_user

def _load_chat_history_store():
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def _save_chat_history_store(store):
    try:
        os.makedirs(os.path.dirname(CHAT_HISTORY_FILE), exist_ok=True)
        tmp = CHAT_HISTORY_FILE + '.tmp'
        items = sorted(store.items(), key=lambda kv: (kv[1][-1].get('ts', 0) if kv[1] else 0), reverse=True)[:300]
        clean = {k: (hist[-16:] if isinstance(hist, list) else []) for k, hist in items}
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(clean, f, ensure_ascii=False)
        os.replace(tmp, CHAT_HISTORY_FILE)
    except Exception:
        pass

def _get_chat_context(handler, user_key, max_turns=8):
    key = _history_key(handler, user_key)
    store = _load_chat_history_store()
    file_hist = store.get(key, []) if isinstance(store.get(key, []), list) else []
    mem_hist = _CHAT_CONTEXT.get(key, []) if isinstance(_CHAT_CONTEXT.get(key, []), list) else []
    hist = (file_hist + [t for t in mem_hist if t not in file_hist])[-max_turns:]
    lines = []
    for turn in hist:
        role = turn.get('role', 'user')
        text = (turn.get('text') or '').replace('\n', ' ').strip()
        if text:
            lines.append(role.upper() + ': ' + text[:800])
    return '\n'.join(lines)

def _append_chat_context(handler, user_key, role, text, max_items=16):
    import time
    key = _history_key(handler, user_key)
    turn = {'role': role, 'text': text or '', 'ts': time.time()}
    hist = _CHAT_CONTEXT.get(key, [])
    hist.append(turn)
    _CHAT_CONTEXT[key] = hist[-max_items:]
    store = _load_chat_history_store()
    sh = store.get(key, []) if isinstance(store.get(key, []), list) else []
    sh.append(turn)
    store[key] = sh[-max_items:]
    _save_chat_history_store(store)


def _public_do_POST(self):
    p = urllib.parse.urlparse(self.path).path
    if p not in ('/api/chat', '/api/image', '/api/song'):
        return _json_resp(self, {'status': 'error', 'error': 'not found'}, 404)
    try:
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        data = json.loads(body.decode('utf-8') if isinstance(body, bytes) else body)
        if not isinstance(data, dict):
            raise ValueError('Invalid JSON payload')
        if p == '/api/image':
            return _handle_image(self, data)
        if p == '/api/song':
            return _handle_song(self, data)
        user_key = data.get('session') or data.get('user') or data.get('token') or 'anonymous'
        if not _rate_ok(self, user_key=user_key, limit=5, window=60):
            return _json_resp(self, {'status': 'error', 'reply': 'Rate limit exceeded. Please wait a moment — maximum 5 chats per minute per user/IP.', 'error': 'rate_limited', 'limit': '5/minute'}, 429)
        msg = (data.get('message') or '').strip()
        if not msg:
            return _json_resp(self, {'reply': 'Yo, ketik sesuatu bro', 'cited': []})
        if len(msg) > 2000:
            msg = msg[:2000]
        # lightweight KB shortcut
        if msg.lower() in ('stats', 'knowledge', 'kb', 'apa yang lo pelajari', 'what do you know'):
            reply_text = cp.kb_summary()
            _append_chat_context(self, user_key, 'user', msg)
            _append_chat_context(self, user_key, 'assistant', reply_text)
            return _json_resp(self, {'reply': reply_text, 'cited': [], 'kb_context_used': True, 'public': True})
        intent = cp.detect_intent(msg)
        if intent == 'build_request':
            reply = 'Untuk public chat, gw cuma ngobrol dan jelasin knowledge dulu bro. Build/trigger agent sengaja nggak dibuka publik biar aman.'
            return _json_resp(self, {'reply': reply, 'cited': [], 'public': True})
        chat_context = _get_chat_context(self, user_key)
        first_turn = not bool(chat_context.strip())
        result = cp.handle_question(msg, chat_context=chat_context, force_english_first=first_turn)
        result['public'] = True
        result['chat_model'] = os.environ.get('CHAT_LLM_MODEL', 'gpt-5.4-mini')
        reply_text = result.get('reply') or result.get('error') or ''
        _append_chat_context(self, user_key, 'user', msg)
        _append_chat_context(self, user_key, 'assistant', reply_text)
        return _json_resp(self, result)
    except Exception as e:
        return _json_resp(self, {'status': 'error', 'reply': 'Error bentar bro: ' + str(e)[:120], 'error': str(e)[:120]}, 500)

def _quiet_log(self, fmt, *args):
    pass

H.do_GET = _public_do_GET
H.do_POST = _public_do_POST
H.log_message = _quiet_log

os.chdir('/opt/gitpup/web_dist')
srv = http.server.ThreadingHTTPServer(('0.0.0.0', 5173), H)
srv.daemon_threads = True
print("GitPup web v3.0 on :5173 with build pipeline")
server_thread = threading.Thread(target=srv.serve_forever, daemon=True)
server_thread.start()
import time
while True:
    time.sleep(3600)