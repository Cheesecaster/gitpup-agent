#!/usr/bin/env bash
# scripts/evolve.sh — One evolution cycle for Evo Garden
# Run by GitLawb CI schedule or manually on VPS.
#
# Usage: LLM_API_KEY=your-key ./scripts/evolve.sh
#
# Environment:
#   LLM_API_KEY     — required
#   EVO_CONFIG      — path to config.yaml (optional)
#   EVO_MODE        — "ci" (single run) or "vps" (daemon)
#   MAX_RETRIES     — retry count on API failure (default: 2)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# ── Config ──
LLM_API_KEY="${LLM_API_KEY:-}"
MAX_RETRIES="${MAX_RETRIES:-2}"
EVO_MODE="${EVO_MODE:-ci}"
DATE=$(date +%Y-%m-%d)
SESSION_TIME=$(date +%H:%M)

# ── Validation ──
if [ -z "$LLM_API_KEY" ]; then
    echo "❌ LLM_API_KEY is not set"
    exit 1
fi
export LLM_API_KEY

echo "🌱 === Evo Garden Evolution ==="
echo "📅 Date: $DATE $SESSION_TIME"
echo "🔧 Mode: $EVO_MODE"
echo "🔄 Max retries: $MAX_RETRIES"
echo ""

# ── Pull latest ──
if git rev-parse --is-inside-work-tree &>/dev/null; then
    echo "📥 Pulling latest..."
    git pull --rebase --quiet 2>/dev/null || true
    echo ""
fi

# ── Pre-flight: Run tests before evolution ──
echo "🧪 Pre-flight test check..."
python -m pytest -q 2>&1 || {
    echo "⚠️ Tests failing before evolution — proceeding anyway (agent will fix)"
}
echo ""

# ── Run the agent ──
ATTEMPT=0
success=false

while [ $ATTEMPT -lt $((MAX_RETRIES + 1)) ]; do
    ATTEMPT=$((ATTEMPT + 1))
    echo "🌿 Attempt $ATTEMPT of $((MAX_RETRIES + 1))..."

    if [ "$EVO_MODE" = "ci" ]; then
        # CI mode: run one cycle and exit
        python agent/main.py --cycle 2>&1
        result=$?
    else
        # VPS daemon mode: run continuously
        python agent/main.py --daemon 2>&1
        result=$?
    fi

    if [ $result -eq 0 ]; then
        success=true
        break
    fi

    echo "⚠️ Attempt $ATTEMPT failed. Retrying in 30s..."
    sleep 30
done

# ── Post-flight: Run tests after ──
echo ""
echo "🧪 Post-flight test check..."
if python -m pytest -q 2>&1; then
    echo "✅ All tests passing!"
else
    echo "❌ Tests failing after evolution!"
    if [ "$success" = true ]; then
        echo "⚠️ Agent may have introduced a regression"
    fi
fi

# ── Push changes ──
if git rev-parse --is-inside-work-tree &>/dev/null; then
    changes=$(git status --short 2>/dev/null | wc -l)
    if [ "$changes" -gt 0 ]; then
        echo "📤 Pushing changes..."
        git add -A
        git commit -m "Evo Garden: evolution cycle $DATE $SESSION_TIME" || true
        git push origin HEAD 2>/dev/null || echo "⚠️ Push failed"
    fi
fi

echo ""
if [ "$success" = true ]; then
    echo "🌻 Evolution cycle complete! The garden grows. 🌱"
else
    echo "🥀 Evolution cycle failed after $MAX_RETRIES retries."
    exit 1
fi
