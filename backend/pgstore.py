"""Postgres store on Tiger Data: the system of record (tables in tiger/app_schema.sql).

Same interface as SupabaseStore, and rows come back the way PostgREST returns them
(UUIDs and timestamps as strings), so the engine and live waiting room don't change.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from store import StoreError
from tiger import _Conn

PATIENT_COLS = ("id", "bay", "arrival_time", "initial_triage", "chief_complaint")
EVENT_COLS = ("patient_id", "observed_at", "hr", "spo2", "pain", "note", "run_id", "event_key")
AUDIT_COLS = ("patient_id", "actor", "action", "reason", "run_id", "queue_version", "idempotency_key")
CHECKIN_COLS = ("id", "ticket", "display_name", "date_of_birth", "symptoms", "notes", "priority",
                "status", "reassessment_requested_at", "created_at", "bed", "suggested_priority")


def _plain(v):
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _row(r: dict) -> dict:
    return {k: _plain(v) for k, v in r.items()}


def _cols(fields: dict, allowed) -> list[str]:
    # Column names only ever come from these fixed allowlists, never from input.
    return [k for k in allowed if k in fields]


class PostgresStore:
    name = "tiger"

    def __init__(self, url: str):
        self.conn = _Conn(url)

    def _run(self, fn):
        import psycopg

        try:
            return self.conn.run(fn)
        except psycopg.errors.FeatureNotSupported:
            # A schema change (e.g. a new column) invalidates psycopg's prepared plans:
            # "cached plan must not change result type". A fresh connection fixes it.
            self.conn._conn = None
            return self.conn.run(fn)

    def _all(self, sql, params=None) -> list[dict]:
        def fn(cur):
            cur.execute(sql, params)
            return [_row(r) for r in cur.fetchall()] if cur.description else []
        return self._run(fn)

    def _one(self, sql, params=None):
        rows = self._all(sql, params)
        return rows[0] if rows else None

    # ---------- patients and events ----------

    def list_patients(self, ids):
        return self._all("SELECT * FROM patients WHERE id = ANY(%s::uuid[])", (list(ids),))

    def list_events(self, ids):
        return self._all("SELECT * FROM events WHERE patient_id = ANY(%s::uuid[]) ORDER BY observed_at", (list(ids),))

    def upsert_patients(self, rows):
        sql = (
            "INSERT INTO patients (id, bay, arrival_time, initial_triage, chief_complaint) "
            "VALUES (%(id)s, %(bay)s, %(arrival_time)s, %(initial_triage)s, %(chief_complaint)s) "
            "ON CONFLICT (id) DO UPDATE SET bay = EXCLUDED.bay, arrival_time = EXCLUDED.arrival_time, "
            "initial_triage = EXCLUDED.initial_triage, chief_complaint = EXCLUDED.chief_complaint"
        )
        self._run(lambda cur: cur.executemany(sql, [{c: r.get(c) for c in PATIENT_COLS} for r in rows]))

    def update_patient(self, patient_id, fields):
        cols = _cols(fields, PATIENT_COLS[1:])
        if cols:
            sets = ", ".join(f"{c} = %({c})s" for c in cols)
            self._all(f"UPDATE patients SET {sets} WHERE id = %(pid)s", {**fields, "pid": patient_id})

    def delete_patients(self, ids):
        # events, audit_log and checkins cascade.
        if ids:
            self._all("DELETE FROM patients WHERE id = ANY(%s::uuid[])", (list(ids),))

    def delete_events(self, ids):
        self._all("DELETE FROM events WHERE patient_id = ANY(%s::uuid[])", (list(ids),))

    def insert_events(self, rows):
        if not rows:
            return []
        sql = (
            f"INSERT INTO events ({', '.join(EVENT_COLS)}) "
            f"VALUES ({', '.join(f'%({c})s' for c in EVENT_COLS)}) "
            "ON CONFLICT (event_key) DO NOTHING RETURNING *"
        )

        def fn(cur):
            out = []
            for r in rows:
                cur.execute(sql, {c: r.get(c) for c in EVENT_COLS})
                out.extend(_row(x) for x in cur.fetchall())
            return out
        return self._run(fn)

    # ---------- audit ----------

    def list_audit(self, ids, run_id=None):
        if run_id is None:
            return self._all("SELECT * FROM audit_log WHERE patient_id = ANY(%s::uuid[]) ORDER BY created_at", (list(ids),))
        return self._all(
            "SELECT * FROM audit_log WHERE patient_id = ANY(%s::uuid[]) AND run_id = %s ORDER BY created_at",
            (list(ids), run_id),
        )

    def find_audit(self, idempotency_key):
        return self._one("SELECT * FROM audit_log WHERE idempotency_key = %s LIMIT 1", (idempotency_key,))

    def insert_audit(self, row):
        out = self._one(
            f"INSERT INTO audit_log ({', '.join(AUDIT_COLS)}) "
            f"VALUES ({', '.join(f'%({c})s' for c in AUDIT_COLS)}) RETURNING *",
            {c: row.get(c) for c in AUDIT_COLS},
        )
        if not out:
            raise StoreError("audit write was not confirmed")
        return out

    # ---------- scripted replay run ----------

    def get_run(self):
        return self._one("SELECT * FROM atria_demo_runs WHERE active LIMIT 1")

    def save_run(self, run):
        params = {"run_id": run["run_id"], "cursor": run.get("cursor", 0), "status": run.get("status", "paused"),
                  "speed": run.get("speed", 1), "active": run.get("active", True)}

        def fn(cur):
            if params["active"]:
                cur.execute("UPDATE atria_demo_runs SET active = false WHERE active AND run_id <> %(run_id)s", params)
            cur.execute(
                'INSERT INTO atria_demo_runs (run_id, "cursor", status, speed, active, updated_at) '
                "VALUES (%(run_id)s, %(cursor)s, %(status)s, %(speed)s, %(active)s, now()) "
                'ON CONFLICT (run_id) DO UPDATE SET "cursor" = EXCLUDED."cursor", status = EXCLUDED.status, '
                "speed = EXCLUDED.speed, active = EXCLUDED.active, updated_at = now() RETURNING *",
                params,
            )
            return [_row(r) for r in cur.fetchall()]
        rows = self._run(fn)
        if not rows:
            raise StoreError("run state write was not confirmed")
        return rows[0]

    # ---------- live check-ins ----------

    def insert_checkin(self, row):
        cols = _cols(row, CHECKIN_COLS)
        out = self._one(
            f"INSERT INTO checkins ({', '.join(cols)}) VALUES ({', '.join(f'%({c})s' for c in cols)}) RETURNING *",
            row,
        )
        if not out:
            raise StoreError("check-in write was not confirmed")
        return out

    def list_checkins(self):
        return self._all("SELECT * FROM checkins ORDER BY created_at")

    def get_checkin(self, checkin_id):
        return self._one("SELECT * FROM checkins WHERE id = %s", (checkin_id,))

    def update_checkin(self, checkin_id, fields):
        cols = _cols(fields, CHECKIN_COLS[1:])
        sets = ", ".join([f"{c} = %({c})s" for c in cols] + ["updated_at = now()"])
        return self._one(f"UPDATE checkins SET {sets} WHERE id = %(cid)s RETURNING *", {**fields, "cid": checkin_id})
