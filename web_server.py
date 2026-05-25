import http.server
import json
import os

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = {"stage": "puppy", "score": 0.05, "repos": 0, "prs": 0, "projects": 0, "llm": True}
            self.wfile.write(json.dumps(data).encode())
        else:
            super().do_GET()
    def log_message(self, fmt, *args):
        pass

os.chdir('/opt/gitpup/web_dist')
srv = http.server.HTTPServer(('0.0.0.0', 5173), Handler)
print("GitPup web on :5173")
srv.serve_forever()
