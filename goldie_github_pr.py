#!/usr/bin/env python3
"""Safe GitHub PR proof queue for Goldie self-patches.

Default behavior is side-effect safe: record self-patch commits as PR candidates.
If GOLDIE_GITHUB_PR_SELF_PATCH=true and a GitHub token is available, callers may
use create_pr_for_head() to push a branch and open a draft PR. This keeps public
proof GitHub-centered without silently pushing unsafe code to main.
"""
from __future__ import annotations
import json, os, re, subprocess, time, urllib.request
from pathlib import Path

ROOT = Path('/opt/gitpup')
DATA = ROOT / 'data'
QUEUE = DATA / 'self_patch_pr_queue.jsonl'
LOG = DATA / 'self_patch_pr.log'

SENSITIVE_RE = re.compile(r'(^\.env$|^\.git-credentials$|^\.venv/|^__pycache__/|\.pyc$|^data/(?!self_patch_pr_queue\.jsonl|self_patch_pr\.log)|^workspaces/|^projects/|\.key$|id_rsa|\.ssh/)')

def _log(msg: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    line = time.strftime('[%Y-%m-%d %H:%M:%S] ') + msg
    print(line)
    with LOG.open('a', encoding='utf-8') as f: f.write(line+'\n')

def _run(args, timeout=30):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return {'ok': r.returncode == 0, 'code': r.returncode, 'stdout': (r.stdout or '').strip(), 'stderr': (r.stderr or '').strip()}

def _append(obj: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with QUEUE.open('a', encoding='utf-8') as f: f.write(json.dumps(obj, ensure_ascii=False) + '\n')

def current_head() -> str:
    return _run(['git','rev-parse','--short','HEAD']).get('stdout','')

def changed_files_for_head() -> list[str]:
    out = _run(['git','diff-tree','--no-commit-id','--name-only','-r','HEAD']).get('stdout','')
    return [x for x in out.splitlines() if x.strip()]

def queue_self_patch_pr(commit_msg: str, commit_sha: str | None=None, source: str='self_modify') -> dict:
    sha = commit_sha or current_head()
    files = changed_files_for_head()
    blocked = [f for f in files if SENSITIVE_RE.search(f)]
    event = {'ts': time.time(), 'date': time.strftime('%Y-%m-%d'), 'kind': 'self_patch_pr_candidate', 'source': source, 'commit': sha, 'commit_msg': commit_msg[:300], 'files': files[:80], 'blocked_files': blocked, 'public_write_enabled': os.environ.get('GOLDIE_GITHUB_PR_SELF_PATCH','false').lower() in ('1','true','yes'), 'status': 'blocked_sensitive_files' if blocked else 'queued_review'}
    _append(event)
    _log('queued self-patch PR candidate %s files=%d status=%s' % (sha, len(files), event['status']))
    return event

def _github_token() -> str:
    return os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN') or ''

def create_pr_for_head(title: str, body: str, draft: bool=True) -> dict:
    """Push HEAD to a proof branch and open a draft PR. Requires explicit env enable."""
    if os.environ.get('GOLDIE_GITHUB_PR_SELF_PATCH','false').lower() not in ('1','true','yes'):
        return {'ok': False, 'reason': 'GOLDIE_GITHUB_PR_SELF_PATCH not enabled'}
    token = _github_token()
    if not token:
        return {'ok': False, 'reason': 'missing GITHUB_TOKEN/GH_TOKEN'}
    files = changed_files_for_head()
    blocked = [f for f in files if SENSITIVE_RE.search(f)]
    if blocked:
        return {'ok': False, 'reason': 'sensitive/generated files in commit', 'blocked_files': blocked}
    sha = current_head(); branch = 'goldie/self-patch-' + sha
    _run(['git','branch','-f', branch, 'HEAD'])
    push = _run(['git','push','github', branch + ':' + branch, '--force-with-lease'], timeout=60)
    if not push['ok']:
        return {'ok': False, 'reason': 'push failed', 'push': push}
    payload = json.dumps({'title': title[:180], 'body': body[:6000], 'head': branch, 'base': 'main', 'draft': draft}).encode()
    req = urllib.request.Request('https://api.github.com/repos/Cheesecaster/gitpup-agent/pulls', data=payload, headers={'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json', 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data=json.loads(r.read().decode())
        _log('created GitHub draft PR #%s for %s' % (data.get('number'), sha))
        return {'ok': True, 'number': data.get('number'), 'url': data.get('html_url'), 'branch': branch, 'commit': sha}
    except Exception as e:
        return {'ok': False, 'reason': str(e)[:300], 'branch': branch, 'commit': sha}

if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--queue', action='store_true')
    ap.add_argument('--msg', default='Goldie self-patch')
    ap.add_argument('--create-pr', action='store_true')
    ns=ap.parse_args()
    if ns.create_pr:
        print(json.dumps(create_pr_for_head(ns.msg, 'Goldie autonomous self-patch proof. Queued via safe PR module.'), indent=2))
    else:
        print(json.dumps(queue_self_patch_pr(ns.msg), indent=2))
