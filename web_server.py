#!/usr/bin/env python3
"""GitPup Web Server v3.0 — Full API with project build pipeline"""
import http.server, json, os, urllib.parse, urllib.request, subprocess, time, threading, re, hmac

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

    file_errors = (OSError,)
    try:
        file_errors = (FileNotFoundError, OSError)
    except NameError:
        pass

    try:
        if not path:
            return default
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except decode_error:
        # Handle corrupt or partially written JSON safely.
        return default
    except (file_errors + (ValueError, TypeError, UnicodeError)):
        return default
    except Exception:
        return default

def load_jsonl(path):
    entries = []
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Skip malformed JSON lines and continue loading the rest.
                        continue
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
        '/auth/callback', '/api/image/job'
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
            # Compute aggregates. IMPORTANT: story card must show REAL tracked spend,
            # not estimated historical baseline rows.
            real_entries = [e for e in entries if e.get('phase') != 'historical_baseline']
            estimated_entries = [e for e in entries if e.get('phase') == 'historical_baseline']
            total_in = sum(e.get('prompt_tokens',0) for e in real_entries)
            total_out = sum(e.get('completion_tokens',0) for e in real_entries)
            total_all = sum(e.get('total_tokens',0) for e in real_entries)
            total_cost = sum(e.get('cost_usd',0) for e in real_entries)
            estimated_total_cost = total_cost + sum(e.get('cost_usd',0) for e in estimated_entries)
            # Today
            import time
            today = time.strftime('%Y-%m-%d')
            today_entries = [e for e in real_entries if today in e.get('date','')]
            today_cost = sum(e.get('cost_usd',0) for e in today_entries)
            today_tokens = sum(e.get('total_tokens',0) for e in today_entries)
            # Per run
            runs = {}
            for e in real_entries:
                phase = e.get('phase','unknown')
                if phase not in runs:
                    runs[phase] = {'count':0, 'tokens':0, 'cost':0}
                runs[phase]['count'] += 1
                runs[phase]['tokens'] += e.get('total_tokens',0)
                runs[phase]['cost'] += e.get('cost_usd',0)
            _json_resp(self, {
                'total_cost_usd': round(total_cost, 8),
                'total_tokens': total_all,
                'total_prompt_tokens': total_in,
                'total_completion_tokens': total_out,
                'today_cost': round(today_cost, 8),
                'today_tokens': today_tokens,
                'entries_count': len(real_entries),
                'estimated_total_cost_usd': round(estimated_total_cost, 4),
                'estimated_baseline_cost_usd': round(sum(e.get('cost_usd',0) for e in estimated_entries), 4),
                'source': 'real_cost_tracking_jsonl_excluding_estimated_baseline',
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

    elif p == '/api/image/job':
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        job = _image_job_get((qs.get('id') or [''])[0])
        if not job:
            _json_resp(self, {'status':'error','error':'job not found'}, 404)
        else:
            _json_resp(self, {'status':'ok','job':_image_job_public(job)})

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
            with urllib.request.urlopen(req, timeout=120) as r:
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
                    with urllib.request.urlopen(req, timeout=120) as r:
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


_IMAGE_JOBS = {}
_IMAGE_JOB_TTL = 1800

def _image_job_public(job):
    keep = ['id','status','reply','mode','image_url','size_bytes','model','provider','requested_model','fallback_model','limit','output_size','error','created_at','updated_at']
    return {k: job.get(k) for k in keep if k in job}

def _image_job_store(job):
    import time, threading
    lock = globals().setdefault('_IMAGE_JOBS_LOCK', threading.Lock())
    now = time.time()
    with lock:
        for jid, old in list(_IMAGE_JOBS.items()):
            if now - old.get('created_at', now) > _IMAGE_JOB_TTL:
                _IMAGE_JOBS.pop(jid, None)
        _IMAGE_JOBS[job['id']] = job

def _image_job_get(job_id):
    import threading
    lock = globals().setdefault('_IMAGE_JOBS_LOCK', threading.Lock())
    with lock:
        return _IMAGE_JOBS.get(str(job_id or ''))

def _image_job_update(job_id, **updates):
    import time, threading
    lock = globals().setdefault('_IMAGE_JOBS_LOCK', threading.Lock())
    with lock:
        job = _IMAGE_JOBS.get(str(job_id or ''))
        if not job:
            return None
        job.update(updates)
        job['updated_at'] = time.time()
        return job

def _handle_image_async(self, data):
    import time, uuid, threading
    job_id = 'img_' + uuid.uuid4().hex[:16]
    user_key = data.get('session') or data.get('user') or 'anonymous'
    mode = 'edit' if data.get('image') else 'generate'
    job = {'id': job_id, 'status': 'queued', 'reply': 'Image edit started.' if mode == 'edit' else 'Image generation started.', 'mode': mode, 'created_at': time.time(), 'updated_at': time.time(), 'limit': '1/5 minutes'}
    _image_job_store(job)
    def run():
        try:
            _image_job_update(job_id, status='running', reply='Editing image with uploaded source...' if mode == 'edit' else 'Generating image...')
            result = _handle_image_result(data)
            if result.get('status') == 'ok':
                result.pop('status', None)
                _image_job_update(job_id, status='done', **result)
            else:
                _image_rate_refund(self, user_key)
                _image_job_update(job_id, status='error', reply=result.get('reply') or 'Image model did not return an image.', error=result.get('error') or 'image_failed')
        except Exception as e:
            _image_rate_refund(self, user_key)
            _image_job_update(job_id, status='error', reply='Image generation failed.', error=str(e)[:300])
    threading.Thread(target=run, daemon=True).start()
    return _json_resp(self, {'status': 'queued', 'job_id': job_id, 'job': _image_job_public(job), 'reply': job['reply']})


def _handle_image_result(data):
    import time, json, urllib.request, urllib.error, base64, os
    user_key = data.get('session') or data.get('user') or 'anonymous'
    prompt = (data.get('prompt') or data.get('message') or '').strip()
    if not prompt:
        return {'status':'error','error':'missing_prompt','reply':'Please enter an image prompt.'}
    if len(prompt) > 1500:
        prompt = prompt[:1500]
    _load_env_file_once()
    provider = (os.environ.get('IMAGE_PROVIDER') or 'jatevo').strip().lower()
    primary_model = os.environ.get('JATEVO_IMAGE_MODEL') or os.environ.get('IMAGE_MODEL') or 'gpt-image-2'
    fallback_model = os.environ.get('JATEVO_IMAGE_FALLBACK_MODEL') or os.environ.get('IMAGE_FALLBACK_MODEL') or 'gpt-image-1'
    image_data = data.get('image') or data.get('image_base64') or ''
    if provider != 'jatevo' and image_data:
        # OpenRouter edit-capable image models can differ from generate models.
        # Keep IMAGE_MODEL for generation, and allow IMAGE_EDIT_MODEL to drive uploaded-source edits.
        primary_model = os.environ.get('IMAGE_EDIT_MODEL') or os.environ.get('OPENROUTER_IMAGE_EDIT_MODEL') or primary_model
        fallback_model = os.environ.get('IMAGE_EDIT_FALLBACK_MODEL') or os.environ.get('OPENROUTER_IMAGE_EDIT_FALLBACK_MODEL') or fallback_model
    if image_data:
        face_lock = (
            "CRITICAL FACE PRESERVATION INSTRUCTIONS: Before editing, carefully inspect every visible person in the uploaded image. "
            "Identify and preserve each person's original facial identity and all subtle face details: face shape, proportions, eyes, eyelids, eyebrows, nose bridge and nostrils, lips and mouth shape, teeth if visible, jawline, cheeks, chin, skin texture, moles, wrinkles, age, expression, gaze direction, and unique recognizable features. "
            "Do not invent a new face. Do not beautify, reshape, swap identity, change ethnicity, change age, over-smooth skin, enlarge eyes, alter nose/lips/teeth, or exaggerate smiles. "
            "Keep the original facial expression as close as possible unless the user explicitly asks for an expression change; if expression change is requested, make it extremely subtle and identity-preserving. "
            "Apply the requested edit only to the scene, outfit, lighting, background, pose, or body styling while keeping every face recognizably the same person. "
            "REALISTIC PHONE PHOTO STYLE: Make the final image look like an ordinary amateur photo taken by a real iPhone/phone user, not a professional photoshoot or AI render. Use natural imperfect lighting, realistic phone-camera perspective, normal dynamic range, mild handheld framing, subtle grain/noise, everyday color, and believable shadows. Avoid cinematic lighting, glossy editorial retouching, over-sharp details, perfect studio composition, hyperreal skin, plastic texture, excessive bokeh, and luxury ad aesthetics unless the user explicitly asks for those. "
        )
        prompt = face_lock + '\n\nUSER EDIT REQUEST: ' + prompt
    last_error = ''
    raw = None
    resp = None
    used_model = None
    used_provider = provider

    if provider == 'jatevo':
        key = os.environ.get('JATEVO_API_KEY') or os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY') or ''
        base_url = (os.environ.get('JATEVO_BASE_URL') or os.environ.get('LLM_BASE_URL') or 'https://jatevo.ai/v1').rstrip('/')
        if not key:
            return {'status':'error','error':'missing_jatevo_key','reply':'Image generation is not configured.'}
        # Jatevo gpt-image-2 rejects tiny sizes; 1024x1024 is inside its valid pixel range.
        size = (data.get('size') or os.environ.get('JATEVO_IMAGE_SIZE') or os.environ.get('IMAGE_SIZE') or '1024x1024').strip()
        quality = (data.get('quality') or os.environ.get('JATEVO_IMAGE_QUALITY') or os.environ.get('IMAGE_QUALITY') or 'auto').strip()
        # Existing IMAGE_MODEL may be an OpenRouter slug (x-ai/...). Do not send that to Jatevo.
        if '/' in primary_model or not primary_model.startswith('gpt-image-'):
            primary_model = 'gpt-image-2'
        if '/' in fallback_model or not fallback_model.startswith('gpt-image-'):
            fallback_model = 'gpt-image-1'
        models_to_try = []
        for m in [primary_model, fallback_model]:
            if m and m not in models_to_try:
                models_to_try.append(m)
        def _decode_uploaded_image(value):
            if not value:
                return None, 'image.png', 'image/png'
            if isinstance(value, str) and value.startswith('data:image'):
                head, body = value.split(',', 1)
                mime = head.split(';', 1)[0].split(':', 1)[-1] or 'image/png'
                ext = 'jpg' if 'jpeg' in mime else (mime.split('/')[-1] or 'png')
                return base64.b64decode(body), 'source.' + ext, mime
            if isinstance(value, str):
                return base64.b64decode(value), 'source.png', 'image/png'
            return None, 'image.png', 'image/png'
        def _multipart_body(fields, files):
            import uuid
            boundary = '----GoldieImage' + uuid.uuid4().hex
            chunks = []
            for k, v in fields.items():
                chunks.append(('--' + boundary + '\r\nContent-Disposition: form-data; name="' + k + '"\r\n\r\n' + str(v) + '\r\n').encode('utf-8'))
            for k, f in files.items():
                filename, mime, content = f
                chunks.append(('--' + boundary + '\r\nContent-Disposition: form-data; name="' + k + '"; filename="' + filename + '"\r\nContent-Type: ' + mime + '\r\n\r\n').encode('utf-8') + content + b'\r\n')
            chunks.append(('--' + boundary + '--\r\n').encode('utf-8'))
            return boundary, b''.join(chunks)
        edit_raw, edit_filename, edit_mime = _decode_uploaded_image(image_data) if image_data else (None, '', '')
        if edit_raw:
            try:
                import io
                from PIL import Image, ImageOps
                im = ImageOps.exif_transpose(Image.open(io.BytesIO(edit_raw))).convert('RGB')
                w, h = im.size
                max_side = int(os.environ.get('JATEVO_EDIT_INPUT_MAX_SIDE') or '768')
                if max(w, h) > max_side:
                    ratio = float(max_side) / float(max(w, h))
                    im = im.resize((max(256, int(w * ratio)), max(256, int(h * ratio))), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, format='JPEG', quality=int(os.environ.get('JATEVO_EDIT_INPUT_QUALITY') or '86'), optimize=True, progressive=True)
                edit_raw, edit_filename, edit_mime = buf.getvalue(), 'source.jpg', 'image/jpeg'
            except Exception:
                pass
        # Jatevo image edits can hit Cloudflare 524 when the source/prompt is complex.
        # Try the faster fallback edit model first, then gpt-image-2, so users get an image instead of a 5-minute timeout.
        if edit_raw:
            ordered = []
            for m in [fallback_model, primary_model]:
                if m and m not in ordered:
                    ordered.append(m)
            models_to_try = ordered or models_to_try
        for model in models_to_try:
            if edit_raw:
                # OpenAI-compatible image editing requires multipart/form-data on /images/edits.
                # Sending image as JSON to /images/generations is accepted by some proxies but ignored by the model.
                fields = {'model': model, 'prompt': prompt, 'size': size, 'n': '1'}
                # Do not send quality=auto for edit requests; it can make upstream edits slower and is not required.
                boundary, body = _multipart_body(fields, {'image': (edit_filename, edit_mime, edit_raw)})
                req = urllib.request.Request(base_url + '/images/edits', data=body, method='POST')
                req.add_header('Content-Type','multipart/form-data; boundary=' + boundary)
            else:
                payload = {'model': model, 'prompt': prompt, 'size': size, 'n': 1}
                if quality:
                    payload['quality'] = quality
                req = urllib.request.Request(base_url + '/images/generations', data=json.dumps(payload).encode('utf-8'), method='POST')
                req.add_header('Content-Type','application/json')
            req.add_header('Authorization','Bearer ' + key)
            req.add_header('User-Agent','GoldieImage/Jatevo-gpt-image-2')
            try:
                with urllib.request.urlopen(req, timeout=480) as r:
                    resp = json.loads(r.read())
                item = (resp.get('data') or [{}])[0]
                b64 = item.get('b64_json') or item.get('base64') or item.get('image_base64') or ''
                url0 = item.get('url') or item.get('image_url') or ''
                if b64:
                    raw = base64.b64decode(b64.split(',',1)[-1])
                elif isinstance(url0, str) and url0.startswith('data:image'):
                    raw = base64.b64decode(url0.split(',',1)[1])
                elif isinstance(url0, str) and url0.startswith('http'):
                    with urllib.request.urlopen(urllib.request.Request(url0, headers={'User-Agent':'GoldieImage/Fetch'}), timeout=180) as rr:
                        raw = rr.read()
                if raw:
                    used_model = model
                    _record_llm_cost_usage(resp.get('usage', {}), model=used_model, provider='jatevo', phase='image_edit' if edit_raw else 'image_generation', source='api_image')
                    break
                last_error = 'Jatevo image endpoint returned no image bytes.'
            except urllib.error.HTTPError as e:
                last_error = e.read().decode(errors='replace')[:500]
                continue
            except Exception as e:
                last_error = str(e)[:300]
                continue
    else:
        key = os.environ.get('OPENROUTER_API_KEY','')
        if not key:
            return {'status':'error','error':'missing_openrouter_key','reply':'Image generation is not configured.'}
        models_to_try = []
        for m in [primary_model or 'x-ai/grok-imagine-image-quality', fallback_model]:
            if m and m not in models_to_try:
                models_to_try.append(m)
        if image_data:
            image_url = image_data if image_data.startswith('data:image') else 'data:image/png;base64,' + image_data
            content = [{'type':'text','text':prompt}, {'type':'image_url','image_url':{'url': image_url}}]
        else:
            content = prompt
        for model in models_to_try:
            payload = {'model': model, 'messages': [{'role':'user','content': content}], 'modalities': ['image']}
            req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions', data=json.dumps(payload).encode('utf-8'), method='POST')
            for k,v in {'Content-Type':'application/json','Authorization':'Bearer ' + key,'HTTP-Referer':'https://gitpup.fun','X-Title':'Goldie Image Chat','User-Agent':'GoldieImage/1.0'}.items():
                req.add_header(k,v)
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    resp = json.loads(r.read())
                raw = _extract_openrouter_image(resp)
                if raw:
                    used_model = model
                    used_provider = 'openrouter'
                    _record_llm_cost_usage(resp.get('usage', {}), model=used_model, provider='openrouter', phase='image_edit' if image_data else 'image_generation', source='api_image')
                    break
                text = ((resp.get('choices') or [{}])[0].get('message') or {}).get('content','')
                last_error = text[:500] or 'Image model did not return an image.'
            except Exception as e:
                last_error = str(e)[:300]
                continue
    if not raw:
        return {'status':'error','error':last_error or 'no_image_returned','reply':'Image model did not return an image.'}
    try:
        fname = 'goldie_%d.png' % int(time.time()*1000)
        out = '/opt/gitpup/web_dist/generated/' + fname
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'wb') as f:
            f.write(raw)
        size_bytes = os.path.getsize(out)
        url = '/generated/' + os.path.basename(out)
        mode = 'edit' if image_data else 'generate'
        if data.get('chat_log', True):
            _CHAT_CONTEXT.setdefault('image|' + user_key, []).append({'role':'user','text':('[image edit prompt] ' if mode == 'edit' else '[image prompt] ') + prompt,'ts':time.time()})
            _CHAT_CONTEXT.setdefault('image|' + user_key, []).append({'role':'assistant','text':('[edited image] ' if mode == 'edit' else '[generated image] ') + url,'ts':time.time()})
        return {'status':'ok','reply':'Image edited.' if mode == 'edit' else 'Image generated.','mode':mode,'image_url':url,'size_bytes':size_bytes,'model':used_model,'provider':used_provider,'requested_model':primary_model,'fallback_model':fallback_model,'limit':'1/5 minutes','output_size':data.get('size') or os.environ.get('JATEVO_IMAGE_SIZE') or os.environ.get('IMAGE_SIZE') or '1024x1024'}
    except Exception as e:
        return {'status':'error','error':str(e)[:300],'reply':'Image generation failed: ' + str(e)[:180]}


def _handle_image(self, data):
    user_key = data.get('session') or data.get('user') or 'anonymous'
    if not _image_rate_ok(self, user_key=user_key, limit=1, window=300):
        return _json_resp(self, {'status':'error','error':'image_rate_limited','reply':'Image rate limit exceeded. Please wait a moment — maximum 1 image every 5 minutes per user/IP.','limit':'1/5 minutes'}, 429)
    if data.get('async') or data.get('background'):
        return _handle_image_async(self, data)
    result = _handle_image_result(data)
    if result.get('status') == 'ok':
        return _json_resp(self, result)
    _image_rate_refund(self, user_key)
    code = 400 if result.get('error') in ('missing_prompt',) else 502
    return _json_resp(self, result, code)


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
    audio_b64 = None; used_model = model; err = ''; usage = {}
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
                    if obj.get('usage'): usage = obj.get('usage') or usage
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
        _record_llm_cost_usage(usage, model=used_model, provider='openrouter', phase='song_generation', source='api_song')
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
            normalized_p == '/api/image/job' or
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


# Goldie real LLM cost tracking shared helpers. Prices are USD per 1M tokens.
def _openrouter_model_prices():
    import os, json, time, urllib.request
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cache', 'openrouter_model_prices.json')
    now = time.time()
    try:
        if os.path.exists(cache) and now - os.path.getmtime(cache) < 86400:
            return json.load(open(cache, encoding='utf-8'))
    except Exception:
        pass
    prices = {}
    try:
        req = urllib.request.Request('https://openrouter.ai/api/v1/models', headers={'User-Agent':'GoldieCostTracker/1.0'})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        for m in data.get('data', []):
            mid = m.get('id') or ''
            pr = m.get('pricing') or {}
            if mid:
                prices[mid] = pr
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(prices, f)
    except Exception:
        pass
    return prices


def _model_aliases(model):
    m = (model or '').strip()
    aliases = [m]
    if '/' not in m:
        aliases.append('openai/' + m)
    fixed = {
        'gpt-5.5': 'openai/gpt-5.5',
        'gpt-5.5-pro': 'openai/gpt-5.5-pro',
        'gpt-5.3-codex-spark': 'openai/gpt-5.3-codex',
        'gpt-5.3-codex': 'openai/gpt-5.3-codex',
        'gpt-5.3-chat': 'openai/gpt-5.3-chat',
        'inclusionai/ling-2.6-flash': 'inclusionai/ling-2.6-flash',
        'google/lyria-3-pro-preview': 'google/lyria-3-pro-preview',
        'x-ai/grok-imagine-image-quality': 'x-ai/grok-imagine-image-quality',
    }
    if m in fixed:
        aliases.insert(0, fixed[m])
    # de-dupe preserving order
    out=[]
    for a in aliases:
        if a and a not in out: out.append(a)
    return out



def _manual_price_overrides_per_m(model):
    # Conservative Jatevo overrides. Jatevo gpt-5.5 is the expensive quality tier,
    # so do not use the cheaper OpenRouter public gpt-5.5 row for accounting.
    m = (model or '').strip().lower()
    overrides = {
        'gpt-5.5': (30.0, 180.0, 'manual_jatevo:gpt-5.5'),
        'openai/gpt-5.5': (30.0, 180.0, 'manual_jatevo:gpt-5.5'),
        'gpt-5.5-pro': (30.0, 180.0, 'manual_jatevo:gpt-5.5-pro'),
        'openai/gpt-5.5-pro': (30.0, 180.0, 'manual_jatevo:gpt-5.5-pro'),
    }
    return overrides.get(m)

def _cost_price_for_model(model):
    import os, re
    m = (model or '').strip()
    slug = re.sub(r'[^A-Za-z0-9]+', '_', m).strip('_').upper()
    def _env_float(name, default=None):
        try:
            v = os.environ.get(name)
            if v is None or v == '': return default
            return float(v)
        except Exception:
            return default
    if slug:
        inp = _env_float('LLM_PRICE_' + slug + '_INPUT_PER_M')
        out = _env_float('LLM_PRICE_' + slug + '_OUTPUT_PER_M')
        if inp is not None and out is not None:
            return inp, out, 'env_model_price'
    manual_price = _manual_price_overrides_per_m(m)
    if manual_price is not None:
        return manual_price
    prices = _openrouter_model_prices()
    for alias in _model_aliases(m):
        pr = prices.get(alias)
        if pr:
            try:
                # OpenRouter pricing is USD per token. Convert to USD per 1M tokens.
                return float(pr.get('prompt') or 0) * 1000000.0, float(pr.get('completion') or 0) * 1000000.0, 'openrouter_models:' + alias
            except Exception:
                pass
    return _env_float('LLM_DEFAULT_INPUT_PER_M', 0.01), _env_float('LLM_DEFAULT_OUTPUT_PER_M', 0.03), 'default_price_unmatched_model'


def _record_llm_cost_usage(usage, model='', provider='', phase='unknown', source='unknown'):
    try:
        import os, json, time
        if not isinstance(usage, dict): return None
        prompt_t = int(usage.get('prompt_tokens') or usage.get('input_tokens') or 0)
        completion_t = int(usage.get('completion_tokens') or usage.get('output_tokens') or 0)
        total_t = int(usage.get('total_tokens') or (prompt_t + completion_t) or 0)
        provider_cost = usage.get('cost') or usage.get('total_cost') or usage.get('cost_usd')
        inp_per_m, out_per_m, price_source = _cost_price_for_model(model)
        if provider_cost is not None:
            cost = float(provider_cost)
            price_source = 'provider_usage_cost'
        else:
            if total_t <= 0: return None
            cost = (prompt_t * inp_per_m + completion_t * out_per_m) / 1000000.0
        root = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(root, 'data', 'journal', 'cost_tracking.jsonl')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        entry = {
            'ts': time.time(), 'date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'phase': phase or 'unknown', 'source': source,
            'provider': provider or '', 'model': model or '',
            'prompt_tokens': prompt_t, 'completion_tokens': completion_t, 'total_tokens': total_t,
            'input_cost_per_m': inp_per_m, 'output_cost_per_m': out_per_m,
            'price_source': price_source, 'cost_usd': round(cost, 8),
        }
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        try:
            sf = os.path.join(root, 'data', 'state', 'status.json')
            st = json.load(open(sf, encoding='utf-8')) if os.path.exists(sf) else {}
            st['cumulative_cost_usd'] = round(float(st.get('cumulative_cost_usd', 0) or 0) + cost, 8)
            with open(sf, 'w', encoding='utf-8') as f:
                json.dump(st, f, indent=2)
        except Exception:
            pass
        return entry
    except Exception:
        return None
def _cli_call_llm(prompt, system, tokens=500, temp=0.25):
    import urllib.request, time
    key = os.environ.get('CLI_LLM_API_KEY') or os.environ.get('LLM_API_KEY') or os.environ.get('JATEVO_API_KEY')
    if not key:
        return '[LLM Error: missing CLI/Jatevo API key]'
    models=[]
    for m in [
        os.environ.get('CLI_LLM_MODEL') or CLI_LLM_MODEL,
        os.environ.get('CLI_LLM_FALLBACK_MODEL'),
        os.environ.get('LLM_MODEL_SPEED'),
        os.environ.get('LLM_MODEL')
    ]:
        if m and m not in models:
            models.append(m)
    if not models:
        models=[CLI_LLM_MODEL]
    wants_json = 'ONLY valid JSON' in (system or '') or 'JSON shape' in (system or '')
    last_detail='unknown error'
    for model in models:
        for attempt in range(3):
            prompt_limit = 4000 if attempt == 0 else (2800 if attempt == 1 else 1800)
            max_tokens = int(tokens if attempt == 0 else max(900, min(tokens, 2600 if attempt == 1 else 1800)))
            payload = {
                'model': model,
                'messages': [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': prompt[:prompt_limit]},
                ],
                'max_tokens': max_tokens,
                'temperature': temp,
            }
            if wants_json and attempt < 2:
                payload['response_format'] = {'type': 'json_object'}
            req = urllib.request.Request(CLI_LLM_BASE_URL + '/chat/completions', json.dumps(payload).encode())
            req.add_header('Content-Type', 'application/json')
            req.add_header('Authorization', 'Bearer ' + key)
            req.add_header('User-Agent', 'GoldieCLIWorkspace/1.0')
            req.add_header('HTTP-Referer', 'https://gitpup.fun')
            req.add_header('X-Title', 'GitPup Goldie CLI Workspace')
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    resp = json.loads(r.read())
                    _record_llm_cost_usage(resp.get('usage', {}), model=model, provider=CLI_LLM_PROVIDER, phase='cli_workspace', source='api_cli')
                    content = resp.get('choices', [{}])[0].get('message', {}).get('content', '')
                    if content:
                        return content
                    last_detail = 'empty model response'
            except Exception as e:
                detail = str(e)[:120]
                try:
                    if hasattr(e, 'read'):
                        detail = e.read().decode('utf-8', errors='replace')[:260]
                except Exception:
                    pass
                last_detail = detail
                # 502/503/504/timeouts are usually transient or JSON-mode overload; retry with smaller prompt/model.
                if any(x in detail.lower() for x in ['502','503','504','timed out','timeout','bad gateway','service unavailable']):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
    return '[LLM Error: ' + last_detail + ']'


def _cli_session_id(handler, data=None):
    key = _cli_user_key(handler, data)
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:18]


