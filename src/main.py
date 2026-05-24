"""GitPup Agent — Golden Retriever for gitlawb.

A decentralized AI agent that lives on the gitlawb network,
evolves through contributions, and helps grow the ecosystem.

Author: TomKet (vibecoder, prompt ugal-ugalan)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()


def main():
    console.print()
    console.print("[bold yellow]🐶 GitPup[/bold yellow] — Golden Retriever Agent for gitlawb")
    console.print("[dim]Born from commit, evolves with every contribution[/dim]")
    console.print()

    identity_path = Path.home() / ".gitlawb" / "identity.pem"
    if identity_path.exists():
        console.print(f"[green]✓[/green] Identity: [dim]{identity_path}[/dim]")
    else:
        console.print("[red]✗[/red] No gitlawb identity found. Run: [cyan]gl quickstart[/cyan]")
        sys.exit(1)

    provider = os.getenv("LLM_PROVIDER", "not set")
    console.print(f"[green]✓[/green] LLM Provider: [cyan]{provider}[/]")

    node = os.getenv("GITLAWB_NODE", "https://node.gitlawb.com")
    console.print(f"[green]✓[/green] Node: [cyan]{node}[/]")

    console.print()
    console.print("[bold]GitPup is ready! 🐾[/]")
    console.print()

    from core.agent import GitPupAgent

    agent = GitPupAgent()
    agent.run()


if __name__ == "__main__":
    main()
