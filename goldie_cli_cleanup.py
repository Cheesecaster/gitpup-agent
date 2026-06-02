#!/usr/bin/env python3
"""Goldie CLI workspace cleanup daemon.

Safe-by-default cleanup for public CLI sandbox junk:
- only touches /opt/gitpup/workspaces/user_* and /opt/gitpup/data/cli_memory/*.jsonl
- deletes old ZIP exports quickly
- deletes inactive workspaces after retention window
- deletes stale CLI memory after retention window
- optional pruning of heavy dependency dirs in inactive workspaces
- dry-run by default unless --apply is passed
"""
import argparse, json, os, shutil, sys, time
from pathlib import Path

ROOT = Path('/opt/gitpup')
WORKSPACES = (ROOT / 'workspaces').resolve()
CLI_MEMORY = (ROOT / 'data' / 'cli_memory').resolve()
LOG = ROOT / 'data' / 'logs' / 'cli_cleanup.log'
LOCK = ROOT / 'data' / 'locks' / 'cli_cleanup.lock'

HEAVY_DIRS = {'node_modules', '.venv', 'venv', '__pycache__', '.pytest_cache', '.next', 'dist', 'build'}


def now(): return time.time()
def age_seconds(path: Path): return max(0, now() - path.stat().st_mtime)
def fmt_age(sec):
    if sec < 3600: return f'{int(sec/60)}m'
    if sec < 86400: return f'{sec/3600:.1f}h'
    return f'{sec/86400:.1f}d'

def safe_child(parent: Path, path: Path) -> bool:
    try:
        rp = path.resolve()
        return rp == parent or str(rp).startswith(str(parent) + os.sep)
    except Exception:
        return False

def size_bytes(path: Path) -> int:
    if path.is_file():
        try: return path.stat().st_size
        except OSError: return 0
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for f in files:
            p = Path(root) / f
            try: total += p.stat().st_size
            except OSError: pass
    return total

def log_line(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + msg
    with LOG.open('a', encoding='utf-8') as f: f.write(line + '\n')
    print(line)

def acquire_lock(max_age=3600):
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.exists() and age_seconds(LOCK) < max_age:
        raise SystemExit('cleanup already running')
    LOCK.write_text(str(os.getpid()), encoding='utf-8')

def release_lock():
    try: LOCK.unlink()
    except FileNotFoundError: pass

def remove_path(path: Path, apply: bool, reason: str, stats: dict):
    if not safe_child(WORKSPACES, path) and not safe_child(CLI_MEMORY, path):
        log_line(f'SKIP unsafe path {path}')
        return
    b = size_bytes(path)
    stats['candidates'] += 1; stats['bytes_candidate'] += b
    log_line(('DELETE' if apply else 'DRY') + f' {path} bytes={b} reason={reason}')
    if apply:
        if path.is_dir(): shutil.rmtree(path)
        elif path.exists(): path.unlink()
        stats['deleted'] += 1; stats['bytes_deleted'] += b

def cleanup(args):
    stats = {'candidates':0,'deleted':0,'bytes_candidate':0,'bytes_deleted':0,'kept':0}
    if not WORKSPACES.exists():
        log_line('no workspaces root')
        return stats
    ws_keep = args.workspace_days * 86400
    mem_keep = args.memory_days * 86400
    zip_keep = args.zip_hours * 3600
    heavy_prune_age = args.heavy_hours * 3600

    for ws in sorted(WORKSPACES.iterdir()):
        if not ws.is_dir() or not ws.name.startswith('user_') or not safe_child(WORKSPACES, ws):
            continue
        # never follow symlink workspaces
        if ws.is_symlink():
            log_line(f'SKIP symlink workspace {ws}')
            continue
        age = age_seconds(ws)
        # delete stale exports first
        for z in list(ws.glob('tmp/*.zip')) + list(ws.glob('*.zip')):
            if z.is_file() and age_seconds(z) > zip_keep:
                remove_path(z, args.apply, f'zip older than {args.zip_hours}h', stats)
        # prune heavy dependency/build dirs after shorter inactivity
        if age > heavy_prune_age:
            for root, dirs, files in os.walk(ws, topdown=True, followlinks=False):
                rootp = Path(root)
                for d in list(dirs):
                    if d in HEAVY_DIRS:
                        target = rootp / d
                        if safe_child(WORKSPACES, target):
                            remove_path(target, args.apply, f'heavy dir inactive {fmt_age(age)}', stats)
                            dirs.remove(d)
        # delete whole inactive workspace after retention
        if age > ws_keep:
            remove_path(ws, args.apply, f'workspace inactive {fmt_age(age)} > {args.workspace_days}d', stats)
        else:
            stats['kept'] += 1

    if CLI_MEMORY.exists():
        for f in CLI_MEMORY.glob('*.jsonl'):
            if f.is_file() and safe_child(CLI_MEMORY, f) and age_seconds(f) > mem_keep:
                remove_path(f, args.apply, f'cli memory older than {args.memory_days}d', stats)

    log_line('SUMMARY ' + json.dumps(stats, sort_keys=True))
    return stats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='actually delete files; default dry-run')
    ap.add_argument('--workspace-days', type=float, default=float(os.environ.get('GOLDIE_CLI_WORKSPACE_DAYS','3')))
    ap.add_argument('--memory-days', type=float, default=float(os.environ.get('GOLDIE_CLI_MEMORY_DAYS','14')))
    ap.add_argument('--zip-hours', type=float, default=float(os.environ.get('GOLDIE_CLI_ZIP_HOURS','6')))
    ap.add_argument('--heavy-hours', type=float, default=float(os.environ.get('GOLDIE_CLI_HEAVY_HOURS','12')))
    args = ap.parse_args()
    acquire_lock()
    try:
        cleanup(args)
    finally:
        release_lock()

if __name__ == '__main__':
    main()