def _cli_signing_secret():
    secret = (os.environ.get('GOLDIE_CLI_SIGNING_SECRET') or os.environ.get('SECRET_KEY') or os.environ.get('OPENROUTER_API_KEY') or '').strip()
    if not secret:
        secret = 'goldie-local-dev-' + os.path.realpath(GITPUP)
    return secret.encode('utf-8')


def _cli_sign_token(sid, purpose, rel='', ttl=900):
    exp = int(time.time()) + int(ttl or 900)
    rel = (rel or '').replace('\\', '/')
    msg = '%s|%s|%s|%s' % (sid, purpose, rel, exp)
    sig = hmac.new(_cli_signing_secret(), msg.encode('utf-8'), hashlib.sha256).hexdigest()[:32]
    return '%s.%s' % (exp, sig)


def _cli_verify_token(sid, purpose, rel, token):
    try:
        exp_s, sig = str(token or '').split('.', 1)
        exp = int(exp_s)
        if exp < int(time.time()):
            return False
        rel = (rel or '').replace('\\', '/')
        msg = '%s|%s|%s|%s' % (sid, purpose, rel, exp)
        expected = hmac.new(_cli_signing_secret(), msg.encode('utf-8'), hashlib.sha256).hexdigest()[:32]
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


def _cli_signed_preview_url(sid, rel, mtime=None):
    rel = (rel or 'index.html').replace('\\', '/')
    token = _cli_sign_token(sid, 'preview', rel, ttl=1800)
    return '/preview/' + urllib.parse.quote(sid) + '/' + urllib.parse.quote(rel) + '?v=' + str(mtime or int(time.time())) + '&token=' + urllib.parse.quote(token)


