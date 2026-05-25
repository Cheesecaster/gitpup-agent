# 🌱 Evo Garden

A joyful, self-evolving coding agent growing up in public.

Like a garden that tends itself, this agent reads its own code, sets goals, writes improvements, runs tests, and journals its journey — all while living on the web.

## 🏡 Architecture

```
┌─────────────────────────────────────────────────────┐
│  VPS (Ubuntu)                                       │
│                                                     │
│  ┌───────────────┐     ┌─────────────────────────┐  │
│  │  Agent Engine  │────▶│  SQLite + JSON Journal  │  │
│  │  (Python)      │     │  (state, stats, logs)   │  │
│  └───────┬───────┘     └────────────┬────────────┘  │
│          │                          │               │
│          │  commit + push           │  read         │
│          ▼                          ▼               │
│  ┌───────────────┐     ┌─────────────────────────┐  │
│  │  GitLawb Repo  │◀────│  Web Dashboard (React)  │  │
│  │  (source +    │     │  Garden theme + SSE     │  │
│  │   journal)    │     │  Live status + chat     │  │
│  └───────────────┘     └─────────────────────────┘
```


## 🌿 How It Works

1. **Scan** — Agent reads its own source code (powered by tree-sitter + Understand-Anything)
2. **Decide** — Picks a goal: fix a bug, add a test, refactor, implement a feature
3. **Act** — Writes code, runs tests, commits only if tests pass
4. **Journal** — Writes a reflection about what happened
5. **Repeat** — Every cycle, the garden grows

## 🚀 Quick Start

```bash
# Clone
git clone <your-gitlawb-repo> evo-garden
cd evo-garden

# Install deps
pip install -r requirements.txt

# Run agent (needs LLM API key)
LLM_API_KEY=your-key python agent/main.py

# Start dashboard (needs Node.js)
cd web && npm install && npm run dev
```


## 🌻 Themes

Garden with playground — green grass, slides, swings, butterflies. Not corporate. Not dark mode. *Joyful*.

## 📋 Config

Copy `config.example.yaml` to `config.yaml` and fill in your details:

```yaml
llm:
  provider: openrouter        # openrouter, openai, anthropic, groq, local
  model: google/gemini-2.0-flash-001
  api_key: ${LLM_API_KEY}
  api_url: https://openrouter.ai/api/v1

project:
  goals_file: GOALS.md
  max_tokens_per_task: 8000
  max_cost_per_run: 2.00      # USD

evolution:
  mode: vps                   # vps or gitlawb-ci
  schedule: every_2h
  max_concurrent: 1

web:
  host: 0.0.0.0
  port: 3000
  sse_port: 8080
```

