#!/usr/bin/env python3
"""evolve.py — GitPup Agent main entry point.
Runs the 4-phase pipeline: Assess → Plan → Implement → Respond
Usage: python3 evolve.py [--force] [--dry-run] [--phase assess|plan|impl|resp]"""

import os, sys, json, time, argparse

# Ensure we can import the evolve package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolve import config
from evolve import llm

def main():
    parser = argparse.ArgumentParser(description="GitPup Self-Evolution Pipeline")
    parser.add_argument("--force", action="store_true", help="Bypass cooldown timer")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without executing")
    parser.add_argument("--phase", choices=["assess", "plan", "impl", "resp"], help="Run single phase only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    # Cooldown check
    status = config.get_status()
    now = time.time()
    last_run = status.get("last_run", 0)
    time_since = now - last_run if last_run else float("inf")

    if not args.force and time_since < config.EVOLVE_COOLDOWN:
        remaining = int((config.EVOLVE_COOLER - time_since) / 60)
        print(f"Cooldown active. Next run in {remaining} minutes")
        print("Use --force to override")
        sys.exit(0)

    if args.dry_run:
        print("DRY RUN — showing what would happen:")
        print(f"  Phase 1: Assess codebase (scan {config.PROJECT_ROOT})")
        print(f"  Phase 2: Plan improvements (LLM generates plan)")
        print(f"  Phase 3: Implement changes (apply from plan)")
        print(f"  Phase 4: Respond (commit, journal, update status)")
        print(f"  Current stage: {status.get('stage', 'puppy')}")
        print(f"  Day: {config.get_day()}, Runs: {status.get('runs', 0)}")
        return

    print(f"╔══════════════════════════════════════╗")
    print(f"║  🐶 Goldie Self-Evolution Pipeline   ║")
    print(f"║  Day {config.get_day():>3}  •  Stage: {status.get('stage', 'puppy'):<10}  │")
    print(f"╚══════════════════════════════════════╝")
    print()

    results = {}
    start_time = time.time()
    
    try:
        if args.phase in (None, "assess"):
            print("📊 Phase 1: Assess...")
            from evolve.agents import assess
            results["assess"] = assess.run()
            print("✅ Assess complete\n")

        if args.phase in (None, "plan"):
            print("📝 Phase 2: Plan...")
            from evolve.agents import plan
            results["plan"] = plan.run()
            print("✅ Plan complete\n")

        if args.phase in (None, "impl"):
            print("🔧 Phase 3: Implement...")
            from evolve.agents import implement
            results["implement"] = implement.run()
            print("✅ Implement complete\n")

        if args.phase in (None, "resp"):
            print("📤 Phase 4: Respond...")
            from evolve.agents import respond
            results["respond"] = respond.run()
            print("✅ Respond complete\n")

    except Exception as e:
        config.log_evolve(f"ERROR: {e}")
        print(f"❌ Error: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)

    elapsed = time.time() - start_time
    print(f"⏱️  Pipeline completed in {elapsed:.1f}s")
    print(f"📝 Journal written to {config.JOURNAL_FILE}")
    print(f"📊 Status: {json.dumps(config.get_status(), indent=2)}")

if __name__ == "__main__":
    main()
