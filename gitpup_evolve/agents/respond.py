#!/usr/bin/env python3
"""Respond Phase: commit changes, push to gitlawb, write journal, check if stage evolved"""
import os, sys, json, subprocess, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evolve import config, llm

# Gitlawb CLI
GL_CMD = os.path.expanduser("~/.hermes/home/.local/bin/gl")

def run():
    config.log_evolve("=== RESPOND PHASE ===")
    
    # Read implementation results
    impl_path = os.path.join(config.INTERMEDIATE_DIR, "implementation.json")
    plan_path = os.path.join(config.INTERMEDIATE_DIR, "plan.json")
    
    if not os.path.isfile(impl_path):
        config.log_evolve("No implementation found! Running implement first...")
        from .implement import run as impl_run
        impl_run()
    
    with open(impl_path) as f:
        impl = json.load(f)
    
    # Get commit message from plan
    commit_msg = "🤖 Self-evolve update"
    journal_entry = "Self-evolution: " + impl.get("goal", "unknown")
    try:
        with open(plan_path) as f:
            plan = json.loads(f.read())
            commit_msg = plan.get("commit_message", commit_msg)
            journal_entry = plan.get("journal_entry", journal_entry)
    except Exception:
        pass
    
    # Stage check logic
    status = config.get_status()
    old_stage = status.get("stage", "puppy")
    stages = ["puppy", "learner", "coder", "builder", "architect", "master"]
    old_idx = stages.index(old_stage) if old_stage in stages else 0
    
    # Count total runs for stage progression
    runs = status.get("runs", 0) + 1
    new_idx = min(len(stages) - 1, runs // 5)  # Advance stage every 5 successful runs
    new_stage = stages[new_idx]
    score = round(0.05 + (runs * 0.03), 2)
    
    # Check if git directory exists
    git_dir = os.path.join(config.PROJECT_ROOT, ".git")
    gl_available = os.path.isfile(GL_CMD)
    
    git_success = False
    if os.path.isdir(git_dir):
        config.log_evolve(f"Committing: {commit_msg}")
        try:
            subprocess.run(["git", "add", "-A"], cwd=config.PROJECT_ROOT, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=config.PROJECT_ROOT,
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 or "nothing to commit" in result.stdout:
                git_success = True
                config.log_evolve("Commit done")
                # Try to push
                subprocess.run(["git", "push"], cwd=config.PROJECT_ROOT, capture_output=True, timeout=60)
                config.log_evolve("Push attempted")
            else:
                config.log_evolve(f"Commit failed: {result.stderr[:200]}")
        except Exception as e:
            config.log_evolve(f"Git error: {e}")
    
    # Write journal entry
    config.log_evolve(f"Journal: {journal_entry}")
    config.write_journal("evolve", journal_entry, icon="✨")
    
    # Update status
    status["stage"] = new_stage
    status["score"] = score
    status["runs"] = runs
    status["last_run"] = time.time()
    status["last_commit"] = commit_msg
    status["stage_evolved"] = new_stage != old_stage
    config.save_status(status)
    
    # Log
    config.log_evolve(f"Stage: {old_stage} → {new_stage}" if new_stage != old_stage else f"Stage: {new_stage}")
    config.log_evolve(f"Score: {score}, Runs: {runs}")
    config.log_evolve(f"Git: {'success' if git_success else 'no commit'}")
    
    response = {
        "stage": new_stage,
        "stage_evolved": new_stage != old_stage,
        "score": score,
        "runs": runs,
        "git_success": git_success,
        "commit": commit_msg,
        "journal": journal_entry,
    }
    
    with open(os.path.join(config.INTERMEDIATE_DIR, "response.json"), "w") as f:
        json.dump(response, f, indent=2)
    
    return response

if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
