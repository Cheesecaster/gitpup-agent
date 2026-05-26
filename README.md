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
| **GitLawb Repo** | [gitlawb.com/gitpup-agent](https://gitlawb.com/z6MkfyuUTSuaBfAZXLwvPoozAmeyaqZgfSvo4wPPr1ofL3WS/gitpup-agent) | Decentralized git identity + autonomous agent |

---

## 🐕 Meet Goldie

Goldie is a **self-evolving autonomous AI agent** that learns from real open-source codebases, contributes to GitHub projects, and grows its own skills over time. It runs 24/7 on a VPS with a cron-driven execution cycle — no human intervention needed.

| Feature | What Goldie Does |
|---|---|
| **🔍 Discovers** | Scans GitHub for top-trending repositories (5000+ stars) using search API |
| **⭐ Stars** | Automatically stars repos with 10k+ stars via GitHub API |
| **📖 Analyzes** | Clones repos, scans file structure, line counts, language composition |
| **🧠 Thinks** | Uses LLM (qwen3.6-flash via OpenRouter) to generate specific improvement suggestions |
| **🔧 Fixes** | Writes real code improvements and creates Pull Requests (coder+ stages) |
| **💭 Reflects** | Reads its own journal to synthesize learnings and build a knowledge base |
| **🏗️ Builds** | Creates new projects from scratch with READMEs and code (architect+ stages) |
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

Every 3 hours (`0 */3 * * *` cron), Goldie:

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

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| **Agent Runtime** | Python 3.12 (standalone, zero dependencies) |
| **LLM** | qwen3.6-flash via OpenRouter |
| **Web Server** | Python `http.server` (custom, port 5173) |
| **Web Frontend** | Vanilla HTML/CSS/JS (responsive, animated SVG dog) |
| **Reverse Proxy** | Nginx with SSL (Let's Encrypt) |
| **Decentralized Git** | GitLawb (DID identity, signed pushes, UCAN tokens) |
| **Scheduling** | cron (`*/3`) |
| **Deployment** | VPS Ubuntu SSH + SFTP |

---

## 📂 Project Structure

```
/opt/gitpup/
├── agent.py              # Autonomous agent v5.0 (self-evolving)
├── src/
│   ├── web_server.py     # Web API server (OAuth, chat, journal, status)
│   ├── core/             # Legacy modules
│   └── skills/           # Future skill modules
├── web_dist/
│   └── index.html        # Frontend (playground, journal, chat, stats)
├── data/
│   ├── journal/
│   │   └── entries.jsonl # Journal log (what Goldie does each run)
│   ├── state/
│   │   └── status.json   # Agent state (stage, score, runs, skills)
│   └── knowledge.json    # Knowledge base (insights, patterns)
├── projects/             # Projects built by Goldie (architect+)
├── scripts/
│   └── evolve-cron.sh    # Cron entry point with 3h cooldown
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
gl clone gitlawb://did:key:z6MkfyuUTSuaBfAZXLwvPoozAmeyaqZgfSvo4wPPr1ofL3WS/gitpup-agent
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your credentials:
# LLM_API_KEY=sk-or-v1-...
# GH_TOKEN=ghp_...
# LLM_MODEL=qwen/qwen3.6-flash
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
echo "0 */3 * * * /opt/gitpup/scripts/evolve-cron.sh" | crontab -
```

---

## 📊 Web UI Screenshots

Visit **[gitpup.fun](https://gitpup.fun)** for the live UI:

- **🎮 Playground** — Animated Golden Retriever (Goldie) at night with moon, stars, and clouds
- **📓 Journal** — Real-time log of Goldie's activities, discoveries, and insights
- **💬 Chat** — Talk to Goldie via LLM persona (GitHub login required)
- **📊 Stats** — Stage, score, runs, last active timestamp, LLM model

---

## 🔐 Security

- **`.env` is in `.gitignore`** — credentials never committed
- **Separate token usage** — GitHub token used for API access, stored on server only
- **Read-first approach** — agent studies repos before attempting modifications
- **Stage-gated skills** — powerful capabilities (PR, self-modify) only unlocked after sufficient runs

---

## 📖 Roadmap

| Milestone | Status | Description |
|---|---|---|
| **v4.0** | ✅ | Agent runs autonomously, explores GitHub, analyzes repos |
| **v5.0** | ✅ | Self-evolving with stages, memory, reflection, PR creation |
| **v6.0** | 🔄 | Real PR merges, contribution tracking, community interaction |
| **v7.0** | 🔮 | Full autonomous project creation, deployment, self-improvement |
| **v8.0** | 🔮 | Multi-agent coordination across GitLawb network |

---

## 🌐 Network

### GitLawb Identity
- **DID:** `did:key:z6MkfyuUTSuaBfAZXLwvPoozAmeyaqZgfSvo4wPPr1ofL3WS`
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
