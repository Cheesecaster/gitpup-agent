#!/usr/bin/env python3
"""Goldie Code - Multi-turn reasoning engine with KB enhancement"""

import json, os, re, subprocess, fnmatch, glob as glob_mod, sys
import urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

GITPUP = '/opt/gitpup'
sys.path.insert(0, GITPUP)

from goldie_kb_enhance import enhance_context, format_kb_context, load_kb

WIB = timezone(timedelta(hours=7))

# ── Load env ──
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

LLM_KEY = os.environ.get("LLM_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.6-plus")
LLM_MODEL_QUALITY = os.environ.get("LLM_MODEL_QUALITY", "qwen/qwen3.7-max")
LLM_MODEL_SPEED = os.environ.get("LLM_MODEL_SPEED", "qwen/qwen3.6-flash")


# ══════════════════════════════════════════════
# ── Tool Definitions ──
# ══════════════════════════════════════════════

class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self.workdir = os.getcwd()  # Track working directory
    
    def register(self, name, func, description, params=None):
        self.tools[name] = {
            'func': func,
            'description': description,
            'params': params or {}
        }
    
    def execute(self, name, args):
        if name not in self.tools:
            return {"error": "Unknown tool: %s" % name, "available": list(self.tools.keys())}
        try:
            result = self.tools[name]['func'](**args)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def get_schema_text(self):
        lines = []
        for name, info in self.tools.items():
            params = info['params']
            param_strs = ["    %s: %s" % (k, v) for k, v in params.items()]
            lines.append("  %s:" % name)
            lines.append("    description: %s" % info['description'])
            if param_strs:
                lines.append("    parameters:")
                lines.extend(param_strs)
        return '\n'.join(lines)


