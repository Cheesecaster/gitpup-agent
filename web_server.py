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
    decode_error = getattr(json, "JSONDecodeError", ValueError)
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, OSError, decode_error, TypeError, UnicodeError):
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
        def _is_self_reflection_entry(e):
            ev = e.get('event', {}) if isinstance(e.get('event', {}), dict) else {}
            title = str(e.get('x') or '').strip().lower()
            return ev.get('phase') == 'deep_self_reflection' or ev.get('type') == 'self_modify' or 'self-reflection' in title or 'self reflection' in title
        narrative = [e for e in entries if e.get('type') == 'narrative' and not _is_self_reflection_entry(e) and len(e.get('body','')) > 50]
        narrative = narrative[-50:]
        _json_resp(self, {'entries': list(reversed(narrative)), 'total': len(narrative)})
    elif p == '/api/reflections':
        entries = _cached_jsonl('reflections', JF)
        def _is_self_reflection_entry(e):
            ev = e.get('event', {}) if isinstance(e.get('event', {}), dict) else {}
            title = str(e.get('x') or '').strip().lower()
            return ev.get('phase') == 'deep_self_reflection' or ev.get('type') == 'self_modify' or 'self-reflection' in title or 'self reflection' in title
        reflections = [e for e in entries if e.get('type') == 'narrative' and _is_self_reflection_entry(e) and len(e.get('body','')) > 40]
        reflections = reflections[-30:]
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

    max_content_length = getattr(self, "max_content_length", 1024 * 1024)
    if content_length > max_content_length:
        raise ValueError("Payload too large")

    body = self.rfile.read(content_length)
    if len(body) != content_length:
        raise ValueError("Invalid JSON payload")

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

    if normalized_p == '/api/cli/download':
        return _serve_cli_download(self)
    if normalized_p.startswith('/preview/'):
        return _serve_cli_preview(self)
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



# === Goldie Secure CLI Workspace (Phase 1) ===
import hashlib, shlex, re as _re_cli, pathlib as _pathlib_cli
WORKSPACES = os.path.join(GITPUP, 'workspaces')
CLI_MEMORY_ROOT = os.path.join(DATA, 'cli_memory')
CLI_MAX_TURNS = 40
CLI_MAX_OUTPUT = 12000
CLI_COOLDOWN_SECONDS = int(os.environ.get('CLI_COOLDOWN_SECONDS', '60') or '60')
CLI_LLM_MODEL = os.environ.get('CLI_LLM_MODEL') or os.environ.get('LLM_MODEL_SPEED') or os.environ.get('LLM_MODEL') or 'gpt-5.3-codex-spark'
CLI_LLM_BASE_URL = (os.environ.get('CLI_LLM_BASE_URL') or os.environ.get('LLM_BASE_URL') or 'https://jatevo.ai/v1').rstrip('/')
CLI_LLM_PROVIDER = os.environ.get('CLI_LLM_PROVIDER', 'jatevo')
CLI_ALLOWED_BINARIES = {
    'pwd', 'ls', 'find', 'tree', 'python', 'python3', 'node', 'npm', 'npx',
    'git', 'grep', 'rg', 'cat', 'sed', 'head', 'tail', 'wc', 'mkdir', 'touch',
    'cp', 'mv', 'rm', 'zip', 'unzip', 'tar', 'curl'
}
CLI_DENY_RE = _re_cli.compile(
    r'(sudo\b|su\b|ssh\b|scp\b|rsync\b|nc\b|ncat\b|socat\b|mkfs\b|mount\b|umount\b|reboot\b|shutdown\b|systemctl\b|service\b|crontab\b|docker\b|podman\b|chmod\s+-R\s+777|chown\s+-R|rm\s+-rf\s+/(\s|$)|/opt/gitpup/\.env|\.env\b|/root/|/etc/shadow|/etc/passwd|\.ssh|id_rsa|BEGIN\s+(RSA|OPENSSH|PRIVATE)\s+KEY|GITPUP|OPENROUTER|LLM_API_KEY|GH_TOKEN)',
    _re_cli.I
)
CLI_SECRET_RE = _re_cli.compile(r'(sk-[A-Za-z0-9_\-]{12,}|ghp_[A-Za-z0-9_]{12,}|github_pat_[A-Za-z0-9_\-]{12,}|AIza[0-9A-Za-z_\-]{20,}|[A-Za-z0-9_\-]{24,}\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,})')


def _cli_redact(text):
    text = str(text or '')
    text = CLI_SECRET_RE.sub('[REDACTED]', text)
    text = text.replace(os.path.join(GITPUP, '.env'), '[REDACTED_ENV_PATH]')
    return text[:CLI_MAX_OUTPUT]


def _cli_user_key(handler, data=None):
    data = data or {}
    raw = data.get('session') or data.get('user') or data.get('token') or handler.headers.get('X-Goldie-Session') or 'anonymous'
    raw = str(raw)[:120]
    ip = _client_ip(handler) if '_client_ip' in globals() else handler.client_address[0]
    return ip + '|' + raw


def _cli_cooldown_key(handler, sid):
    ip = _client_ip(handler) if '_client_ip' in globals() else handler.client_address[0]
    return 'cli_cmd:' + hashlib.sha256((ip + '|' + sid).encode()).hexdigest()[:24]


def _cli_cooldown_check(handler, sid, seconds=None):
    seconds = int(seconds or CLI_COOLDOWN_SECONDS)
    if seconds <= 0:
        return True, 0
    key = _cli_cooldown_key(handler, sid)
    now = time.time()
    bucket = _CHAT_RATE.get(key, []) if '_CHAT_RATE' in globals() else []
    bucket = [t for t in bucket if now - t < seconds]
    if bucket:
        wait = max(1, int(seconds - (now - bucket[-1])))
        _CHAT_RATE[key] = bucket
        return False, wait
    bucket.append(now)
    _CHAT_RATE[key] = bucket
    return True, 0


def _cli_direct_command(msg):
    return (msg or '').lstrip().startswith(('/files','/run ','/read ','/write ','/help'))


def _cli_call_llm(prompt, system, tokens=500, temp=0.25):
    import urllib.request
    key = os.environ.get('CLI_LLM_API_KEY') or os.environ.get('LLM_API_KEY') or os.environ.get('JATEVO_API_KEY')
    if not key:
        return '[LLM Error: missing CLI/Jatevo API key]'
    payload = {
        'model': CLI_LLM_MODEL,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompt[:4000]},
        ],
        'max_tokens': tokens,
        'temperature': temp,
    }
    if 'ONLY valid JSON' in (system or '') or 'JSON shape' in (system or ''):
        payload['response_format'] = {'type': 'json_object'}
    req = urllib.request.Request(CLI_LLM_BASE_URL + '/chat/completions', json.dumps(payload).encode())
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', 'Bearer ' + key)
    req.add_header('User-Agent', 'GoldieCLIWorkspace/1.0')
    req.add_header('HTTP-Referer', 'https://gitpup.fun')
    req.add_header('X-Title', 'GitPup Goldie CLI Workspace')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            return resp.get('choices', [{}])[0].get('message', {}).get('content', '')
    except Exception as e:
        detail = str(e)[:80]
        try:
            if hasattr(e, 'read'):
                detail = e.read().decode('utf-8', errors='replace')[:180]
        except Exception:
            pass
        return '[LLM Error: ' + detail + ']'


def _cli_session_id(handler, data=None):
    key = _cli_user_key(handler, data)
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:18]


