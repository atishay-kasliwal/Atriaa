import tiger
from store import MemoryStore


class FakeConn:
    def __init__(self, fail=False):
        self.batches, self.fail = [], fail

    def run(self, fn):
        if self.fail:
            raise RuntimeError("tiger down")

        class Cur:
            def executemany(_, sql, rows):
                self.batches.append(rows)

        return fn(Cur())


def test_mirror_copies_vitals_and_skips_notes():
    conn = FakeConn()
    store = tiger.TigerMirror(MemoryStore(), conn)
    store.insert_events([
        {"patient_id": "p1", "observed_at": "2026-10-19T10:00:00+00:00", "run_id": "live", "event_key": "k1", "hr": 90},
        {"patient_id": "p1", "observed_at": "2026-10-19T10:05:00+00:00", "run_id": "live", "event_key": "k2", "note": "x"},
    ])
    store._pool.shutdown(wait=True)
    assert [r["event_key"] for r in conn.batches[0]] == ["k1"]
    assert len(store.list_events({"p1"})) == 2  # primary store got both
    assert store.name == "memory"


def test_mirror_failure_never_breaks_primary_write():
    store = tiger.TigerMirror(MemoryStore(), FakeConn(fail=True))
    out = store.insert_events([{"patient_id": "p1", "observed_at": "2026-10-19T10:00:00+00:00", "event_key": "k", "hr": 1}])
    store._pool.shutdown(wait=True)
    assert len(out) == 1


def test_tiger_endpoints_report_not_configured(client):
    assert client.get("/tiger/stats").status_code == 503
    assert client.get("/health").json()["tiger"] is False
