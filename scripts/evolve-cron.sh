#!/bin/bash
cd /opt/gitpup
[ -f ".env" ] && export $(grep -v '^#' .env | xargs 2>/dev/null || true)
NOW=$(date "+%Y-%m-%d %H:%M:%S")
echo "" >> data/evolve.log
echo "=== $NOW ===" >> data/evolve.log
if [ -f "data/state/status.json" ]; then
    python3 -c "
import json,time
try:
    s=json.load(open('data/state/status.json'))
    gap=time.time()-s.get('last_run',0)
    if gap<10800:
        print(f'Cooldown: {int((10800-gap)/60)}m remaining')
        exit(0)
except: pass" 2>/dev/null || true
fi
python3 agent.py --all --force >> data/evolve.log 2>&1
echo "[$NOW] Done" >> data/evolve.log
