#!/usr/bin/env python3
"""Goldie CLI v2.0 - Interactive coding assistant with deep KB integration"""

import sys, os, json, readline, argparse, shutil
from datetime import datetime, timezone, timedelta

GITPUP = '/opt/gitpup'
sys.path.insert(0, GITPUP)

# Load environment
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

from goldie_code import create_tool_registry, CodeReasoner

WIB = timezone(timedelta(hours=7))

# ── ANSI colors ──
C_RESET  = '\033[0m'
C_BOLD   = '\033[1m'
C_DIM    = '\033[2m'
C_GOLD   = '\033[33m'
C_GREEN  = '\033[32m'
C_CYAN   = '\033[36m'
C_RED    = '\033[31m'
C_BLUE   = '\033[34m'
C_GRAY   = '\033[90m'

def c(text, color):
    return "%s%s%s" % (color, text, C_RESET)

def print_banner():
    banner = """
╔══════════════════════════════════════════════╗
║  🐶 Goldie Code CLI v2.0                     ║
║  Deep KB-powered coding assistant            ║
║                                              ║
║  Type /help              - list commands     ║
║  Type your question      - start coding      ║
║  Ctrl+C or /quit         - exit              ║
╚══════════════════════════════════════════════╝
"""
    print(c(banner, C_GOLD))

def load_status():
    try:
        with open('%s/data/state/status.json' % GITPUP) as f:
            return json.load(f)
    except:
        return {}

def cmd_status():
    """Show agent status"""
    st = load_status()
    stage = st.get('stage', '?')
    print()
    print(c("  [Agent Status]", C_BOLD))
    print("  Stage:       %s" % c(stage, C_CYAN))
    print("  Runs:        %d" % st.get('runs', 0))
    print("  Self-mods:   %d" % st.get('self_modifications', 0))
    print("  PRs created: %d" % st.get('prs_created', 0))
    
    # KB stats
    try:
        kb = json.load(open('%s/data/knowledge.json' % GITPUP))
        n_repos = len(kb.get('repos', {}))
        n_patterns = sum(len(r.get('patterns', [])) for r in kb['repos'].values())
        n_insights = sum(len(r.get('insights', [])) for r in kb['repos'].values())
        print("  KB repos:    %d" % n_repos)
        print("  KB patterns: %d" % n_patterns)
        print("  KB insights: %d" % n_insights)
    except:
        pass
    print()

def cmd_kb():
    """Show knowledge base"""
    try:
        kb = json.load(open('%s/data/knowledge.json' % GITPUP))
    except:
        print(c("  KB not available", C_RED))
        return
    
    repos = kb.get('repos', {})
    print()
    print(c("  [Knowledge Base]", C_BOLD))
    print("  Repos: %d | Patterns: %d | Insights: %d" % (
        len(repos),
        sum(len(r.get('patterns', [])) for r in repos.values()),
        sum(len(r.get('insights', [])) for r in repos.values())
    ))
    print()
    print(c("  Studied Repos:", C_DIM))
    for name, data in sorted(repos.items(), key=lambda x: x[1].get('study_level', 0), reverse=True):
        level = data.get('study_level', 0)
        stars = data.get('stars', 0)
        patterns = len(data.get('patterns', []))
        lang = data.get('lang', '?')
        bar = '█' * level + '░' * (4 - level)
        print("  [%s] %s" % (bar, c(name, C_GOLD)))
        print("     %s | %d★ | %d patterns" % (lang, stars, patterns))

def cmd_persona():
    """Show personality"""
    try:
        data = json.load(open('%s/data/personality.json' % GITPUP))
    except:
        print(c("  Personality data not available", C_RED))
        return
    
    dims = data.get('dimensions', {})
    print()
    print(c("  [Personality Radar]", C_BOLD))
    for key, info in dims.items():
        val = info.get('value', 0) if isinstance(info, dict) else 0
        bar = '█' * int(val * 20) + '░' * (20 - int(val * 20))
        label = (info.get('label', '') if isinstance(info, dict) else key).capitalize()
        print("  %s %s %.2f" % (label.ljust(12), c(bar, C_GREEN), val))
    print()