def _cli_workspace(handler, data=None):
    sid = _cli_session_id(handler, data)
    root = os.path.realpath(WORKSPACES)
    path = os.path.realpath(os.path.join(root, 'user_' + sid))
    if not path.startswith(root + os.sep):
        raise ValueError('Invalid workspace path')
    os.makedirs(path, exist_ok=True)
    for sub in ('projects', 'repos', 'tmp', 'logs'):
        os.makedirs(os.path.join(path, sub), exist_ok=True)
    meta = os.path.join(path, '.goldie-session.json')
    if not os.path.exists(meta):
        with open(meta, 'w', encoding='utf-8') as f:
            json.dump({'session_id': sid, 'created_at': time.time(), 'sandbox': True, 'root': path}, f, ensure_ascii=False)
    return sid, path


def _cli_memory_file(sid):
    os.makedirs(CLI_MEMORY_ROOT, exist_ok=True)
    return os.path.join(CLI_MEMORY_ROOT, sid + '.jsonl')


def _cli_append_memory(sid, role, text):
    try:
        fp = _cli_memory_file(sid)
        rows = []
        if os.path.exists(fp):
            with open(fp, encoding='utf-8') as f:
                rows = [line for line in f if line.strip()][-CLI_MAX_TURNS+1:]
        rows.append(json.dumps({'ts': time.time(), 'role': role, 'text': _cli_redact(text)}, ensure_ascii=False) + '\n')
        tmp = fp + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.writelines(rows[-CLI_MAX_TURNS:])
        os.replace(tmp, fp)
    except Exception:
        pass


def _cli_load_memory(sid, limit=12):
    try:
        fp = _cli_memory_file(sid)
        if not os.path.exists(fp):
            return []
        out = []
        with open(fp, encoding='utf-8') as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return out[-limit:]
    except Exception:
        return []


def _cli_safe_path(workspace, rel):
    rel = str(rel or '').strip().lstrip('/').replace('..', '')
    path = os.path.realpath(os.path.join(workspace, rel or '.'))
    root = os.path.realpath(workspace)
    if path != root and not path.startswith(root + os.sep):
        raise ValueError('Path blocked: outside workspace')
    return path


def _cli_list_files(workspace, limit=80):
    rows = []
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__')]
        for name in files:
            p = os.path.join(root, name)
            rel = os.path.relpath(p, workspace)
            rows.append(rel)
            if len(rows) >= limit:
                return rows
    return rows


def _cli_safe_command(cmd):
    cmd = str(cmd or '').strip()
    if not cmd or len(cmd) > 500:
        return False, 'Command empty or too long'
    if CLI_DENY_RE.search(cmd):
        return False, 'Blocked by Goldie VPS/core security policy'
    if any(x in cmd for x in ['&&', '||', ';', '`', '$(', '>', '<']):
        return False, 'Shell chaining/redirection is blocked in sandbox mode'
    try:
        parts = shlex.split(cmd)
    except Exception:
        return False, 'Invalid command quoting'
    if not parts:
        return False, 'Empty command'
    exe = os.path.basename(parts[0])
    if exe not in CLI_ALLOWED_BINARIES:
        return False, 'Command not allowed yet: ' + exe
    # Extra rm safety: only relative paths and no recursive force combo.
    if exe == 'rm' and ('-rf' in parts or '-fr' in parts or any(p.startswith('/') for p in parts[1:])):
        return False, 'Dangerous rm pattern blocked'
    return True, parts


def _cli_run(workspace, cmd, timeout=25):
    ok, parts_or_msg = _cli_safe_command(cmd)
    if not ok:
        return {'ok': False, 'blocked': True, 'output': parts_or_msg, 'returncode': 126}
    env = {'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin'), 'HOME': workspace, 'PWD': workspace, 'PYTHONUNBUFFERED': '1', 'NO_COLOR': '1'}
    try:
        r = subprocess.run(parts_or_msg, cwd=workspace, env=env, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or '') + (('\n' + r.stderr) if r.stderr else '')
        return {'ok': r.returncode == 0, 'blocked': False, 'output': _cli_redact(out), 'returncode': r.returncode}
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or '') if isinstance(e.stdout, str) else '') + '\n[TIMEOUT] command exceeded sandbox timeout'
        return {'ok': False, 'blocked': False, 'output': _cli_redact(out), 'returncode': 124}
    except Exception as e:
        return {'ok': False, 'blocked': False, 'output': _cli_redact(str(e)), 'returncode': 1}


def _cli_kb_context(message):
    try:
        results = cp.kb_query(message, limit=4)
        lines = []
        for r in results[:4]:
            lines.append('- %s L%s: %s' % (r.get('repo'), r.get('depth'), (r.get('summary') or '')[:160]))
            pats = r.get('patterns') or []
            if pats:
                lines.append('  patterns: ' + '; '.join(pats[:2])[:260])
        return '\n'.join(lines)
    except Exception:
        return ''



def _cli_is_build_command(msg):
    t = (msg or '').lower()
    build_words = ['build', 'buat', 'bikin', 'create', 'generate', 'kodekan', 'make']
    target_words = ['landing', 'website', 'page', 'html', 'app', 'portfolio', 'todo']
    return any(w in t for w in build_words) and any(w in t for w in target_words)

def _cli_template_for_prompt(msg):
    t = (msg or '').lower()
    if 'cyberpunk' in t or 'neon' in t:
        return 'cyberpunk-landing'
    if 'todo' in t or 'task' in t:
        return 'todo-static'
    return 'static-landing'


def _cli_extract_json_object(text):
    t = (text or '').strip()
    if t.startswith('```'):
        t = t.strip('`')
        if t.lower().startswith('json'):
            t = t[4:].strip()
    start = t.find('{')
    end = t.rfind('}')
    if start >= 0 and end > start:
        t = t[start:end+1]
    return json.loads(t)