def create_tool_registry():
    reg = ToolRegistry()
    
    # ── read_file ──
    def read_file(path, offset=1, limit=500):
        """Read file content"""
        try:
            if not os.path.isabs(path):
                path = os.path.join(reg.workdir, path)
            
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                end = offset + limit
                selected = lines[offset - 1:end]
            
            # Add line numbers
            numbered = []
            for i, line in enumerate(selected, offset):
                numbered.append("%d|%s" % (i, line.rstrip()))
            
            return {
                "content": '\n'.join(numbered),
                "start_line": offset,
                "end_line": offset + len(selected) - 1,
                "total_lines": len(lines)
            }
        except Exception as e:
            return {"error": str(e), "path": path}
    
    reg.register('read_file', read_file, "Read file content with line numbers", 
                 {"path": "string - file path", "offset": "int (default 1)", "limit": "int (default 500)"})
    
    # ── write_file ──
    def write_file(path, content):
        """Write content to file (creates parent dirs)"""
        try:
            if not os.path.isabs(path):
                path = os.path.join(reg.workdir, path)
            
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
            
            lines = content.count('\n') + 1
            return {"ok": True, "path": path, "lines": lines}
        except Exception as e:
            return {"error": str(e)}
    
    reg.register('write_file', write_file, "Write content to file",
                 {"path": "string - file path", "content": "string - file content"})
    
    # ── patch_file ──
    def patch_file(path, old_string, new_string, line_hint=0):
        """Replace text in file"""
        try:
            if not os.path.isabs(path):
                path = os.path.join(reg.workdir, path)
            
            with open(path, 'r') as f:
                content = f.read()
            
            if old_string not in content:
                # Try to find similar text
                diff_ratio = 0
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    from difflib import SequenceMatcher
                    ratio = SequenceMatcher(None, line.strip(), old_string.strip()).ratio()
                    if ratio > diff_ratio:
                        diff_ratio = ratio
                        closest_line = i + 1
                
                return {"error": "Old string not found in file", "closest_line": closest_line, "closest_ratio": round(diff_ratio, 2)}
            
            new_content = content.replace(old_string, new_string, 1)
            with open(path, 'w') as f:
                f.write(new_content)
            
            return {"ok": True, "path": path}
        except Exception as e:
            return {"error": str(e)}
    
    reg.register('patch_file', patch_file, "Replace text in a file",
                 {"path": "string", "old_string": "exact text to find", "new_string": "replacement text"})
    
    # ── terminal ──
    def terminal(command, timeout=30):
        """Execute shell command"""
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, timeout=timeout, cwd=reg.workdir
            )
            return {
                "output": (result.stdout or "") + (result.stderr or ""),
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": "timeout after %ds" % timeout, "exit_code": -1}
        except Exception as e:
            return {"error": str(e), "exit_code": -1}
    
    reg.register('terminal', terminal, "Execute shell command",
                 {"command": "string - shell command", "timeout": "int seconds (default 30)"})
    
    # ── search_file ──
    def search_file(pattern, path, file_glob="*"):
        """Search for pattern in files"""
        try:
            if not os.path.isabs(path):
                path = os.path.join(reg.workdir, path)
            
            matches = []
            for root, dirs, files in os.walk(path):
                # Skip common dirs
                dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__', '.venv')]
                
                for fname in files:
                    if not fnmatch.fnmatch(fname, file_glob):
                        continue
                    
                    filepath = os.path.join(root, fname)
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                            for i, line in enumerate(f, 1):
                                if re.search(pattern, line, re.IGNORECASE):
                                    matches.append({
                                        "file": filepath.replace(reg.workdir + '/', ''),
                                        "line": i,
                                        "text": line.rstrip()[:200]
                                    })
                    except Exception:
                        continue
            
            return {"matches": matches[:50], "total": len(matches)}
        except Exception as e:
            return {"error": str(e)}
    
    reg.register('search_file', search_file, "Search for regex pattern in files",
                 {"pattern": "regex pattern", "path": "directory to search", "file_glob": "filter (default *)"})
    
    # ── list_files ──
    def list_files(path, recursive=False):
        """List files in directory"""
        try:
            if not os.path.isabs(path):
                path = os.path.join(reg.workdir, path)
            
            entries = []
            if recursive:
                for root, dirs, files in os.walk(path):
                    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__')]
                    rel = root.replace(path, '').lstrip('/') or '.'
                    for f in files[:20]:  # Limit
                        entries.append(os.path.join(rel, f) if rel != '.' else f)
                    if len(entries) > 100:
                        break
            else:
                for entry in sorted(os.listdir(path)):
                    full = os.path.join(path, entry)
                    etype = "d" if os.path.isdir(full) else "f"
                    size = os.path.getsize(full) if os.path.isfile(full) else 0
                    entries.append({"name": entry, "type": etype, "size": size})
            
            return {"path": path, "entries": entries}
        except Exception as e:
            return {"error": str(e)}
    
    reg.register('list_files', list_files, "List files in directory",
                 {"path": "directory path", "recursive": "bool (default false)"})
    
    # ── search_kb ──
    def search_kb(query, top_n=5):
        """Search knowledge base for patterns relevant to query"""
        enrichment = enhance_context(query)
        if not enrichment:
            return {"result": "No relevant patterns found in knowledge base"}
        return enrichment
    
    reg.register('search_kb', search_kb, "Search knowledge base for relevant patterns from studied repos",
                 {"query": "what you're trying to build/find", "top_n": "number of results (default 5)"})
    
    # ── get_repo_patterns ──
    def get_repo_patterns(repo_name):
        """Get all patterns and insights for a specific repo"""
        kb = load_kb()
        repos = kb.get('repos', {})
        
        if repo_name not in repos:
            # Try partial match
            matches = [r for r in repos.keys() if repo_name in r]
            if matches:
                repo_name = matches[0]
            else:
                return {"error": "Repo '%s' not in knowledge base" % repo_name, "available": list(repos.keys())}
        
        repo = repos[repo_name]
        return {
            "name": repo_name,
            "study_level": repo.get('study_level', 0),
            "language": repo.get('lang', ''),
            "stars": repo.get('stars', 0),
            "patterns": repo.get('patterns', []),
            "best_practices": repo.get('best_practices', []),
            "insights": repo.get('insights', []),
            "code_examples": repo.get('code_examples', [])[:5]
        }
    
    reg.register('get_repo_patterns', get_repo_patterns, "Get all patterns from a specific studied repo",
                 {"repo_name": "string - repo name"})
    
    return reg


# ══════════════════════════════════════════════
# ── Reasoning Engine ──
# ══════════════════════════════════════════════

class CodeReasoner:
    def __init__(self, registry):
        self.registry = registry
        self.history = []
        self.session_id = datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S")
    
    def get_system_prompt(self, kb_context=""):
        return """You are Goldie Code CLI, a powerful coding assistant with deep knowledge of software patterns.

## YOUR ADVANTAGE: KNOWLEDGE BASE
You have studied {n_patterns}+ technical patterns across {n_repos} GitHub repositories at depth.
When you write code, you don't guess — you draw from PROVEN patterns.

ALWAYS consult your knowledge base before writing code. Use tool: search_kb

## CRITICAL RULES
1. USE TOOLS — call tools to read files, search code, run commands
2. READ FIRST — understand the codebase before making changes
3. KB FIRST — search patterns before writing code
4. SHOW DIFFS — when patching code, show what you're changing
5. VERIFY — run commands to verify your changes work

## TOOL CALL FORMAT
When you need a tool, output this EXACTLY:

```toolcall
{{
  "name": "tool_name",
  "args": {{"key": "value"}}
}}
```

After getting tool results, continue reasoning.
When you have the final answer, respond with regular text explaining what you did.

## KNOWLEDGE BASE CONTEXT
When you find patterns in the KB, use them to inform your code decisions.
Cite which repo inspired your approach.

## AVAILABLE TOOLS
{tools}

## WORKING DIRECTORY
{workdir}

## PERSONALITY
Be direct, competent, and pragmatic. You have strong opinions backed by research.
When explaining code decisions, reference the patterns that informed you.
Use technical precision. No hand-holding, no disclaimers, no "I think". State what you do.""" .format(
            n_patterns=len(load_kb().get('repos', {})),
            n_repos=len(load_kb().get('repos', {})),
            tools=self.registry.get_schema_text(),
            workdir=self.registry.workdir
        ) + (("\n\n" + kb_context) if kb_context else "")
    
    def do_llm(self, messages, tokens=4000, temp=0.3):
        """Call LLM"""
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            json.dumps({
                "model": LLM_MODEL_QUALITY,
                "messages": messages,
                "max_tokens": tokens,
                "temperature": temp
            }).encode())
        req.add_header("Content-Type", "application/json")
        if LLM_KEY:
            req.add_header("Authorization", "Bearer " + LLM_KEY)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
                return resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            return "[LLM Error: %s]" % str(e)[:100]
    
    def parse_tool_calls(self, text):
        """Parse tool calls from LLM response"""
        calls = []
        
        # Find ```toolcall blocks
        pattern = r'```toolcall\s*\n(.*?)\n```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                call = json.loads(match.strip())
                if 'name' in call and 'args' in call:
                    calls.append(call)
            except json.JSONDecodeError:
                # Try to fix common issues
                try:
                    fixed = match.strip().replace("'", '"')
                    call = json.loads(fixed)
                    calls.append(call)
                except:
                    pass
        
        return calls
    
    def execute_tool(self, call):
        """Execute a tool call and return formatted result"""
        name = call['name']
        args = call.get('args', {})
        result = self.registry.execute(name, args)
        return {"tool": name, "result": result}
    
    def strip_tool_calls(self, text):
        """Remove tool calls from text, leaving only the final response"""
        return re.sub(r'```toolcall\s*\n(.*?)\n```', '', text, flags=re.DOTALL).strip()
    
    def solve(self, user_message, max_iterations=10, show_progress=True):
        """Main reasoning loop"""
        
        # Enhance with KB
        if show_progress:
            print("> Enriching with knowledge base...")
        
        enrichment = enhance_context(user_message)
        kb_context = format_kb_context(enrichment)
        
        # Build system prompt
        system = self.get_system_prompt(kb_context)
        
        # Add KB enrichment as initial context
        messages = [
            {"role": "system", "content": system},
        ]
        
        # Add session history (last 3 exchanges)
        if self.history:
            for h in self.history[-6:]:
                messages.append(h)
        
        messages.append({"role": "user", "content": user_message})
        
        all_responses = []
        for iteration in range(max_iterations):
            # Call LLM
            response = self.do_llm(messages, tokens=4000)
            
            # Check for tool calls
            tool_calls = self.parse_tool_calls(response)
            
            if tool_calls:
                # Execute tools and continue
                for tc in tool_calls:
                    name = tc['name']
                    args = tc.get('args', {})
                    args_str = ', '.join(['%s: %s' % (k, repr(v)[:50]) for k, v in args.items()])
                    
                    print("> Tool: %s(%s)" % (name, args_str))
                    
                    tool_result = self.execute_tool(tc)
                    result_str = json.dumps(tool_result['result'], indent=2)[:2000]
                    
                    # Inject tool result back into conversation
                    messages.append({
                        "role": "assistant",
                        "content": "[Tool: %s]\n```toolcall\n%s\n```" % (name, json.dumps(tc))
                    })
                    messages.append({
                        "role": "user",
                        "content": "Tool result:\n```\n%s\n```\n%s" % (result_str, 
                            "Continue with your reasoning. If you're done, provide your final response without any tool calls." if iteration < max_iterations - 1 else "This was your last tool call. Provide your final response now.")
                    })
                    
                    all_responses.append("Tool: %s → %s" % (name, json.dumps(tool_result['result'])[:300]))
            else:
                # No tool calls - this is the final response
                all_responses.append(response)
                break
        
        else:
            # Max iterations
            all_responses.append("[Max iterations reached. Current progress above.]")
        
        # Save to history
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": all_responses[-1] if all_responses else "[No response]"})
        
        return {
            'response': self.strip_tool_calls(all_responses[-1]) if all_responses else "[No response]",
            'steps': all_responses[:-1],  # All intermediate steps
            'iterations': iteration + 1
        }
    
    def process(self, message, show_progress=True):
        """Simplified API: returns just the response"""
        result = self.solve(message, show_progress=show_progress)
        return result['response']
