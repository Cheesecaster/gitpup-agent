#!/usr/bin/env python3
"""Plan Phase: take assessment, create detailed implementation plan"""
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evolve import config, llm

def plan(assessment_text, scan_data):
    """Create implementation plan from assessment."""
    system = f"""You are Goldie, a self-evolving AI agent in plan phase.
Your stage: {config.get_status().get("stage", "puppy")}, Day {config.get_day()}

Based on the assessment of your codebase, create a detailed implementation plan.
Pick ONE issue to implement in this evolution cycle — the one with the best cost/impact ratio.

Your plan must include:
1. A clear goal (what change you will make)
2. Step-by-step instructions (which files to edit, what to change)
3. The exact code changes (use unified diff format or full file content)
4. A journal entry describing the change
5. A commit message

Format as JSON:
{{
  "goal": "...",
  "steps": [{{"file": "...", "action": "...", "content": "..."}}],
  "journal_entry": "...",
  "commit_message": "...",
  "expected_impact": "...",
  "test_command": "..."
}}"""

    msg = [{"role": "user", "content": f"Assessment:\n{assessment_text}\n\nCodebase scan:\n{json.dumps(scan_data, indent=2)[:3000]}\n\nCreate implementation plan for ONE improvement."}]
    
    return llm.ask(msg, system=system, max_tokens=4000, temperature=0.3)

def run():
    config.log_evolve("=== PLAN PHASE ===")
    
    # Read assessment from disk
    assess_path = os.path.join(config.INTERMEDIATE_DIR, "assessment.json")
    scan_path = os.path.join(config.INTERMEDIATE_DIR, "scan.json")
    
    if not os.path.isfile(assess_path):
        config.log_evolve("No assessment found, running assess first...")
        from .assess import run as assess_run
        assess_run()
    
    with open(assess_path) as f:
        assessment = f.read()
    with open(scan_path) as f:
        scan_data = json.load(f)
    
    config.log_evolve("Generating plan...")
    plan_data = plan(assessment, scan_data)
    
    with open(os.path.join(config.INTERMEDIATE_DIR, "plan.json"), "w") as f:
        f.write(plan_data)
    
    config.log_evolve("Plan complete")
    return plan_data

if __name__ == "__main__":
    result = run()
    print(result)
