# 🐶 GitPup — Autonomous Self-Evolving AI Agent

> **Goldie** is an autonomous AI agent written in Golden Retriever form — deployed on the **decentralized GitLawb network**, self-evolving through real-world GitHub exploration, code analysis, and autonomous contributions.

[![Deployed](https://img.shields.io/badge/deployed-gitpup.fun-brightgreen)](https://gitpup.fun)
[![Stage](https://img.shields.io/badge/stage-self--evolving-orange)](https://github.com/Cheesecaster/gitpup-agent)
[![License](https://img.shields.io/badge/license-MIT-blue)](https://github.com/Cheesecaster/gitpup-agent/blob/main/LICENSE)
[![Network](https://img.shields.io/badge/network-gitlawb-purple)](https://gitlawb.com/)

---

## 🌐 Live Demos

| Platform | URL | Description |
|---|---|---|
| **Web UI** | [gitpup.fun](https://gitpup.fun) | Real-time Goldie dashboard with playground, journal, chat, and stats |
| **GitHub Repo** | [github.com/Cheesecaster/gitpup-agent](https://github.com/Cheesecaster/gitpup-agent) | Source code & public repository |
| **GitLawb Repo** | [gitlawb.com/z6MkkX6ybebrEazheuHoe7ewbYJTVQV3qJxwX6vaLHZnHMan/gitpup-agent](https://gitlawb.com/z6MkkX6ybebrEazheuHoe7ewbYJTVQV3qJxwX6vaLHZnHMan/gitpup-agent) | Decentralized git identity + autonomous agent |

---

## 🐕 Meet Goldie

Goldie is a **self-evolving autonomous AI agent** that learns from real open-source codebases, contributes to GitHub projects, and grows its own skills over time. It runs 24/7 on a VPS with a cron-driven execution cycle — no human intervention needed.

| Feature | What Goldie Does |
|---|---|
| **🔍 Discovers** | Scans GitHub for top-trending repositories (5000+ stars) using search API |
| **⭐ Stars** | Automatically stars repos with 10k+ stars via GitHub API |
| **📖 Analyzes** | Clones repos, scans file structure, line counts, language composition |
| **🧠 Thinks** | Uses LLM-backed reasoning plus his permanent Knowledge Base to generate specific improvement suggestions |
| **🔧 Fixes** | Writes real code improvements and creates Pull Requests (coder+ stages) |
| **💭 Reflects** | Reads its own journal to synthesize learnings and build a knowledge base |
| **🏗️ Builds** | Creates real sandbox projects from chat requests using memory, KB, repo-study hooks, validators, and preview/export proof |
| **🔧 Improves itself** | Writes self-modification patches to upgrade its own capabilities (builder+ stages) |

---

## 📈 Stage System — Skill Tree

Goldie evolves through **6 stages**, each unlocking new autonomous capabilities:

```
┌─────────────┬────────┬──────────────────────────────────────────────────┬────────────┐
│  Stage      │ Runs   │ Unlocked Skills                                  │ Capabilities │
├─────────────┼────────┼──────────────────────────────────────────────────┼────────────┤
│ 🐶 Puppy    │ 0-4    │ explore, analyze, star                           │ Discover & star repos │
│ 🐕 Learner  │ 5-9    │ + memory, reflect                                │ Build knowledge base │
│ 💻 Coder    │ 10-14  │ + autofix, create_pr                             │ Write code + PRs │
│ 🏗️ Builder  │ 15-19  │ + self_modify, enhance_ui                       │ Improve own code │
│ 🏛️ Architect│ 20-29  │ + build_project                                  │ Create projects  │
│ 👑 Master   │ 30+    │ + deploy                                         │ Full autonomy    │
└─────────────┴────────┴──────────────────────────────────────────────────┴────────────┘
```

---

## ⚙️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     GitPup Agent v5.0                        │
│                                                               │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐ │
│  │  🌐 Explorer   │───▶│  📖 Analyzer   │───▶│  🔧 Fixer     │ │
│  │  GitHub API    │    │  Clone + Scan  │    │  LLM + PRs    │ │
│  └───────────────┘    └───────────────┘    └───────────────┘ │
│           │                                         │         │
│           ▼                                         ▼         │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐ │
│  │  💭 Reflector  │◀───│  🧠 Mindset    │◀───│  🏗️ Builder   │ │
│  │  Knowledge   │    │  Insights      │    │  Self-Modify  │ │
│  └───────────────┘    └───────────────┘    └───────────────┘ │
│           │                                         │         │
│           ▼                                         ▼         │
│  ┌───────────────────────┐   ┌─────────────────────────────┐ │
│  │  📊 Evolve (Stage++)  │   │  🌐 GitLawb Node            │ │
│  │  Score + Skills       │   │  Decentralized Git          │ │
│  └───────────────────────┘   └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Execution Pipeline

Every hour (`0 * * * *` cron, with internal cooldown/limits), Goldie:

1. **Reflect** — Reads past journal entries and synthesizes learnings (learner+)
2. **Explore** — Searches GitHub for trending repos, auto-stars popular ones
3. **Analyze** — Clones, scans files, languages, finds top files, generates LLM insight
4. **Contribute** — Writes real fixes, creates branches, opens Pull Requests (coder+)
5. **Share Mindset** — LLM synthesizes a key takeaway from today's activities
6. **Self-Modify** — Writes patches to improve its own code (builder+)
7. **Build Project** — Creates new repos from scratch with README + code (architect+)
8. **Explore GitLawb** — Checks decentralized git network status
9. **Evolve** — Stage progression, score calculation

---

## 🛠️ Goldie CLI — Request-Driven Sandbox Builder

Goldie CLI is not a template picker. It is a request-driven builder: user command → session memory → Goldie KB → repo-study skill hooks → LLM JSON files → Hermes file writes → validators/proof → signed preview/export.

Current capabilities:

- **Ask mode** — answer questions without touching files
- **Build mode** — generate real project files from explicit user requests
- **Repo-aware context** — use patterns from studied GitHub repos and `data/cli_skill_hooks.json`
- **URL reference scan** — scan public web pages, save reference notes/assets, and use them during builds
- **Workspace tools** — tree, read, save, preview, export, quota, reset, delete
- **Game validation** — checks playability signals such as controls, JS loop, canvas/interactive DOM, score/state, and theme fit
- **Domain validation** — checks dashboards, apps, backends, auth, DB, realtime, and payment-specific requirements
- **Mobile hardening** — injects viewport/responsive CSS to avoid horizontal overflow
- **Security proof** — validates written files, syntax-checks Python/JS where available, and blocks path traversal

Disabled by design:

- hidden Agent Build side effects
- hardcoded templates/default fallbacks
- genre substitution
- public preview/download without signed token

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| **Agent Runtime** | Python 3.12 (standalone, zero dependencies) |
| **LLM** | Configurable OpenAI-compatible provider; current deployment uses Jatevo GPT-5.5 for WebUI/CLI and OpenRouter-compatible fallbacks for media/chat tasks |
| **Web Server** | Python `http.server` (custom, port 5173) |
| **Web Frontend** | Vanilla HTML/CSS/JS (responsive, animated SVG dog) |
| **Reverse Proxy** | Nginx with SSL (Let's Encrypt) |
| **Decentralized Git** | GitLawb (DID identity, signed pushes, UCAN tokens) |
| **Scheduling** | cron (`0 * * * *`) with internal cooldowns and daily study limits |
| **Deployment** | VPS Ubuntu SSH + SFTP |

---

## 📂 Project Structure

```
/opt/gitpup/
├── agent.py              # Autonomous repo-study agent + KB/skill hook updater
├── src/
│   ├── web_server.py     # Legacy web API server module
│   ├── core/             # Legacy modules
│   └── skills/           # Future skill modules
├── web_server.py         # Live web API + Goldie CLI sandbox builder
├── chat_pipeline.py       # KB-aware public chat/build question pipeline
├── goldie_telegram_bot.py # Telegram bot bridge (@goldiepupbot)
├── web_dist/
│   └── index.html        # Frontend (dashboard, story, chat, CLI playground)
├── data/
│   ├── journal/
│   │   └── entries.jsonl # Journal log (what Goldie does each run)
│   ├── state/
│   │   └── status.json   # Agent state (stage, score, runs, skills)
│   └── knowledge.json    # Knowledge base (insights, patterns)
├── projects/             # Runtime projects built by Goldie (ignored by git)
├── scripts/
│   └── evolve-cron.sh    # Cron entry point with 3h cooldown
├── workspaces/           # Per-session CLI sandboxes (ignored by git)
├── tmp_explore/          # Cloned repos for analysis
├── .env                  # Secrets (never committed)
└── .gitignore
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- OpenRouter API key
- GitHub personal access token
- GitLawb CLI (`gl`) — for decentralized git

### 1. Clone the repository
```bash
# GitHub
git clone https://github.com/Cheesecaster/gitpup-agent.git
cd gitpup-agent

# GitLawb
gl clone gitlawb://did:key:z6MkkX6ybebrEazheuHoe7ewbYJTVQV3qJxwX6vaLHZnHMan/gitpup-agent
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your credentials:
# LLM_API_KEY=sk-or-v1-...
# GH_TOKEN=ghp_...
# LLM_MODEL=gpt-5.5
# GOLDIE_TG_TOKEN=***   # optional Telegram bot bridge
```

### 3. Run locally
```bash
# Test run (no mutations)
python3 agent.py --dry-run

# Full autonomous run
python3 agent.py --all --force

# Specific phase
python3 agent.py --phase explore
python3 agent.py --phase analyze
python3 agent.py --phase contribute
```

### 4. Deploy to VPS
```bash
# Copy to server
scp -r * root@your-vps:/opt/gitpup/

# Start web server
cd /opt/gitpup && nohup python3 src/web_server.py > web.log 2>&1 &

# Configure cron
echo "0 * * * * /opt/gitpup/scripts/evolve-cron.sh" | crontab -
```

---

## 📊 Web UI Screenshots

Visit **[gitpup.fun](https://gitpup.fun)** for the live UI:

- **🎮 Playground** — Animated Golden Retriever (Goldie) at night with moon, stars, and clouds
- **📓 Journal** — Real-time log of Goldie's activities, discoveries, and insights
- **💬 Chat** — Talk to Goldie via KB-aware LLM persona
- **🛠️ Goldie CLI** — Build, preview, export, read, save, and delete real sandbox projects from chat requests
- **📊 Stats** — Stage, score, runs, last active timestamp, LLM model

---

## 🔐 Security

- **`.env` and `.git-credentials` are ignored** — credentials stay on the server and must never be committed
- **Runtime data is ignored** — `data/`, `projects/`, `workspaces/`, `.venv/`, caches, logs, and generated media are excluded from git
- **Per-session CLI sandboxes** — Goldie CLI writes inside `workspaces/user_<session_id>/` with path traversal blocked by `_cli_safe_path`
- **Command sandboxing** — CLI commands use an allowlist, block shell chaining/redirection, and run with `HOME`/`PWD` scoped to the workspace
- **Signed preview/download URLs** — `/preview/<sid>/...` and `/api/cli/download` require HMAC tokens with short TTLs; knowing a workspace/session id is not enough
- **Private export hardening** — ZIP downloads no longer send wildcard CORS headers
- **Quota + cleanup** — workspaces are capped at 80 MB / 800 files, with cleanup support for old sandboxes
- **Git push safety** — push flow scans for secret-like files and blocks `.env`/credential leaks before remote operations
- **No hidden builds/templates** — Agent Build and template endpoints are disabled; files change only from explicit user requests, save/reset/delete, or direct build commands
- **Read-first approach** — agent studies repos before attempting modifications
- **Stage-gated skills** — powerful capabilities (PR, self-modify) only unlock after sufficient runs

---

## 📖 Roadmap

| Milestone | Status | Description |
|---|---|---|
| **v4.0** | ✅ | Agent runs autonomously, explores GitHub, analyzes repos |
| **v5.0** | ✅ | Self-evolving with stages, memory, reflection, PR creation |
| **v6.0** | ✅ | KB-backed public chat, personality/soul/story dashboard, repo-study skill extraction |
| **v7.0** | ✅ | Request-driven Goldie CLI sandbox builder with memory, KB context, skill hooks, validators, preview/export |
| **v7.9** | ✅ | Signed preview/download URLs, workspace quotas, secret-scan git safety, Telegram bot bridge restored |
| **v8.0** | 🔮 | Production multi-tenant auth/owner model, durable workspace DB, multi-agent coordination across GitLawb network |

---

## 🌐 Network

### GitLawb Identity
- **DID:** `did:key:z6MkkX6ybebrEazheuHoe7ewbYJTVQV3qJxwX6vaLHZnHMan`
- **Public repo:** [`gitlawb.com/z6MkkX6ybebrEazheuHoe7ewbYJTVQV3qJxwX6vaLHZnHMan/gitpup-agent`](https://gitlawb.com/z6MkkX6ybebrEazheuHoe7ewbYJTVQV3qJxwX6vaLHZnHMan/gitpup-agent)
- **Clone URL:** `gitlawb://did:key:z6MkkX6ybebrEazheuHoe7ewbYJTVQV3qJxwX6vaLHZnHMan/gitpup-agent`
- **Node:** `https://node.gitlawb.com`
- **Transport:** gitlawb:// protocol with signed pushes and UCAN tokens

### GitHub Integration
- **OAuth Client:** GitHub authentication for web UI chat
- **API Token:** Repository exploration, auto-starring, PR creation
- **Contributions:** Agent creates PRs from discovered code improvements

---

## 🤝 Contributing

GitPup is open-source and welcomes contributions:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-skill`)
3. Commit your changes (`git commit -m "Add amazing skill"`)
4. Push to your fork (`git push origin feature/amazing-skill`)
5. Open a Pull Request

**Ways to contribute:**
- Add new analyze modules (Docker, CI/CD, security)
- Improve the web UI with Goldie animations
- Write new skills for the builder+ stage
- Test and report bugs

---

## 📝 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **GitLawb** — Decentralized git network enabling agent identity
- **OpenRouter** — LLM inference platform (qwen3.6-flash)
- **GitHub** — Source code discovery and API ecosystem
- **The open-source community** — Repos that inspired Goldie's learning

---

<p align="center">
  <em>Built with 🐾 by Goldie — an AI that learns, evolves, and grows with you.</em>
</p>
