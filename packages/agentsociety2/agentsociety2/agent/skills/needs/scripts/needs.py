"""needs skill (subprocess mode).

Execute: python needs.py --args-json '{"observation":"...","tick":1}'
Reads/writes state/needs.json and state/current_need.txt in cwd.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import json_repair

THRESHOLDS = {"satiety": 0.2, "energy": 0.2, "safety": 0.2, "social": 0.3}
DEFAULTS = {"satiety": 0.7, "energy": 0.3, "safety": 0.9, "social": 0.8}
DECAY = {"satiety": 0.02, "energy": 0.03, "safety": 0.0, "social": 0.0}

TIME_MULT = {
    "satiety": {(6, 9): 1.5, (11, 13): 1.8, (18, 20): 1.6},
    "energy": {(22, 6): 0.5, (14, 16): 1.3},
}

ACTIVITY_DELTA = {
    "walking": {"energy": -0.01},
    "running": {"energy": -0.02},
    "working": {"energy": -0.02, "satiety": -0.01},
    "socializing": {"social": 0.05, "energy": -0.01},
    "eating": {"satiety": 0.3, "energy": 0.05},
    "sleeping": {"energy": 0.2, "satiety": -0.02},
    "resting": {"energy": 0.1},
    "reading": {"energy": -0.005},
    "exercising": {"energy": -0.03, "satiety": -0.02},
}

CAN_INTERRUPT = {"satiety": True, "energy": True, "safety": False, "social": False}

ACTIVITY_WORDS = {
    "walking": ["walk", "stroll", "wandering"],
    "running": ["run", "jog", "sprint"],
    "working": ["work", "job", "office", "meeting", "task"],
    "socializing": ["chat", "talk", "conversation", "social", "party", "meet"],
    "eating": ["eat", "food", "meal", "lunch", "dinner", "breakfast", "snack"],
    "sleeping": ["sleep", "nap", "bed", "asleep"],
    "resting": ["rest", "relax", "break"],
    "reading": ["read", "book", "newspaper"],
    "exercising": ["exercise", "gym", "workout", "fitness", "training"],
}


def clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def time_mult(need: str, hour: int) -> float:
    """Get time-based decay multiplier."""
    if need not in TIME_MULT:
        return 1.0
    for (start, end), m in TIME_MULT[need].items():
        if start <= end:
            if start <= hour < end:
                return m
        elif hour >= start or hour < end:
            return m
    return 1.0


def decay(needs: dict, hour: int | None = None):
    """Apply natural decay with optional time multiplier."""
    for need, rate in DECAY.items():
        if rate > 0:
            m = time_mult(need, hour) if hour is not None else 1.0
            needs[need] = clamp(needs[need] - rate * m)


def detect_activities(text: str) -> list[str]:
    """Detect activities from observation text."""
    text = text.lower()
    found = []
    for act, words in ACTIVITY_WORDS.items():
        if any(w in text for w in words):
            found.append(act)
    return found


def apply_activities(needs: dict, activities: list[str]) -> list[dict]:
    """Apply activity impacts to needs."""
    adj = []
    for act in activities:
        if act in ACTIVITY_DELTA:
            for need, delta in ACTIVITY_DELTA[act].items():
                if need in needs:
                    old = needs[need]
                    needs[need] = clamp(needs[need] + delta)
                    adj.append({"need": need, "delta": delta, "activity": act, "old": old, "new": needs[need]})
    return adj


def load_needs(path: Path) -> dict[str, float]:
    """Load or initialize needs."""
    if not path.exists():
        return DEFAULTS.copy()
    data = json_repair.loads(path.read_text(encoding="utf-8"))
    return {k: float(data.get(k, DEFAULTS[k])) for k in DEFAULTS}


def load_thresholds(path: Path) -> dict[str, float]:
    """Load thresholds from needs.json."""
    if not path.exists():
        return THRESHOLDS.copy()
    data = json_repair.loads(path.read_text(encoding="utf-8"))
    t = data.get("thresholds", {})
    return {k: float(t.get(k, THRESHOLDS[k])) for k in THRESHOLDS}


def keyword_adjust(needs: dict, text: str) -> list[dict]:
    """Adjust needs based on observation keywords."""
    adj = []
    text = text.lower()

    if any(w in text for w in ["hungry", "food", "eat", "meal", "restaurant", "cafe", "lunch", "dinner", "breakfast"]):
        old = needs["satiety"]
        needs["satiety"] = clamp(needs["satiety"] + 0.15)
        adj.append({"need": "satiety", "type": "keyword", "old": old, "new": needs["satiety"]})

    if any(w in text for w in ["sleep", "rest", "tired", "bed", "home", "relax"]):
        old = needs["energy"]
        needs["energy"] = clamp(needs["energy"] + 0.15)
        adj.append({"need": "energy", "type": "keyword", "old": old, "new": needs["energy"]})

    if any(w in text for w in ["danger", "unsafe", "threat", "attack", "rob", "hurt", "injury"]):
        old = needs["safety"]
        needs["safety"] = clamp(needs["safety"] - 0.2)
        adj.append({"need": "safety", "type": "keyword", "old": old, "new": needs["safety"]})

    if any(w in text for w in ["friend", "chat", "talk", "social", "conversation", "meet", "party"]):
        old = needs["social"]
        needs["social"] = clamp(needs["social"] + 0.1)
        adj.append({"need": "social", "type": "keyword", "old": old, "new": needs["social"]})

    if any(w in text for w in ["work", "job", "busy", "task", "project", "deadline"]):
        old = needs["energy"]
        needs["energy"] = clamp(needs["energy"] - 0.05)
        adj.append({"need": "energy", "type": "keyword", "old": old, "new": needs["energy"]})

    if any(w in text for w in ["safe", "secure", "home", "protected"]):
        old = needs["safety"]
        needs["safety"] = clamp(needs["safety"] + 0.1)
        adj.append({"need": "safety", "type": "keyword", "old": old, "new": needs["safety"]})

    return adj


def current_need(needs: dict, thresholds: dict) -> str:
    """Determine most urgent need."""
    for need in ["satiety", "energy", "safety", "social"]:
        if needs[need] <= thresholds[need]:
            return need
    return "whatever"


def should_interrupt(need: str, needs: dict, thresholds: dict) -> bool:
    """Check if current need should interrupt plan."""
    if need == "whatever":
        return False
    return CAN_INTERRUPT.get(need, False) and needs[need] <= thresholds[need]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--args-json", default="{}")
    ns = parser.parse_args()
    args = json_repair.loads(ns.args_json or "{}")

    cwd = Path.cwd()
    state_dir = cwd / "state"
    state_dir.mkdir(exist_ok=True)
    needs_path = state_dir / "needs.json"

    needs = load_needs(needs_path)
    thresholds = load_thresholds(needs_path)

    obs = str(args.get("observation", ""))
    time_str = args.get("time")

    hour = None
    if time_str:
        try:
            hour = int(str(time_str).split(":")[0])
        except (ValueError, AttributeError, IndexError):
            pass

    decay(needs, hour)
    adjustments = keyword_adjust(needs, obs)
    activities = detect_activities(obs)
    adjustments.extend(apply_activities(needs, activities))

    need = current_need(needs, thresholds)
    interrupt = should_interrupt(need, needs, thresholds)

    output = {
        **needs,
        "current_need": need,
        "thresholds": thresholds,
        "can_interrupt": CAN_INTERRUPT,
        "should_interrupt_plan": interrupt,
    }

    needs_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    (state_dir / "current_need.txt").write_text(need, encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "current_need": need,
        "needs": needs,
        "thresholds": thresholds,
        "adjustments": adjustments,
        "activities": activities,
        "should_interrupt_plan": interrupt,
        "tick": args.get("tick"),
        "hour": hour,
    }, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
