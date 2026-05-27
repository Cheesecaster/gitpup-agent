#!/usr/bin/env python3
"""Final patch — personality tracking into agent.py"""

path = '/opt/gitpup/agent.py'
with open(path) as f:
    content = f.read()

changes = 0

# 1. Import personality (already done)
print("1. import personality: already done")

# 2. After journal("Looked at:") in do_explore
if "personality.track('explore', day())" not in content:
    old = '                    journal("\\U0001f310", "Looked at: " + name,'
    new = '                    personality.track(\'explore\', day())\n                    journal("\\U0001f310", "Looked at: " + name,'
    content = content.replace(old, new, 1)
    changes += 1
    print("2. track(explore): added")
else:
    print("2. track(explore): exists")

# 3. After star_repo
if "personality.track('star_repo', day())" not in content:
    old = '        log("  STARRED: " + repo_name)\n        journal('
    new = '        log("  STARRED: " + repo_name)\n        personality.track(\'star_repo\', day())\n        journal('
    content = content.replace(old, new, 1)
    changes += 1
    print("3. track(star_repo): added")
else:
    print("3. track(star_repo): exists")

# 4. study_pass_complete (already done)
print("4. track(study_pass_complete): already done")

# 5. narrative (already done)
print("5. track(narrative): already done")

# 6. evolve (already done from VPS patch)
if "personality.track('evolve', day())" not in content:
    old = '    do_evolve()'
    new = '    do_evolve()\n    personality.track(\'evolve\', day())'
    content = content.replace(old, new, 1)
    changes += 1
    print("6. track(evolve): added")
else:
    print("6. track(evolve): exists")

# 7. self_modify (already done from VPS patch)
if "personality.track('self_modify', day())" not in content:
    old = '        do_self_modify()'
    new = '        do_self_modify()\n        personality.track(\'self_modify\', day())'
    content = content.replace(old2, new2, 1)
    changes += 1
    print("7. track(self_modify): added")
else:
    print("7. track(self_modify): exists")

# 8. build_project (already done from VPS patch)
if "personality.track('build_project', day())" not in content:
    old = '        do_build_project()'
    new = '        do_build_project()\n        personality.track(\'build_project\', day())'
    content = content.replace(old3, new3, 1)
    changes += 1
    print("8. track(build_project): added")
else:
    print("8. track(build_project): exists")

with open(path, 'w') as f:
    f.write(content)
print(f"\nTotal new patches: {changes}\nFile saved!")
