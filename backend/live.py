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
import scenario
from tracing import span

UNASSIGNED_SORT = 4  # below Priority 3, used only for ordering; never stored or shown
# Sample waiting room: the fixed scenario as fictional check-ins (bay -> name, date of birth).
SAMPLE_PEOPLE = {
    "Bay 7": ("Daniel Reyes", "1958-03-14"),
    "Bay 4": ("Maya Patel", "1988-04-12"),
    "Bay 2": ("Grace Kim", "1995-07-30"),
    "Bay 9": ("Omar Haddad", "1979-11-02"),
    "Bay 1": ("Sofia Alvarez", "2003-01-25"),
    "Bay 3": ("Ethan Brooks", "1991-05-08"),
    "Bay 5": ("Priya Nair", "1966-09-19"),
    "Bay 6": ("Lucas Meyer", "1984-12-03"),
}
SAMPLE_PRIORITY = {1: 1, 2: 2, 3: 3, 4: 3, 5: 3}  # illustrative ESI -> Priority 1-3

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
        self.sample: Optional[dict] = None  # {"ids": scenario id -> check-in id, "cursor": int}

    # ---------- writes ----------

    def check_in(self, name: str, date_of_birth: Optional[str], symptoms: list[str],
                 notes: Optional[str], pain: Optional[int], arrived_at: Optional[datetime] = None,
                 intake: Optional[dict] = None) -> dict:
        pid = str(uuid.uuid4())
        arrived = arrived_at or now()
        at = arrived.isoformat()
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
                "created_at": at,
                "id": pid,
                "ticket": ticket,
                "display_name": name,
                "date_of_birth": date_of_birth or None,
                "symptoms": symptoms,
                "notes": notes or None,
            })
            readings = intake or {"pain": pain}
            self._event(pid, "intake", at=at, note=f"Check-in: {', '.join(symptoms)}", **readings)
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

    def acknowledge(self, checkin_id: str, actor: str, priority: Optional[int] = None) -> dict:
        """Nurse acknowledges an Atria flag, optionally raising priority (which moves them up the line)."""
        old = (self.store.get_checkin(checkin_id) or {}).get("priority")
        if priority is not None and priority != old:
            self.set_priority(checkin_id, priority)
            reason = f"Acknowledged Atria flag; priority {old or 'unassigned'} -> {priority}"
        else:
            reason = "Acknowledged Atria flag; priority unchanged"
        with span("atria.audit", "insert_audit", action="acknowledge", patient_id=checkin_id):
            return self._audit(checkin_id, actor, "acknowledge", reason)

    def call_in(self, checkin_id: str, actor: str) -> dict:
        self._audit(checkin_id, actor, "resolve", "Called in from the waiting room")
        return self.store.update_checkin(checkin_id, {"status": "called", "reassessment_requested_at": None})

    def reset(self) -> int:
        self.sample = None
        ids = [c["id"] for c in self.store.list_checkins()]
        self.store.delete_patients(ids)
        return len(ids)

    # ---------- sample waiting room (demo) ----------

    def load_sample(self) -> dict:
        """Replace the waiting room with 8 fictional patients from the fixed scenario."""
        self.reset()
        events = scenario.schedule()
        start = core.parse_dt(events[0]["observed_at"])
        current = now()
        ids = {}
        rows = sorted(scenario.PATIENTS, key=lambda p: (p[2], p[0]))
        for bay, sid, arrival, esi, complaint, readings in rows:
            name, dob = SAMPLE_PEOPLE[bay]
            arrived = current - (start - core.parse_dt(scenario.t(arrival)))
            _, hr, spo2, pain, _ = readings[0]
            c = self.check_in(name, dob, [complaint.replace(" (synthetic demo)", "")], None, None,
                              arrived_at=arrived, intake={"hr": hr, "spo2": spo2, "pain": pain})
            self.set_priority(c["id"], SAMPLE_PRIORITY[esi])
            ids[sid] = c["id"]
        self.sample = {"ids": ids, "cursor": 0}
        return self.sample_state()

    def sample_next(self) -> dict:
        """Record the next scripted reading as if a nurse or patient entered it now."""
        if not self.sample:
            raise LookupError("load the sample waiting room first")
        events = scenario.schedule()
        if self.sample["cursor"] < len(events):
            e = events[self.sample["cursor"]]
            pid = self.sample["ids"][e["patient_id"]]
            if self.store.get_checkin(pid):
                with span("atria.ingest", "sample_reading", cursor=self.sample["cursor"]):
                    self._event(pid, "sample", **{k: e[k] for k in ("hr", "spo2", "pain", "note")})
            self.sample["cursor"] += 1
        return self.sample_state()

    def sample_state(self) -> dict:
        total = len(scenario.schedule())
        if not self.sample:
            return {"loaded": False, "cursor": 0, "total": total}
        return {"loaded": True, "cursor": self.sample["cursor"], "total": total,
                "done": self.sample["cursor"] >= total}

    def _event(self, pid: str, kind: str, at: Optional[str] = None, **values) -> dict:
        row = {
            "patient_id": pid,
            # Full precision, to order readings against acknowledgements.
            "observed_at": at or now().isoformat(),
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

        acks: dict[str, dict] = {}
        for a in (self.store.list_audit(ids, "live") if ids else []):
            if a["action"] == "acknowledge":
                acks[a["patient_id"]] = a  # list is oldest first, so the latest wins
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
            ack = acks.get(v["id"])
            # A flag stays acknowledged until a newer reading arrives.
            acked = bool(ack) and (
                not v["current"]["observed_at"]
                or core.parse_dt(ack["created_at"]) >= core.parse_dt(v["current"]["observed_at"])
            )
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
                "alert_active": v["reassessment_signal"] and not acked,
                "acknowledged_at": ack["created_at"] if ack else None,
                "acknowledged_by": ack["actor"] if ack else None,
                "acknowledgement": ack["reason"] if ack else None,
                "readings": sum(1 for e in by_patient.get(c["id"], []) if any(e.get(m) is not None for m in core.METRICS)),
                "demo": False,
            })
            # Live patients have a check-in, not a scripted intake.
            v["reasons"] = [r.replace("since intake", "since check-in") for r in v["reasons"]]
            v["ordering_reason"] = v["ordering_reason"].replace("intake severity", "priority").replace(
                "intake labels unchanged", "priority unchanged")
        return {
            "queue": ordered,
            "as_of": core.iso(as_of),
            "queue_version": f"live@{core.hhmm(as_of)}",
            "data_note": "live demo check-ins, not real patients",
            "policy_version": core.POLICY_VERSION,
            "waiting": len(ordered),
            "awaiting_triage": sum(1 for v in ordered if not v["priority"]),
            "flagged": sum(1 for v in ordered if v["reassessment_signal"]),
            "alerts": sum(1 for v in ordered if v["alert_active"]),
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
