#!/usr/bin/env python3
"""GitPup web server startup script with proper env loading"""
import os, subprocess, time

# Read .env
env = {}
with open('/opt/gitpup/.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

# Merge with current environment
child_env = os.environ.copy()
child_env.update(env)

# Start web server with env
proc = subprocess.Popen(
    ['python3', '/opt/gitpup/web_server.py'],
    cwd='/opt/gitpup/web_dist',
    env=child_env,
    stdout=open('/tmp/web_server.log', 'w'),
    stderr=subprocess.STDOUT,
)
print(f"Web server started with PID {proc.pid}")
print(f"LLM_KEY set: {'YES' if env.get('LLM_API_KEY') else 'NO'}")
print(f"GH_TOKEN set: {'YES' if env.get('GH_TOKEN') else 'NO'}")
print(f"Model: {env.get('LLM_MODEL', 'default')}")
