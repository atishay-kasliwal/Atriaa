"""Deterministic Atria intelligence: agents, coordinators and queue policy.

Everything here is plain Python over stored events. No model is involved, and
the thresholds are illustrative demo values, not validated clinical criteria.
"""
from datetime import datetime, timezone
from typing import Optional

from dateutil import parser as dateparser

POLICY_VERSION = "atria-demo-policy-1"
METRICS = ("hr", "spo2", "pain")
UNITS = {"hr": "bpm", "spo2": "%", "pain": "/10"}
LABELS = {"hr": "Heart rate", "spo2": "SpO2", "pain": "Reported pain"}

# Direction that counts as worsening for each metric.
WORSENING_UP = {"hr": True, "spo2": False, "pain": True}

# Illustrative display thresholds for "notable" current values (demo only).
NOTABLE = {"hr": 110, "spo2": 92, "pain": 7}

# Smallest step between readings that counts toward persistent change, so
# measurement noise (e.g. HR 82 -> 83) is not read as a trend (demo only).
MIN_STEP = {"hr": 2, "spo2": 1, "pain": 1}

# Change since intake that marks a current deviation (demo only).
DEVIATION = {"hr": 15, "spo2": 3, "pain": 2}

WORSENING_WORDS = ("worse", "worsening", "increasing", "new ")

TRAJECTORY_TIER = {
    "persistent_change": 0,
    "mixed_change": 1,
    "transient_change": 1,
    "stable": 2,
    "insufficient_data": 2,
}


def parse_dt(value) -> datetime:
    dt = value if isinstance(value, datetime) else dateparser.isoparse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hhmm(value) -> str:
    return parse_dt(value).astimezone(timezone.utc).strftime("%H:%M")


def sort_events(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda e: parse_dt(e["observed_at"]))


def series(events: list[dict], key: str) -> list[dict]:
    return [{"value": e[key], "observed_at": e["observed_at"]} for e in events if e.get(key) is not None]


def is_worsening(delta: float, metric: str) -> bool:
    return delta > 0 if WORSENING_UP[metric] else delta < 0


# ---------- agents ----------

def vital_agent(events: list[dict]) -> dict:
    """What is happening now? Latest available value per metric."""
    current, notable = {}, []
    for m in METRICS:
        pts = series(events, m)
        if not pts:
            current[m] = None
            continue
        latest = pts[-1]
        current[m] = latest
        limit = NOTABLE[m]
        if (WORSENING_UP[m] and latest["value"] >= limit) or (not WORSENING_UP[m] and latest["value"] <= limit):
            notable.append(m)
    status = "insufficient_data" if all(v is None for v in current.values()) else "ok"
    findings = [
        f"{LABELS[m]} {current[m]['value']}{UNITS[m]} at {hhmm(current[m]['observed_at'])} is beyond the demo display threshold"
        for m in notable
    ]
    return {"agent": "vital", "status": status, "current": current, "notable": notable, "findings": findings}


def trend_agent(events: list[dict]) -> dict:
    """What changed since intake, how fast, and does it persist?"""
    intake, current, deltas, persistent, rates, resolved = {}, {}, {}, {}, {}, []
    for m in METRICS:
        pts = series(events, m)
        intake[m] = pts[0] if pts else None
        current[m] = pts[-1] if pts else None
        if len(pts) < 2:
            deltas[m] = None
            persistent[m] = False
            rates[m] = None
            continue
        vals = [p["value"] for p in pts]
        steps = [b - a for a, b in zip(vals, vals[1:])]
        deltas[m] = vals[-1] - vals[0]
        persistent[m] = len(vals) >= 3 and all(is_worsening(s, m) and abs(s) >= MIN_STEP[m] for s in steps)
        hours = (parse_dt(pts[-1]["observed_at"]) - parse_dt(pts[0]["observed_at"])).total_seconds() / 3600
        rates[m] = round(deltas[m] / hours, 1) if hours > 0 else None
        # A reading that deviated from intake but the latest one no longer does.
        for p in pts[1:-1]:
            d = p["value"] - vals[0]
            if is_worsening(d, m) and abs(d) >= DEVIATION[m] and not (
                is_worsening(deltas[m], m) and abs(deltas[m]) >= DEVIATION[m]
            ):
                resolved.append({"metric": m, "value": p["value"], "observed_at": p["observed_at"]})
                break

    deviating = [
        m for m in METRICS
        if deltas[m] is not None and is_worsening(deltas[m], m) and abs(deltas[m]) >= DEVIATION[m]
    ]
    count = sum(persistent.values())
    readings = sum(1 for e in events if any(e.get(m) is not None for m in METRICS))

    if readings < 2:
        trajectory = "insufficient_data"
    elif count >= 2:
        trajectory = "persistent_change"
    elif count == 1:
        trajectory = "mixed_change"
    elif deviating:
        trajectory = "transient_change"
    else:
        trajectory = "stable"

    findings = []
    for m in METRICS:
        if persistent[m]:
            vals = " -> ".join(str(p["value"]) for p in series(events, m))
            findings.append(f"{LABELS[m]} worsened on every reading: {vals}")
    for m in deviating:
        if not persistent[m]:
            findings.append(
                f"{LABELS[m]} changed {fmt_delta(deltas[m])}{UNITS[m]} since intake but not on every reading"
            )
    for r in resolved:
        findings.append(
            f"{LABELS[r['metric']]} deviated to {r['value']}{UNITS[r['metric']]} at {hhmm(r['observed_at'])}, then returned toward intake"
        )

    return {
        "agent": "trend",
        "status": "insufficient_data" if trajectory == "insufficient_data" else "ok",
        "trajectory": trajectory,
        "intake": intake,
        "current": current,
        "deltas": deltas,
        "rates_per_hour": rates,
        "signals_worsening": persistent,
        "worsening_count": count,
        "deviating": deviating,
        "resolved_deviations": resolved,
        "findings": findings,
    }


