"""GitPup Agent — Golden Retriever for gitlawb.

A decentralized AI agent that lives on the gitlawb network,
evolves through contributions, and helps grow the ecosystem.

Author: TomKet (vibecoder, prompt ugal-ugalan)
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

console = Console()


def load_config():
    """Load environment variables with safe fallback defaults."""
    load_dotenv()
    return {
        "DB_ENDPOINT": os.getenv("DB_ENDPOINT", "localhost:5432"),
        "LLM_API_KEY": os.getenv("LLM_API_KEY", ""),
        "NETWORK_PORT": os.getenv("NETWORK_PORT", "8080"),
    }


def validate_config(config: dict) -> None:
    """Validate critical configuration and exit gracefully if missing."""
    critical_keys = ["LLM_API_KEY", "DB_ENDPOINT"]
    missing = [k for k in critical_keys if not config.get(k)]

    if missing:
        console.print()
        console.print("[bold red]❌ Configuration Error:[/bold red]")
        for key in missing:
            console.print(f"   - Missing or empty: [yellow]{key}[/yellow]")
        console.print("[dim]Please set these in your .env file or export them before running.[/dim]")
        console.print()
        sys.exit(1)

    # Structured startup logging
    console.print("[bold green]✅ Configuration Loaded:[/bold green]")
    console.print(f"   DB_ENDPOINT: {config['DB_ENDPOINT']}")
    console.print(f"   NETWORK_PORT: {config['NETWORK_PORT']}")
    console.print(f"   LLM_API_KEY: {'*' * 8} (configured)")
    console.print()


def main():
    parser = argparse.ArgumentParser(description="🐶 GitPup — Golden Retriever AI Agent")
    parser.add_argument("--scan", help="Scan a specific repo on gitlawb")
    parser.add_argument("--explore", action="store_true", help="Explore the gitlawb network")
    parser.add_argument("--trust", action="store_true", help="Check trust score")
    parser.add_argument("--create-repo", help="Create a new repo on gitlawb")
    args = parser.parse_args()

    # Load and validate configuration
    config = load_config()
    validate_config(config)

    console.print()
    console.print("[bold yellow]🐶 GitPup[/bold yellow] — Golden Retriever Agent for gitlawb")
    console.print("[dim]Born from commit, evolves with every contribution[/dim]")
    console.print()

    # Import here so deps are loaded
    from core.agent import GitPupAgent

    agent = GitPupAgent(config=config)

    if args.scan:
        console.print(f"[cyan]🔍 Scanning repo: {args.scan}[/]")
        result = agent.mcp.execute("scan_repo", {"repo_path": args.scan})
        console.print(f"[green]{result}[/]")
    elif args.explore:
        console.print("[cyan]🌐 Exploring gitlawb network...[/]")
        result = agent.mcp.execute("explore_network", {"filter_type": "all"})
        console.print(f"[dim]{result}[/]")
    elif args.trust:
        console.print("[cyan]🔑 Checking trust score...[/]")
        result = agent.mcp.execute("get_trust_score", {})
        console.print(f"[green]{result}[/]")
    elif args.create_repo:
        console.print(f"[cyan]📦 Creating repo: {args.create_repo}[/]")
        result = agent.mcp.execute("create_repo", {"name": args.create_repo})
        console.print(f"[green]{result}[/]")
    else:
        # Default: full autonomous run
        agent.run()


if __name__ == "__main__":
    main()