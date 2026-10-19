"""Synthetic persistence tests; no provider, clinical or legacy-service claims."""
import copy
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from atria.db import DemoDatabase, StaleStateError
from atria.demo_data import BATCHES


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "demo.sqlite3"
        self.db = DemoDatabase(self.path)
        self.db.initialize()
        self.state = self.db.reset()

    def patient(self, state, patient_id="bay4"):
        return next(p for p in state["patients"] if p["patient_id"] == patient_id)

    def advance(self):
        s = self.db.snapshot()
        return self.db.next_batch(run_id=s["run_id"], expected_version=s["version"])

    def event(self, **changes):
        event = dict(run_id=self.state["run_id"], patient_id="bay4", event_id="manual-event-1",
                     sequence_no=99, event_time="2026-10-19T10:04:00Z", event_type="pain_report",
                     payload={"pain": 5}, expected_version=0)
        return {**event, **changes}

    def test_init_is_idempotent_and_data_survives_reopen(self):
        self.db.initialize()
        self.assertEqual(DemoDatabase(self.path).snapshot(), self.state)
        self.assertEqual(len(self.state["patients"]), 4)
        self.assertTrue(self.patient(self.state, "bay7")["reassessment_requested"])
        self.assertEqual(self.patient(self.state, "bay9")["waiting_minutes"], 112)

    def test_unrelated_database_is_never_modified(self):
        other = Path(self.tmp.name) / "legacy.sqlite3"
        with sqlite3.connect(other) as conn:
            conn.execute("CREATE TABLE legacy_data (value TEXT)")
            conn.execute("INSERT INTO legacy_data VALUES ('preserve me')")
        with self.assertRaises(ValueError):
            DemoDatabase(other).initialize()
        with sqlite3.connect(other) as conn:
            self.assertEqual(conn.execute("SELECT value FROM legacy_data").fetchone()[0], "preserve me")
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 0)

    def test_three_batches_exact_final_values_and_completed_noop(self):
        first = self.advance()
        self.assertEqual(self.patient(first, "bay2")["current"]["hr"], 106)
        second = self.advance()
        self.assertEqual(self.patient(second, "bay2")["current"]["hr"], 84)
        final = self.advance()
        self.assertEqual(self.patient(final)["delta"], {"hr": 29, "spo2_pp": -7, "pain": 3})
        self.assertEqual(self.patient(final)["initial_triage"], 3)
        self.assertTrue(final["completed"])
        self.assertEqual(self.advance(), final)

    def test_sparse_update_preserves_other_values_and_measurement_age(self):
        self.assertTrue(self.db.append_event(**self.event()))
        patient = self.patient(self.db.snapshot())
        self.assertEqual(patient["current"]["hr"], 92)
        self.assertEqual(patient["current"]["pain"], 5)
        self.assertNotEqual(patient["measured_at"]["hr"], patient["measured_at"]["pain"])
        self.assertEqual(patient["delta"]["pain"], 1)

    def test_event_retry_idempotency_and_payload_conflict(self):
        self.assertTrue(self.db.append_event(**self.event()))
        self.assertFalse(self.db.append_event(**self.event()))
        before = self.db.snapshot()
        with self.assertRaises(ValueError):
            self.db.append_event(**self.event(payload={"pain": 6}))
        self.assertEqual(self.db.snapshot(), before)

    def test_validation_prevents_invalid_or_prearrival_event(self):
        for changes in ({"payload": {"pain": 11}}, {"payload": {"pain": float("nan")}},
                        {"payload": {"pain": True}}, {"payload": {"unknown": 4}},
                        {"event_time": "2026-10-19T10:04:00"},
                        {"event_time": "2026-10-19T10:01:00Z"},
                        {"patient_id": "unknown"}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, LookupError)):
                self.db.append_event(**self.event(**changes))
        self.assertEqual(self.db.snapshot(), self.state)

    def test_request_is_recorded_and_duplicate_safe_without_changing_intake(self):
        args = dict(run_id=self.state["run_id"], patient_id="bay4", expected_version=0,
                    actor="Demo Nurse", reason="Review changes since intake")
        result = self.db.request_reassessment(**args)
        self.assertTrue(result["created"])
        repeated = self.db.request_reassessment(**args)
        self.assertFalse(repeated["created"])
        self.assertEqual(result["action"], repeated["action"])
        reopened = DemoDatabase(self.path).snapshot()
        p = self.patient(reopened)
        self.assertTrue(p["reassessment_requested"])
        self.assertEqual(p["intake"], self.patient(self.state)["intake"])
        self.assertEqual(p["initial_triage"], 3)
        self.assertEqual(sum(e["type"] == "reassessment_requested" for e in p["timeline"]), 1)

    def test_reset_archives_history_and_rejects_old_writes(self):
        old = self.advance()
        fresh = self.db.reset()
        self.assertNotEqual(old["run_id"], fresh["run_id"])
        self.assertEqual(fresh["cursor"], 0)
        self.assertFalse(self.db.snapshot(old["run_id"])["active"])
        self.assertEqual(self.db.snapshot(old["run_id"])["cursor"], 1)
        with self.assertRaises(StaleStateError):
            self.db.next_batch(run_id=old["run_id"], expected_version=old["version"])
        with self.assertRaises(StaleStateError):
            self.db.append_event(**self.event())
        self.assertEqual(self.db.snapshot(), fresh)

    def test_intake_cannot_be_overwritten_directly(self):
        with sqlite3.connect(self.path) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE er_encounters SET initial_triage=1 WHERE patient_id='bay4'")
        self.assertEqual(self.patient(self.db.snapshot())["initial_triage"], 3)

    def test_failed_batch_rolls_back_earlier_events_and_cursor(self):
        broken = copy.deepcopy(BATCHES)
        broken[0][1]["bay4"]["spo2"] = 101
        with patch("atria.db.BATCHES", broken), self.assertRaises(ValueError):
            self.advance()
        self.assertEqual(self.db.snapshot(), self.state)

    def test_two_writers_with_same_version_advance_only_once(self):
        def attempt(_):
            try:
                self.db.next_batch(run_id=self.state["run_id"], expected_version=0)
                return "ok"
            except StaleStateError:
                return "stale"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertCountEqual(results, ["ok", "stale"])
        self.assertEqual(self.db.snapshot()["cursor"], 1)


if __name__ == "__main__":
    unittest.main()