def _cli_generate_project_files_locally(msg):
    import html as _html_mod, re as _re_mod
    raw = (msg or '').strip()
    low = raw.lower()
    title = 'Goldie CLI Project'
    if 'ramen' in low:
        title = 'Cyberpunk Ramen'
    elif 'cyberpunk' in low or 'neon' in low:
        title = 'Cyberpunk Landing'
    elif 'todo' in low:
        title = 'Todo App'
    elif 'portfolio' in low:
        title = 'Portfolio Landing'
    words = [w for w in _re_mod.findall(r'[A-Za-z0-9][A-Za-z0-9\-]{2,}', raw) if w.lower() not in {'build','buat','bikin','create','generate','landing','page','with','yang','dan','baru','real'}]
    keyword = next((w for w in words if any(c.isdigit() for c in w) or '-' in w), '')
    subtitle = raw[:180] or 'A polished static web experience generated by Goldie CLI.'
    esc=lambda x:_html_mod.escape(str(x), quote=True)
    cyber = 'cyberpunk' in low or 'neon' in low or 'ramen' in low
    cards = ['Neon rain atmosphere','Glitch call-to-action','Responsive conversion layout']
    if 'price' in low or 'pricing' in low or 'harga' in low:
        cards = ['Starter Bowl — $9','Night Market Combo — $19','Neon Feast — $39']
    elif 'ramen' in low:
        cards = ['Shoyu Voltage — $12','Miso Afterburner — $15','RAMEN-77X Special — $21']
    palette_bg = '#05020d' if cyber else '#08111f'
    accent = '#28f7ff' if cyber else '#64ffda'
    accent2 = '#ff2bd6' if cyber else '#f4c542'
    html = """<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>{title}</title>
<style>
:root{{--bg:{bg};--accent:{accent};--accent2:{accent2};--text:#f7fbff;--muted:#b7c7df}}
*{{box-sizing:border-box}} body{{margin:0;min-height:100vh;font-family:Inter,ui-sans-serif,system-ui;background:radial-gradient(circle at 18% 8%,rgba(255,43,214,.25),transparent 26%),radial-gradient(circle at 82% 14%,rgba(40,247,255,.20),transparent 28%),linear-gradient(180deg,var(--bg),#02040b);color:var(--text);overflow-x:hidden}}
.rain{{position:fixed;inset:0;background-image:linear-gradient(115deg,transparent 0 48%,rgba(40,247,255,.22) 49%,transparent 51%),linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px);background-size:90px 90px,42px 42px;animation:drift 16s linear infinite;pointer-events:none;mask-image:linear-gradient(to bottom,transparent,#000 18%,#000 82%,transparent)}}@keyframes drift{{to{{background-position:180px 360px,42px 84px}}}}
.wrap{{position:relative;z-index:1;min-height:100vh;display:grid;place-items:center;padding:34px}} .hero{{width:min(1120px,94vw);border:1px solid color-mix(in srgb,var(--accent),transparent 62%);border-radius:34px;padding:42px;background:linear-gradient(135deg,rgba(255,43,214,.14),rgba(40,247,255,.08));box-shadow:0 0 90px rgba(255,43,214,.20),inset 0 0 60px rgba(40,247,255,.08)}}
.kicker{{color:var(--accent);letter-spacing:.24em;text-transform:uppercase;font-weight:900;text-shadow:0 0 18px var(--accent)}} h1{{font-size:clamp(48px,9vw,116px);line-height:.88;margin:18px 0;text-transform:uppercase;text-shadow:5px 0 var(--accent2),-4px 0 var(--accent),0 0 38px rgba(255,43,214,.48)}} p{{max-width:760px;color:var(--muted);font-size:20px;line-height:1.7}} .keyword{{display:inline-block;margin:8px 0 20px;padding:8px 12px;border:1px solid var(--accent2);color:var(--accent2);border-radius:999px;font-weight:900;box-shadow:0 0 22px rgba(255,43,214,.25)}}
.cta{{display:flex;gap:14px;flex-wrap:wrap;margin:26px 0}} .btn{{padding:14px 20px;border-radius:14px;text-decoration:none;font-weight:950;color:#06010d;background:linear-gradient(90deg,var(--accent),#f8ff4a);box-shadow:0 0 28px rgba(40,247,255,.38)}} .btn.alt{{background:transparent;color:var(--accent2);border:1px solid var(--accent2)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin-top:34px}} .card{{border:1px solid rgba(255,255,255,.13);border-radius:20px;padding:20px;background:rgba(0,0,0,.30);min-height:130px}} .card b{{color:var(--accent);font-size:24px}} footer{{margin-top:30px;color:#7f93af;font-size:13px}}
</style></head><body><div class=\"rain\"></div><main class=\"wrap\"><section class=\"hero\"><div class=\"kicker\">generated from CLI command</div><h1>{title}</h1>{kw}<p>{subtitle}</p><div class=\"cta\"><a class=\"btn\" href=\"#order\">Launch Now</a><a class=\"btn alt\" href=\"#menu\">View Protocol</a></div><div class=\"grid\">{cards}</div><footer>Built and persisted by Goldie CLI from: {prompt}</footer></section></main></body></html>""".format(title=esc(title),bg=palette_bg,accent=accent,accent2=accent2,kw=('<div class=\"keyword\">'+esc(keyword)+'</div>' if keyword else ''),subtitle=esc(subtitle),cards=''.join('<div class=\"card\"><b>%02d</b><br>%s</div>'%(i+1,esc(c)) for i,c in enumerate(cards)),prompt=esc(raw[:260]))
    readme = '# '+title+'\n\nBuilt and persisted by Goldie CLI from this command:\n\n```text\n'+raw[:1000]+'\n```\n\n## Files\n\n- `index.html` — previewable static page\n- `README.md` — this file\n'
    return [{'path':'index.html','content':html},{'path':'README.md','content':readme}]


def _cli_files_from_llm_text(raw, msg):
    import re as _re_mod
    text = raw or ''
    files=[]
    # Parse fenced blocks with optional filename hints: ```html, ```index.html, ```md
    blocks = _re_mod.findall(r'```([^\n`]*)\n([\s\S]*?)```', text)
    for lang, body in blocks:
        hint=(lang or '').strip().lower()
        content=body.strip()
        if not content: continue
        if 'html' in hint or '<!doctype html' in content.lower() or '<html' in content.lower():
            files.append({'path':'index.html','content':content})
        elif hint in ('md','markdown','readme.md') or hint.endswith('.md'):
            files.append({'path':'README.md','content':content})
        elif hint.endswith('.css'):
            files.append({'path':hint,'content':content})
        elif hint.endswith('.js'):
            files.append({'path':hint,'content':content})
    if not any(f['path']=='index.html' for f in files):
        m = _re_mod.search(r'(<!doctype html[\s\S]*)', text, _re_mod.I)
        if m:
            files.append({'path':'index.html','content':m.group(1).strip()})
    if any(f['path']=='index.html' for f in files) and not any(f['path']=='README.md' for f in files):
        files.append({'path':'README.md','content':'# Goldie CLI Project\n\nBuilt by Goldie CLI from command:\n\n```text\n'+msg[:1000]+'\n```\n'})
    return files


def _cli_files_from_json_obj(obj, msg):
    files = obj.get('files') if isinstance(obj, dict) else None
    if isinstance(files, list) and files:
        return files
    if not isinstance(obj, dict):
        return []
    out=[]
    # Common LLM variants: {"index.html":"..."}, {"index_html":"..."}, {"html":"..."}, {"readme":"..."}
    for key in ('index.html','index_html','html','index'):
        val = obj.get(key)
        if isinstance(val, str) and ('<html' in val.lower() or '<!doctype' in val.lower() or len(val) > 80):
            out.append({'path':'index.html','content':val})
            break
    for key in ('README.md','readme_md','readme','markdown'):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            out.append({'path':'README.md','content':val})
            break
    # Variant: {"files":{"index.html":"...","README.md":"..."}}
    fdict = obj.get('files')
    if isinstance(fdict, dict):
        for k,v in fdict.items():
            if isinstance(v, str): out.append({'path':str(k),'content':v})
    if any(f.get('path')=='index.html' for f in out) and not any(f.get('path')=='README.md' for f in out):
        out.append({'path':'README.md','content':'# Goldie CLI Project\n\nBuilt by Goldie CLI from command:\n\n```text\n'+msg[:1000]+'\n```\n'})
    return out

def _cli_generate_project_files_with_llm(msg, existing_files, memory_text='', kb_text='', workspace=''):
    system = (
        'You are Goldie CLI inside a secure Hermes-style sandbox. You are a REAL file-writing builder. '
        'Use the user command, session memory, Goldie KB context, and current workspace files to create files. '
        'Return ONLY valid JSON, no markdown, no prose. JSON shape: '
        '{"files":[{"path":"index.html","content":"..."},{"path":"README.md","content":"..."}],"summary":"..."}. '
        'Paths must be safe relative paths only. Do not use absolute paths or .. traversal. '
        'For static sites, write a complete previewable index.html with inline CSS/JS unless separate files are necessary. '
        'Do not claim files are written; just return file contents for Hermes tools to write.'
    )
    prompt = (
        'USER COMMAND:\n{cmd}\n\n'
        'SESSION MEMORY:\n{mem}\n\n'
        'GOLDIE KB CONTEXT:\n{kb}\n\n'
        'CURRENT WORKSPACE FILES:\n{files}\n\n'
        'WORKSPACE ROOT (for context only; never output absolute paths):\n{ws}\n\n'
        'Now generate the actual files to write. Minimum required files: index.html and README.md.'
    ).format(cmd=msg[:1800], mem=memory_text[:1800] or '(none)', kb=kb_text[:1800] or '(none)', files='\n'.join(existing_files[:80]) or '(empty)', ws=workspace)
    raw = _cli_call_llm(prompt, system=system, tokens=2200, temp=0.25)
    if raw.startswith('[LLM Error:'):
        raise ValueError(raw)
    try:
        obj = _cli_extract_json_object(raw)
        files = _cli_files_from_json_obj(obj, msg)
    except Exception:
        files = _cli_files_from_llm_text(raw, msg)
    if not isinstance(files, list) or not files:
        files = _cli_files_from_llm_text(raw, msg)
    if not isinstance(files, list) or not files:
        repair_system = 'Return ONLY one complete HTML document for index.html. No explanation, no markdown.'
        repair_prompt = 'Create a previewable static landing page for this user command:\n' + msg[:1200]
        repair_raw = _cli_call_llm(repair_prompt, system=repair_system, tokens=1800, temp=0.25)
        files = _cli_files_from_llm_text('```html\n' + repair_raw + '\n```', msg)
    if not isinstance(files, list) or not files:
        raise ValueError('LLM builder did not return index.html')
    cleaned=[]
    has_index=False
    for item in files[:16]:
        if not isinstance(item, dict): continue
        rel = str(item.get('path') or item.get('filename') or item.get('file') or item.get('name') or '').strip().lstrip('/').replace('\\','/')
        content = item.get('content') if item.get('content') is not None else (item.get('html') if item.get('html') is not None else item.get('code'))
        if not rel or content is None: continue
        if rel.startswith('../') or '/../' in rel or rel in ('.','..'):
            continue
        if rel.endswith('/index.html') and not has_index:
            rel = 'index.html'
        if rel == 'index.html':
            has_index=True
        cleaned.append({'path': rel, 'content': str(content)[:300000]})
    if not any(f['path'] == 'index.html' for f in cleaned):
        raise ValueError('LLM builder did not return index.html')
    if not any(f['path'] == 'README.md' for f in cleaned):
        cleaned.append({'path':'README.md','content':'# Goldie CLI Project\n\nBuilt by Goldie CLI from command:\n\n```text\n'+msg[:1000]+'\n```\n'})
    return cleaned


