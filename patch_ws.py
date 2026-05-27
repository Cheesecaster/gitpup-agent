#!/usr/bin/env python3
"""Patch web_server.py for personality, soul, and story endpoints"""

path = '/opt/gitpup/web_server.py'
with open(path) as f:
    content = f.read()

# Add /api/personality, /api/soul, /story endpoints before /api/kb
api_block = """        elif p == '/api/personality':
            try:
                _json_resp(self, pers.get_radar())
            except:
                _json_resp(self, {'labels': [], 'data': [], 'colors': [], 'keys': []})
        elif p == '/api/soul':
            sc = ''
            try:
                with open('/opt/gitpup/data/soul.md', encoding='utf-8') as f:
                    sc = f.read()
            except:
                pass
            _json_resp(self, {'content': sc})
        elif p == '/api/story':
            _json_resp(self, {'ok': True, 'url': '/story'})
        elif p == '/story':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                with open('/opt/gitpup/web_dist/story.html', 'rb') as f:
                    self.wfile.write(f.read())
            except Exception:
                self.wfile.write(b'<h1>Story not found</h1>')
            return
"""

# Insert before /api/kb
if "/api/personality" not in content:
    marker = "elif p == '/api/kb':"
    content = content.replace(marker, api_block + marker, 1)
    print("Added: /api/personality, /api/soul, /story endpoints")
else:
    print("Endpoints already exist")

# Add import personality
if "import personality" not in content:
    content = content.replace(
        "import chat_pipeline as cp",
        "import chat_pipeline as cp\nimport personality as pers"
    )
    print("Added: import personality")
else:
    print("Import already exists")

with open(path, 'w') as f:
    f.write(content)
print("web_server.py patched!")
