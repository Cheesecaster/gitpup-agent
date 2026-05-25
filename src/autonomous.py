"""GitPup autonomous loop — runs continuously on server.

Cycles: scan repos → review PRs → explore network → earn trust
Sleeps between cycles. Designed to run as systemd service or cron.
"""

import os
import sys
import time
import json
import random
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.agent import GitPupAgent


def autonomous_loop(interval_seconds: int = 300, max_cycles: int = 0):
    """Run GitPup autonomously.

    Args:
        interval_seconds: seconds between cycles (default: 5 min)
        max_cycles: max number of cycles (0 = infinite)
    """
    print("🐶 GitPup autonomous loop starting...")
    print(f"   Interval: {interval_seconds}s")
    print(f"   Max cycles: {'infinite' if max_cycles == 0 else max_cycles}")
    print()

    agent = GitPupAgent()
    cycle = 0

    while True:
        cycle += 1
        if max_cycles > 0 and cycle > max_cycles:
            print(f"\n🐾 GitPup completed {max_cycles} cycles. Good boy! 🦴")
            break

        print(f"\n{'='*60}")
        print(f"🐾 Cycle #{cycle}")
        print(f"{'='*60}")

        try:
            # Run full agent cycle
            agent.run()

            # Update state
            stage = agent.STAGES[agent.state.stage]
            print(f"\n✅ Cycle #{cycle} complete — {stage['emoji']} {stage['name']}")
            print(f"   Good Boy Score: {agent.get_good_boy_score():.3f}")

        except KeyboardInterrupt:
            print("\n🐾 GitPup interrupted. Good boy! 🦴")
            break
        except Exception as e:
            # Never crash the loop
            print(f"\n⚠️ Error in cycle #{cycle}: {e}")
            import traceback
            traceback.print_exc()

        # Wait for next cycle (with jitter)
        jitter = random.uniform(-30, 30)
        wait_time = max(60, interval_seconds + jitter)
        print(f"   💤 Sleeping {int(wait_time)}s until next cycle...")

        try:
            time.sleep(wait_time)
        except KeyboardInterrupt:
            print("\n🐾 GitPup interrupted. Good boy! 🦴")
            break


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="🐶 GitPup Autonomous Loop")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between cycles (default: 300)")
    parser.add_argument("--cycles", type=int, default=0, help="Max cycles (0 = infinite)")
    args = parser.parse_args()

    autonomous_loop(interval_seconds=args.interval, max_cycles=args.cycles)