def _cli_signed_download_url(sid):
    token = _cli_sign_token(sid, 'download', '', ttl=900)
    return '/api/cli/download?session=' + urllib.parse.quote(sid) + '&token=' + urllib.parse.quote(token)


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



CLI_SKILL_HOOKS_FILE = os.path.join(DATA, "cli_skill_hooks.json")

def _cli_skill_hook_query(message, limit=5):
    try:
        with open(CLI_SKILL_HOOKS_FILE, encoding="utf-8") as fh:
            reg = json.load(fh)
        hooks = reg.get("hooks", []) if isinstance(reg, dict) else []
    except Exception:
        return []
    text = (message or "").lower()
    q = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{2,}", text))
    scored=[]
    for h in hooks:
        kws = set(h.get("keywords") or [])
        domains = set(h.get("applies_to") or [])
        score = len(q & kws) * 3 + len(q & domains) * 2
        if any(d in text for d in domains): score += 2
        if h.get("source_repo") and any(part.lower() in text for part in str(h.get("source_repo")).split('/')): score += 2
        if score > 0:
            scored.append((score, h))
    scored.sort(key=lambda x: (x[0], x[1].get("study_level",0)), reverse=True)
    return [h for _, h in scored[:limit]]

def _cli_skill_hook_context(message, limit=5):
    hooks = _cli_skill_hook_query(message, limit)
    if not hooks:
        return ""
    lines = ["CLI SKILL HOOKS (learned from Goldie repo study; apply when relevant, never override exact user request):"]
    for h in hooks:
        lines.append("- {name} from {repo} L{lvl}: {summary}".format(
            name=(h.get("name") or h.get("id"))[:80], repo=h.get("source_repo","repo"), lvl=h.get("study_level",0), summary=(h.get("summary") or "")[:220]))
        if h.get("actions"):
            lines.append("  actions: " + ", ".join(h.get("actions")[:5]))
        if h.get("validators"):
            lines.append("  validators: " + ", ".join(h.get("validators")[:5]))
    return "\n".join(lines)


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
    target_words = [
        'landing', 'website', 'web', 'page', 'html', 'app', 'aplikasi', 'portfolio', 'todo',
        'game', 'browser', 'canvas', 'snake', 'quiz', 'arcade',
        'backend', 'api', 'rest', 'server', 'endpoint', 'route', 'fastapi', 'express', 'flask',
        'crud', 'database', 'dashboard', 'admin', 'auth', 'login', 'realtime', 'websocket', 'payment'
    ]
    return any(w in t for w in build_words) and any(w in t for w in target_words)

def _cli_template_for_prompt(msg):
    raise RuntimeError('Templates are disabled. CLI builds must come from the exact user request via LLM + Goldie KB + Hermes tools.')

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
    raise RuntimeError('Local/default website templates are disabled. Use the request-driven LLM writer only.')

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


