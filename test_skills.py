import sys; sys.path.insert(0, '/opt/gitpup')
import agent
kb = agent.load_kb()
d3 = kb["repos"].get("d3/d3", {})
print("D3 patterns:", len(d3.get("patterns",[])), "| best_practices:", len(d3.get("best_practices",[])), "| insights:", len(d3.get("insights",[])))
n = agent.kb_extract_skills(repo_name="d3/d3", patterns=d3.get("patterns",[]), insights=d3.get("insights",[]), best_practices=d3.get("best_practices",[]))
print("Extracted %d skills from d3/d3" % n)
kb2 = agent.load_kb()
sm = kb2.get("skills_memory", [])
print("Total skills in memory: %d" % len(sm))
for s in sm[-5:]:
    print("  [%s] %s" % (s["category"], s["name"][:70]))
ctx = agent.kb_get_skill_context(max_skills=5)
if ctx:
    print("=== SKILL CONTEXT ===")
    print(ctx)
