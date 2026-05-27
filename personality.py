#!/usr/bin/env python3
"""Goldie Personality System — tracks personality dimensions based on agent activities."""
import json, os
from datetime import datetime

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
PFILE = os.path.join(DATA, 'personality.json')

def load():
    if os.path.exists(PFILE):
        try:
            with open(PFILE, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    p = default()
    save(p)
    return p

def save(p):
    os.makedirs(os.path.dirname(PFILE), exist_ok=True)
    tmp = f'{PFILE}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(p, f, indent=2, ensure_ascii=False)
    os.replace(tmp, PFILE)

def default():
    return {
        "dimensions": {
            "explorer": {"value": 0.10, "color": "#5cb88a", "label": "Explorer"},
            "scholar": {"value": 0.05, "color": "#d4a24c", "label": "Scholar"},
            "builder": {"value": 0.02, "color": "#5eadb8", "label": "Builder"},
            "contributor": {"value": 0.0, "color": "#8b82b8", "label": "Contributor"},
            "architect": {"value": 0.02, "color": "#c9a24c", "label": "Architect"},
            "dreamer": {"value": 0.02, "color": "#c95c5c", "label": "Dreamer"},
        },
        "activity_weights": {},
        "timeline": [],
        "mood_timeline": [],
        "stats": {"total_actions": 0, "days_active": 1}
    }

def track(activity_type, day_num=None):
    """Increment personality dimensions based on agent activity type."""
    p = load()
    weights = p.get("activity_weights", {})
    aw = weights.get(activity_type, {})
    if not aw:
        return False
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for dim, delta in aw.items():
        if dim in p["dimensions"]:
            old = p["dimensions"][dim]["value"]
            p["dimensions"][dim]["value"] = min(old + delta, 1.0)
    p["timeline"].append({
        "activity": activity_type,
        "deltas": {k: round(v, 3) for k, v in aw.items()},
        "timestamp": now,
        "day": day_num,
    })
    p["history"] = p["timeline"][-200:]
    p["stats"]["total_actions"] = p.get("stats", {}).get("total_actions", 0) + 1
    save(p)
    return True

def get_radar():
    """Return data formatted for personality radar chart."""
    p = load()
    dims = p.get("dimensions", {})
    return {
        "labels": [v.get("label", k) for k, v in dims.items()],
        "data": [round(v["value"], 3) for v in dims.values()],
        "colors": [v.get("color", "#ccc") for v in dims.values()],
        "keys": list(dims.keys()),
    }