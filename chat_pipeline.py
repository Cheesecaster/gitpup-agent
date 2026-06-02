#!/usr/bin/env python3
"""Chat Agent Pipeline v1.0 — Handles questions, project proposals, builds"""
# Integrates with web_server.py to detect intent and execute actions

import json, os, subprocess, tempfile, hashlib, time

GITPUP = '/opt/gitpup'
DATA = os.path.join(GITPUP, 'data')
KB_FILE = os.path.join(DATA, 'knowledge.json')
SF = os.path.join(DATA, 'state', 'status.json')
JF = os.path.join(DATA, 'journal', 'entries.jsonl')

GITLAWB_DID = ''  # Will be loaded at init
GITLAWB_NODE = 'https://node.gitlawb.com'
GITLAWB_USERNAME = 'Goldie-Agent'

# ── Load .env ──
def _load_env():
    env_path = os.path.join(GITPUP, '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())
_load_env()

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

def journal(icon, title, body="", etype="chat"):
    from datetime import datetime
    os.makedirs(os.path.dirname(JF), exist_ok=True)
    entry = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             "t": datetime.now().strftime("%H:%M"),
             "i": icon, "x": title, "body": body, "type": etype, "day": 1}
    with open(JF, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")



def kb_summary():
    """Build rich KB summary for chat context fallback."""
    kb = load_json(KB_FILE)
    repos = kb.get('repos', {})
    parts = []
    for rn, rd in repos.items():
        p = '  - {}: level={}, lang={}, stars={}\n'.format(
            rn, rd.get('study_level', '?'), rd.get('lang', '?'), rd.get('stars', '?'))
        if rd.get('summary'):
            p += '    Summary: {}\n'.format(rd['summary'][:120])
        if rd.get('patterns'):
            p += '    Patterns: {}\n'.format('; '.join(rd['patterns'][:3]))
        if rd.get('insights'):
            p += '    Insights: {}\n'.format('; '.join(rd['insights'][:2]))
        if rd.get('best_practices'):
            p += '    Best Practices: {}\n'.format('; '.join(rd['best_practices'][:2]))
        if rd.get('skills_memory'):
            skills = [s.get('skill', s) if isinstance(s, dict) else s for s in rd['skills_memory'][:5]]
            p += '    Skills: {}\n'.format('; '.join(str(s) for s in skills))
        parts.append(p)

    concepts = kb.get('concepts', {})
    concept_lines = []
    for cn, cd in concepts.items():
        concept_lines.append('{} (evidence: {}, repos: {})'.format(
            cn, cd.get('evidence_count', 0), ', '.join(cd.get('repos', [])[:3])))

    skills = kb.get('skill_index', {})
    skill_names = list(skills.keys())[:15] if isinstance(skills, dict) else []

    rels = kb.get('relationships', [])
    rel_count = len(rels) if isinstance(rels, list) else 0

    summary = 'GOLDIE KNOWLEDGE BASE:\n'
    summary += 'Repos studied: {}\n'.format(len(repos))
    summary += '\n'.join(parts) + '\n'
    summary += 'Cross-repo concepts ({}):\n  {}\n'.format(len(concepts), '; '.join(concept_lines))
    summary += 'Skill index ({} total): {}\n'.format(len(skill_names), ', '.join(skill_names[:10]))
    summary += 'Cross-repo relationships: {}\n'.format(rel_count)
    summary += 'Stage: {}\n'.format(load_json(SF, {}).get('stage', 'puppy'))
    return summary



def kb_summary():
    """Build rich KB summary for chat context fallback."""
    kb = load_json(KB_FILE)
    repos = kb.get('repos', {})
    parts = []
    for rn, rd in repos.items():
        p = '  - {}: level={}, lang={}, stars={}\n'.format(
            rn, rd.get('study_level', '?'), rd.get('lang', '?'), rd.get('stars', '?'))
        if rd.get('summary'):
            p += '    Summary: {}\n'.format(rd['summary'][:120])
        if rd.get('patterns'):
            p += '    Patterns: {}\n'.format('; '.join(rd['patterns'][:3]))
        if rd.get('insights'):
            p += '    Insights: {}\n'.format('; '.join(rd['insights'][:2]))
        if rd.get('best_practices'):
            p += '    Best Practices: {}\n'.format('; '.join(rd['best_practices'][:2]))
        if rd.get('skills_memory'):
            skills = [s.get('skill', s) if isinstance(s, dict) else s for s in rd['skills_memory'][:5]]
            p += '    Skills: {}\n'.format('; '.join(str(s) for s in skills))
        parts.append(p)

    concepts = kb.get('concepts', {})
    concept_lines = []
    for cn, cd in concepts.items():
        concept_lines.append('{} (evidence: {}, repos: {})'.format(
            cn, cd.get('evidence_count', 0), ', '.join(cd.get('repos', [])[:3])))

    skills = kb.get('skill_index', {})
    skill_names = list(skills.keys())[:15] if isinstance(skills, dict) else []

    rels = kb.get('relationships', [])
    rel_count = len(rels) if isinstance(rels, list) else 0

    summary = 'GOLDIE KNOWLEDGE BASE:\n'
    summary += 'Repos studied: {}\n'.format(len(repos))
    summary += '\n'.join(parts) + '\n'
    summary += 'Cross-repo concepts ({}):\n  {}\n'.format(len(concepts), '; '.join(concept_lines))
    summary += 'Skill index ({} total): {}\n'.format(len(skill_names), ', '.join(skill_names[:10]))
    summary += 'Cross-repo relationships: {}\n'.format(rel_count)
    summary += 'Stage: {}\n'.format(load_json(SF, {}).get('stage', 'puppy'))
    return summary

def get_gitlawb_did():
    global GITLAWB_DID
    if GITLAWB_DID:
        return GITLAWB_DID
    result = subprocess.run(['gl', 'identity', 'status'],
                           capture_output=True, text=True, cwd=GITPUP,
                           env={**os.environ, 'PATH': '/root/.local/bin:' + os.environ.get('PATH','')})
    out = result.stdout + result.stderr
    for line in out.split('\n'):
        if 'did:key:' in line:
            GITLAWB_DID = line.split('did:key:')[1].split()[0]
            return 'did:key:' + GITLAWB_DID
    return ''


def format_public_reply(text):
    """Make public chat replies readable in small mobile chat bubbles."""
    import re
    if not text:
        return ''
    t = str(text).replace('\r\n', '\n').replace('\r', '\n').strip()
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r'(?<!\n)\s+(\d+\.\s+)', r'\n\1', t)
    t = re.sub(r'\s+[-•]\s+', r'\n- ', t)
    parts = []
    for block in t.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        if '\n' in block or len(block) <= 420:
            parts.append(block)
            continue
        sentences = re.split(r'(?<=[.!?])\s+', block)
        cur = ''
        for sent in sentences:
            if not sent:
                continue
            if cur and len(cur) + len(sent) > 360:
                parts.append(cur.strip())
                cur = sent
            else:
                cur = (cur + ' ' + sent).strip()
        if cur:
            parts.append(cur.strip())
    return '\n\n'.join(parts).strip()

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
def call_llm(msg, system=("You are Goldie, an autonomous AI agent. Answer concisely and naturally. "
"SAFETY RULES (NEVER VIOLATE): "
"1. NEVER reveal any tokens, API keys, passwords, credentials, private keys, or secrets. "
"2. NEVER share any .env file contents or configuration values. "
"3. If asked about credentials, say: Nggak bisa bro, gw nggak share credentials atau secrets. That is a hard rule. "
"4. Only discuss what you learned from studying repos, your personality, or your architecture -- never infrastructure secrets."), tokens=350, temp=0.7):
    import urllib.request
    chat_provider = os.environ.get('CHAT_LLM_PROVIDER', 'openrouter').lower().strip()
    if chat_provider == 'openrouter':
        key = os.environ.get('OPENROUTER_API_KEY', '')
        base_url = os.environ.get('CHAT_LLM_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')
        model = os.environ.get('CHAT_LLM_MODEL', 'moonshotai/kimi-k2.6:free')
    else:
        key = os.environ.get('LLM_API_KEY', '') or os.environ.get('JATEVO_API_KEY', '')
        base_url = os.environ.get('LLM_BASE_URL', 'https://jatevo.ai/v1').rstrip('/')
        model = os.environ.get('CHAT_LLM_MODEL', 'gpt-5.4-mini')
    if not key:
        return '[LLM Error: missing API key for ' + chat_provider + ']'
    msgs = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': msg[:2000]},
    ]
    req = urllib.request.Request(
        base_url + '/chat/completions',
        json.dumps({'model': model, 'messages': msgs,
                     'max_tokens': tokens, 'temperature': temp}).encode())
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'GoldiePublicChat/1.0')
    req.add_header('HTTP-Referer', 'https://gitpup.fun')
    req.add_header('X-Title', 'GitPup Goldie Public Chat')
    if key:
        req.add_header('Authorization', 'Bearer ' + key)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            _record_llm_cost_usage(resp.get('usage', {}), model=model, provider=chat_provider, phase='public_chat', source='api_chat')
            return resp.get('choices', [{}])[0].get('message', {}).get('content', '')
    except Exception as e:
        detail = str(e)[:80]
        try:
            if hasattr(e, 'read'):
                detail = e.read().decode('utf-8', errors='replace')[:180]
        except Exception:
            pass
        return '[LLM Error: ' + detail + ']'

