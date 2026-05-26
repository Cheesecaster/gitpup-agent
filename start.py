#!/usr/bin/env python3
"""GitPup server starter - loads .env then starts web_server.py as subprocess."""
import os, subprocess, sys
from pathlib import Path

ROOT = Path('/opt/gitpup')
os.chdir(str(ROOT))

# Load .env
from dotenv import load_dotenv
load_dotenv(str(ROOT / '.env'))

# Show what's loaded
print(f"LLM_API_KEY: {'yes' if os.environ.get('LLM_API_KEY') else 'NO'}", flush=True)
print(f"LLM_MODEL: {os.environ.get('LLM_MODEL', 'not set')}", flush=True)

# Start web_server.py as subprocess (it will run in correct dir)
os.chdir(str(ROOT))
os.execv(sys.executable, [sys.executable, str(ROOT / 'src/web_server.py')])
