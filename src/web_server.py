#!/usr/bin/env python3
"""GitPup web server: static HTML + live status API."""
import http.server, socketserver, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / 'web'
SRC_DIR = ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))
os.chdir(str(WEB_DIR))

class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/status':
            try:
                from dotenv import load_dotenv
                load_dotenv(str(ROOT / '.env'))
                from core.agent import GitPupAgent
                a = GitPupAgent()
                d = dict(stage=a.state.stage, score=round(a.get_good_boy_score(),3),
                         repos=a.state.repos_scanned, prs=a.state.prs_reviewed,
                         projects=a.state.projects_led, llm=bool(a.llm is not None))
            except Exception as e:
                d = dict(stage='puppy', score=0.05, repos=0, prs=0, projects=0, error=str(e))
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps(d).encode())
        else:
            super().do_GET()
    def log_message(self, *a): pass

PORT = int(os.environ.get('WEB_PORT', '5173'))
sock = socketserver.TCPServer(("", PORT), H)
print(f"GitPup web :{PORT}", flush=True)
sock.serve_forever()