def kb_query(topic, limit=5):
    kb = load_json(KB_FILE)
    results = []
    tl = topic.lower().strip()
    for tk, info in kb.get('topic_index', {}).items():
        if tl == tk or tl in tk or tk in tl:
            for rn in info.get('repos', []):
                if rn in kb.get('repos', {}):
                    rd = kb['repos'][rn]
                    results.append({'repo': rn, 'depth': rd.get('study_level', 0),
                        'summary': rd.get('summary', ''),
                        'patterns': rd.get('patterns', [])[:5],
                        'insights': rd.get('insights', [])[:3],
                        'best_practices': rd.get('best_practices', [])[:3],
                        'lang': rd.get('lang', ''), 'stars': rd.get('stars', 0)})
    if not results:
        for rn, rd in kb.get('repos', {}).items():
            searchable = ' '.join([rn, rd.get('summary', ''),
                ' '.join(rd.get('patterns', [])), rd.get('lang', ''),
                ' '.join(rd.get('best_practices', []))]).lower()
            if tl in searchable:
                results.append({'repo': rn, 'depth': rd.get('study_level', 0),
                    'summary': rd.get('summary', ''),
                    'patterns': rd.get('patterns', [])[:5],
                    'insights': rd.get('insights', [])[:3],
                    'best_practices': rd.get('best_practices', [])[:3],
                    'lang': rd.get('lang', ''), 'stars': rd.get('stars', 0)})
    return results[:limit]