def cmd_study(force=False):
    """Trigger study phase"""
    print(c("\n  [Starting study phase...]\n", C_CYAN))
    import subprocess
    cmd = ['python3', '%s/agent.py' % GITPUP, '--phase', 'study']
    if force:
        cmd.append('--force')
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=GITPUP, timeout=240)
    
    # Extract key lines
    for line in result.stdout.split('\n'):
        line = line.strip()
        if any(kw in line for kw in ['STUDY', 'PASS', 'patterns', 'insights', 'Done in', '===']):
            print("  " + line)
    
    if result.returncode != 0:
        print(c("  [Error] %s" % result.stderr[:200], C_RED))

def cmd_contribute(force=False):
    """Trigger contribute phase"""
    print(c("\n  [Starting contribute phase...]\n", C_CYAN))
    import subprocess
    cmd = ['python3', '%s/agent.py' % GITPUP, '--phase', 'contribute']
    if force:
        cmd.append('--force')
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=GITPUP, timeout=240)
    
    for line in result.stdout.split('\n'):
        line = line.strip()
        if any(kw in line for kw in ['CONTRIBUTE', 'PR', 'Fix', 'Done in', '===', 'fork', '✓']):
            print("  " + line)

def cmd_workdir(registry, path):
    """Change working directory"""
    if not path:
        print("  Working directory: %s" % c(registry.workdir, C_CYAN))
        return
    
    new_path = os.path.expanduser(path)
    if not os.path.isabs(new_path):
        new_path = os.path.abspath(os.path.join(registry.workdir, new_path))
    
    if not os.path.isdir(new_path):
        print(c("  Error: %s is not a directory" % new_path, C_RED))
        return
    
    registry.workdir = new_path
    print("  Working directory: %s" % c(new_path, C_CYAN))

def cmd_help():
    print(c("""
  [Goldie CLI Commands]

  Status & Info
    /status              Agent status, runs, self-mods, KB stats
    /kb                  Knowledge base overview
    /persona             Personality radar

  Autonomous Phases
    /study               Trigger study phase (learns from GitHub repos)
    /study --force       Force study (ignore cooldown)
    /contribute          Trigger contribute phase (opens PRs)
    /contribute --force  Force contribute (ignore quota)

  Working Directory
    /cd <path>           Change working directory
    /cd                  Show current directory

  Coding
    /ask <question>      Ask Goldie a coding question (uses KB)
    /fix <file>          Ask Goldie to fix a file
    /build <desc>        Describe what you want, Goldie builds it

  Other
    /help                This help
    /quit, /exit         Exit

  Direct Mode
    Just type your question or request directly.
    Goldie will use tools to read files, search code,
    execute commands, and leverage the knowledge base.
""", C_DIM))

def run_agent(force=False):
    """Full agent run"""
    print(c("\n  [Running full agent...]\n", C_CYAN))
    import subprocess
    cmd = ['python3', '%s/agent.py' % GITPUP, '--force'] if force else ['python3', '%s/agent.py' % GITPUP]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=GITPUP, timeout=300)
    
    for line in result.stdout.split('\n'):
        line = line.strip()
        if any(kw in line for kw in ['===', 'Done in', 'STUDY', 'CONTRIBUTE', 'SELF', 'EVOLVE', '✓', 'PR']):
            print("  " + line)

