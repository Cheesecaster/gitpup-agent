#!/usr/bin/env python3
"""Implement Phase: execute the plan, make code changes, verify"""
import os, sys, json, subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evolve import config, llm

def run():
    config.log_evolve("=== IMPLEMENT PHASE ===")
    
    plan_path = os.path.join(config.INTERMEDIATE_DIR, "plan.json")
    if not os.path.isfile(plan_path):
        config.log_evolve("No plan found! Running plan phase first...")
        from .plan import run as plan_run
        plan_run()
    
    with open(plan_path) as f:
        plan_text = f.read()
    
    # Try to parse the plan
    try:
        plan = json.loads(plan_text)
        steps = plan.get("steps", [])
        goal = plan.get("goal", "Unknown goal")
    except json.JSONDecodeError:
        steps = []
        goal = plan_text[:200]
        config.log_evolve(f"Plan is not valid JSON, treating as text: {goal}...")
    
    config.log_evolve(f"Executing plan: {goal}")
    config.log_evolve(f"Steps: {len(steps)}")
    
    results = []
    for step in steps:
        fpath = step.get("file", "")
        action = step.get("action", "")
        content = step.get("content", "")
        
        if not fpath:
            continue
        
        full_path = os.path.join(config.PROJECT_ROOT, fpath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        if action == "create":
            config.log_evolve(f"  Create: {fpath}")
            with open(full_path, "w") as f:
                f.write(content)
            results.append({"file": fpath, "action": "create", "status": "done"})
        elif action == "edit":
            config.log_evolve(f"  Edit: {fpath}")
            with open(full_path, "w") as f:
                f.write(content)
            results.append({"file": fpath, "action": "edit", "status": "done"})
        elif action in ("delete", "remove"):
            config.log_evolve(f"  Delete: {fpath}")
            if os.path.exists(full_path):
                os.remove(full_path)
            results.append({"file": fpath, "action": "delete", "status": "done"})
        else:
            config.log_evolve(f"  Unknown action '{action}' for {fpath}")
            results.append({"file": fpath, "action": action, "status": "unknown"})
    
    # Run test command if specified
    test_cmd = None
    try:
        plan_obj = json.loads(plan_text)
        test_cmd = plan_obj.get("test_command", "")
    except Exception:
        pass
    
    test_result = None
    if test_cmd:
        config.log_evolve(f"  Running test: {test_cmd}")
        try:
            result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=60)
            test_result = {
                "cmd": test_cmd,
                "returncode": result.returncode,
                "stdout": result.stdout[:500],
                "stderr": result.stderr[:500],
                "passed": result.returncode == 0,
            }
        except Exception as e:
            test_result = {"cmd": test_cmd, "error": str(e), "passed": False}
    
    # Save implementation results
    impl_result = {
        "goal": goal,
        "steps_executed": results,
        "test_result": test_result,
    }
    with open(os.path.join(config.INTERMEDIATE_DIR, "implementation.json"), "w") as f:
        json.dump(impl_result, f, indent=2)
    
    config.log_evolve(f"Implementation complete. {len(results)} steps executed. Test: {'PASSED' if test_result and test_result.get('passed') else 'SKIPPED/FAILED'}")
    return impl_result

if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