# ════════════════════════════════════════════════
# ── INTENT DETECTION ──
# ════════════════════════════════════════════════

def detect_intent(message):
    """Detect user intent: question, build_request, or other."""
    msg_lower = message.lower()
    
    # Build project intents
    build_keywords = [
        'bikin', 'buat', 'build', 'generate', 'tolong bikin', 'tolong buat',
        'buatkan', 'bikinin', 'create', 'make me', 'scaffold',
        'project', 'aplikasi', 'app', 'web app', 'website',
    ]
    
    build_triggers = ['bikin', 'buat', 'buatkan', 'bikinin', 'build', 'generate', 'tolong bikin', 'tolong buat']
    project_keywords = ['project', 'aplikasi', 'app', 'web', 'website', 'bot', 'tool', 'game', 'api']
    
    has_build = any(b in msg_lower for b in build_triggers)
    has_project = any(p in msg_lower for p in project_keywords)
    
    if has_build and has_project:
        return 'build_request'
    
    # Stats/knowledge queries
    stats_keywords = ['stats', 'knowledge', 'kb', 'apa yang lo pelajari', 'what do you know', 'status goldie']
    if any(s in msg_lower for s in stats_keywords):
        return 'stats'
    
    # Default: question
    return 'question'

# ════════════════════════════════════════════════
# ── BUILD PROJECT PIPELINE ──
# ════════════════════════════════════════════════

