"""Backend-owned deterministic replay plus queue/evidence projections."""
import threading
import uuid
from typing import Optional

import core
import scenario
from tracing import span

BASE_INTERVAL_SECONDS = 3.0
SPEEDS = (1, 2, 5)


class DemoEngine:
    def __init__(self, store):
        self.store = store
        self.schedule = scenario.schedule()
        self.ids = scenario.PATIENT_IDS
        self._lock = threading.Lock()
        self._positions_version = None
        self._positions: dict = {}
        self._previous: dict = {}

    # ---------- run state ----------

    def run(self) -> Optional[dict]:
        return self.store.get_run()

    def reset(self) -> dict:
        with self._lock:
            run_id = "run-" + uuid.uuid4().hex[:8]
            self.store.upsert_patients(scenario.patient_rows())
            self.store.delete_events(self.ids)
            self.store.insert_events([self._row(e, run_id) for e in scenario.intake_events()])
            self._positions_version, self._positions, self._previous = None, {}, {}
            return self.store.save_run(
                {"run_id": run_id, "cursor": 0, "status": "paused", "speed": 1, "active": True}
            )

    def _row(self, event: dict, run_id: str) -> dict:
        return {**event, "run_id": run_id, "event_key": f"{run_id}:{scenario.event_key(event)}"}

    def step(self, run_id: Optional[str] = None) -> dict:
        """Apply the next scheduled event. A stale run_id is ignored, never applied."""
        with self._lock:
            run = self.store.get_run()
            if not run:
                raise LookupError("no active demo run; reset first")
            if run_id is not None and run["run_id"] != run_id:
                return run
            cursor = run["cursor"]
            if cursor >= len(self.schedule):
                return self.store.save_run({**run, "status": "complete"})
            event = self.schedule[cursor]
            with span("atria.ingest", "replay_event", patient_id=event["patient_id"], observed_at=event["observed_at"], cursor=cursor):
                self.store.insert_events([self._row(event, run["run_id"])])
            cursor += 1
            status = "complete" if cursor >= len(self.schedule) else run["status"]
            return self.store.save_run({**run, "cursor": cursor, "status": status})

    def set_status(self, status: str, speed: Optional[float] = None) -> dict:
        with self._lock:
            run = self.store.get_run()
            if not run:
                raise LookupError("no active demo run; reset first")
            if run["status"] == "complete" and status == "running":
                return run
            update = {**run, "status": status}
            if speed is not None:
                update["speed"] = speed
            return self.store.save_run(update)

    def interval(self, run: dict) -> float:
        return BASE_INTERVAL_SECONDS / float(run.get("speed") or 1)

    # ---------- projections ----------

    def context(self) -> dict:
        run = self.run()
        patients = self.store.list_patients(self.ids)
        events = self.store.list_events(self.ids)
        if run:
            cursor = run["cursor"]
            as_of = scenario.start_time() if cursor == 0 else self.schedule[cursor - 1]["observed_at"]
            version = f"{run['run_id']}.v{cursor}"
            events = [e for e in events if e.get("run_id") == run["run_id"]]
        else:
            cursor = None
            as_of = max((e["observed_at"] for e in events), default=scenario.start_time())
            version = "unversioned"
        return {
            "run": run,
            "patients": patients,
            "events": events,
            "as_of": core.parse_dt(as_of),
            "queue_version": version,
            "total_events": len(self.schedule),
            "cursor": cursor,
        }

    def queue(self, ctx: Optional[dict] = None) -> dict:
        ctx = ctx or self.context()
        by_patient: dict[str, list] = {}
        for e in ctx["events"]:
            by_patient.setdefault(e["patient_id"], []).append(e)
        with span("atria.coordinator", "patient_coordinator", patients=len(ctx["patients"])):
            views = [core.patient_coordinator(p, by_patient.get(p["id"], []), ctx["as_of"]) for p in ctx["patients"]]

        with self._lock, span("atria.coordinator", "waiting_room_coordinator", queue_version=ctx["queue_version"]):
            if ctx["queue_version"] != self._positions_version:
                self._previous = self._positions
            ordered = core.waiting_room_coordinator(views, self._previous)
            if ctx["queue_version"] != self._positions_version:
                self._positions = {v["id"]: v["attention_position"] for v in ordered}
                self._positions_version = ctx["queue_version"]

        return {
            "queue": ordered,
            "queue_version": ctx["queue_version"],
            "policy_version": core.POLICY_VERSION,
            "as_of": core.iso(ctx["as_of"]),
            "run": self.public_run(ctx),
            "official_triage_unchanged": True,
            "demo": True,
        }

    def public_run(self, ctx: dict) -> dict:
        run = ctx["run"]
        if not run:
            return {"status": "needs_reset", "run_id": None, "cursor": None, "total_events": ctx["total_events"]}
        next_event = self.schedule[run["cursor"]] if run["cursor"] < len(self.schedule) else None
        return {
            "run_id": run["run_id"],
            "status": run["status"],
            "speed": float(run.get("speed") or 1),
            "cursor": run["cursor"],
            "total_events": ctx["total_events"],
            "next_event_at": next_event["observed_at"] if next_event else None,
            "store": self.store.name,
        }

    def evidence(self, patient_id: str) -> Optional[dict]:
        ctx = self.context()
        q = self.queue(ctx)
        view = next((v for v in q["queue"] if v["id"] == patient_id), None)
        if not view:
            return None
        run_id = ctx["run"]["run_id"] if ctx["run"] else None
        events = [e for e in ctx["events"] if e["patient_id"] == patient_id]
        audit = self.store.list_audit([patient_id], run_id)
        view = dict(view)
        view["timeline"] = timeline(view, events, audit)
        view["audit_log"] = audit
        view["queue_version"] = q["queue_version"]
        view["as_of"] = q["as_of"]
        view["limitations"] = [
            "Synthetic demo data; thresholds are illustrative and not clinically validated.",
            "Independent model signal unavailable." if view["agents"]["open_model"]["status"] == "unavailable" else "",
        ]
        view["limitations"] = [x for x in view["limitations"] if x]
        return view


def timeline(view: dict, events: list[dict], audit: list[dict]) -> list[dict]:
    items = []
    for i, e in enumerate(core.sort_events(events)):
        has_vitals = any(e.get(m) is not None for m in core.METRICS)
        kind = "intake" if i == 0 else ("measurement" if has_vitals else "report")
        items.append({
            "id": e.get("id"),
            "type": kind,
            "at": e["observed_at"],
            "hr": e.get("hr"),
            "spo2": e.get("spo2"),
            "pain": e.get("pain"),
            "note": e.get("note"),
            "source": "synthetic demo replay",
        })
    for a in audit:
        items.append({
            "id": a.get("id"),
            "type": "human_action",
            "at": a["created_at"],
            "action": a["action"],
            "actor": a["actor"],
            "reason": a.get("reason"),
            "source": "audit_log",
            "wall_clock": True,
        })
    return items