def main():
    parser = argparse.ArgumentParser(description="Goldie CLI v2.0")
    parser.add_argument('message', nargs='*', help="Question or request")
    parser.add_argument('-q', '--quiet', action='store_true', help="Suppress progress output")
    parser.add_argument('--workdir', '-w', default=os.getcwd(), help="Working directory")
    parser.add_argument('--agent', action='store_true', help="Run full autonomous agent")
    parser.add_argument('--force', action='store_true', help="Force (bypass cooldown)")
    args = parser.parse_args()
    
    # Initialize
    registry = create_tool_registry()
    if args.workdir:
        registry.workdir = os.path.abspath(args.workdir)
    
    reasoner = CodeReasoner(registry)
    
    # One-shot mode
    if args.agent:
        run_agent(args.force)
        return
    
    if args.message:
        message = ' '.join(args.message)
        
        # Parse commands in one-shot mode too
        if message.startswith('/'):
            parts = message.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ''
            
            if cmd in ('/help',):
                cmd_help()
            elif cmd == '/status':
                cmd_status()
            elif cmd == '/kb':
                cmd_kb()
            elif cmd == '/persona':
                cmd_persona()
            elif cmd == '/study':
                cmd_study('--force' in message)
            elif cmd == '/contribute':
                cmd_contribute('--force' in message)
            elif cmd in ('/cd', '/workdir'):
                cmd_workdir(registry, arg)
            elif cmd == '/agent':
                run_agent('--force' in message)
            else:
                print("Unknown command: %s" % cmd)
            return
        
        # Regular query
        result = reasoner.solve(message, show_progress=not args.quiet)
        if 'response' in result:
            print()
            for rline in result['response'].split('\n'):
                print("  " + rline)
        return
    
    # Interactive mode
    print_banner()
    cmd_status()
    
    while True:
        try:
            # Readline with workdir in prompt
            wdir_short = os.path.basename(registry.workdir) if registry.workdir != os.path.expanduser('~') else '~'
            prompt = c("goldie", C_GOLD) + c("(%s)" % wdir_short, C_GRAY) + " > "
            line = input(prompt).strip()
            
            if not line:
                continue
            
            # ── Command parsing ──
            if line.startswith('/'):
                parts = line.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ''
                
                if cmd in ('/quit', '/exit', '/q'):
                    print(c("\n  👋 Bye!\n", C_GOLD))
                    break
                
                elif cmd == '/help':
                    cmd_help()
                
                elif cmd == '/status':
                    cmd_status()
                
                elif cmd == '/kb':
                    cmd_kb()
                
                elif cmd == '/persona':
                    cmd_persona()
                
                elif cmd == '/study':
                    cmd_study('--force' in line)
                
                elif cmd == '/contribute':
                    cmd_contribute('--force' in line)
                
                elif cmd in ('/cd', '/workdir'):
                    cmd_workdir(registry, arg)
                
                elif cmd == '/agent':
                    run_agent('--force' in line)
                
                elif cmd == '/ask':
                    if arg:
                        reasoner.solve(arg, show_progress=True)
                    else:
                        print(c("  Usage: /ask <question>", C_DIM))
                
                elif cmd == '/fix':
                    if arg:
                        reasoner.solve("Fix issues in this file: %s" % arg, show_progress=True)
                    else:
                        print(c("  Usage: /fix <file_path>", C_DIM))
                
                elif cmd == '/build':
                    if arg:
                        reasoner.solve("Build this: %s" % arg, show_progress=True)
                    else:
                        print(c("  Usage: /build <description of what you want>", C_DIM))
                
                else:
                    print(c("  Unknown command: %s (type /help)" % cmd, C_RED))
            
            # ── Direct question ──
            else:
                result = reasoner.solve(line, show_progress=True)
                if result['steps']:
                    print()
                    print(c("  [%d tool calls executed]" % len(result['steps']), C_DIM))
                
                # Print response
                print()
                # Indent the response
                for rline in result['response'].split('\n'):
                    print("  " + rline)
                print()
        
        except KeyboardInterrupt:
            print(c("\n\n  👋 Bye!\n", C_GOLD))
            break
        except EOFError:
            break
        except Exception as e:
            print(c("\n  [Error: %s]" % str(e), C_RED))

if __name__ == '__main__':
    main()