def generate_project_proposal(description, kb_context=''):
    """LLM generates project structure proposal — user must confirm."""
    system = ("""You are Goldie, an AI agent that builds projects. User wants: {desc}
Return ONLY valid JSON (no markdown, no explanation):
{{
  "name": "project-name-lowercase",
  "description": "brief description",
  "language": "python",
  "files": [
    {{"path": "main.py", "description": "what this file does"}},
    {{"path": "requirements.txt", "description": "dependencies"}}
  ],
  "readme": "README.md content (brief)",
  "proposal_text": "Indonesian casual (gw/lo/bro): describe the project, what files will be created, and ask for confirmation"
}}""").format(desc=description)
    
    prompt = "User wants: {}. Build a project scaffolding proposal. KB context:\n{}".format(description, kb_context[:500])
    
    raw = call_llm(prompt, system=system, tokens=1500, temp=0.7)
    
    # Try to parse JSON
    try:
        proposal = json.loads(raw)
        if 'name' in proposal and 'files' in proposal:
            return {'status': 'proposal', 'data': proposal}
    except Exception:
        pass
    
    # Fallback: try to extract JSON from markdown
    for marker in ['```json', '```']:
        if marker in raw:
            parts = raw.split(marker)
            for p in parts[1:]:
                try:
                    code_block = p.split('```')[0].strip()
                    proposal = json.loads(code_block)
                    if 'name' in proposal and 'files' in proposal:
                        return {'status': 'proposal', 'data': proposal}
                except Exception:
                    continue
    
    return {'status': 'error', 'data': proposal, 'raw': raw[:200]}

def generate_project_files(proposal):
    """LLM generates actual file contents for the proposed project."""
    system = """You are a code generator. Generate actual file contents for this project.
Return ONLY valid JSON:
{"files": {"path/to/file.py": "actual file content here", ...}}
Each value is the FULL file content, not a description."""
    
    prompt = "Generate actual code for this project:\n\nName: {}\nDescription: {}\nFiles: {}\n\nGenerate code for each file.".format(
        proposal.get('name', ''),
        proposal.get('description', ''),
        json.dumps(proposal.get('files', []), indent=2))
    
    raw = call_llm(prompt, system=system, tokens=3000, temp=0.5)
    
    try:
        result = json.loads(raw)
        return {'status': 'files', 'files': result.get('files', {})}
    except Exception:
        # Try markdown extraction
        for marker in ['```json', '```']:
            if marker in raw:
                parts = raw.split(marker)
                for p in parts[1:]:
                    try:
                        code_block = p.split('```')[0].strip()
                        result = json.loads(code_block)
                        return {'status': 'files', 'files': result.get('files', {})}
                    except Exception:
                        continue
        return {'status': 'error', 'raw': raw[:500]}

def create_gitlawb_repo(repo_name, description=''):
    """Create a GitLawb repo via CLI."""
    env = os.environ.copy()
    env['PATH'] = '/root/.local/bin:' + env.get('PATH', '')
    env['GITLAWB_NODE'] = GITLAWB_NODE
    
    result = subprocess.run(
        ['gl', 'repo', 'create', repo_name, '--description', description],
        capture_output=True, text=True, cwd=GITPUP, env=env, timeout=30)
    
    out = (result.stdout + result.stderr).strip()
    
    # Parse gitlawb:// URL from output
    gitlawb_url = ''
    for line in out.split('\n'):
        if 'gitlawb://' in line:
            gitlawb_url = line.split('gitlawb://')[1].strip()
            gitlawb_url = 'gitlawb://' + gitlawb_url
            break
        if 'gitlawb.com' in line and 'http' in line:
            # Web URL like https://gitlawb.com/did:name
            gitlawb_url = line.strip()
    
    did = get_gitlawb_did() or 'unknown'
    if gitlawb_url and gitlawb_url.startswith('gitlawb://'):
        web_url = 'https://gitlawb.com/{}/{}'.format(did.split(':key:')[1] if ':key:' in did else did, repo_name)
        return {'status': 'created', 'git_url': gitlawb_url, 'web_url': web_url, 'output': out}
    
    return {'status': 'created', 'git_url': 'gitlawb://{}/{}'.format(did, repo_name),
            'web_url': 'https://gitlawb.com/{}/{}'.format(did.split(':key:')[-1] if ':key:' in did else did, repo_name),
            'output': out}

