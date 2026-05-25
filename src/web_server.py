import http.server, socketserver, json, os, sys
from pathlib import Path
os.chdir(Path(__file__).resolve().parent)
sys.path.insert(0, str(Path('/opt/gitpup/src')))

class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/api/status':
            try:
                from dotenv import load_dotenv; load_dotenv('/opt/gitpup/.env')
                from core.agent import GitPupAgent
                a=GitPupAgent()
                d={'stage':a.state.stage,'score':a.get_good_boy_score(),'repos':a.state.repos_scanned,'prs':a.state.prs_reviewed,'projects':a.state.projects_led}
            except: d={'stage':'Puppy','score':.05,'repos':0,'prs':0,'projects':0}
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps(d).encode())
        else: super().do_GET()
    def log_message(self, *a): pass

with socketserver.TCPServer(('',5173),H) as s: print('🐶 GitPup web :5173'); s.serve_forever()
