#!/bin/bash
cd /opt/gitpup
export PATH=/opt/gitpup/.venv/bin:/usr/local/bin:/usr/bin:$PATH
source .env 2>/dev/null
export $(grep -v '^#' .env | xargs) 2>/dev/null
/opt/gitpup/.venv/bin/python /opt/gitpup/agent_real.py 2>&1 | tee -a /opt/gitpup/data/evolve.log
echo "--- $(date) ---" >> /opt/gitpup/data/evolve.log
