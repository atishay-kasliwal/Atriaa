from datetime import datetime, timezone

import core


def ev(t, hr=None, spo2=None, pain=None, note=None):
    return {"observed_at": f"2026-10-19T10:{t:02d}:00Z", "hr": hr, "spo2": spo2, "pain": pain, "note": note}


AS_OF = datetime(2026, 10, 19, 10, 40, tzinfo=timezone.utc)
PATIENT = {"id": "p", "bay": "Bay X", "initial_triage": 3, "arrival_time": "2026-10-19T10:00:00Z"}


def test_persistent_needs_two_signals_every_step():
    t = core.trend_agent([ev(0, 92, 98, 4), ev(10, 101, 96, 5), ev(20, 110, 94, 6)])
    assert t["trajectory"] == "persistent_change"
    assert t["deltas"] == {"hr": 18, "spo2": -4, "pain": 2}


def test_single_spike_that_resolves_is_not_persistent():
    t = core.trend_agent([ev(0, 82, 98, 3), ev(10, 115, 93, 6), ev(20, 85, 98, 3)])
    assert t["trajectory"] == "stable"
    assert t["resolved_deviations"][0]["value"] == 115


def test_noise_step_does_not_make_a_trend():
    t = core.trend_agent([ev(0, 82, 98, 3), ev(5, 83, 98, 3), ev(10, 115, 93, 6)])
    assert t["trajectory"] == "transient_change"


def test_one_signal_is_mixed_not_persistent():
    t = core.trend_agent([ev(0, 80, 98, 3), ev(10, 81, 98, 4), ev(20, 80, 98, 5)])
    assert t["trajectory"] == "mixed_change"


def test_note_only_event_keeps_latest_measurement_as_current():
    v = core.patient_coordinator(PATIENT, [ev(0, 92, 98, 4), ev(10, 101, 96, 5), ev(20, note="Reports worsening")], AS_OF)
    assert v["current"]["hr"] == 101
    assert v["agents"]["context"]["reported_worsening"] is True


def test_insufficient_data_with_intake_only():
    v = core.patient_coordinator(PATIENT, [ev(0, 92, 98, 4)], AS_OF)
    assert v["trajectory"] == "insufficient_data"
    assert v["reassessment_signal"] is False


def test_waiting_uses_as_of_not_wall_clock():
    v = core.patient_coordinator(PATIENT, [ev(0, 92, 98, 4)], AS_OF)
    assert v["waiting_minutes"] == 40


def test_open_model_is_unavailable_not_a_vote():
    v = core.patient_coordinator(PATIENT, [ev(0, 92, 98, 4), ev(10, 92, 98, 4)], AS_OF)
    assert v["agents"]["open_model"]["status"] == "unavailable"