def context_agent(events: list[dict]) -> dict:
    """What did the patient report or staff observe?"""
    reports = [
        {"event_id": e.get("id"), "observed_at": e["observed_at"], "note": e["note"]}
        for e in events if e.get("note")
    ]
    worsening = [r for r in reports if any(w in r["note"].lower() for w in WORSENING_WORDS)]
    findings = [f"{hhmm(r['observed_at'])}: \"{r['note']}\"" for r in reports]
    return {
        "agent": "context",
        "status": "ok" if reports else "no_reports",
        "reports": reports,
        "reported_worsening": bool(worsening),
        "findings": findings,
        "method": "keyword match on synthetic notes",
    }


def model_agent() -> dict:
    """Placeholder for the independent open-model signal. Not implemented."""
    return {
        "agent": "open_model",
        "status": "unavailable",
        "findings": [],
        "note": "Independent numeric model not connected; counted as unavailable, not as a reassuring vote.",
    }


# ---------- coordinators ----------

def fmt_delta(v) -> str:
    if v is None:
        return "n/a"
    return f"+{v}" if v > 0 else str(v)


def patient_coordinator(patient: dict, events: list[dict], as_of: datetime) -> dict:
    events = sort_events(events)
    vital = vital_agent(events)
    trend = trend_agent(events)
    context = context_agent(events)
    model = model_agent()

    votes = {
        "trend": trend["trajectory"] == "persistent_change",
        "vital": bool(vital["notable"]),
        "context": context["reported_worsening"],
    }
    concern = sum(votes.values())
    if concern == 0 and trend["trajectory"] in ("stable", "insufficient_data"):
        consensus = "agree_no_change"
    elif concern == 3:
        consensus = "agree_change"
    elif trend["trajectory"] == "persistent_change" and concern >= 2:
        consensus = "majority_change"
    else:
        consensus = "low_consensus"

    reasons = []
    if trend["trajectory"] == "persistent_change":
        reasons.append(f"{trend['worsening_count']} of 3 signals worsened on every reading since intake")
    elif trend["trajectory"] == "mixed_change":
        reasons.append("1 of 3 signals worsened persistently; others unchanged")
    elif trend["trajectory"] == "transient_change":
        reasons.append("Latest reading differs from intake but the change is not persistent")
    elif trend["trajectory"] == "insufficient_data":
        reasons.append("Only intake reading available")
    else:
        reasons.append("No persistent change since intake")
    if trend["resolved_deviations"]:
        reasons.append("Earlier deviation resolved")
    if context["reported_worsening"]:
        reasons.append("Patient-reported worsening in notes")

    arrival = parse_dt(patient["arrival_time"])
    waiting = max(0, int((as_of - arrival).total_seconds() // 60))
    last = events[-1]["observed_at"] if events else None

    def value(point):
        return point["value"] if point else None

    return {
        "id": patient["id"],
        "patient_id": patient["id"],
        "bay": patient["bay"],
        "initial_triage": patient["initial_triage"],
        "chief_complaint": patient.get("chief_complaint"),
        "arrival_time": patient["arrival_time"],
        "as_of": iso(as_of),
        "waiting_minutes": waiting,
        "last_change": last,
        "trajectory": trend["trajectory"],
        "reassessment_signal": trend["trajectory"] == "persistent_change",
        "consensus": consensus,
        "low_consensus": consensus == "low_consensus",
        "reasons": reasons,
        "intake": {m: value(trend["intake"][m]) for m in METRICS}
        | {"observed_at": events[0]["observed_at"] if events else None},
        "current": {m: value(vital["current"][m]) for m in METRICS} | {"observed_at": last},
        "deltas": trend["deltas"],
        "signals_worsening": trend["signals_worsening"],
        "worsening_count": trend["worsening_count"],
        "series": {m: series(events, m) for m in METRICS},
        "agents": {"vital": vital, "trend": trend, "context": context, "open_model": model},
        "demo": True,
    }


def magnitude(view: dict) -> float:
    d = view.get("deltas") or {}
    return (
        max(0, d.get("hr") or 0) / 10
        + max(0, -(d.get("spo2") or 0)) / 2
        + max(0, d.get("pain") or 0) / 2
    )


def queue_sort_key(view: dict):
    tier = TRAJECTORY_TIER.get(view["trajectory"], 2)
    changing = tier < 2
    return (
        tier,
        -view.get("worsening_count", 0),
        # Size of change only orders patients who are changing; noise must not reorder stable ones.
        -round(magnitude(view), 3) if changing else 0,
        view["initial_triage"],
        -view["waiting_minutes"],
        view["bay"],
    )


def waiting_room_coordinator(views: list[dict], previous: Optional[dict] = None) -> list[dict]:
    """Order patients for reassessment attention. Separate from official triage."""
    previous = previous or {}
    ordered = sorted(views, key=queue_sort_key)
    for i, v in enumerate(ordered):
        v["attention_position"] = i + 1
        v["previous_position"] = previous.get(v["id"])
    for i, v in enumerate(ordered):
        below = [o for o in ordered[i + 1:] if o["initial_triage"] < v["initial_triage"]]
        if v["trajectory"] == "persistent_change" and below:
            v["ordering_reason"] = (
                f"Above higher-intake-severity {', '.join(o['bay'] for o in below)} because of persistent change; "
                "intake labels unchanged"
            )
        elif v["trajectory"] in ("persistent_change", "mixed_change", "transient_change"):
            v["ordering_reason"] = v["reasons"][0]
        else:
            v["ordering_reason"] = "No persistent change; ordered by intake severity, then waiting time"
    return ordered
