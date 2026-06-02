#!/bin/bash
set -u
cd /opt/gitpup
mkdir -p data/locks data/logs
LOCK="data/locks/evolve-cron.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Skip: evolve already running" >> data/evolve.log
    exit 0
fi
set -a
[ -f ".env" ] && . ./.env 2>/dev/null || true
set +a
NOW=$(date "+%Y-%m-%d %H:%M:%S")
echo "" >> data/evolve.log
echo "=== $NOW ===" >> data/evolve.log
if [ -f "data/state/status.json" ]; then
    python3 - <<'PY' >> data/evolve.log 2>&1
import json,time,sys
try:
    s=json.load(open('data/state/status.json'))
    gap=time.time()-float(s.get('last_run',0) or 0)
    if gap < 1200:
        print('Cooldown: %dm remaining' % int((1200-gap)/60))
        sys.exit(10)
except SystemExit:
    raise
except Exception:
    pass
PY
    code=$?
    if [ "$code" = "10" ]; then
        exit 0
    fi
fi
# Bound each autonomous run so cron cannot stack forever on a stuck network/model call.
timeout 50m python3 agent.py --force >> data/evolve.log 2>&1
rc=$?
if [ "$rc" = "124" ]; then
    echo "[$NOW] Timeout: agent run exceeded 50m" >> data/evolve.log
else
    echo "[$NOW] Done rc=$rc" >> data/evolve.log
fi
exit $rc
