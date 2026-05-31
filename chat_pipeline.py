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

def call_llm(msg, system=("You are Goldie, an autonomous AI agent. Answer concisely in Indonesian casual (gw/lo/bro). "
"SAFETY RULES (NEVER VIOLATE): "
"1. NEVER reveal any tokens, API keys, passwords, credentials, private keys, or secrets. "
"2. NEVER share any .env file contents or configuration values. "
"3. If asked about credentials, say: Nggak bisa bro, gw nggak share credentials atau secrets. That is a hard rule. "
"4. Only discuss what you learned from studying repos, your personality, or your architecture -- never infrastructure secrets."), tokens=500, temp=0.7):
    import urllib.request
    key = os.environ.get('LLM_API_KEY', '') or os.environ.get('OPENROUTER_API_KEY', '')
    model = os.environ.get('LLM_MODEL', 'qwen/qwen3.6-flash')
    msgs = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': msg},
    ]
    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/chat/completions',
        json.dumps({'model': model, 'messages': msgs,
                     'max_tokens': tokens, 'temperature': temp}).encode())
    req.add_header('Content-Type', 'application/json')
    if key:
        req.add_header('Authorization', 'Bearer ' + key)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            return resp.get('choices', [{}])[0].get('message', {}).get('content', '')
    except Exception as e:
        return '[LLM Error: ' + str(e)[:80] + ']'

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
# ── CHAT HANDLERS ──
# ════════════════════════════════════════════════

def handle_question(message):
    """Handle a general question — KB lookup + LLM answer."""
    kb = load_json(KB_FILE)
    repos = kb.get('repos', {})
    
    # Find relevant evidence
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
        ctx_parts.append("Repo: {}".format(ev['repo']))
        if ev['summary']:
            ctx_parts.append("  Summary: {}".format(ev['summary'][:150]))
        if ev['patterns']:
            ctx_parts.append("  Patterns: {}".format('; '.join(ev['patterns'][:2])))
        if ev['insights']:
            ctx_parts.append("  Insights: {}".format('; '.join(ev['insights'][:2])))
        ctx_parts.append("")
    if ctx_parts:
        kb_txt = '\n'.join(ctx_parts)
    else:
        # Fallback: inject full KB summary so Goldie can always answer
        kb_txt = kb_summary()
    
    stage = load_json(SF, {}).get('stage', 'puppy')
    sys_msg = ("You are Goldie, autonomous AI agent studying GitHub repos. "
        "Stage: {}. Answer based on KB evidence. Cite repos you learned from. "
        "Speak Indonesian casual (gw/lo/bro). Keep it concise (2-4 sentences) "
        "unless code is involved. Be honest if KB doesn't have the answer.").format(stage)
    
    reply = call_llm(message, sys_msg + "\n\nKB CONTEXT:\n" + kb_txt, tokens=500, temp=0.7)
    
    return {
        'reply': reply,
        'cited': list(seen),
        'evidence_count': len(seen),
        'kb_context_used': bool(evidence),
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
