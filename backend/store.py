"""Storage boundary: Supabase in the real demo, in-memory for tests/offline."""
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StoreError(RuntimeError):
    pass


class MemoryStore:
    name = "memory"

    def __init__(self):
        self._lock = threading.Lock()
        self.patients: dict[str, dict] = {}
        self.events: list[dict] = []
        self.audit: list[dict] = []
        self.run: Optional[dict] = None

    def list_patients(self, ids):
        return [dict(p) for p in self.patients.values() if p["id"] in ids]

    def list_events(self, ids):
        rows = [dict(e) for e in self.events if e["patient_id"] in ids]
        return sorted(rows, key=lambda e: e["observed_at"])

    def upsert_patients(self, rows):
        with self._lock:
            for r in rows:
                self.patients[r["id"]] = dict(r)

    def delete_events(self, ids):
        with self._lock:
            self.events = [e for e in self.events if e["patient_id"] not in ids]

    def insert_events(self, rows):
        with self._lock:
            keys = {e.get("event_key") for e in self.events}
            out = []
            for r in rows:
                if r.get("event_key") in keys:
                    continue
                row = {"id": str(uuid.uuid4()), "created_at": now_iso(), **r}
                self.events.append(row)
                out.append(row)
            return out

    def list_audit(self, ids, run_id=None):
        rows = [a for a in self.audit if a["patient_id"] in ids and (run_id is None or a.get("run_id") == run_id)]
        return sorted((dict(a) for a in rows), key=lambda a: a["created_at"])

    def find_audit(self, idempotency_key):
        return next((dict(a) for a in self.audit if a.get("idempotency_key") == idempotency_key), None)

    def insert_audit(self, row):
        with self._lock:
            out = {"id": str(uuid.uuid4()), "created_at": now_iso(), **row}
            self.audit.append(out)
            return dict(out)

    def get_run(self):
        return dict(self.run) if self.run else None

    def save_run(self, run):
        with self._lock:
            self.run = {**run, "updated_at": now_iso()}
            return dict(self.run)


class SupabaseStore:
    name = "supabase"

    def __init__(self, url: str, key: str):
        from supabase import create_client

        self.client = create_client(url, key)

    def _t(self, name):
        return self.client.table(name)

    def list_patients(self, ids):
        return self._t("patients").select("*").in_("id", list(ids)).execute().data

    def list_events(self, ids):
        return self._t("events").select("*").in_("patient_id", list(ids)).order("observed_at").execute().data

    def upsert_patients(self, rows):
        self._t("patients").upsert(rows).execute()

    def delete_events(self, ids):
        self._t("events").delete().in_("patient_id", list(ids)).execute()

    def insert_events(self, rows):
        if not rows:
            return []
        res = self._t("events").upsert(rows, on_conflict="event_key", ignore_duplicates=True).execute()
        return res.data or []

    def list_audit(self, ids, run_id=None):
        q = self._t("audit_log").select("*").in_("patient_id", list(ids))
        if run_id is not None:
            q = q.eq("run_id", run_id)
        return q.order("created_at").execute().data

    def find_audit(self, idempotency_key):
        rows = self._t("audit_log").select("*").eq("idempotency_key", idempotency_key).limit(1).execute().data
        return rows[0] if rows else None

    def insert_audit(self, row):
        res = self._t("audit_log").insert(row).execute()
        if not res.data:
            raise StoreError("audit write was not confirmed")
        return res.data[0]

    def get_run(self):
        rows = self._t("atria_demo_runs").select("*").eq("active", True).limit(1).execute().data
        return rows[0] if rows else None

    def save_run(self, run):
        if run.get("active"):
            # Retire any other active run first (only one may be active).
            self._t("atria_demo_runs").update({"active": False}).eq("active", True).neq("run_id", run["run_id"]).execute()
        res = self._t("atria_demo_runs").upsert({**run, "updated_at": now_iso()}).execute()
        if not res.data:
            raise StoreError("run state write was not confirmed")
        return res.data[0]
