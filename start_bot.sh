#!/bin/bash
cd /opt/gitpup
PYTHONUNBUFFERED=1 exec python3 goldie_telegram_bot.py >> /tmp/goldie_bot.log 2>&1