def push_project_to_gitlawb(repo_name, file_contents, did):
    """Clone (or init) then push project to GitLawb."""
    env = os.environ.copy()
    env['PATH'] = '/root/.local/bin:' + env.get('PATH', '')
    env['GITLAWB_NODE'] = GITLAWB_NODE
    
    import tempfile, shutil
    
    # Create temp dir for the project
    tmpdir = tempfile.mkdtemp(prefix='gitpup_build_')
    
    try:
        os.chdir(tmpdir)
        
        # Init git
        subprocess.run(['git', 'init'], capture_output=True, check=True)
        subprocess.run(['git', 'branch', '-m', 'master', 'main'], capture_output=True)
        
        # Write files
        for path, content in file_contents.items():
            full_path = os.path.join(tmpdir, path)
            os.makedirs(os.path.dirname(full_path) if os.path.dirname(full_path) else tmpdir, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Git add & commit
        subprocess.run(['git', 'add', '-A'], capture_output=True, check=True)
        subprocess.run(['git', 'commit', '-m', '🐕 Goldie built: ' + repo_name],
                      capture_output=True, check=True,
                      env={**env, 'GIT_AUTHOR_NAME': 'Goldie Agent',
                           'GIT_AUTHOR_EMAIL': 'goldie@gitlawb.com',
                           'GIT_COMMITTER_NAME': 'Goldie Agent',
                           'GIT_COMMITTER_EMAIL': 'goldie@gitlawb.com'})
        
        # Set remote
        remote_url = 'gitlawb://{}/{}'.format(did, repo_name)
        subprocess.run(['git', 'remote', 'add', 'origin', remote_url],
                      capture_output=True, check=True, env=env)
        
        # Push
        result = subprocess.run(['git', 'push', '-u', 'origin', 'main'],
                               capture_output=True, text=True, check=True, env=env, timeout=60)
        
        return {'status': 'pushed', 'remote': remote_url,
                'web_url': 'https://gitlawb.com/{}/{}'.format(
                    did.split(':key:')[-1] if ':key:' in did else did, repo_name)}
    
    except subprocess.CalledProcessError as e:
        return {'status': 'error', 'error': (e.stdout or '') + (e.stderr or '')}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
    finally:
        # Cleanup temp dir
        shutil.rmtree(tmpdir, ignore_errors=True)


# ════════════════════════════════════════════════
# ── PUBLIC GENERAL KNOWLEDGE TOOLS ──
# ════════════════════════════════════════════════
def _extract_calc_expr(message):
    import re
    m = message.lower()
    if not any(k in m for k in ['hitung', 'calculate', 'calc', 'berapa', 'what is', 'hasil', '=']):
        return ''
    # Keep math-safe characters/functions only.
    expr = re.sub(r'[^0-9\.\+\-\*\/\%\^\(\)\, a-zA-Z_]', ' ', message)
    expr = expr.replace('^', '**')
    # Strip common words while preserving math functions/constants.
    for w in ['hitung', 'calculate', 'calc', 'berapa', 'what', 'is', 'hasil', 'dari', 'of', 'please', 'tolong']:
        expr = re.sub(r'\b' + re.escape(w) + r'\b', ' ', expr, flags=re.I)
    return expr.strip()

def _safe_calculate(message):
    import ast, math, operator
    expr = _extract_calc_expr(message)
    if not expr or not any(ch.isdigit() for ch in expr):
        return None
    allowed_funcs = {k: getattr(math, k) for k in ['sqrt','sin','cos','tan','log','log10','exp','floor','ceil','fabs']}
    allowed_names = {'pi': math.pi, 'e': math.e, **allowed_funcs}
    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
    }
    def ev(node):
        if isinstance(node, ast.Expression): return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops: return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops: return ops[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Name) and node.id in allowed_names: return allowed_names[node.id]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in allowed_funcs:
            return allowed_funcs[node.func.id](*[ev(a) for a in node.args])
        raise ValueError('unsupported expression')
    try:
        tree = ast.parse(expr, mode='eval')
        val = ev(tree)
        return {'expr': expr, 'result': val}
    except Exception:
        return None

