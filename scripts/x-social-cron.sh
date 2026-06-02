#!/usr/bin/env bash
set -euo pipefail
cd /opt/gitpup
export PATH="$PATH:/usr/local/bin:/root/.local/bin:$HOME/.local/bin"
set -a
[ -f ./.env ] && . ./.env || true
set +a
# Full autonomous mode. If xurl/auth is missing, candidates are generated and queued locally without public writes.
python3 goldie_x_social.py --scan --publish >> /opt/gitpup/data/x_social.log 2>&1
