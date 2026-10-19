"""Live waiting room: real check-ins from the ER Priority intake.

The scripted replay (engine.py) tells the fixed Bay 4 story. This module runs the
same Atria agents and coordinators over patients who actually checked in, using
wall-clock time. Where readings come from:

- the patient's own phone: pain score and "I feel worse / same / better" updates
- staff re-checks entered on the ER dashboard: heart rate, SpO2, pain

Priority is always assigned by a human. Atria never changes it; it only orders
the separate reassessment attention list and flags persistent change.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

import core
from tracing import span

UNASSIGNED_SORT = 4  # below Priority 3, used only for ordering; never stored or shown
FEELING_NOTES = {
    "worse": "Patient reports feeling worse",
    "same": "Patient reports no change",
    "better": "Patient reports feeling better",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


class LiveWaitingRoom:
    def __init__(self, store):
        self.store = store

    # ---------- writes ----------

    def check_in(self, name: str, date_of_birth: Optional[str], symptoms: list[str],
                 notes: Optional[str], pain: Optional[int]) -> dict:
        pid = str(uuid.uuid4())
        at = core.iso(now())
        ticket = f"W-{len(self.store.list_checkins()) + 1:02d}"
        with span("atria.live", "check_in", ticket=ticket):
            self.store.upsert_patients([{
                "id": pid,
                "bay": ticket,
                "arrival_time": at,
                "initial_triage": None,
                "chief_complaint": ", ".join(symptoms),
            }])
            checkin = self.store.insert_checkin({
                "id": pid,
                "ticket": ticket,
                "display_name": name,
                "date_of_birth": date_of_birth or None,
                "symptoms": symptoms,
                "notes": notes or None,
            })
            self._event(pid, "intake", pain=pain, note=f"Check-in: {', '.join(symptoms)}")
        return checkin

    def report(self, checkin_id: str, pain: Optional[int], feeling: Optional[str]) -> dict:
        with span("atria.live", "patient_report", feeling=feeling):
            return self._event(checkin_id, "report", pain=pain, note=FEELING_NOTES.get(feeling))

    def record_vitals(self, checkin_id: str, hr: Optional[int], spo2: Optional[int], pain: Optional[int]) -> dict:
        with span("atria.live", "staff_recheck"):
            event = self._event(checkin_id, "recheck", hr=hr, spo2=spo2, pain=pain)
            # A re-check answers an open reassessment request.
            self.store.update_checkin(checkin_id, {"reassessment_requested_at": None})
        return event

    def set_priority(self, checkin_id: str, priority: Optional[int]) -> dict:
        self.store.update_patient(checkin_id, {"initial_triage": priority})
        return self.store.update_checkin(checkin_id, {"priority": priority})

    def request_reassessment(self, checkin_id: str, actor: str, reason: Optional[str]) -> dict:
        with span("atria.audit", "insert_audit", action="request_reassessment", patient_id=checkin_id):
            entry = self._audit(checkin_id, actor, "request_reassessment", reason)
        self.store.update_checkin(checkin_id, {"reassessment_requested_at": entry["created_at"]})
        return entry

    def call_in(self, checkin_id: str, actor: str) -> dict:
        self._audit(checkin_id, actor, "resolve", "Called in from the waiting room")
        return self.store.update_checkin(checkin_id, {"status": "called", "reassessment_requested_at": None})

    def reset(self) -> int:
        ids = [c["id"] for c in self.store.list_checkins()]
        self.store.delete_patients(ids)
        return len(ids)

    def _event(self, pid: str, kind: str, **values) -> dict:
        row = {
            "patient_id": pid,
            "observed_at": core.iso(now()),
            "run_id": "live",
            "event_key": f"live:{pid}:{kind}:{uuid.uuid4().hex[:12]}",
            **{k: v for k, v in values.items() if v is not None},
        }
        out = self.store.insert_events([row])
        return out[0] if out else row

    def _audit(self, pid: str, actor: str, action: str, reason: Optional[str]) -> dict:
        return self.store.insert_audit({
            "patient_id": pid,
            "actor": actor,
            "action": action,
            "reason": reason,
            "run_id": "live",
            "idempotency_key": f"live:{uuid.uuid4()}",
        })

    # ---------- reads ----------

    def get(self, checkin_id: str) -> Optional[dict]:
        return self.store.get_checkin(checkin_id)

    def waiting(self) -> list[dict]:
        return [c for c in self.store.list_checkins() if c["status"] == "waiting"]

    @staticmethod
    def line(checkins: list[dict]) -> list[dict]:
        """The official line: human priority, then check-in time. Unassigned patients await triage."""
        assigned = [c for c in checkins if c.get("priority")]
        return sorted(assigned, key=lambda c: (c["priority"], c["created_at"]))

    def queue(self, include_agents: bool = False) -> dict:
        as_of = now()
        checkins = self.waiting()
        ids = [c["id"] for c in checkins]
        patients = {p["id"]: p for p in self.store.list_patients(ids)} if ids else {}
        by_patient: dict[str, list] = {}
        for e in (self.store.list_events(ids) if ids else []):
            by_patient.setdefault(e["patient_id"], []).append(e)

        line_pos = {c["id"]: i + 1 for i, c in enumerate(self.line(checkins))}
        views = []
        with span("atria.coordinator", "patient_coordinator", patients=len(checkins), mode="live"):
            for c in checkins:
                p = patients.get(c["id"])
                if not p:
                    continue
                sortable = {**p, "initial_triage": c.get("priority") or UNASSIGNED_SORT}
                views.append(core.patient_coordinator(sortable, by_patient.get(c["id"], []), as_of))
        with span("atria.coordinator", "waiting_room_coordinator", mode="live"):
            ordered = core.waiting_room_coordinator(views)

        info = {c["id"]: c for c in checkins}
        for v in ordered:
            c = info[v["id"]]
            if not include_agents:
                v.pop("agents", None)
            v.update({
                "ticket": c["ticket"],
                "name": c["display_name"],
                "date_of_birth": c.get("date_of_birth"),
                "symptoms": c.get("symptoms") or [],
                "notes": c.get("notes"),
                "priority": c.get("priority"),
                "initial_triage": c.get("priority"),
                "severity_label": "Priority",
                "line_position": line_pos.get(c["id"]),
                "reassessment_requested_at": c.get("reassessment_requested_at"),
                "checked_in_at": c["created_at"],
                "readings": sum(1 for e in by_patient.get(c["id"], []) if any(e.get(m) is not None for m in core.METRICS)),
                "demo": False,
            })
        return {
            "queue": ordered,
            "as_of": core.iso(as_of),
            "queue_version": f"live@{core.hhmm(as_of)}",
            "data_note": "live demo check-ins, not real patients",
            "policy_version": core.POLICY_VERSION,
            "waiting": len(ordered),
            "awaiting_triage": sum(1 for v in ordered if not v["priority"]),
            "flagged": sum(1 for v in ordered if v["reassessment_signal"]),
            "official_priority_unchanged": True,
        }

    def status(self, checkin_id: str) -> Optional[dict]:
        """What the patient sees: their own place in line, never other patients' details."""
        c = self.store.get_checkin(checkin_id)
        if not c:
            return None
        waited = max(0, int((now() - core.parse_dt(c["created_at"])).total_seconds() // 60))
        base = {
            "id": c["id"],
            "ticket": c["ticket"],
            "name": c["display_name"],
            "symptoms": c.get("symptoms") or [],
            "checked_in_at": c["created_at"],
            "waited_minutes": waited,
            "status": c["status"],
            "as_of": core.iso(now()),
        }
        if c["status"] != "waiting":
            return {**base, "stage": "called"}
        waiting = self.waiting()
        line = self.line(waiting)
        tickets = [{"ticket": w["ticket"], "you": w["id"] == c["id"]} for w in line]
        pos = next((i + 1 for i, w in enumerate(line) if w["id"] == c["id"]), None)
        events = [e for e in self.store.list_events([c["id"]])]
        last_report = next((e["observed_at"] for e in reversed(core.sort_events(events)) if e.get("run_id") == "live"), None)
        if c.get("reassessment_requested_at"):
            stage = "recheck_requested"
        elif pos is None:
            stage = "awaiting_triage"
        else:
            stage = "waiting"
        return {
            **base,
            "stage": stage,
            "priority_assigned": pos is not None,
            "line_position": pos,
            "ahead": (pos - 1) if pos else None,
            "line": tickets,
            "awaiting_triage_count": sum(1 for w in waiting if not w.get("priority")),
            "total_waiting": len(waiting),
            "last_update": last_report,
        }