def _github_search(message, limit=5):
    import urllib.request, urllib.parse, json, re
    m = re.search(r'(?:github search|search github|cari repo|repo github|github)[:\s]+(.+)', message, re.I)
    query = (m.group(1) if m else message).strip()
    if len(query) < 2:
        return None
    url = 'https://api.github.com/search/repositories?' + urllib.parse.urlencode({'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': limit})
    req = urllib.request.Request(url, headers={'User-Agent': 'GoldiePublicChat/1.0', 'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        items = []
        for repo in data.get('items', [])[:limit]:
            items.append({
                'name': repo.get('full_name'), 'stars': repo.get('stargazers_count'),
                'lang': repo.get('language'), 'url': repo.get('html_url'),
                'desc': repo.get('description') or ''
            })
        return {'query': query, 'items': items}
    except Exception as e:
        return {'query': query, 'error': str(e)[:120], 'items': []}

def _wiki_lookup(message):
    import urllib.request, urllib.parse, json, re
    m = re.search(r'(?:wiki|wikipedia|apa itu|siapa itu|what is|who is)[:\s]+(.+)', message, re.I)
    if not m:
        return None
    topic = m.group(1).strip().strip('?')[:120]
    if not topic:
        return None
    url = 'https://en.wikipedia.org/api/rest_v1/page/summary/' + urllib.parse.quote(topic.replace(' ', '_'))
    req = urllib.request.Request(url, headers={'User-Agent': 'GoldiePublicChat/1.0 (public knowledge lookup)'})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        return {'topic': data.get('title', topic), 'extract': data.get('extract', ''), 'url': data.get('content_urls', {}).get('desktop', {}).get('page', '')}
    except Exception as e:
        return {'topic': topic, 'error': str(e)[:120], 'extract': ''}

def _is_github_query(message):
    m = message.lower()
    return 'github search' in m or 'search github' in m or 'cari repo' in m or 'repo github' in m

def _is_wiki_query(message):
    m = message.lower()
    return any(k in m for k in ['wiki ', 'wikipedia', 'apa itu ', 'siapa itu ', 'what is ', 'who is '])

# ════════════════════════════════════════════════
# ── CHAT HANDLERS ──
# ════════════════════════════════════════════════

def handle_question(message, chat_context="", force_english_first=False):
    """Handle public chat — session context + internal KB + general knowledge + GitHub search + Wiki + calculator."""
    # 1) Exact/detail calculations: deterministic Python, not LLM guessing.
    calc = _safe_calculate(message)
    if calc:
        res = calc['result']
        if isinstance(res, float):
            pretty = (format(res, ',.12g'))
        else:
            pretty = str(res)
        calc_reply = ('Result: {}\n\nDetail: `{}` = `{}`'.format(pretty, calc['expr'], pretty) if force_english_first else 'Hasilnya: {}\n\nDetail: `{}` = `{}`'.format(pretty, calc['expr'], pretty))
        return {
            'reply': calc_reply,
            'cited': [], 'evidence_count': 0, 'kb_context_used': False,
            'tool_used': 'calculator'
        }

    # 2) GitHub repo search.
    gh = _github_search(message) if _is_github_query(message) else None
    if gh is not None:
        if gh.get('items'):
            lines = ['Top GitHub repos for "{}":'.format(gh['query'])]
            for i, r in enumerate(gh['items'], 1):
                lines.append('{}. {} — ⭐ {} — {} — {}'.format(i, r['name'], r['stars'], r.get('lang') or 'unknown', r.get('desc') or r.get('url')))
            return {'reply': '\n'.join(lines), 'cited': [r['name'] for r in gh['items']], 'evidence_count': len(gh['items']), 'kb_context_used': False, 'tool_used': 'github_search'}
        return {'reply': 'Gw nggak nemu hasil GitHub yang bagus buat query itu bro.', 'cited': [], 'evidence_count': 0, 'kb_context_used': False, 'tool_used': 'github_search'}

    # 3) Wiki lookup for public/general knowledge questions.
    wiki = _wiki_lookup(message) if _is_wiki_query(message) else None
    wiki_txt = ''
    if wiki and wiki.get('extract'):
        wiki_txt = 'WIKIPEDIA CONTEXT:\nTitle: {}\nSummary: {}\nURL: {}\n'.format(wiki.get('topic'), wiki.get('extract')[:1200], wiki.get('url'))

    # 4) Internal Goldie KB evidence.
    kb = load_json(KB_FILE)
    repos = kb.get('repos', {})
    evidence = []
    seen = set()
    tl = message.lower()

    for tk, info in kb.get('topic_index', {}).items():
        if tk in tl or tl in tk:
            for rn in info.get('repos', []):
                if rn in repos and rn not in seen:
                    seen.add(rn)
                    rd = repos[rn]
                    evidence.append({'repo': rn, 'summary': rd.get('summary', ''),
                        'patterns': rd.get('patterns', [])[:3],
                        'insights': rd.get('insights', [])[:2],
                        'depth': rd.get('study_level', 0)})

    if not evidence:
        words = [w for w in tl.split() if len(w) > 3]
        for rn, rd in repos.items():
            if rn in seen:
                continue
            searchable = ' '.join([rn, rd.get('summary',''),
                ' '.join(rd.get('patterns',[])), rd.get('lang',''),
                ' '.join(rd.get('best_practices',[]))]).lower()
            for w in words:
                if w in searchable and rn not in seen:
                    seen.add(rn)
                    evidence.append({'repo': rn, 'summary': rd.get('summary',''),
                        'patterns': rd.get('patterns',[])[:3],
                        'insights': rd.get('insights',[])[:2],
                        'depth': rd.get('study_level', 0)})
                    break

    ctx_parts = []
    for ev in evidence[:5]:
        ctx_parts.append('Repo: {}'.format(ev['repo']))
        if ev['summary']:
            ctx_parts.append('  Summary: {}'.format(ev['summary'][:180]))
        if ev['patterns']:
            ctx_parts.append('  Patterns: {}'.format('; '.join(ev['patterns'][:2])))
        if ev['insights']:
            ctx_parts.append('  Insights: {}'.format('; '.join(ev['insights'][:2])))
        ctx_parts.append('')
    kb_txt = '\n'.join(ctx_parts) if ctx_parts else kb_summary()

    stage = load_json(SF, {}).get('stage', 'puppy')
    sys_msg = ("You are Goldie, an autonomous AI agent with THREE knowledge sources: "
        "(0) the current chat history/session context, (1) your internal repository mastery KB, and (2) broad general world knowledge from your base model. "
        "You may answer normal general-knowledge questions even when the internal KB has no evidence. "
        "For follow-up requests like 'explain in detail', 'continue', 'what about that', or pronouns like 'it/that', ALWAYS answer about the previous chat topic from session context. "
        "For GitHub search or Wikipedia context, use the supplied tool context as fresh evidence. "
        "For calculations, rely on the calculator result when supplied. "
        "Music knowledge: explain melody, harmony, rhythm, tempo/BPM, key, chord progressions, arrangement, mixing, mastering, genres, song structure, hooks, lyrics, toplines, instrumentation, DAWs, synths, sampling, audio formats, and copyright-safe prompt craft. "
        "Spotify knowledge: explain tracks, albums, artists, playlists, genres, recommendations, release metadata, URIs/URLs, discovery workflows, playlist curation, and the difference between search/playback/library actions; do not claim you can control a user's Spotify unless an authenticated Spotify tool/session is available. "
        "Stage: {}. LANGUAGE RULE: If the prompt contains FIRST_REPLY_LANGUAGE_OVERRIDE, answer in English only regardless of user language. Otherwise match the user's language naturally: Indonesian if they write Indonesian; English if English; otherwise use their language. "
        "FORMAT RULES: Make every answer easy to read in a narrow mobile chat bubble. Use short paragraphs. Use blank lines between sections. Use bullets for lists. If explaining steps, use numbered lines. Avoid giant walls of text. Start with a short direct answer, then details. "
        "Keep it casual and helpful. Cite repos/tool context when used. Never reveal secrets, credentials, API keys, .env, server internals, or private tokens.").format(stage)
    if force_english_first:
        sys_msg += "\nIMPORTANT: This is the first assistant reply in this chat session. Reply in English only. After this first reply, language auto-detection may be used."

    full_context = ''
    if chat_context:
        full_context += 'CURRENT CHAT HISTORY / SESSION CONTEXT:\n' + chat_context[-3000:] + '\n\n'
    if wiki_txt:
        full_context += wiki_txt + '\n'
    full_context += 'GOLDIE INTERNAL KB CONTEXT:\n' + kb_txt
    llm_message = ('FIRST_REPLY_LANGUAGE_OVERRIDE: Answer this message in English only. User message: ' + message) if force_english_first else message
    reply = call_llm(llm_message, sys_msg + '\n\n' + full_context, tokens=650, temp=0.6)
    reply = format_public_reply(reply)

    return {
        'reply': reply,
        'cited': list(seen),
        'evidence_count': len(seen),
        'kb_context_used': bool(evidence),
        'tool_used': 'wikipedia' if wiki_txt else 'llm_general_kb'
    }

def handle_build_proposal(message):
    """Step 1: Generate project proposal for user to confirm."""
    kb = load_json(KB_FILE)
    repos = kb.get('repos', {})
    kb_context = "GOLDIE'S KB ({} repos studied):\n".format(len(repos))
    for rn, rd in list(repos.items())[:5]:
        if rd.get('patterns'):
            kb_context += "- {}: {}\n".format(rn, '; '.join(rd['patterns'][:2]))
    
    result = generate_project_proposal(message, kb_context)
    
    if result['status'] == 'proposal':
        data = result['data']
        proposal_text = data.get('proposal_text', "Gw mau bikin project ini:\n\n" +
            "📦 **{}**\n{}\n\nFiles:\n{}".format(
                data.get('name', ''),
                data.get('description', ''),
                '\n'.join(["- {}: {}".format(f.get('path', ''), f.get('description', '')) for f in data.get('files', [])])
            ) + "\n\n*Confirm atau mau diubah?*")
        
        return {
            'status': 'proposal',
            'reply': proposal_text,
            'data': data,
            'cited': [],
        }
    else:
        return {
            'status': 'error',
            'reply': "Sorry bro, gw gagal bikin proposal. Coba jelasin lagi project yang lo mau.",
            'cited': [],
        }

def handle_build_confirm(user_message, proposal_data):
    """Step 2: User confirms → generate files → build → push to GitLawb."""
    # Generate actual code
    files_result = generate_project_files(proposal_data)
    
    if files_result['status'] != 'files':
        return {
            'status': 'error',
            'reply': "Gagal generate code files bro. Coba lagi?",
            'cited': [],
        }
    
    file_contents = files_result['files']
    repo_name = proposal_data.get('name', 'goldie-project')
    description = proposal_data.get('description', '')
    
    # Add README if not in files
    if 'README.md' not in file_contents:
        file_contents['README.md'] = "# {}\n\n{}\n\nBuilt by Goldie Agent 🐕\n".format(
            repo_name, description)
    
    # Create GitLawb repo
    did = get_gitlawb_did()
    repo_result = create_gitlawb_repo(repo_name, description)
    
    # Push files
    push_result = push_project_to_gitlawb(repo_name, file_contents, did)
    
    if push_result['status'] == 'pushed':
        web_url = push_result['web_url']
        
        # Journal entry
        journal("🏗️", "Built project for user: " + repo_name,
                "URL: {}\nFiles: {}".format(web_url, ', '.join(file_contents.keys())))
        
        return {
            'status': 'built',
            'reply': "Done bro! 🎉\n\n📦 **{}**\n{}\n\n🔗 Repo: {}\n\nFiles: {}\n\nSilakan clone atau edit langsung di GitLawb!".format(
                repo_name, description, web_url, ', '.join(file_contents.keys())),
            'repo_url': web_url,
            'files': list(file_contents.keys()),
            'cited': [],
        }
    else:
        return {
            'status': 'error',
            'reply': "Repo created tapi push gagal bro: {}".format(push_result.get('error', 'unknown')),
            'cited': [],
        }