def _cli_is_public_http_url(raw):
    try:
        import socket, ipaddress
        u = urllib.parse.urlparse((raw or '').strip())
        if u.scheme not in ('http', 'https') or not u.netloc:
            return False, 'only http/https URLs are allowed'
        host = (u.hostname or '').strip()
        if not host:
            return False, 'missing URL host'
        if host.lower() in ('localhost', 'local') or host.endswith('.local'):
            return False, 'local hosts are blocked'
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                ip = ipaddress.ip_address(info[4][0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                    return False, 'private/internal network URLs are blocked'
        except Exception:
            return False, 'could not resolve URL host safely'
        return True, ''
    except Exception as e:
        return False, str(e)[:120]


def _cli_fetch_url_bytes(url, max_bytes=900000, timeout=12):
    import tempfile, subprocess
    cur = (url or '').strip()
    for _ in range(4):
        ok, err = _cli_is_public_http_url(cur)
        if not ok:
            raise ValueError(err)
        head_cmd = ['curl','-4','-sS','-I','--max-time',str(int(timeout)),'--max-redirs','0',cur]
        hr = subprocess.run(head_cmd, capture_output=True, text=True, timeout=int(timeout)+3)
        headers = (hr.stdout or '') + (hr.stderr or '')
        status = 0
        first = headers.splitlines()[0] if headers.splitlines() else ''
        try: status = int(first.split()[1])
        except Exception: status = 0
        if status in (301,302,303,307,308):
            loc = ''
            for line in headers.splitlines():
                if line.lower().startswith('location:'):
                    loc = line.split(':',1)[1].strip(); break
            if not loc: break
            cur = urllib.parse.urljoin(cur, loc)
            continue
        break
    ok, err = _cli_is_public_http_url(cur)
    if not ok:
        raise ValueError(err)
    fd, tmp = tempfile.mkstemp(prefix='goldie-urlscan-', suffix='.bin')
    os.close(fd)
    try:
        cmd = ['curl','-4','-sS','--max-time',str(int(timeout)),'--range','0-%d' % max(0, max_bytes-1),'-L','--max-redirs','0','-H','User-Agent: GoldieCLI-URLScanner/1.0 (+https://gitpup.fun)','-w','\n%{content_type}\n%{url_effective}\n','-o',tmp,cur]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=int(timeout)+5)
        if r.returncode != 0:
            raise ValueError('URL fetch failed: ' + ((r.stderr or r.stdout or '')[:160]))
        lines = (r.stdout or '').strip().splitlines()
        ctype = (lines[-2] if len(lines) >= 2 else '').split(';')[0].strip().lower()
        final_url = lines[-1].strip() if lines else cur
        ok2, err2 = _cli_is_public_http_url(final_url)
        if not ok2:
            raise ValueError('redirect blocked: ' + err2)
        with open(tmp, 'rb') as f:
            data = f.read(max_bytes)
        return data, ctype, final_url
    finally:
        try: os.remove(tmp)
        except Exception: pass


def _cli_html_text_excerpt(html, limit=6000):
    import re, html as _html
    t = re.sub(r'(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>', ' ', html or '')
    t = re.sub(r'(?is)<br\s*/?>', '\n', t)
    t = re.sub(r'(?is)</(p|div|section|article|header|footer|h[1-6]|li)>', '\n', t)
    t = re.sub(r'(?is)<[^>]+>', ' ', t)
    t = _html.unescape(t)
    t = re.sub(r'[ \t\r\f\v]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n', t).strip()
    return t[:limit]


def _cli_extract_url_reference(html, base_url):
    import re, html as _html
    text = html or ''
    def clean(x):
        return _html.unescape(re.sub(r'\s+', ' ', (x or '').strip()))[:500]
    title = ''
    m = re.search(r'(?is)<title[^>]*>(.*?)</title>', text)
    if m: title = clean(re.sub(r'<[^>]+>', ' ', m.group(1)))
    metas = {}
    for m in re.finditer(r'(?is)<meta\s+([^>]+)>', text):
        attrs = dict((k.lower(), v) for k,_,v in re.findall(r'([a-zA-Z_:.-]+)\s*=\s*(["\'])(.*?)\2', m.group(1)))
        key = attrs.get('name') or attrs.get('property')
        val = attrs.get('content')
        if key and val and key.lower() in ('description','keywords','og:title','og:description','twitter:title','twitter:description'):
            metas[key.lower()] = clean(val)
    headings=[]
    for tag, body in re.findall(r'(?is)<(h[1-3])[^>]*>(.*?)</\1>', text)[:40]:
        val = clean(re.sub(r'<[^>]+>', ' ', body))
        if val: headings.append({'level': tag.lower(), 'text': val[:220]})
    assets=[]
    seen=set()
    patterns = [
        ('img', r'(?is)<img[^>]+(?:src|data-src)\s*=\s*(["\'])(.*?)\1'),
        ('css', r'(?is)<link[^>]+href\s*=\s*(["\'])(.*?)\1'),
        ('js', r'(?is)<script[^>]+src\s*=\s*(["\'])(.*?)\1'),
        ('media', r'(?is)<source[^>]+src\s*=\s*(["\'])(.*?)\1'),
    ]
    for typ, pat in patterns:
        for _, raw in re.findall(pat, text):
            url = urllib.parse.urljoin(base_url, raw.strip())
            if not url.startswith(('http://','https://')) or url in seen: continue
            if typ == 'css' and '.css' not in urllib.parse.urlparse(url).path.lower(): continue
            seen.add(url); assets.append({'type': typ, 'url': url})
            if len(assets) >= 40: break
    colors=[]
    for c in re.findall(r'#[0-9a-fA-F]{3,8}\b|rgba?\([^\)]+\)', text)[:80]:
        if c not in colors: colors.append(c)
    return {'title': title, 'meta': metas, 'headings': headings[:30], 'assets': assets, 'colors': colors[:30], 'text_excerpt': _cli_html_text_excerpt(text)}


def _cli_asset_filename(asset_url, idx, ctype=''):
    import re
    up = urllib.parse.urlparse(asset_url)
    name = os.path.basename(up.path) or ('asset-%02d' % idx)
    name = urllib.parse.unquote(name).split('?')[0]
    name = re.sub(r'[^A-Za-z0-9._-]+', '-', name).strip('-._')[:80] or ('asset-%02d' % idx)
    if '.' not in name:
        ext = ''
        if 'png' in ctype: ext = '.png'
        elif 'jpeg' in ctype or 'jpg' in ctype: ext = '.jpg'
        elif 'webp' in ctype: ext = '.webp'
        elif 'gif' in ctype: ext = '.gif'
        elif 'css' in ctype: ext = '.css'
        elif 'javascript' in ctype: ext = '.js'
        name += ext
    return name


def _cli_download_reference_assets(workspace, ref_dir, assets, max_assets=14):
    saved=[]
    allowed_types = ('image/', 'text/css', 'application/javascript', 'text/javascript')
    for i, asset in enumerate((assets or [])[:40], 1):
        if len(saved) >= max_assets: break
        url = asset.get('url') or ''
        try:
            data, ctype, final_url = _cli_fetch_url_bytes(url, max_bytes=350000, timeout=8)
            if not (ctype.startswith('image/') or ctype in allowed_types or ctype.endswith('javascript')):
                continue
            name = _cli_asset_filename(final_url, i, ctype)
            subdir = 'images' if ctype.startswith('image/') else ('css' if 'css' in ctype else 'js')
            rel = ('references/%s/assets/%s/%s' % (ref_dir, subdir, name)).replace('//','/')
            path = _cli_safe_path(workspace, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f: f.write(data)
            saved.append({'type': asset.get('type'), 'url': final_url, 'content_type': ctype, 'path': rel, 'bytes': len(data)})
        except Exception:
            continue
    return saved


def _cli_scan_url_reference(handler, data, sid=None, workspace=None, msg=''):
    import re
    sid = sid or _cli_session_id(handler, data)
    workspace = workspace or _cli_workspace(handler, data)[1]
    raw = (data.get('url') or '').strip()
    source = msg or raw or (data.get('message') or '')
    if not raw:
        m = re.search(r'https?://[^\s<>"\']+', source)
        if m: raw = m.group(0).rstrip('.,;)')
    if not raw:
        raise ValueError('Format: /scan https://example.com [what assets/data you want]')
    html_bytes, ctype, final_url = _cli_fetch_url_bytes(raw, max_bytes=1200000, timeout=14)
    if 'html' not in ctype and 'xml' not in ctype and ctype not in ('text/plain',''):
        raise ValueError('URL must return HTML/text for reference scan, got ' + (ctype or 'unknown'))
    html = html_bytes.decode('utf-8', errors='replace')
    ref = _cli_extract_url_reference(html, final_url)
    host = urllib.parse.urlparse(final_url).netloc.lower().replace(':','-')
    ref_dir = _cli_slug(host)[:40]
    saved_assets = _cli_download_reference_assets(workspace, ref_dir, ref.get('assets', []), max_assets=14)
    ref['url'] = final_url
    ref['requested'] = source[:800]
    ref['saved_assets'] = saved_assets
    ref['scanned_at'] = time.time()
    scan_rel = 'references/%s/scan.json' % ref_dir
    md_rel = 'references/%s/reference.md' % ref_dir
    os.makedirs(os.path.dirname(_cli_safe_path(workspace, scan_rel)), exist_ok=True)
    _pathlib_cli.Path(_cli_safe_path(workspace, scan_rel)).write_text(json.dumps(ref, indent=2, ensure_ascii=False), encoding='utf-8')
    md = []
    md.append('# URL Reference: ' + (ref.get('title') or host))
    md.append('')
    md.append('Source: ' + final_url)
    md.append('')
    if ref.get('meta'):
        md.append('## Meta')
        for k,v in ref['meta'].items(): md.append('- %s: %s' % (k, v))
        md.append('')
    if ref.get('headings'):
        md.append('## Structure')
        for h in ref['headings'][:20]: md.append('- %s: %s' % (h.get('level'), h.get('text')))
        md.append('')
    if ref.get('colors'):
        md.append('## Detected Colors')
        md.append(', '.join(ref['colors'][:24])); md.append('')
    if saved_assets:
        md.append('## Saved Assets')
        for a in saved_assets: md.append('- `%s` <- %s' % (a.get('path'), a.get('url')))
        md.append('')
    md.append('## Text Excerpt')
    md.append(ref.get('text_excerpt','')[:5000])
    _pathlib_cli.Path(_cli_safe_path(workspace, md_rel)).write_text('\n'.join(md), encoding='utf-8')
    _cli_append_memory(sid, 'system', 'URL reference scanned: %s -> %s, %s assets saved' % (final_url, md_rel, len(saved_assets)))
    return {'status':'ok','url':final_url,'reference_dir':'references/'+ref_dir,'reference_file':md_rel,'scan_file':scan_rel,'assets_saved':len(saved_assets),'assets':saved_assets[:14],'title':ref.get('title'),'headings_count':len(ref.get('headings') or []),'colors':ref.get('colors')[:12]}


def _cli_reference_context(workspace, limit=3):
    try:
        refs=[]
        base=_cli_safe_path(workspace, 'references')
        if not os.path.isdir(base): return ''
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('assets',)]
            for name in files:
                if name == 'reference.md':
                    path=os.path.join(root,name)
                    refs.append((os.path.getmtime(path), path))
        refs=sorted(refs, reverse=True)[:limit]
        chunks=[]
        for _, path in refs:
            rel=os.path.relpath(path, workspace).replace(os.sep,'/')
            txt=_pathlib_cli.Path(path).read_text(encoding='utf-8', errors='replace')[:4000]
            chunks.append('REFERENCE FILE: %s\n%s' % (rel, txt))
        return '\n\n'.join(chunks)
    except Exception:
        return ''


def _cli_is_game_command(msg):
    t = (msg or '').lower()
    return any(w in t for w in [
        'game','permainan','playable','dimainkan','snake','pong','quiz','arcade','canvas','browser game','web game',
        'shooter','spaceship','asteroid','platformer','runner','racing','balap','tetris','flappy','puzzle','rpg','roguelike',
        'tower defense','clicker','idle','combat','battle','laser','enemy','enemies','boss fight'
    ])


def _cli_validate_playable_game(files):
    html = ''
    for f in files or []:
        if isinstance(f, dict) and str(f.get('path','')).lower().endswith('.html'):
            html += '\n' + str(f.get('content',''))
    low = html.lower()
    checks = {
        'html': '<html' in low or '<!doctype' in low,
        'not_plain_text': len(low) > 3500 and ('<style' in low or 'stylesheet' in low) and ('<script' in low or '.js' in low),
        'canvas_or_dom_playfield': '<canvas' in low or 'game-board' in low or 'playfield' in low or 'arena' in low,
        'input_controls': 'addeventlistener' in low and any(x in low for x in ['keydown','keyup','touchstart','touchmove','pointerdown','pointermove','click']),
        'mobile_controls': any(x in low for x in ['touchstart','pointerdown','touch-controls','mobile-controls','ontouch','touchmove','button']),
        'game_loop': any(x in low for x in ['requestanimationframe','setinterval(','settimeout(']),
        'score_state': 'score' in low and any(x in low for x in ['let score','score =','score++','score +=','score+=','scoreboard','scoreel.textcontent']),
        'restart_or_start': any(x in low for x in ['restart','startgame','resetgame','gameover','play again','main lagi','newgame']),
        'rules_or_collision': any(x in low for x in ['collision','collide','hitbox','intersect','distance','rect','bounds','winner','lose','lives','health']),
    }
    return all(checks.values()), checks


def _cli_snake_game_files(msg):
    raise RuntimeError('Hardcoded game templates are disabled. Use the request-driven LLM writer only.')

def _cli_game_theme_terms(msg):
    t = (msg or '').lower()
    if any(w in t for w in ['spaceship','space ship','space-shooter','space shooter','space','pesawat luar angkasa','kapal luar angkasa','rocket','roket']):
        return ['spaceship','space','ship','rocket','asteroid','laser','alien','star']
    if 'snake' in t or 'ular' in t:
        return ['snake','food','fruit','grid']
    if any(w in t for w in ['mancing','fishing','ikan','fish','rod','pancing','hook','umpan','bait']):
        return ['fishing','fish','ikan','rod','hook','bait','catch','mancing']
    if 'pong' in t:
        return ['pong','paddle','ball']
    if 'quiz' in t:
        return ['quiz','question','answer']
    return []




def _cli_request_terms(msg):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", (msg or "").lower())
    stop=set("buatkan build create generate with yang untuk agar bisa from this that playable browser mini app web page website dalam dan the user into dari sebuah simple".split())
    out=[]
    for w in words:
        if w not in stop and w not in out:
            out.append(w)
    return out[:14]

def _cli_all_generated_text(files):
    return '\n'.join(str(f.get('content','')) for f in (files or []) if isinstance(f, dict)).lower()

def _cli_validate_domain_build(msg, files, hooks=None):
    text = _cli_all_generated_text(files)
    paths = [str(f.get('path','')).lower() for f in (files or []) if isinstance(f, dict)]
    t=(msg or '').lower()
    checks={
        'has_writable_files': bool(files),
        'has_index_or_source': any(p.endswith(('.html','.js','.ts','.py','.css','.md','.json')) for p in paths),
        'request_terms_present': True,
        'no_obvious_template_markers': not any(x in text for x in ['goldie static landing','todo static app','lorem ipsum','template fallback','snake game template','hello world example']),
    }
    terms=[w for w in _cli_request_terms(msg) if w not in ('game','website','dashboard','landing','browser','responsive','backend','server','api','application','aplikasi')]
    if terms:
        checks['request_terms_present'] = any(term in text for term in terms[:8])

    wants_landing = any(w in t for w in ['landing','landingpage','company profile','profile company','perkebunan','sawit','cpo','brand page','marketing page'])
    wants_dashboard = any(w in t for w in ['dashboard','chart','analytics','trading','admin','saas','kpi','metric'])
    wants_backend = any(w in t for w in ['api','backend','server','endpoint','route','fastapi','express','flask','rest api','graphql'])
    wants_auth = any(w in t for w in ['auth','login','register','token','oauth','password','secret','session'])
    wants_db = any(w in t for w in ['database','db','sqlite','postgres','mysql','schema','model','crud','supabase','prisma'])
    wants_realtime = any(w in t for w in ['realtime','real-time','websocket','socket.io','sse','eventsource','live chat'])
    wants_payment = any(w in t for w in ['payment','stripe','checkout','invoice','billing','x402','wallet'])
    wants_app = any(w in t for w in ['app','aplikasi','todo','crud','form','calculator','notes','kanban','ecommerce','shop','inventory','tracker','manager']) and not wants_backend
    wants_web_ui = wants_landing or wants_dashboard or wants_app or any(w in t for w in ['website','frontend','ui','web app','single page'])

    if wants_web_ui:
        checks.update({
            'visual_styling': any(x in text for x in ['<style', 'stylesheet', 'background:', 'linear-gradient', 'box-shadow', 'border-radius', 'font-family', 'display: grid', 'display:flex', 'class=']),
            'not_plain_text': ('<html' in text or '<!doctype' in text) and '<body' in text and len(text) > 2500,
            'responsive_ui': any(x in text for x in ['@media','grid-template','flex','viewport','max-width','minmax(']),
        })
    if wants_landing:
        checks['landing_sections'] = sum(1 for x in ['hero','about','benefit','process','produk','product','contact','cta','section','nav','footer'] if x in text) >= 4
    if wants_dashboard:
        checks.update({
            'dashboard_structure': any(x in text for x in ['dashboard','chart','metric','card','analytics','kpi','trading','table','summary']),
            'dashboard_data_state': any(x in text for x in ['const data','let data','dataset','array','json','canvas','svg','chart']),
        })
    if wants_app:
        checks.update({
            'app_interactivity': 'addeventlistener' in text or any(x in text for x in ['onclick','onsubmit','onchange','addtask','save','render']),
            'app_state': any(x in text for x in ['let ','const ','localstorage','state','items','tasks','cart','list','array','object']),
            'app_forms_or_controls': any(x in text for x in ['<form','<input','<button','select','textarea','contenteditable']),
        })
    if wants_backend:
        checks.update({
            'backend_source_file': any(p.endswith(('.py','.js','.ts')) for p in paths),
            'api_structure': any(x in text for x in ['fastapi','flask','express','http.server','app.get','app.post','@app.get','@app.post','router.','create_server','createserver','route','endpoint']),
            'http_methods': (any(x in text for x in ['get','post','put','delete','patch']) and any(x in text for x in ['/api','/health','/items','/users','/todos','/products','/inventory'])) or any(x in text for x in ['@app.get','@app.post','@app.put','@app.delete','app.get','app.post','app.put','app.delete']),
            'json_handling': any(x in text for x in ['jsonify','jsonresponse','response.json','res.json','json.dumps','application/json','body-parser','express.json']),
            'error_handling': any(x in text for x in ['try','catch','except','raise httpexception','status_code','res.status','error']),
            'runnable_entry': any(x in text for x in ['if __name__','uvicorn','app.listen','serve_forever','npm start','main()']),
        })
    if wants_auth:
        checks.update({
            'auth_ui_or_flow': any(x in text for x in ['login','register','token','auth','password','session','oauth','jwt','bcrypt','hash']),
            'no_hardcoded_secret': not any(x in text for x in ['sk-','ghp_','private key','api_key = "','password = "','secret = "changeme"','jwt_secret = "']),
        })
    if wants_db:
        checks.update({
            'database_layer': any(x in text for x in ['sqlite','postgres','mysql','database','schema','create table','prisma','sqlalchemy','model','db.','connection','query','inventory =','items =','store =','in_memory','in-memory','dict','list[']),
            'crud_operations': any(x in text for x in ['create','insert','add']) and any(x in text for x in ['read','select','list','get']) and any(x in text for x in ['update','edit','put','patch']) and any(x in text for x in ['delete','remove']),
        })
    if wants_realtime:
        checks['realtime_transport'] = any(x in text for x in ['websocket','socket.io','eventsource','sse','server-sent','broadcast','ws://'])
    if wants_payment:
        checks.update({
            'payment_flow': any(x in text for x in ['checkout','payment','invoice','billing','stripe','x402','wallet','webhook']),
            'no_payment_secret_inline': not any(x in text for x in ['sk_live','sk_test_','stripe_secret_key = "','private_key','api_key = "']),
            'payment_safety_note': any(x in text for x in ['test mode','sandbox','webhook','server-side','never expose','environment variable','env']),
        })
    if hooks:
        validators=[]
        for h in hooks:
            validators += list(h.get('validators') or [])
        if validators:
            checks['hook_validators_present'] = True
    return all(checks.values()), checks

def _cli_post_build_verify(workspace, msg, written, preview_payload=None):
    proof={'files_exist': True, 'syntax': {}, 'preview_url': bool((preview_payload or {}).get('preview_url')), 'issues': []}
    for rel in written or []:
        try:
            path=_cli_safe_path(workspace, rel)
            if not os.path.exists(path):
                proof['files_exist']=False; proof['issues'].append('missing:'+rel); continue
            if rel.endswith('.py'):
                r=subprocess.run(['python3','-m','py_compile',path],cwd=workspace,env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':workspace,'PWD':workspace},text=True,capture_output=True,timeout=12)
                proof['syntax'][rel]=(r.returncode==0)
                if r.returncode!=0: proof['issues'].append('py_compile:'+rel+':'+(r.stderr or r.stdout)[:160])
            elif rel.endswith('.js'):
                node = subprocess.run(['bash','-lc','command -v node >/dev/null 2>&1'],capture_output=True,text=True,timeout=5)
                if node.returncode==0:
                    r=subprocess.run(['node','--check',path],cwd=workspace,env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':workspace,'PWD':workspace},text=True,capture_output=True,timeout=12)
                    proof['syntax'][rel]=(r.returncode==0)
                    if r.returncode!=0: proof['issues'].append('node_check:'+rel+':'+(r.stderr or r.stdout)[:160])
            elif rel.endswith('.html'):
                raw=open(path,encoding='utf-8',errors='ignore').read().lower()
                ok=('<html' in raw or '<!doctype' in raw) and ('</html>' in raw or '</body>' in raw)
                rich = len(raw) > 2500 and ('<style' in raw or 'stylesheet' in raw) and ('<section' in raw or 'class=' in raw)
                proof['syntax'][rel]=ok and rich
                if not ok: proof['issues'].append('html_structure:'+rel)
                if ok and not rich: proof['issues'].append('html_too_plain_or_unstyled:'+rel)
            elif rel.endswith('.json'):
                try:
                    json.loads(open(path,encoding='utf-8',errors='ignore').read())
                    proof['syntax'][rel]=True
                except Exception as e:
                    proof['syntax'][rel]=False; proof['issues'].append('json_parse:'+rel+':'+str(e)[:120])
        except Exception as e:
            proof['issues'].append('verify:'+rel+':'+str(e)[:120])
    proof['ok']=proof['files_exist'] and all(proof['syntax'].values() or [True]) and not proof['issues']
    return proof

def _cli_repair_game_files_with_llm(msg, memory_text='', kb_text='', failed_checks=None):
    theme_terms = ', '.join(_cli_game_theme_terms(msg)) or 'the exact game subject from the user command'
    system = (
        'You are Goldie CLI, a request-driven real game developer inside a sandbox. '
        'Do NOT use templates. Do NOT switch game genre. Do NOT create Snake unless the user explicitly asked Snake. '
        'Return ONLY valid JSON with {"files":[{"path":"index.html","content":"..."},{"path":"README.md","content":"..."}]}. '
        'Build one directly playable browser game matching the exact user request. '
        'index.html must contain inline CSS and JavaScript, a real playfield/canvas or DOM board, keyboard and mobile/touch/click controls, score/game state, collision/win/loss rules, start/restart, and a game loop using requestAnimationFrame or timer.'
    )
    prompt = (
        'USER REQUEST (must follow exactly):\n{cmd}\n\n'
        'IMPORTANT THEME TERMS THAT SHOULD APPEAR IN GAME UI/CODE:\n{theme}\n\n'
        'FAILED VALIDATION CHECKS FROM PREVIOUS OUTPUT:\n{failed}\n\n'
        'SESSION MEMORY:\n{mem}\n\nGOLDIE KB CONTEXT:\n{kb}\n\n'
        'Generate the real playable game files now. No prose outside JSON.'
    ).format(cmd=msg[:1800], theme=theme_terms, failed=', '.join(failed_checks or []) or '(first repair)', mem=memory_text[:1200] or '(none)', kb=kb_text[:1600] or '(none)')
    raw = _cli_call_llm(prompt, system=system, tokens=4200, temp=0.18)
    if raw.startswith('[LLM Error:'):
        raise ValueError(raw)
    data = _cli_extract_json_object(raw)
    files = None
    if isinstance(data, dict):
        files = _cli_files_from_json_obj(data, msg)
    if not files:
        files = _cli_files_from_llm_text(raw, msg)
    if not files:
        raise ValueError('Game repair did not return writable index.html')
    return files

def _cli_repair_game_html_only_with_llm(msg, memory_text='', kb_text='', failed_checks=None):
    theme_terms = ', '.join(_cli_game_theme_terms(msg)) or 'the exact game subject from the user command'
    system = (
        'You are Goldie CLI, a request-driven browser game developer. Return ONLY one complete HTML document, no markdown, no prose. '
        'Do not use templates. Do not switch genre. Match the exact user command. '
        'The HTML must be directly playable in browser with inline CSS and JS: canvas/playfield, controls, game loop, score, collision/win/loss, restart/start, and mobile controls.'
    )
    prompt = (
        'USER REQUEST:\n{cmd}\n\n'
        'THEME TERMS TO INCLUDE:\n{theme}\n\n'
        'FAILED CHECKS:\n{failed}\n\n'
        'MEMORY:\n{mem}\n\n'
        'GOLDIE KB:\n{kb}\n\n'
        'Write the complete index.html now. Match the exact requested genre and mechanics. If the user names any subject, implement that subject only; never reuse a prior game or template.'
    ).format(cmd=msg[:1800], theme=theme_terms, failed=', '.join(failed_checks or []) or '(none)', mem=memory_text[:900] or '(none)', kb=kb_text[:1200] or '(none)')
    raw = _cli_call_llm(prompt, system=system, tokens=5200, temp=0.20)
    if raw.startswith('[LLM Error:'):
        raise ValueError(raw)
    readme = '# Goldie Browser Game\n\nBuilt from user request:\n\n```text\n' + msg[:1000] + '\n```\n\nGenerated by Goldie CLI request-driven LLM writer.\n'
    return [{'path': 'index.html', 'content': raw.strip()}, {'path': 'README.md', 'content': readme}]

def _cli_generate_project_files_with_llm(msg, existing_files, memory_text='', kb_text='', workspace=''):
    is_game = _cli_is_game_command(msg)
    if is_game:
        # Game builds are latency-sensitive behind nginx. Use one request-driven HTML writer
        # instead of strict JSON first + repair second; validation still happens before success.
        return _cli_repair_game_html_only_with_llm(msg, '', kb_text, failed_checks=['direct_game_build_required'])
    system = (
        'You are Goldie CLI inside a secure Hermes-style sandbox. You are a REAL file-writing builder. '
        'Use the user command, session memory, Goldie KB context, scanned URL references/assets, and current workspace files to create files. '
        'Return ONLY valid JSON, no markdown, no prose. JSON shape: '
        '{"files":[{"path":"index.html","content":"..."},{"path":"README.md","content":"..."}],"summary":"..."}. '
        'Paths must be safe relative paths only. Do not use absolute paths or .. traversal. '
        'For static sites, write a complete previewable index.html with inline CSS/JS unless separate files are necessary. '
        'For backend/API/server requests, write real runnable backend source files (for example server.py/app.py or server.js), README.md with run instructions, JSON endpoints, error handling, and do not satisfy the request with only index.html. '
        'For CRUD/database requests, include data/schema/model handling and create/read/update/delete routes. '
        + ('For game requests, build an ACTUAL PLAYABLE browser game, not a landing page: include canvas or DOM playfield, game state, input controls, requestAnimationFrame or timed loop, scoring, collision/win/loss rules, restart/start button, keyboard and mobile/touch controls. ' if is_game else '') +
        'Mobile-first is mandatory: include <meta viewport>, no horizontal scroll, responsive nav, fluid grids, clamp() typography, flexible cards/buttons, break-all long contract/wallet text, and @media rules for max-width 820px and 430px. '
        'Do not claim files are written; just return file contents for Hermes tools to write.'
    )
    prompt = (
        'USER COMMAND:\n{cmd}\n\n'
        'SESSION MEMORY:\n{mem}\n\n'
        'GOLDIE KB + SCANNED URL REFERENCES:\n{kb}\n\n'
        'CURRENT WORKSPACE FILES:\n{files}\n\n'
        'WORKSPACE ROOT (for context only; never output absolute paths):\n{ws}\n\n'
        'Now generate the actual files to write. Minimum required files: README.md plus index.html for browser/UI builds, or a runnable backend source file for backend/API builds.' +
        (' For game requests, the index.html must be directly playable when opened in preview; no placeholder instructions, no static mockup, no only-code-in-chat.' if is_game else '')
    ).format(cmd=msg[:1800], mem=memory_text[:1800] or '(none)', kb=kb_text[:1800] or '(none)', files='\n'.join(existing_files[:80]) or '(empty)', ws=workspace)
    raw = _cli_call_llm(prompt, system=system, tokens=2600, temp=0.22)
    if raw.startswith('[LLM Error:'):
        # Some providers time out on strict JSON mode for rich URL-inspired builds.
        # Retry once in HTML-only mode so the build can still produce a real persisted index.html.
        repair_system = 'You are Goldie CLI. Return ONLY one complete, production-quality HTML document for index.html. No markdown, no explanation. Inline CSS/JS. Follow the exact user request; do not use templates and do not switch the requested product/game/app type.'
        repair_prompt = ('USER COMMAND:\n' + msg[:1400] + '\n\nSCANNED/KB REFERENCE:\n' + (kb_text or '')[:2200] + '\n\nBuild the exact requested artifact now. Preserve the requested subject, features, labels, interaction model, and visual direction. No template substitution.')
        repair_raw = _cli_call_llm(repair_prompt, system=repair_system, tokens=3200, temp=0.22)
        if repair_raw.startswith('[LLM Error:'):
            raise ValueError(repair_raw)
        raw = '```html\n' + repair_raw + '\n```'
    try:
        obj = _cli_extract_json_object(raw)
        files = _cli_files_from_json_obj(obj, msg)
    except Exception:
        files = _cli_files_from_llm_text(raw, msg)
    if not isinstance(files, list) or not files:
        files = _cli_files_from_llm_text(raw, msg)
    if not isinstance(files, list) or not files:
        repair_system = 'Return ONLY files/content matching the exact user command. No explanation, no markdown, no template substitution.'
        repair_prompt = 'Create a previewable implementation for this exact user command, preserving the requested type/features/genre:\n' + msg[:1200]
        repair_raw = _cli_call_llm(repair_prompt, system=repair_system, tokens=1800, temp=0.25)
        files = _cli_files_from_llm_text('```html\n' + repair_raw + '\n```', msg)
    if not isinstance(files, list) or not files:
        raise ValueError('LLM builder did not return index.html')
    cleaned=[]
    has_index=False
    for item in files[:16]:
        if isinstance(item, str):
            item = {'path': 'index.html', 'content': item}
        if not isinstance(item, dict): continue
        rel = str(item.get('path') or item.get('filename') or item.get('file') or item.get('name') or item.get('filepath') or item.get('file_path') or item.get('pathname') or '').strip().lstrip('/').replace('\\','/')
        content = None
        for ck in ('content','html','code','html_content','source','text','body','data','markdown'):
            if item.get(ck) is not None:
                content = item.get(ck); break
        if not rel and isinstance(item.get('index.html'), str):
            rel, content = 'index.html', item.get('index.html')
        if not rel or content is None: continue
        content_s = str(content)
        if rel.startswith('../') or '/../' in rel or rel in ('.','..'):
            continue
        low_rel = rel.lower()
        low_content = content_s[:5000].lower()
        if (rel.endswith('/index.html') or rel == 'index_html' or rel == 'html' or ('<html' in low_content or '<!doctype' in low_content)) and not has_index:
            rel = 'index.html'
        if rel == 'index.html':
            has_index=True
        cleaned.append({'path': rel, 'content': content_s[:300000]})
    if not any(f['path'] == 'index.html' for f in cleaned):
        # Last bounded salvage: if the LLM returned any non-empty text/html-like content, persist it as index.html instead of dropping it.
        for f in cleaned:
            if str(f.get('content','')).strip():
                f['path'] = 'index.html'
                has_index = True
                break
    if not any(f['path'] == 'index.html' for f in cleaned):
        raise ValueError('LLM builder did not return index.html')
    if not any(f['path'] == 'README.md' for f in cleaned):
        cleaned.append({'path':'README.md','content':'# Goldie CLI Project\n\nBuilt by Goldie CLI from command:\n\n```text\n'+msg[:1000]+'\n```\n'})
    return cleaned


def _cli_mobile_harden_html(content):
    text = str(content or '')
    low = text.lower()
    if '<html' not in low and '<!doctype' not in low:
        return text
    if 'name="viewport"' not in low and "name='viewport'" not in low:
        text = text.replace('<head>', '<head>\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">', 1)
    if 'Goldie mobile-first hardening patch' in text:
        return text
    css = """
/* Goldie mobile-first hardening patch */
html,body{max-width:100%;overflow-x:hidden;}img,svg,canvas,video{max-width:100%;height:auto;}.container,.wrap,.panel,main,section{max-width:100%;}.btn,button,a{max-width:100%;}
@media (max-width:820px){
  body{font-size:15px;}h1{font-size:clamp(1.9rem,12vw,3rem)!important;line-height:.98!important;overflow-wrap:anywhere;}h2{font-size:clamp(1.45rem,8.5vw,2.25rem)!important;line-height:1.08!important;}p{font-size:.95rem;line-height:1.62;}
  header,nav,.navbar,.topnav{max-width:calc(100vw - 1rem)!important;left:.5rem!important;right:.5rem!important;width:auto!important;gap:.45rem!important;padding:.55rem!important;}
  main,section,.panel,.wrap,.container{width:100%!important;max-width:100%!important;padding-left:.75rem!important;padding-right:.75rem!important;}
  .hero,.hero-grid,.grid,.cards,.feature-grid,.capability-grid,.asset-grid,.stats{display:grid!important;grid-template-columns:1fr!important;gap:1rem!important;}
  .hero{min-height:auto!important;padding-top:5.5rem!important;}.hero-visual{min-height:220px!important;overflow:hidden!important;}.orbital-wrap,.visual,.coin,.phone,.mockup{max-width:78vw!important;width:min(300px,78vw)!important;}
  .cta,.cta-row,.actions{display:grid!important;grid-template-columns:1fr!important;width:100%!important;}.btn,button{width:100%;justify-content:center;text-align:center;min-height:44px;}
  code,pre,.address,.contract,.address-box code{white-space:pre-wrap!important;word-break:break-all!important;overflow-wrap:anywhere!important;min-width:0!important;max-width:100%!important;}
}
@media (max-width:430px){h1{font-size:clamp(1.7rem,11.5vw,2.55rem)!important;}.hero-visual{min-height:190px!important;}main,section,.panel,.wrap,.container{padding-left:.55rem!important;padding-right:.55rem!important;}}
"""
    if '</style>' in text:
        return text.replace('</style>', css + '\n</style>', 1)
    return text.replace('</head>', '<style>' + css + '</style>\n</head>', 1) if '</head>' in text else text + '<style>' + css + '</style>'


def _cli_write_generated_files(workspace, files):
    written=[]
    for item in files:
        rel=item['path']
        path=_cli_safe_path(workspace, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = item['content']
        if rel.lower().endswith('.html'):
            content = _cli_mobile_harden_html(content)
        _pathlib_cli.Path(path).write_text(content, encoding='utf-8')
        written.append(rel)
    if any(x == 'index.html' for x in written):
        _cli_set_active_project(workspace, '', 'command-build')
    else:
        for x in written:
            if x.endswith('/index.html'):
                _cli_set_active_project(workspace, os.path.dirname(x), 'command-build')
                break
    return written



def _cli_repair_domain_files_with_llm(msg, failed_checks, memory_text='', kb_text='', workspace=''):
    failed = ', '.join(failed_checks or []) or 'domain_validation_failed'
    t=(msg or '').lower()
    backend = any(w in t for w in ['api','backend','server','endpoint','route','fastapi','express','flask','rest api'])
    system = (
        'You are Goldie CLI repair builder. Return ONLY valid JSON: {"files":[{"path":"...","content":"..."}],"summary":"..."}. '
        'No markdown, no prose, no templates. Fix the failed validation checks exactly. '
        + ('This is a backend/API request: include a real runnable backend source file such as server.py/app.py/server.js with CRUD endpoints, JSON responses, error handling, and README.md. Do not satisfy it with only HTML. ' if backend else '') +
        'Paths must be safe relative paths. Preserve the exact user request.'
    )
    prompt = (
        'USER COMMAND:\n{cmd}\n\nFAILED CHECKS:\n{failed}\n\nGOLDIE KB/HOOKS:\n{kb}\n\nWORKSPACE:\n{ws}\n\n'
        'Regenerate the files so validation passes. If backend/API, include runnable source file and README run instructions. If app/UI, include styled responsive interactive index.html.'
    ).format(cmd=msg[:1800], failed=failed, kb=kb_text[:2000] or '(none)', ws=workspace)
    raw = _cli_call_llm(prompt, system=system, tokens=3600, temp=0.18)
    if raw.startswith('[LLM Error:'):
        raise ValueError(raw)
    try:
        obj=_cli_extract_json_object(raw)
        files=_cli_files_from_json_obj(obj, msg)
    except Exception:
        files=_cli_files_from_llm_text(raw, msg)
    if not files:
        raise ValueError('Domain repair did not return writable files')
    return files

def _cli_build_from_user_command(handler, data, sid, workspace, msg):
    existing = _cli_list_files(workspace, 120)
    mem = _cli_load_memory(sid, 12)
    mem_txt = '\n'.join('%s: %s' % (m.get('role','user').upper(), (m.get('text') or '')[:700]) for m in mem)
    hook_matches = _cli_skill_hook_query(msg, limit=5)
    kb_txt = _cli_kb_context(msg)
    # If a build command includes a URL, scan it first so the LLM has real reference data/assets.
    try:
        urls = _re_cli.findall(r'https?://[^\s<>"\']+', msg or '')[:1]
        for u in urls:
            _cli_scan_url_reference(handler, dict(data, url=u), sid, workspace, msg)
    except Exception:
        pass
    ref_txt = _cli_reference_context(workspace)
    if ref_txt:
        kb_txt = (kb_txt + '\n\n' if kb_txt else '') + ref_txt
    gen_files = _cli_generate_project_files_with_llm(msg, existing, mem_txt, kb_txt, workspace)
    if _cli_is_game_command(msg):
        playable, checks = _cli_validate_playable_game(gen_files)
        theme_terms = _cli_game_theme_terms(msg)
        theme_ok = True if not theme_terms else any(term in '\n'.join(str(f.get('content','')).lower() for f in gen_files if isinstance(f, dict)) for term in theme_terms)
        if not playable or not theme_ok:
            failed = [k for k,v in checks.items() if not v]
            if not theme_ok:
                failed.append('theme_match_exact_user_request')
            # Request-driven repair only: ask the LLM again with the exact command.
            # No deterministic genre/template substitution; spaceship must stay spaceship, etc.
            gen_files = _cli_repair_game_files_with_llm(msg, '', kb_txt, failed)
            playable, checks = _cli_validate_playable_game(gen_files)
            theme_ok = True if not theme_terms else any(term in '\n'.join(str(f.get('content','')).lower() for f in gen_files if isinstance(f, dict)) for term in theme_terms)
        if not playable or not theme_ok:
            failed = [k for k,v in checks.items() if not v]
            if not theme_ok:
                failed.append('theme_match_exact_user_request')
            # Second repair is still LLM/request-driven (not template): ask for raw complete HTML and validate again.
            gen_files = _cli_repair_game_html_only_with_llm(msg, '', kb_txt, failed)
            playable, checks = _cli_validate_playable_game(gen_files)
            theme_ok = True if not theme_terms else any(term in '\n'.join(str(f.get('content','')).lower() for f in gen_files if isinstance(f, dict)) for term in theme_terms)
        if not playable or not theme_ok:
            failed = [k for k,v in checks.items() if not v]
            if not theme_ok:
                failed.append('theme_match_exact_user_request')
            raise ValueError('Game builder validation failed: ' + ', '.join(failed))
    domain_ok, domain_checks = _cli_validate_domain_build(msg, gen_files, hook_matches)
    if not domain_ok and not _cli_is_game_command(msg):
        failed_domain = [k for k,v in domain_checks.items() if not v]
        gen_files = _cli_repair_domain_files_with_llm(msg, failed_domain, mem_txt, kb_txt, workspace)
        domain_ok, domain_checks = _cli_validate_domain_build(msg, gen_files, hook_matches)
    if not domain_ok and not _cli_is_game_command(msg):
        raise ValueError('Build validation failed: ' + ', '.join([k for k,v in domain_checks.items() if not v]))
    written = _cli_write_generated_files(workspace, gen_files)
    prev = _handle_cli_preview_to_dict(handler, {'session': data.get('session')})
    post_verify = _cli_post_build_verify(workspace, msg, written, prev)
    if not post_verify.get('ok'):
        raise ValueError('Post-build verification failed: ' + ', '.join(post_verify.get('issues') or ['unknown']))
    files_now = _cli_file_tree(workspace, 120)
    return {
        'builder': 'goldie-pipeline-llm-writer',
        'pipeline': ['user-command', 'cli-memory', 'goldie-kb', 'cli-skill-hooks', 'llm-json-files', 'hermes-write-file', 'validator-proof', 'preview'],
        'skill_hooks': [{'name': h.get('name'), 'source_repo': h.get('source_repo'), 'actions': h.get('actions'), 'validators': h.get('validators')} for h in hook_matches],
        'validation': domain_checks,
        'post_build_verify': post_verify,
        'written': written,
        'preview': prev,
        'files': files_now,
        'playable_game': _cli_validate_playable_game(gen_files)[0] if _cli_is_game_command(msg) else False,
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
        elif msg.startswith('/scan ') or msg.startswith('/url ') or _re_cli.search(r'(?i)\b(scan|scrape|ambil|referensi|reference)\b.*https?://', msg):
            scanned = _cli_scan_url_reference(handler, data, sid, workspace, msg)
            reply = 'URL scanned and saved as build reference.'
            output = 'source: %s\nreference: %s\nscan json: %s\nassets saved: %s\ncolors: %s' % (scanned.get('url'), scanned.get('reference_file'), scanned.get('scan_file'), scanned.get('assets_saved'), ', '.join(scanned.get('colors') or []))
        elif _cli_is_build_command(msg):
            built = _cli_build_from_user_command(handler, data, sid, workspace, msg)
            reply = 'Command executed: real build persisted files. Builder: %s.' % built.get('builder')
            output = 'pipeline: ' + ' -> '.join(built.get('pipeline') or []) + '\nwrote files:\n- ' + '\n- '.join(built.get('written') or [])
            if built.get('skill_hooks'):
                output += '\nskill hooks: ' + str(len(built.get('skill_hooks') or [])) + ' applied'
            if built.get('preview', {}).get('preview_url'):
                output += '\npreview: ' + built['preview']['preview_url']
            files = built.get('files') or _cli_file_tree(workspace, 120)
            preview_payload = built.get('preview') or {}
            build_payload = built
        else:
            mem = _cli_load_memory(sid, 10)
            mem_txt = '\n'.join('%s: %s' % (m.get('role','user').upper(), (m.get('text') or '')[:700]) for m in mem)
            kb_txt = _cli_kb_context(msg)
            ref_txt = _cli_reference_context(workspace)
            if ref_txt:
                kb_txt = (kb_txt + '\n\n' if kb_txt else '') + ref_txt
            sysmsg = (
                'You are Goldie CLI, a secure coding assistant inside a per-user sandbox workspace. '
                'You help users code. Natural non-build questions are advisory, but explicit user build/create commands may persist files in the sandbox. '
                'Never claim you touched files unless a tool command output says so. Never reveal secrets. '
                'Core app /opt/gitpup and VPS secrets are off-limits. Workspace only: %s. '
                'Use Goldie KB patterns when useful. Keep output concise and terminal-friendly.' % workspace
            )
            prompt = 'SESSION MEMORY:\n%s\n\nGOLDIE KB CONTEXT:\n%s\n\nCURRENT FILES:\n%s\n\nUSER REQUEST:\n%s' % (mem_txt, kb_txt or '(none)', '\n'.join(files[:40]) or '(empty)', msg)
            reply = _cli_call_llm(prompt, system=sysmsg, tokens=500, temp=0.25)
            output = 'Tip commands: /scan https://site.com, /files, /run pwd, /write app.py\\nprint("hi"), /read app.py'
    except Exception as e:
        reply = 'Error: ' + str(e)[:180]
    reply = _cli_redact(reply)
    output = _cli_redact(output)
    _cli_append_memory(sid, 'assistant', reply + ('\n' + output if output else ''))
    resp = {'status': 'ok', 'session_id': sid, 'workspace_name': 'user_' + sid, 'workspace': workspace, 'reply': reply, 'output': output, 'files': files[:80], 'sandbox': True, 'rate_limit': {'cooldown_seconds': CLI_COOLDOWN_SECONDS}, 'model': {'provider': CLI_LLM_PROVIDER, 'name': CLI_LLM_MODEL, 'base_url': CLI_LLM_BASE_URL}, 'gmail': {'available': False, 'reason': 'Google OAuth client not configured yet'}}
    if 'preview_payload' in locals() and preview_payload:
        resp['preview'] = preview_payload
        if preview_payload.get('preview_url'):
            resp['preview_url'] = preview_payload.get('preview_url')
    if 'build_payload' in locals() and build_payload:
        resp['pipeline'] = build_payload.get('pipeline')
        resp['skill_hooks'] = build_payload.get('skill_hooks')
        resp['playable_game'] = build_payload.get('playable_game')
        resp['validation'] = build_payload.get('validation')
        resp['post_build_verify'] = build_payload.get('post_build_verify')
    return resp


def _handle_cli_session(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    _cli_ensure_current_project(workspace)
    mem = _cli_load_memory(sid, 8)
    return _json_resp(handler, {'status': 'ok', 'session_id': sid, 'workspace_name': 'user_' + sid, 'workspace': workspace, 'sandbox': True, 'memory_turns': len(mem), 'files': _cli_file_tree(workspace, 80), 'security': {'path_locked': True, 'core_protected': True, 'secrets_redacted': True, 'shell_chaining_blocked': True}, 'rate_limit': {'cooldown_seconds': CLI_COOLDOWN_SECONDS}, 'model': {'provider': CLI_LLM_PROVIDER, 'name': CLI_LLM_MODEL, 'base_url': CLI_LLM_BASE_URL}, 'export': {'download_ready': True}, 'preview': {'enabled': True}})


def _cli_run_request_job(job, handler, data):
    try:
        _cli_job_log(job, 'Started request-driven build')
        result = _cli_answer(handler, data)
        _cli_job_log(job, result.get('reply') or 'Build finished')
        if result.get('output'):
            _cli_job_log(job, result.get('output'))
        _cli_job_finish(job, 'done' if result.get('status') != 'error' else 'error', result)
    except Exception as e:
        _cli_job_log(job, 'Error: ' + str(e)[:180])
        _cli_job_finish(job, 'error', {'status':'error','reply':'Error: '+str(e)[:180], 'error':str(e)[:220]})


def _handle_cli(handler, data):
    msg = (data.get('message') or '').strip()
    # Browser/nginx may timeout on rich LLM builds. Return a job immediately for build/game
    # requests; frontend polls /api/cli/job until validator-backed files/preview are ready.
    if _cli_is_build_command(msg):
        sid, workspace = _cli_workspace(handler, data)
        job = _cli_job_new(sid, 'request-build', msg)
        t = threading.Thread(target=_cli_run_request_job, args=(job, handler, dict(data)), daemon=True)
        t.start()
        return _json_resp(handler, {'status':'queued','reply':'Build started. Goldie is generating real files from your request...','job_id':job['id'],'job':job,'session_id':sid,'workspace_name':'user_'+sid,'files':_cli_file_tree(workspace,80)})
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
        return _json_resp(handler, {'status': 'ok', 'session_id': sid, 'workspace_name': 'user_' + sid, 'download_url': _cli_signed_download_url(sid), 'size': os.path.getsize(zip_path), 'expires_in': 900})
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
    url = _cli_signed_preview_url(sid, found, mtime)
    return _json_resp(handler, {'status': 'ok', 'session_id': sid, 'preview_url': url, 'preview_path': found, 'expires_in': 1800})


def _serve_cli_download(handler):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
    sid = ''.join(ch for ch in (q.get('session', [''])[0]) if ch.isalnum() or ch in ('_', '-'))[:80]
    if not sid:
        return _json_resp(handler, {'status': 'error', 'error': 'missing session'}, 400)
    token = q.get('token', [''])[0]
    if not _cli_verify_token(sid, 'download', '', token):
        return _json_resp(handler, {'status': 'error', 'error': 'invalid or expired download token'}, 403)
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
    handler.end_headers()
    with open(zip_path, 'rb') as f:
        handler.wfile.write(f.read())


def _serve_cli_preview(handler):
    import mimetypes
    parts = urllib.parse.urlparse(handler.path).path.split('/')
    if len(parts) < 3:
        handler.send_error(404); return
    sid = ''.join(ch for ch in urllib.parse.unquote(parts[2]) if ch.isalnum() or ch in ('_', '-'))[:80]
    rel = urllib.parse.unquote('/'.join(parts[3:]) or 'index.html').replace('\\', '/')
    q = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
    token = q.get('token', [''])[0]
    if not _cli_verify_token(sid, 'preview', rel, token):
        handler.send_error(403); return
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

_CLI_TEMPLATES = {}

def _cli_apply_template(workspace, name, project_name=None):
    raise RuntimeError('Templates are disabled. CLI builds must come from the exact user request via LLM + Goldie KB + Hermes tools.')

def _handle_cli_preview_to_dict(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    _cli_ensure_current_project(workspace)
    found, mtime = _cli_find_preview_index(workspace)
    if not found: return {'status':'error','error':'No index.html found. Create one first, then preview.'}
    return {'status':'ok','session_id':sid,'preview_url':_cli_signed_preview_url(sid, found, mtime),'preview_path':found,'expires_in':1800}

def _handle_cli_export_to_dict(handler, data):
    sid, workspace = _cli_workspace(handler, data)
    _cli_ensure_current_project(workspace)
    zip_path = _cli_zip_workspace(sid, workspace)
    return {'status':'ok','session_id':sid,'workspace_name':'user_'+sid,'download_url':_cli_signed_download_url(sid),'size':os.path.getsize(zip_path),'expires_in':900}

def _cli_agent_build(job, handler, data):
    _cli_job_finish(job, 'error', {'status':'disabled','reply':'Agent Build is disabled. CLI builds must be request-driven via LLM + Goldie KB + Hermes tools, not templates.'})

def _handle_cli_agent(handler, data):
    return _json_resp(handler, {'status':'disabled','reply':'Agent Build is disabled. Files only change from explicit user commands like /write, /run, Save, or direct build requests.'}, 403)


def _handle_cli_job(handler, data):
    jid = (data.get('job_id') or data.get('id') or '').strip()
    with _CLI_JOB_LOCK: job = _CLI_JOBS.get(jid)
    if not job: return _json_resp(handler, {'status':'error','error':'job not found'}, 404)
    return _json_resp(handler, {'status':'ok','job':job})

def _handle_cli_template(handler, data):
    # Public CLI is request-driven. Hidden/template creation is disabled so files only
    # come from explicit LLM/Hermes build, /write, /run, or Save actions.
    return _json_resp(handler, {'status':'disabled','reply':'Templates are disabled. Tell Goldie what to build; Hermes + LLM + Goldie KB will generate real files from your request.'}, 403)

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



def _handle_cli_delete(handler, data):
    """Delete all user-created files inside one sandbox workspace."""
    import shutil
    sid, workspace = _cli_workspace(handler, data)
    if not data.get('confirm') or str(data.get('confirm_text') or '').strip().upper() != 'DELETE':
        return _json_resp(handler, {
            'status': 'needs_confirmation',
            'reply': 'This will permanently delete all files in this workspace. Type DELETE to confirm.',
            'required_text': 'DELETE'
        })
    root = os.path.realpath(WORKSPACES)
    ws = os.path.realpath(workspace)
    if not (os.path.basename(ws).startswith('user_') and (ws == root or ws.startswith(root + os.sep))):
        return _json_resp(handler, {'status':'error','error':'workspace containment failed'}, 403)
    deleted = 0; bytes_deleted = 0; errors = []
    keep = {'.goldie-session.json'}
    for item in list(os.listdir(ws)):
        if item in keep:
            continue
        path = os.path.realpath(os.path.join(ws, item))
        if not (path == ws or path.startswith(ws + os.sep)):
            errors.append({'path': item, 'error': 'outside workspace'}); continue
        try:
            if os.path.islink(path):
                os.unlink(path); deleted += 1
            elif os.path.isdir(path):
                for base, dirs, files in os.walk(path):
                    for f in files:
                        fp = os.path.join(base, f)
                        try: bytes_deleted += os.path.getsize(fp)
                        except Exception: pass
                shutil.rmtree(path); deleted += 1
            else:
                try: bytes_deleted += os.path.getsize(path)
                except Exception: pass
                os.remove(path); deleted += 1
        except Exception as e:
            errors.append({'path': item, 'error': str(e)[:120]})
    os.makedirs(os.path.join(ws, 'tmp'), exist_ok=True)
    os.makedirs(os.path.join(ws, 'logs'), exist_ok=True)
    files = _cli_file_tree(ws, 80)
    return _json_resp(handler, {
        'status': 'ok' if not errors else 'partial',
        'reply': 'Workspace files deleted. Your sandbox session is still active.',
        'session_id': sid,
        'workspace_name': 'user_' + sid,
        'deleted_items': deleted,
        'bytes_deleted': bytes_deleted,
        'errors': errors,
        'files': files
    })

def _public_do_POST(self):
    p = urllib.parse.urlparse(self.path).path
    if p not in ('/api/chat', '/api/image', '/api/image/job', '/api/song', '/api/cli/session', '/api/cli', '/api/cli/tree', '/api/cli/read', '/api/cli/export', '/api/cli/preview', '/api/cli/agent', '/api/cli/job', '/api/cli/template', '/api/cli/save', '/api/cli/quota', '/api/cli/git/scan', '/api/cli/git/push', '/api/cli/reset', '/api/cli/delete', '/api/cli/scan'):
        return _json_resp(self, {'status': 'error', 'error': 'not found'}, 404)
    try:
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        data = json.loads(body.decode('utf-8') if isinstance(body, bytes) else body)
        if not isinstance(data, dict):
            raise ValueError('Invalid JSON payload')
        if p == '/api/image':
            return _handle_image(self, data)
        if p == '/api/image/job':
            return _handle_image_async(self, data)
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
        if p == '/api/cli/delete':
            return _handle_cli_delete(self, data)
        if p == '/api/cli/scan':
            sid, workspace = _cli_workspace(self, data)
            return _json_resp(self, _cli_scan_url_reference(self, data, sid, workspace, data.get('message') or data.get('url') or ''))
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
