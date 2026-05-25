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

load_dotenv()

console = Console()


def main():
    parser = argparse.ArgumentParser(description="🐶 GitPup — Golden Retriever AI Agent")
    parser.add_argument("--scan", help="Scan a specific repo on gitlawb")
    parser.add_argument("--explore", action="store_true", help="Explore the gitlawb network")
    parser.add_argument("--trust", action="store_true", help="Check trust score")
    parser.add_argument("--create-repo", help="Create a new repo on gitlawb")
    args = parser.parse_args()

    console.print()
    console.print("[bold yellow]🐶 GitPup[/bold yellow] — Golden Retriever Agent for gitlawb")
    console.print("[dim]Born from commit, evolves with every contribution[/dim]")
    console.print()

    # Import here so deps are loaded
    from core.agent import GitPupAgent

    agent = GitPupAgent()

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