def _cli_write_generated_files(workspace, files):
    written=[]
    for item in files:
        rel=item['path']
        path=_cli_safe_path(workspace, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _pathlib_cli.Path(path).write_text(item['content'], encoding='utf-8')
        written.append(rel)
    if any(x == 'index.html' for x in written):
        _cli_set_active_project(workspace, '', 'command-build')
    else:
        for x in written:
            if x.endswith('/index.html'):
                _cli_set_active_project(workspace, os.path.dirname(x), 'command-build')
                break
    return written

def _cli_build_from_user_command(handler, data, sid, workspace, msg):
    existing = _cli_list_files(workspace, 120)
    mem = _cli_load_memory(sid, 12)
    mem_txt = '\n'.join('%s: %s' % (m.get('role','user').upper(), (m.get('text') or '')[:700]) for m in mem)
    kb_txt = _cli_kb_context(msg)
    gen_files = _cli_generate_project_files_with_llm(msg, existing, mem_txt, kb_txt, workspace)
    written = _cli_write_generated_files(workspace, gen_files)
    prev = _handle_cli_preview_to_dict(handler, {'session': data.get('session')})
    files_now = _cli_file_tree(workspace, 120)
    return {
        'builder': 'goldie-pipeline-llm-writer',
        'pipeline': ['user-command', 'cli-memory', 'goldie-kb', 'llm-json-files', 'hermes-write-file', 'preview'],
        'written': written,
        'preview': prev,
        'files': files_now,
    }


def _cli_answer(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    msg = (data.get('message') or '').strip()
    if not msg:
        return {'status': 'ok', 'session_id': sid, 'workspace': workspace, 'reply': 'Goldie CLI ready. Try: /files, /run pwd, /write hello.txt\\nhi', 'output': '', 'rate_limit': {'cooldown_seconds': CLI_COOLDOWN_SECONDS}, 'model': {'provider': CLI_LLM_PROVIDER, 'name': CLI_LLM_MODEL}}
    ok_cd, wait_cd = _cli_cooldown_check(handler, sid)
    if not ok_cd:
        return {'status': 'error', 'error': 'cooldown', 'retry_after': wait_cd, 'reply': 'CLI cooldown active. Please wait %ss before sending another command. Limit: 1 command / %ss per workspace.' % (wait_cd, CLI_COOLDOWN_SECONDS), 'rate_limit': {'cooldown_seconds': CLI_COOLDOWN_SECONDS, 'retry_after': wait_cd}, 'model': {'provider': CLI_LLM_PROVIDER, 'name': CLI_LLM_MODEL}}
    _cli_append_memory(sid, 'user', msg)
    reply = ''
    output = ''
    files = _cli_list_files(workspace, 60)
    try:
        if msg.startswith('/files'):
            output = '\n'.join(files) or '(workspace empty)'
            reply = 'Files in sandbox workspace:'
        elif msg.startswith('/run '):
            cmd = msg[5:].strip()
            rr = _cli_run(workspace, cmd)
            output = '$ ' + cmd + '\n' + rr.get('output', '')
            reply = 'Command %s (exit %s).' % ('blocked' if rr.get('blocked') else ('finished' if rr.get('ok') else 'failed'), rr.get('returncode'))
        elif msg.startswith('/read '):
            p = _cli_safe_path(workspace, msg[6:].strip())
            if os.path.getsize(p) > 120000:
                raise ValueError('File too large for modal preview')
            output = _pathlib_cli.Path(p).read_text(encoding='utf-8', errors='replace')[:CLI_MAX_OUTPUT]
            reply = 'Read: ' + os.path.relpath(p, workspace)
        elif msg.startswith('/write '):
            rest = msg[7:]
            if '\n' in rest:
                rel, content = rest.split('\n', 1)
            elif ' | ' in rest:
                rel, content = rest.split(' | ', 1)
            elif '\\n' in rest:
                rel, content = rest.split('\\n', 1)
                content = content.replace('\\n', '\n')
            else:
                raise ValueError('Format: /write path | content')
            p = _cli_safe_path(workspace, rel.strip())
            os.makedirs(os.path.dirname(p), exist_ok=True)
            _pathlib_cli.Path(p).write_text(content[:200000], encoding='utf-8')
            rel_written = os.path.relpath(p, workspace).replace(os.sep, '/')
            if rel_written.endswith('index.html') and '/' in rel_written:
                _cli_set_active_project(workspace, os.path.dirname(rel_written), 'write:index')
            elif rel_written == 'index.html':
                _cli_set_active_project(workspace, '', 'write:root')
            elif rel_written == 'README.md':
                _cli_set_active_project(workspace, '', 'write:root')
            output = 'wrote %d chars to %s' % (len(content[:200000]), rel_written)
            reply = 'File written inside sandbox.'
        elif _cli_is_build_command(msg):
            built = _cli_build_from_user_command(handler, data, sid, workspace, msg)
            reply = 'Command executed: real build persisted files. Builder: %s.' % built.get('builder')
            output = 'pipeline: ' + ' -> '.join(built.get('pipeline') or []) + '\nwrote files:\n- ' + '\n- '.join(built.get('written') or [])
            if built.get('preview', {}).get('preview_url'):
                output += '\npreview: ' + built['preview']['preview_url']
        else:
            mem = _cli_load_memory(sid, 10)
            mem_txt = '\n'.join('%s: %s' % (m.get('role','user').upper(), (m.get('text') or '')[:700]) for m in mem)
            kb_txt = _cli_kb_context(msg)
            sysmsg = (
                'You are Goldie CLI, a secure coding assistant inside a per-user sandbox workspace. '
                'You help users code. Natural non-build questions are advisory, but explicit user build/create commands may persist files in the sandbox. '
                'Never claim you touched files unless a tool command output says so. Never reveal secrets. '
                'Core app /opt/gitpup and VPS secrets are off-limits. Workspace only: %s. '
                'Use Goldie KB patterns when useful. Keep output concise and terminal-friendly.' % workspace
            )
            prompt = 'SESSION MEMORY:\n%s\n\nGOLDIE KB CONTEXT:\n%s\n\nCURRENT FILES:\n%s\n\nUSER REQUEST:\n%s' % (mem_txt, kb_txt or '(none)', '\n'.join(files[:40]) or '(empty)', msg)
            reply = _cli_call_llm(prompt, system=sysmsg, tokens=500, temp=0.25)
            output = 'Tip commands: /files, /run pwd, /write app.py\\nprint("hi"), /read app.py'
    except Exception as e:
        reply = 'Error: ' + str(e)[:180]
    reply = _cli_redact(reply)
    output = _cli_redact(output)
    _cli_append_memory(sid, 'assistant', reply + ('\n' + output if output else ''))
    return {'status': 'ok', 'session_id': sid, 'workspace_name': 'user_' + sid, 'workspace': workspace, 'reply': reply, 'output': output, 'files': files[:80], 'sandbox': True, 'rate_limit': {'cooldown_seconds': CLI_COOLDOWN_SECONDS}, 'model': {'provider': CLI_LLM_PROVIDER, 'name': CLI_LLM_MODEL, 'base_url': CLI_LLM_BASE_URL}, 'gmail': {'available': False, 'reason': 'Google OAuth client not configured yet'}}


def _handle_cli_session(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    _cli_ensure_current_project(workspace)
    mem = _cli_load_memory(sid, 8)
    return _json_resp(handler, {'status': 'ok', 'session_id': sid, 'workspace_name': 'user_' + sid, 'workspace': workspace, 'sandbox': True, 'memory_turns': len(mem), 'files': _cli_file_tree(workspace, 80), 'security': {'path_locked': True, 'core_protected': True, 'secrets_redacted': True, 'shell_chaining_blocked': True}, 'rate_limit': {'cooldown_seconds': CLI_COOLDOWN_SECONDS}, 'model': {'provider': CLI_LLM_PROVIDER, 'name': CLI_LLM_MODEL, 'base_url': CLI_LLM_BASE_URL}, 'export': {'download_ready': True}, 'preview': {'enabled': True}})


def _handle_cli(handler, data):
    return _json_resp(handler, _cli_answer(handler, data))


def _handle_cli_email(handler, data):
    # Gmail sending requires real Google OAuth credentials and explicit user confirmation.
    return _json_resp(handler, {'status': 'setup_required', 'reply': 'Bisa bro, tapi perlu Google OAuth client + user consent Gmail/Drive scope dulu. Phase ini endpoint sengaja belum ngirim email biar aman.', 'gmail': {'available': False, 'needs_oauth': True}}, 501)



# === CLI export / preview / file browser ===


# === CLI active project tracking ===
def _cli_active_file(workspace):
    return os.path.join(workspace, '.goldie-active-project.json')

def _cli_normalize_project_dir(rel):
    rel = (rel or '').strip().replace('\\', '/').strip('/')
    if rel in ('.', 'tmp', 'logs'):
        return ''
    return rel

def _cli_set_active_project(workspace, rel_dir='', source='manual'):
    rel_dir = _cli_normalize_project_dir(rel_dir)
    if rel_dir:
        root = _cli_safe_path(workspace, rel_dir)
        if not os.path.isdir(root): os.makedirs(root, exist_ok=True)
    meta = {'project_dir': rel_dir, 'source': source, 'updated_at': time.time()}
    _pathlib_cli.Path(_cli_active_file(workspace)).write_text(json.dumps(meta), encoding='utf-8')
    return meta

def _cli_get_active_project(workspace):
    try:
        meta = json.loads(_pathlib_cli.Path(_cli_active_file(workspace)).read_text(encoding='utf-8'))
        rel = _cli_normalize_project_dir(meta.get('project_dir'))
        if rel == '' or os.path.isdir(_cli_safe_path(workspace, rel)):
            meta['project_dir'] = rel
            return meta
    except Exception:
        pass
    return None

def _cli_slug(text):
    import re
    slug = re.sub(r'[^a-z0-9]+', '-', (text or 'project').lower()).strip('-')[:32]
    return slug or 'project'


def _cli_extract_project_title(html):
    try:
        import re
        txt = html or ''
        m = re.search(r'<title[^>]*>(.*?)</title>', txt, re.I|re.S) or re.search(r'<h1[^>]*>(.*?)</h1>', txt, re.I|re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if title: return title[:80]
        low = txt.lower()
        if 'cyberpunk' in low: return 'Cyberpunk Landing Page'
        if 'neon' in low: return 'Neon Landing Page'
    except Exception:
        pass
    return 'Landing Page'

def _cli_write_readme_for_root(workspace, source='index'):
    try:
        idx = _cli_safe_path(workspace, 'index.html')
        if not os.path.isfile(idx): return False
        html = _pathlib_cli.Path(idx).read_text(encoding='utf-8', errors='ignore')[:12000]
        title = _cli_extract_project_title(html)
        body = '# ' + title + '\n\nGenerated current project for Goldie CLI.\n\n## Preview\n\nUse the Goldie CLI **Preview** button or open `index.html`.\n'
        _pathlib_cli.Path(_cli_safe_path(workspace, 'README.md')).write_text(body, encoding='utf-8')
        return True
    except Exception:
        return False

def _cli_readme_stale(workspace):
    try:
        idx = _cli_safe_path(workspace, 'index.html')
        rd = _cli_safe_path(workspace, 'README.md')
        if not os.path.isfile(idx): return False
        if not os.path.isfile(rd): return True
        text = _pathlib_cli.Path(rd).read_text(encoding='utf-8', errors='ignore')[:1000].lower()
        stale_markers = ['goldie static landing', 'todo static app', 'old readme', 'click preview in goldie cli']
        if any(m in text for m in stale_markers): return True
        return os.path.getmtime(rd) + 1 < os.path.getmtime(idx)
    except Exception:
        return False

def _cli_promote_project_to_root(workspace, rel_dir, source='promote'):
    """Copy a nested project into workspace root so README/index are the current project, not stale leftovers."""
    rel_dir = _cli_normalize_project_dir(rel_dir)
    if not rel_dir:
        return _cli_set_active_project(workspace, '', source)
    src = _cli_safe_path(workspace, rel_dir)
    if not os.path.isdir(src):
        return _cli_set_active_project(workspace, rel_dir, source)
    skip_dirs = {'.git','node_modules','__pycache__','.venv','venv','tmp','logs'}
    copied=[]
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        for name in files:
            if name.startswith('.') or name.endswith(('.pyc','.zip')): continue
            sp=os.path.join(root,name)
            sub=os.path.relpath(sp, src).replace(os.sep,'/')
            dp=_cli_safe_path(workspace, sub)
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            _pathlib_cli.Path(dp).write_bytes(_pathlib_cli.Path(sp).read_bytes())
            copied.append(sub)
    if 'README.md' not in copied or _cli_readme_stale(workspace):
        _cli_write_readme_for_root(workspace, source)
    _cli_set_active_project(workspace, '', source+':'+rel_dir)
    return {'copied': copied, 'project_dir': ''}


def _cli_ensure_current_project(workspace):
    # Side-effect free now: preview/tree/export must never rewrite user files.
    return False


def _cli_files_under(workspace, rel_root, limit=240):
    rel_root = _cli_normalize_project_dir(rel_root)
    root_path = _cli_safe_path(workspace, rel_root) if rel_root else workspace
    rows=[]
    skip_dirs={'.git','node_modules','__pycache__','.venv','venv','dist','build'}
    if not rel_root:
        skip_dirs.update({'projects','repos','tmp','logs'})
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        rel_dir = os.path.relpath(root, root_path)
        depth = 0 if rel_dir == '.' else rel_dir.count(os.sep)+1
        if depth > 5:
            dirs[:] = []; continue
        for name in sorted(files):
            if name.startswith('.') or name.endswith(('.pyc','.zip')): continue
            path=os.path.join(root,name)
            rel=os.path.relpath(path, workspace).replace(os.sep,'/')
            try: size=os.path.getsize(path)
            except OSError: size=0
            rows.append({'path':rel,'name':name,'size':size,'kind':'file'})
            if len(rows)>=limit: return rows
    return rows

def _cli_file_tree(workspace, limit=240):
    active = _cli_get_active_project(workspace)
    if active:
        return _cli_files_under(workspace, active.get('project_dir'), limit)
    return _cli_files_under(workspace, '', limit)


def _handle_cli_tree(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    _cli_ensure_current_project(workspace)
    return _json_resp(handler, {'status': 'ok', 'session_id': sid, 'workspace_name': 'user_' + sid, 'active_project': _cli_get_active_project(workspace), 'files': _cli_file_tree(workspace)})


def _handle_cli_read(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    rel = (data.get('path') or '').strip()
    if not rel:
        return _json_resp(handler, {'status': 'error', 'error': 'missing path'}, 400)
    path = _cli_safe_path(workspace, rel)
    if not os.path.isfile(path):
        return _json_resp(handler, {'status': 'error', 'error': 'file not found'}, 404)
    if os.path.getsize(path) > 256 * 1024:
        return _json_resp(handler, {'status': 'error', 'error': 'file too large for preview'}, 413)
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = _cli_redact(f.read())
        return _json_resp(handler, {'status': 'ok', 'session_id': sid, 'path': rel, 'content': content})
    except Exception as e:
        return _json_resp(handler, {'status': 'error', 'error': str(e)[:120]}, 500)


def _cli_zip_workspace(sid, workspace):
    import zipfile
    export_dir = os.path.join(workspace, 'tmp')
    os.makedirs(export_dir, exist_ok=True)
    zip_path = os.path.join(export_dir, 'goldie-workspace-' + sid + '.zip')
    skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}
    active = _cli_get_active_project(workspace)
    
    if active and not active.get('project_dir'):
        skip_dirs.update({'projects','repos','tmp','logs'})
    walk_root = _cli_safe_path(workspace, active.get('project_dir')) if (active and active.get('project_dir')) else workspace
    total = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(walk_root):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for name in files:
                path = os.path.join(root, name)
                if path == zip_path or name.endswith('.zip') or name in ('.goldie-session.json', '.goldie-active-project.json'):
                    continue
                rel = os.path.relpath(path, workspace).replace(os.sep, '/')
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                total += size
                if total > 50 * 1024 * 1024:
                    raise ValueError('workspace export too large')
                z.write(path, rel)
    return zip_path


def _handle_cli_export(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    _cli_ensure_current_project(workspace)
    try:
        zip_path = _cli_zip_workspace(sid, workspace)
        return _json_resp(handler, {'status': 'ok', 'session_id': sid, 'workspace_name': 'user_' + sid, 'download_url': '/api/cli/download?session=' + urllib.parse.quote(sid), 'size': os.path.getsize(zip_path)})
    except Exception as e:
        return _json_resp(handler, {'status': 'error', 'error': str(e)[:120]}, 500)




def _cli_find_preview_index(workspace):
    """Return active project's index.html first; fallback to newest index.html."""
    active = _cli_get_active_project(workspace)
    if active:
        base = active.get('project_dir') or ''
        for sub in ['index.html','public/index.html','dist/index.html','build/index.html']:
            rel = (base + '/' + sub).strip('/')
            try:
                path = _cli_safe_path(workspace, rel)
                if os.path.isfile(path): return rel, int(os.path.getmtime(path))
            except Exception: pass
    choices = []
    preferred = ['index.html', 'public/index.html', 'dist/index.html', 'build/index.html', 'projects/index.html']
    seen = set()
    for rel in preferred:
        try:
            path = _cli_safe_path(workspace, rel)
            if os.path.isfile(path):
                choices.append((os.path.getmtime(path), rel)); seen.add(rel)
        except Exception:
            pass
    try:
        for f in _cli_file_tree(workspace, 800):
            rel = f.get('path','')
            if rel in seen: continue
            if rel == 'index.html' or rel.endswith('/index.html'):
                path = _cli_safe_path(workspace, rel)
                if os.path.isfile(path): choices.append((os.path.getmtime(path), rel))
    except Exception:
        pass
    if not choices:
        return None, None
    choices.sort(key=lambda x: x[0], reverse=True)
    return choices[0][1], int(choices[0][0])

def _handle_cli_preview(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    _cli_ensure_current_project(workspace)
    found, mtime = _cli_find_preview_index(workspace)
    if not found:
        return _json_resp(handler, {'status': 'error', 'error': 'No index.html found. Create one first, then preview.'}, 404)
    url = '/preview/' + urllib.parse.quote(sid) + '/' + found + '?v=' + str(mtime or int(time.time()))
    return _json_resp(handler, {'status': 'ok', 'session_id': sid, 'preview_url': url, 'preview_path': found})


def _serve_cli_download(handler):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
    sid = ''.join(ch for ch in (q.get('session', [''])[0]) if ch.isalnum() or ch in ('_', '-'))[:80]
    if not sid:
        return _json_resp(handler, {'status': 'error', 'error': 'missing session'}, 400)
    workspace = os.path.realpath(os.path.join(os.path.realpath(WORKSPACES), 'user_' + sid))
    if not workspace.startswith(os.path.realpath(WORKSPACES) + os.sep):
        return _json_resp(handler, {'status': 'error', 'error': 'invalid session'}, 400)
    zip_path = os.path.join(workspace, 'tmp', 'goldie-workspace-' + sid + '.zip')
    if not os.path.exists(zip_path):
        try:
            zip_path = _cli_zip_workspace(sid, workspace)
        except Exception as e:
            return _json_resp(handler, {'status': 'error', 'error': str(e)[:120]}, 500)
    handler.send_response(200)
    handler.send_header('Content-Type', 'application/zip')
    handler.send_header('Content-Disposition', 'attachment; filename="goldie-workspace-' + sid + '.zip"')
    handler.send_header('Content-Length', str(os.path.getsize(zip_path)))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()
    with open(zip_path, 'rb') as f:
        handler.wfile.write(f.read())


def _serve_cli_preview(handler):
    import mimetypes
    parts = urllib.parse.urlparse(handler.path).path.split('/')
    if len(parts) < 3:
        handler.send_error(404); return
    sid = ''.join(ch for ch in urllib.parse.unquote(parts[2]) if ch.isalnum() or ch in ('_', '-'))[:80]
    rel = urllib.parse.unquote('/'.join(parts[3:]) or 'index.html')
    workspace = os.path.realpath(os.path.join(os.path.realpath(WORKSPACES), 'user_' + sid))
    if not workspace.startswith(os.path.realpath(WORKSPACES) + os.sep):
        handler.send_error(403); return
    try:
        path = _cli_safe_path(workspace, rel)
    except Exception:
        handler.send_error(403); return
    if os.path.isdir(path):
        path = os.path.join(path, 'index.html')
    if not os.path.isfile(path):
        handler.send_error(404); return
    ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    handler.send_response(200)
    handler.send_header('Content-Type', ctype)
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    with open(path, 'rb') as f:
        handler.wfile.write(f.read())


# === CLI Phase 3: agent jobs, templates, editor save, quotas, git safety ===
_CLI_JOBS = {}
_CLI_JOB_LOCK = threading.Lock()
_CLI_MAX_WORKSPACE_BYTES = 80 * 1024 * 1024
_CLI_MAX_FILES = 800

def _cli_workspace_stats(workspace):
    total = 0; files = 0
    skip = {'.git','node_modules','.venv','venv','__pycache__'}
    for root, dirs, names in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip]
        for n in names:
            try:
                total += os.path.getsize(os.path.join(root,n)); files += 1
            except OSError: pass
    return {'bytes': total, 'files': files, 'max_bytes': _CLI_MAX_WORKSPACE_BYTES, 'max_files': _CLI_MAX_FILES}

def _cli_quota_ok(workspace):
    st = _cli_workspace_stats(workspace)
    return st['bytes'] <= st['max_bytes'] and st['files'] <= st['max_files'], st

def _cli_job_new(sid, kind, goal):
    jid = hashlib.sha256((sid+'|'+kind+'|'+str(time.time())).encode()).hexdigest()[:16]
    job = {'id': jid, 'session_id': sid, 'kind': kind, 'goal': goal, 'status': 'queued', 'logs': [], 'created_at': time.time(), 'updated_at': time.time(), 'result': None}
    with _CLI_JOB_LOCK: _CLI_JOBS[jid] = job
    return job

def _cli_job_log(job, msg):
    with _CLI_JOB_LOCK:
        job['logs'].append('[%s] %s' % (time.strftime('%H:%M:%S'), _cli_redact(msg)))
        job['logs'] = job['logs'][-200:]; job['updated_at'] = time.time()

def _cli_job_finish(job, status, result=None):
    with _CLI_JOB_LOCK:
        job['status'] = status; job['result'] = result or {}; job['updated_at'] = time.time()

_CLI_TEMPLATES = {
 'static-landing': {'index.html': '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Goldie Landing</title><style>body{margin:0;font-family:Inter,system-ui;background:#09111f;color:#eef}main{min-height:100vh;display:grid;place-items:center;padding:28px}.card{max-width:760px;background:linear-gradient(135deg,rgba(100,255,218,.14),rgba(244,197,66,.1));border:1px solid rgba(255,255,255,.12);border-radius:28px;padding:34px;box-shadow:0 30px 90px #0008}h1{font-size:clamp(36px,8vw,82px);margin:0}p{font-size:18px;line-height:1.7;color:#b8c7d8}.btn{display:inline-block;margin-top:14px;padding:12px 18px;border-radius:999px;background:#64ffda;color:#07111d;text-decoration:none;font-weight:900}</style></head><body><main><section class="card"><h1>Built by Goldie</h1><p>A polished static landing page generated inside a locked CLI workspace.</p><a class="btn" href="#">Launch</a></section></main></body></html>', 'README.md': '# Goldie static landing\n\nPreview with the CLI Preview button.\n'},
 'cyberpunk-landing': {'index.html': '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cyberpunk Landing</title><style>:root{--bg:#05020d;--pink:#ff2bd6;--cyan:#28f7ff;--yellow:#f8ff4a}*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui;background:radial-gradient(circle at 20% 10%,#24114d,transparent 28%),radial-gradient(circle at 80% 20%,#3b0630,transparent 30%),linear-gradient(180deg,#05020d,#080816 70%,#02040b);color:#f7fbff;min-height:100vh;overflow-x:hidden}.grid{position:fixed;inset:0;background-image:linear-gradient(rgba(40,247,255,.09) 1px,transparent 1px),linear-gradient(90deg,rgba(255,43,214,.08) 1px,transparent 1px);background-size:42px 42px;mask-image:linear-gradient(to bottom,transparent,#000 24%,#000 80%,transparent);pointer-events:none}.wrap{min-height:100vh;display:grid;place-items:center;padding:32px}.hero{width:min(1080px,94vw);border:1px solid rgba(40,247,255,.28);border-radius:34px;padding:42px;background:linear-gradient(135deg,rgba(255,43,214,.13),rgba(40,247,255,.08));box-shadow:0 0 80px rgba(255,43,214,.22),inset 0 0 60px rgba(40,247,255,.08);position:relative;overflow:hidden}.tag{color:var(--cyan);letter-spacing:.22em;text-transform:uppercase;font-weight:900;text-shadow:0 0 18px var(--cyan)}h1{font-size:clamp(48px,9vw,112px);line-height:.88;margin:18px 0;text-transform:uppercase;text-shadow:5px 0 var(--pink),-4px 0 var(--cyan),0 0 34px rgba(255,43,214,.55)}p{max-width:720px;color:#c9d7ff;font-size:20px;line-height:1.7}.cta{display:flex;gap:14px;flex-wrap:wrap;margin-top:28px}.btn{padding:14px 20px;border-radius:14px;text-decoration:none;font-weight:950;color:#06010d;background:linear-gradient(90deg,var(--cyan),var(--yellow));box-shadow:0 0 26px rgba(40,247,255,.38)}.btn.alt{background:transparent;color:var(--pink);border:1px solid var(--pink)}.panel{margin-top:34px;display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}.card{border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:18px;background:rgba(0,0,0,.28)}.card b{color:var(--cyan)}</style></head><body><div class="grid"></div><main class="wrap"><section class="hero"><div class="tag">neon systems online</div><h1>Cyberpunk Landing</h1><p>A high-voltage landing page with neon gradients, glass panels, and futuristic product positioning — generated inside Goldie CLI.</p><div class="cta"><a class="btn" href="#">Enter Night City</a><a class="btn alt" href="#">View Protocol</a></div><div class="panel"><div class="card"><b>01</b><br>Neon visual identity</div><div class="card"><b>02</b><br>Fast static preview</div><div class="card"><b>03</b><br>Export-ready workspace</div></div></section></main></body></html>', 'README.md': '# Cyberpunk Landing\n\nA neon cyberpunk landing page generated by Goldie CLI.\n\n## Preview\n\nUse the Goldie CLI **Preview** button or open `index.html`.\n'},
 'todo-static': {'index.html': '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Todo</title><style>body{font-family:system-ui;background:#101827;color:#fff;display:grid;place-items:center;min-height:100vh}.app{width:min(560px,92vw);background:#172238;border:1px solid #2b3b5d;border-radius:22px;padding:24px}input,button{padding:12px;border-radius:12px;border:0}input{width:70%;background:#0d1424;color:#fff}button{background:#64ffda;font-weight:800}li{margin:10px 0;padding:10px;background:#0d1424;border-radius:10px;cursor:pointer}</style></head><body><div class="app"><h1>Todo App</h1><input id="i" placeholder="New task"><button onclick="add()">Add</button><ul id="l"></ul></div><script>let items=JSON.parse(localStorage.todos||\'[]\');function draw(){l.innerHTML=items.map((x,i)=>\'<li onclick="done(\'+i+\')">\'+x+\'</li>\').join(\'\')}function add(){if(i.value.trim()){items.push(i.value.trim());i.value=\'\';localStorage.todos=JSON.stringify(items);draw()}}function done(n){items.splice(n,1);localStorage.todos=JSON.stringify(items);draw()}draw()</script></body></html>', 'README.md': '# Todo Static App\n\nClick Preview in Goldie CLI.\n'}
}

def _cli_apply_template(workspace, name, project_name=None):
    tpl = _CLI_TEMPLATES.get(name)
    if not tpl: raise ValueError('Unknown template: '+name)
    written=[]
    for rel, content in tpl.items():
        out_rel = rel.replace('//','/')
        path=_cli_safe_path(workspace, out_rel); os.makedirs(os.path.dirname(path), exist_ok=True)
        _pathlib_cli.Path(path).write_text(content, encoding='utf-8'); written.append(out_rel)
    _cli_set_active_project(workspace, '', 'template:'+name)
    return written

def _handle_cli_preview_to_dict(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    _cli_ensure_current_project(workspace)
    found, mtime = _cli_find_preview_index(workspace)
    if not found: return {'status':'error','error':'No index.html found. Create one first, then preview.'}
    return {'status':'ok','session_id':sid,'preview_url':'/preview/'+urllib.parse.quote(sid)+'/'+found+'?v='+str(mtime or int(time.time())),'preview_path':found}

def _handle_cli_export_to_dict(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    _cli_ensure_current_project(workspace)
    zip_path = _cli_zip_workspace(sid, workspace)
    return {'status':'ok','session_id':sid,'workspace_name':'user_'+sid,'download_url':'/api/cli/download?session='+urllib.parse.quote(sid),'size':os.path.getsize(zip_path)}

def _cli_agent_build(job, handler, data):
    sid, workspace = _cli_workspace(handler, data)
    goal = (data.get('goal') or data.get('message') or '').strip()[:1200]
    try:
        job['status']='running'; _cli_job_log(job, 'Agent loop started: '+goal)
        ok, stats = _cli_quota_ok(workspace)
        if not ok: raise ValueError('Workspace quota exceeded before build')
        low = goal.lower(); template = 'cyberpunk-landing' if 'cyberpunk' in low or 'neon' in low else ('todo-static' if 'todo' in low or 'task' in low else 'static-landing')
        _cli_job_log(job, 'Plan: create '+template+' project')
        written = _cli_apply_template(workspace, template, goal); _cli_job_log(job, 'Wrote: '+', '.join(written))
        _cli_job_log(job, 'Validation: index.html exists')
        prev = _handle_cli_preview_to_dict(handler, {'session': data.get('session')})
        exp = _handle_cli_export_to_dict(handler, {'session': data.get('session')})
        result = {'files': _cli_file_tree(workspace, 120), 'preview': prev, 'export': exp, 'template': template}
        _cli_job_log(job, 'Preview: '+str(prev.get('preview_url'))); _cli_job_finish(job, 'done', result)
    except Exception as e:
        _cli_job_log(job, 'ERROR: '+str(e)[:160]); _cli_job_finish(job, 'error', {'error': str(e)[:160]})

def _handle_cli_agent(handler, data):
    return _json_resp(handler, {'status':'disabled','reply':'Agent Build is disabled. Files only change from explicit user commands like /write, Save, or Template.'}, 403)


def _handle_cli_job(handler, data):
    jid = (data.get('job_id') or data.get('id') or '').strip()
    with _CLI_JOB_LOCK: job = _CLI_JOBS.get(jid)
    if not job: return _json_resp(handler, {'status':'error','error':'job not found'}, 404)
    return _json_resp(handler, {'status':'ok','job':job})

def _handle_cli_template(handler, data):
    sid, workspace = _cli_workspace(handler, data); name = (data.get('template') or data.get('name') or 'static-landing').strip()
    try:
        written = _cli_apply_template(workspace, name, name)
        return _json_resp(handler, {'status':'ok','session_id':sid,'template':name,'active_project':_cli_get_active_project(workspace),'written':written,'files':_cli_file_tree(workspace,120)})
    except Exception as e: return _json_resp(handler, {'status':'error','error':str(e)[:120]}, 400)

def _handle_cli_save(handler, data):
    sid, workspace = _cli_workspace(handler, data); rel=(data.get('path') or '').strip(); content=data.get('content') or ''
    if not rel: return _json_resp(handler, {'status':'error','error':'missing path'}, 400)
    try:
        ok, stats = _cli_quota_ok(workspace)
        if not ok: raise ValueError('Workspace quota exceeded')
        path=_cli_safe_path(workspace, rel); os.makedirs(os.path.dirname(path), exist_ok=True)
        _pathlib_cli.Path(path).write_text(str(content)[:300000], encoding='utf-8')
        
        if rel.endswith('index.html') and '/' in rel:
            _cli_set_active_project(workspace, os.path.dirname(rel), 'save:index')
        elif rel == 'index.html':
            _cli_set_active_project(workspace, '', 'save:root')
        elif rel == 'README.md':
            _cli_set_active_project(workspace, '', 'save:root')
        return _json_resp(handler, {'status':'ok','path':rel,'active_project':_cli_get_active_project(workspace),'bytes':len(str(content).encode()),'files':_cli_file_tree(workspace,160)})
    except Exception as e: return _json_resp(handler, {'status':'error','error':str(e)[:120]}, 400)

def _handle_cli_quota(handler, data):
    sid, workspace = _cli_workspace(handler, data); return _json_resp(handler, {'status':'ok','session_id':sid,'quota':_cli_workspace_stats(workspace)})

def _cli_scan_secrets(workspace):
    findings=[]; pat=_re_cli.compile(r'(sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9_]{12,}|BEGIN\s+(RSA|OPENSSH|PRIVATE)\s+KEY|API_KEY\s*=|TOKEN\s*=|SECRET\s*=)', _re_cli.I)
    for f in _cli_file_tree(workspace, 500):
        rel=f['path']
        try:
            path=_cli_safe_path(workspace, rel)
            if os.path.getsize(path)>200000: continue
            txt=_pathlib_cli.Path(path).read_text(encoding='utf-8', errors='ignore')
            if pat.search(txt) or rel.endswith('.env'): findings.append({'path':rel,'reason':'secret-like content or env file'})
        except Exception: pass
    return findings

def _handle_cli_git_scan(handler, data):
    sid, workspace = _cli_workspace(handler, data); findings=_cli_scan_secrets(workspace)
    return _json_resp(handler, {'status':'ok' if not findings else 'blocked','findings':findings,'safe_to_push':not findings})

def _handle_cli_git_push(handler, data):
    sid, workspace = _cli_workspace(handler, data); findings=_cli_scan_secrets(workspace)
    if findings: return _json_resp(handler, {'status':'blocked','reply':'Push blocked: secret-like files found.','findings':findings}, 403)
    if not data.get('confirm'): return _json_resp(handler, {'status':'needs_confirmation','reply':'Git push requires explicit confirmation after scan. Send confirm:true.'})
    return _json_resp(handler, {'status':'setup_required','reply':'Push flow is safety-gated. Configure GitLawb/GitHub remote for this workspace first, then retry with confirmation.'})

def _handle_cli_reset(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    if not data.get('confirm'): return _json_resp(handler, {'status':'needs_confirmation','reply':'Workspace reset requires confirm:true'})
    for item in os.listdir(workspace):
        if item in ('tmp','logs','.goldie-session.json'): continue
        path=os.path.join(workspace,item)
        try:
            if os.path.isdir(path):
                import shutil; shutil.rmtree(path)
            else: os.remove(path)
        except Exception: pass
    return _json_resp(handler, {'status':'ok','reply':'Workspace reset complete','files':_cli_file_tree(workspace,80)})

def _public_do_POST(self):
    p = urllib.parse.urlparse(self.path).path
    if p not in ('/api/chat', '/api/image', '/api/song', '/api/cli/session', '/api/cli', '/api/cli/tree', '/api/cli/read', '/api/cli/export', '/api/cli/preview', '/api/cli/agent', '/api/cli/job', '/api/cli/template', '/api/cli/save', '/api/cli/quota', '/api/cli/git/scan', '/api/cli/git/push', '/api/cli/reset'):
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
        if p == '/api/cli/session':
            return _handle_cli_session(self, data)
        if p == '/api/cli':
            return _handle_cli(self, data)
        if p == '/api/cli/tree':
            return _handle_cli_tree(self, data)
        if p == '/api/cli/read':
            return _handle_cli_read(self, data)
        if p == '/api/cli/export':
            return _handle_cli_export(self, data)
        if p == '/api/cli/preview':
            return _handle_cli_preview(self, data)
        if p == '/api/cli/agent':
            return _handle_cli_agent(self, data)
        if p == '/api/cli/job':
            return _handle_cli_job(self, data)
        if p == '/api/cli/template':
            return _handle_cli_template(self, data)
        if p == '/api/cli/save':
            return _handle_cli_save(self, data)
        if p == '/api/cli/quota':
            return _handle_cli_quota(self, data)
        if p == '/api/cli/git/scan':
            return _handle_cli_git_scan(self, data)
        if p == '/api/cli/git/push':
            return _handle_cli_git_push(self, data)
        if p == '/api/cli/reset':
            return _handle_cli_reset(self, data)
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