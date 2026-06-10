#!/usr/bin/env python3
"""Goldie Personality System v2 - Living Agent with dynamic growth, decay, and cross-pollination."""
import json, os, time
from datetime import datetime, timedelta

PFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'personality.json')
MLOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'journal', 'personality_growth.jsonl')

def load():
    if os.path.exists(PFILE):
        try:
            with open(PFILE, encoding='utf-8') as f:
                p = json.load(f)
            if isinstance(p, dict) and p:
                return p
        except Exception:
            p = None
    p = default()
    save(p)
    return p

def save(p):
    os.makedirs(os.path.dirname(PFILE), exist_ok=True)
    tmp = PFILE + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(p, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, PFILE)
        dirpath = os.path.dirname(PFILE) or '.'
        dirfd = os.open(dirpath, os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            _cleanup_failed = True
        raise

def default():
    return {
        "dimensions": {
            "explorer":     {"value": 0.10, "color": "#5cb88a", "label": "Explorer",     "last_activity": 0, "growth_count": 0},
            "scholar":      {"value": 0.05, "color": "#d4a24c", "label": "Scholar",      "last_activity": 0, "growth_count": 0},
            "builder":      {"value": 0.02, "color": "#5eadb8", "label": "Builder",      "last_activity": 0, "growth_count": 0},
            "contributor":  {"value": 0.0,  "color": "#8b82b8", "label": "Contributor",  "last_activity": 0, "growth_count": 0},
            "architect":    {"value": 0.02, "color": "#c9a24c", "label": "Architect",    "last_activity": 0, "growth_count": 0},
            "dreamer":      {"value": 0.02, "color": "#c95c5c", "label": "Dreamer",      "last_activity": 0, "growth_count": 0},
        },
        "activity_weights": {
            "explore":             {"explorer": 0.15},
            "discover":            {"explorer": 0.10},
            "star_repo":           {"explorer": 0.05, "scholar": 0.03},
            "study_pass_complete": {"scholar": 0.20, "explorer": 0.08},
            "build_project":       {"builder": 0.30, "architect": 0.08},
            "contribute":          {"contributor": 0.25, "builder": 0.08},
            "autofix":             {"contributor": 0.20},
            "self_modify":         {"architect": 0.30, "scholar": 0.08},
            "enhance_ui":          {"architect": 0.20, "builder": 0.12},
            "evolve":              {"architect": 0.20, "scholar": 0.12},
            "journal":             {"dreamer": 0.25, "scholar": 0.05},
            "reflect":             {"dreamer": 0.25, "scholar": 0.08},
            "narrative":          {"dreamer": 0.25, "scholar": 0.05},
            "breakthrough":        {"scholar": 0.35, "dreamer": 0.15, "architect": 0.10},
            "self_assess":         {"dreamer": 0.20, "architect": 0.15},
            "memory_form":         {"scholar": 0.15, "dreamer": 0.10},
        },
        "cross_pollinators": {
            "architect": {"scholar": 0.03},
            "scholar":   {"architect": 0.03},
            "dreamer":   {"explorer": 0.02},
            "explorer":  {"dreamer": 0.02},
            "builder":   {"contributor": 0.03},
            "contributor":{"builder": 0.02},
        },
        "timeline": [],
        "mood_timeline": [],
        "milestones": [],
        "stats": {"total_actions": 0, "days_active": 1, "last_reset": datetime.now().isoformat()},
    }

def track(activity_type, day_num=None):
    p = load()
    weights = p.get("activity_weights", {})
    aw = weights.get(activity_type, {})
    if not aw:
        return False
    recent = [t for t in p.get("timeline", [])[-30:] if t.get("activity") == activity_type]
    frequency_penalty = min(len(recent) * 0.15, 0.6)
    now_ts = time.time()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    for dim, base_delta in aw.items():
        if dim in p["dimensions"]:
            d = p["dimensions"][dim]
            scaled = base_delta * (1.0 - frequency_penalty)
            old_val = d["value"]
            d["value"] = min(old_val + scaled, 0.92)
            d["last_activity"] = now_ts
            d["growth_count"] = d.get("growth_count", 0) + 1
    cross = p.get("cross_pollinators", {})
    for dim, base_delta in aw.items():
        if base_delta > 0.1:
            for target_dim, cross_delta in cross.get(dim, {}).items():
                if target_dim in p["dimensions"]:
                    td = p["dimensions"][target_dim]
                    old_val = td["value"]
                    cross_scaled = cross_delta * (1.0 - frequency_penalty * 0.5)
                    td["value"] = min(old_val + cross_scaled, 0.92)
                    td["last_activity"] = now_ts
    p["timeline"].append({
        "activity": activity_type,
        "deltas": {k: round(v * (1.0 - frequency_penalty), 3) for k, v in aw.items()},
        "timestamp": now_str, "day": day_num, "frequency_penalty": round(frequency_penalty, 2),
    })
    p["timeline"] = p["timeline"][-300:]
    p["stats"]["total_actions"] = p.get("stats", {}).get("total_actions", 0) + 1
    save(p)
    return True

def update_from_experience(experience_type, context="", intensity=1.0):
    p = load()
    now_ts = time.time()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    experience_map = {
        "first_repo_studied":  {"explorer": 0.20, "scholar": 0.10, "dreamer": 0.05},
        "first_reflection":    {"dreamer": 0.25, "scholar": 0.10},
        "self_mod_success":    {"architect": 0.30, "builder": 0.15, "scholar": 0.05},
        "self_mod_fail":       {"builder": 0.10, "scholar": 0.05},
        "breakthrough":        {"scholar": 0.30, "architect": 0.15, "dreamer": 0.10},
        "knowledge_link":      {"architect": 0.20, "scholar": 0.15},
        "stage_evolution":     {"architect": 0.20, "dreamer": 0.10, "scholar": 0.05},
        "first_pr":            {"contributor": 0.30, "builder": 0.10},
        "wisdom_gained":       {"dreamer": 0.25, "scholar": 0.10, "architect": 0.05},
        "self_assessment":     {"dreamer": 0.15, "architect": 0.10},
        "memory_milestone":    {"scholar": 0.15, "dreamer": 0.10},
    }
    deltas = experience_map.get(experience_type, {})
    if not deltas:
        return False
    changes = []
    for dim, delta in deltas.items():
        if dim in p["dimensions"]:
            d = p["dimensions"][dim]
            scaled = delta * intensity
            old_val = d["value"]
            d["value"] = min(old_val + scaled, 0.92)
            d["last_activity"] = now_ts
            d["growth_count"] = d.get("growth_count", 0) + 1
            changes.append({"dim": dim, "old": round(old_val, 3), "new": round(d["value"], 3)})
    if changes:
        p["milestones"].append({"type": experience_type, "context": context[:200], "changes": changes, "timestamp": now_str, "intensity": intensity})
        p["milestones"] = p["milestones"][-50:]
        save(p)
        os.makedirs(os.path.dirname(MLOG), exist_ok=True)
        with open(MLOG, "a") as f:
            f.write(json.dumps({"ts": now_str, "type": experience_type, "context": context[:200], "changes": changes}, ensure_ascii=False) + "\n")
    return len(changes) > 0

def apply_decay():
    p = load()
    now = time.time()
    any_change = False
    min_trait = 0.05
    max_trait = 1.0

    for dim_key, dim in p["dimensions"].items():
        try:
            current_val = float(dim.get("value", min_trait))
        except (TypeError, ValueError):
            current_val = min_trait

        clamped_val = min(max(current_val, min_trait), max_trait)
        if dim.get("value", min_trait) != clamped_val:
            dim["value"] = clamped_val
            any_change = True

        last = dim.get("last_activity", 0)
        days_since = (now - last) / 86400 if last else 999
        if days_since > 3 and dim["value"] > min_trait:
            decay_rate = 0.02 * (days_since - 3)
            old_val = dim["value"]
            dim["value"] = max(old_val - decay_rate, min_trait)
            if dim["value"] > max_trait:
                dim["value"] = max_trait
            if abs(dim["value"] - old_val) > 0.001:
                any_change = True

    if any_change:
        p["stats"]["last_decay"] = datetime.now().isoformat()
        save(p)
    import threading
    threading.Timer(86400, apply_decay).start()
    return any_change

def cross_pollinate_check():
    p = load()
    recent = p.get("timeline", [])[-20:]
    growth = {}
    for t in recent:
        for d, delta in t.get("deltas", {}).items():
            growth[d] = growth.get(d, 0) + delta
    dims = p.get("dimensions", {})
    if growth.get("scholar", 0) > 0.5 and growth.get("architect", 0) > 0.5:
        if dims["architect"]["value"] > 0.3 and dims["scholar"]["value"] > 0.3:
            for target, delta in p.get("cross_pollinators", {}).get("architect", {}).items():
                if target == "scholar":
                    dims["scholar"]["value"] = min(dims["scholar"]["value"] + 0.03, 0.92)
                    dims["architect"]["value"] = min(dims["architect"]["value"] + 0.03, 0.92)
                    save(p)
                    return True
    return False

cross_pollinate_check()

def get_radar():
    apply_decay()
    p = load()
    dims = p.get("dimensions", {})
    result = {
        "labels": [v.get("label", k) for k, v in dims.items()],
        "data": [round(v["value"], 3) for v in dims.values()],
        "colors": [v.get("color", "#ccc") for v in dims.values()],
        "keys": list(dims.keys()),
    }
    # Compute days_active dynamically from BIRTH so it never goes stale
    from datetime import datetime, timezone
    birth_date = datetime(2026, 5, 25, tzinfo=timezone.utc)
    days_active = (datetime.now(timezone.utc) - birth_date).days + 1
    if os.path.exists(PFILE):
        with open(PFILE) as f:
            pd = json.load(f)
            if "stats" in pd:
                result["stats"] = pd["stats"]
                result["stats"]["days_active"] = days_active
    else:
        result["stats"] = {"total_actions": 0, "days_active": days_active}
    return result
