"""SQLite persistence for a local, synthetic ER demo. No clinical queue or AI scoring.

Each operation opens its own connection. Writes use BEGIN IMMEDIATE so a demo batch,
run/version update, or human request commits atomically. No legacy services are imported.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4, uuid5, NAMESPACE_URL

from .demo_data import BASE_TIME, BATCHES, COMMON, PATIENTS, SCENARIO

MEASUREMENTS = ("hr", "bp_sys", "bp_dia", "spo2", "temp_c", "rr", "pain")
TYPES = {"measurement", "pain_report", "symptom_report", "observation"}


class StaleStateError(ValueError):
    """The caller's run/version is no longer current; refetch before writing."""


def timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string with a timezone")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def now() -> str:
    return timestamp(datetime.now(timezone.utc).isoformat())


def encode(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_payload(payload: dict, event_type: str) -> dict:
    if event_type not in TYPES or not isinstance(payload, dict) or not payload:
        raise ValueError("a supported event type and nonempty payload are required")
    if set(payload) - set(MEASUREMENTS) - {"symptom", "observation"}:
        raise ValueError("unknown event fields")
    for key, value in payload.items():
        if key in MEASUREMENTS:
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError(f"{key} must be a finite number")
            if key in {"hr", "bp_sys", "bp_dia"} and value <= 0:
                raise ValueError(f"{key} must be positive")
            if key == "rr" and value < 0:
                raise ValueError("rr cannot be negative")
            if key == "spo2" and not 0 <= value <= 100:
                raise ValueError("spo2 must be 0..100 percent")
            if key == "pain" and (not 0 <= value <= 10 or int(value) != value):
                raise ValueError("pain must be an integer 0..10")
        elif not isinstance(value, str) or not value.strip() or len(value) > 1000:
            raise ValueError(f"{key} must be nonempty text up to 1000 characters")
    required = {"pain_report": "pain", "symptom_report": "symptom", "observation": "observation"}
    if event_type in required and required[event_type] not in payload:
        raise ValueError(f"{event_type} requires {required[event_type]}")
    if event_type == "measurement" and not set(payload).intersection(MEASUREMENTS):
        raise ValueError("measurement requires a numeric measurement")
    return dict(payload)


class DemoDatabase:
    def __init__(self, path: str | Path | None = None):
        default = Path(__file__).resolve().parents[1] / "var" / "atria-demo.sqlite3"
        self.path = Path(path or os.environ.get("ATRIA_DB_PATH") or default).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connection(self, *, write=False):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with sqlite3.connect(self.path) as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            if any(not name.startswith("er_") for name in tables):
                raise ValueError("refusing to initialize a database containing unrelated tables")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError(f"unsupported database schema version: {version}")
            conn.executescript(Path(__file__).with_name("schema.sql").read_text())
        # Initialization never resets an existing run or contacts an external service.

    @staticmethod
    def _run(conn, run_id=None):
        row = conn.execute("SELECT * FROM er_demo_runs WHERE active = 1").fetchone()
        if row is None:
            raise LookupError("no demo run; initialize and explicitly reset once")
        if run_id is not None and row["run_id"] != run_id:
            raise StaleStateError("demo was reset; refetch current run")
        return row

    @staticmethod
    def _version(run, expected_version):
        if expected_version is not None and run["version"] != expected_version:
            raise StaleStateError("state changed; refetch current version")

    @staticmethod
    def _event(conn, *, run_id, patient_id, sequence_no, event_time, event_type, payload, event_id=None):
        encounter = conn.execute("SELECT * FROM er_encounters WHERE run_id=? AND patient_id=?",
                                 (run_id, patient_id)).fetchone()
        if encounter is None:
            raise LookupError("unknown patient in this run")
        event_time = timestamp(event_time)
        if event_time < encounter["arrival_time"]:
            raise ValueError("event cannot precede arrival")
        if isinstance(sequence_no, bool) or not isinstance(sequence_no, int) or sequence_no < 0:
            raise ValueError("sequence_no must be a nonnegative integer")
        event_id = event_id or str(uuid5(NAMESPACE_URL, f"{run_id}/{patient_id}/{sequence_no}"))
        values = (run_id, patient_id, sequence_no, event_time, event_type, encode(payload))
        existing = conn.execute("SELECT * FROM er_patient_events WHERE event_id=?", (event_id,)).fetchone()
        if existing:
            old = tuple(existing[k] for k in ("run_id", "patient_id", "sequence_no", "event_time", "event_type", "payload_json"))
            if old != values:
                raise ValueError("event ID reused with a conflicting payload")
            return False
        conn.execute("INSERT INTO er_patient_events VALUES (?,?,?,?,?,?,?,?)",
                     (event_id, run_id, patient_id, sequence_no, event_time, now(), event_type, encode(payload)))
        return True

    def reset(self) -> dict:
        """Create a new disposable run; archive previous run without deleting history."""
        run_id = str(uuid4())
        with self._connection(write=True) as conn:
            conn.execute("UPDATE er_demo_runs SET active=0 WHERE active=1")
            conn.execute("INSERT INTO er_demo_runs VALUES (?,?,1,0,0,?,?)",
                         (run_id, SCENARIO, timestamp(BASE_TIME), now()))
            for spec in PATIENTS:
                intake = {**COMMON, **{key: spec[key] for key in ("hr", "spo2", "pain")}}
                conn.execute("INSERT INTO er_encounters VALUES (?,?,?,?,?,?,?)", (
                    run_id, spec["patient_id"], spec["bay"], timestamp(spec["arrival_time"]),
                    spec["initial_triage"], "Synthetic demo complaint; not a diagnosis", encode(intake)))
                self._event(conn, run_id=run_id, patient_id=spec["patient_id"], sequence_no=0,
                            event_time=spec["arrival_time"], event_type="intake", payload=intake)
                if spec.get("initial_review"):
                    conn.execute("INSERT INTO er_reassessment_requests VALUES (?,?,?,?,?,?,?,?,?)", (
                        str(uuid4()), run_id, spec["patient_id"], 0, "Synthetic intake nurse",
                        "Existing review request in the synthetic fixture", timestamp(spec["arrival_time"]),
                        now(), "synthetic_fixture"))
        return self.snapshot(run_id)

    def append_event(self, *, run_id, patient_id, event_id, sequence_no,
                     event_time, event_type, payload, expected_version=None) -> bool:
        payload = validate_payload(payload, event_type)
        if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 200:
            raise ValueError("source event_id is required (up to 200 characters)")
        with self._connection(write=True) as conn:
            run = self._run(conn, run_id)
            # Idempotent retries are checked before the optimistic-version check.
            existing = conn.execute("SELECT 1 FROM er_patient_events WHERE event_id=?", (event_id,)).fetchone()
            if not existing:
                self._version(run, expected_version)
            created = self._event(conn, run_id=run_id, patient_id=patient_id, event_id=event_id,
                                  sequence_no=sequence_no, event_time=event_time, event_type=event_type, payload=payload)
            if created:
                conn.execute("UPDATE er_demo_runs SET version=version+1, replay_time=max(replay_time,?) WHERE run_id=?",
                             (timestamp(event_time), run_id))
            return created

    def next_batch(self, *, run_id: str, expected_version: int) -> dict:
        with self._connection(write=True) as conn:
            run = self._run(conn, run_id)
            self._version(run, expected_version)
            if run["cursor"] < len(BATCHES):
                event_time, changes = BATCHES[run["cursor"]]
                for spec in PATIENTS:
                    payload = {**COMMON, **{k: spec[k] for k in ("hr", "spo2", "pain")},
                               **changes.get(spec["patient_id"], {})}
                    validate_payload(payload, "measurement")
                    self._event(conn, run_id=run_id, patient_id=spec["patient_id"],
                                sequence_no=run["cursor"]+1, event_time=event_time,
                                event_type="measurement", payload=payload)
                conn.execute("UPDATE er_demo_runs SET cursor=cursor+1,version=version+1,replay_time=? WHERE run_id=?",
                             (timestamp(event_time), run_id))
        return self.snapshot(run_id)

    def request_reassessment(self, *, run_id, patient_id, expected_version, actor, reason) -> dict:
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 100:
            raise ValueError("demo actor is required (up to 100 characters)")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError("reason is required (up to 1000 characters)")
        with self._connection(write=True) as conn:
            run = self._run(conn, run_id)
            if not conn.execute("SELECT 1 FROM er_encounters WHERE run_id=? AND patient_id=?", (run_id, patient_id)).fetchone():
                raise LookupError("unknown patient in this run")
            existing = conn.execute("SELECT * FROM er_reassessment_requests WHERE run_id=? AND patient_id=?",
                                    (run_id, patient_id)).fetchone()
            if existing:
                return {"created": False, "action": dict(existing)}
            self._version(run, expected_version)
            action_id = str(uuid4())
            conn.execute("INSERT INTO er_reassessment_requests VALUES (?,?,?,?,?,?,?,?,?)", (
                action_id, run_id, patient_id, run["version"], actor.strip(), reason.strip(),
                run["replay_time"], now(), "human_demo_action"))
            conn.execute("UPDATE er_demo_runs SET version=version+1 WHERE run_id=?", (run_id,))
            action = dict(conn.execute("SELECT * FROM er_reassessment_requests WHERE action_id=?", (action_id,)).fetchone())
            return {"created": True, "action": action}

    def snapshot(self, run_id=None) -> dict:
        with self._connection() as conn:
            run = self._run(conn) if run_id is None else conn.execute(
                "SELECT * FROM er_demo_runs WHERE run_id=?", (run_id,)).fetchone()
            if run is None:
                raise LookupError("unknown demo run")
            patients = []
            for row in conn.execute("SELECT * FROM er_encounters WHERE run_id=? ORDER BY bay", (run["run_id"],)):
                intake = json.loads(row["intake_json"])
                current, measured_at, timeline = {}, {}, []
                for event in conn.execute("SELECT * FROM er_patient_events WHERE run_id=? AND patient_id=? ORDER BY event_time,sequence_no,event_id",
                                          (run["run_id"], row["patient_id"])):
                    payload = json.loads(event["payload_json"])
                    for key, value in payload.items():
                        current[key] = value
                        measured_at[key] = event["event_time"]
                    timeline.append({"event_id": event["event_id"], "timestamp": event["event_time"],
                                     "type": event["event_type"], "sequence_no": event["sequence_no"], "payload": payload})
                requests = [dict(r) for r in conn.execute("SELECT * FROM er_reassessment_requests WHERE run_id=? AND patient_id=?",
                                                         (run["run_id"], row["patient_id"]))]
                for action in requests:
                    timeline.append({"event_id": action["action_id"], "timestamp": action["requested_at"],
                                     "type": "reassessment_requested", "actor": action["actor"],
                                     "reason": action["reason"], "origin": action["origin"]})
                timeline.sort(key=lambda e: (e["timestamp"], e.get("sequence_no", 10**12), e["event_id"]))
                waiting = (datetime.fromisoformat(run["replay_time"].replace("Z", "+00:00")) -
                           datetime.fromisoformat(row["arrival_time"].replace("Z", "+00:00"))).total_seconds()/60
                patients.append({"patient_id": row["patient_id"], "bay": row["bay"],
                    "arrival_time": row["arrival_time"], "initial_triage": row["initial_triage"],
                    "chief_complaint": row["chief_complaint"], "intake": intake, "current": current,
                    "measured_at": measured_at, "waiting_minutes": int(waiting),
                    "delta": {"hr": current["hr"]-intake["hr"], "spo2_pp": current["spo2"]-intake["spo2"],
                              "pain": current["pain"]-intake["pain"]},
                    "timeline": timeline, "reassessment_requested": bool(requests), "demo": True})
            return {"run_id": run["run_id"], "version": run["version"], "cursor": run["cursor"],
                    "replay_time": run["replay_time"], "active": bool(run["active"]),
                    "completed": run["cursor"] == len(BATCHES), "demo": True, "patients": patients}
