"""Simple static web server for GitPup dashboard."""

import http.server
import socketserver
import json
import os
import sys
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(Path(__file__).resolve().parent)

# Try to import agent for live stats
try:
    from dotenv import load_dotenv
    load_dotenv('/opt/gitpup/.env')
    from core.agent import GitPupAgent
    HAS_AGENT = True
except Exception:
    HAS_AGENT = False

def get_status():
    """Return agent status for API."""
    if not HAS_AGENT:
        return {"error": "Agent not available", "stage": "Puppy", "score": 0.05, "repos": 0, "prs": 0}
    try:
        agent = GitPupAgent()
        return {
            "stage": agent.state.stage,
            "score": agent.get_good_boy_score(),
            "repos": agent.state.repos_scanned,
            "prs": agent.state.prs_reviewed,
            "projects": agent.state.projects_led,
            "llm": getattr(agent, 'llm', None) is not None,
        }
    except Exception as e:
        return {"error": str(e), "stage": "Puppy", "score": 0.05}


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/status':
            status = get_status()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())
        else:
            super().do_GET()

    def log_message(self, format, *args):
        # Suppress default logging
        pass


if __name__ == '__main__':
    port = int(os.getenv('WEB_PORT', '5173'))
    web_dir = Path(__file__).resolve().parent.parent
    os.chdir(web_dir)
    
    print(f"🐶 GitPup web server starting on port {port}")
    print(f"   Serving: {web_dir / 'web' / 'index.html'}")
    
    with socketserver.TCPServer(("", port), Handler) as httpd:
        httpd.serve_forever()
