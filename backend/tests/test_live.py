"""Live waiting room: check-in -> patient status -> staff priority/re-checks -> Atria flag."""
import uuid

import pytest


@pytest.fixture
def live(client):
    client.post("/live/reset")
    yield client
    client.post("/live/reset")


def check_in(c, name, symptoms, pain=None):
    r = c.post("/checkin", json={"name": name, "date_of_birth": "1990-01-02", "symptoms": symptoms, "pain": pain})
    assert r.status_code == 200, r.text
    return r.json()


def by_ticket(q):
    return {v["ticket"]: v for v in q["queue"]}


def test_checkin_shows_patient_their_place(live):
    a = check_in(live, "Ana Demo", ["Shortness of breath"], pain=4)
    b = check_in(live, "Ben Demo", ["Chest pain"], pain=5)
    assert (a["ticket"], b["ticket"]) == ("W-01", "W-02")

    s = live.get(f"/checkin/{a['id']}").json()
    assert s["stage"] == "awaiting_triage" and s["line_position"] is None
    assert s["awaiting_triage_count"] == 2

    live.post(f"/live/{b['id']}/priority", json={"priority": 2})
    live.post(f"/live/{a['id']}/priority", json={"priority": 3})
    s = live.get(f"/checkin/{a['id']}").json()
    assert s["stage"] == "waiting" and s["line_position"] == 2 and s["ahead"] == 1
    # The patient sees tickets only, never other patients' names or details.
    assert s["line"] == [{"ticket": "W-02", "you": False}, {"ticket": "W-01", "you": True}]
    assert "Ben" not in str(s)


def test_rechecks_flag_change_without_touching_priority(live):
    a = check_in(live, "Ana Demo", ["Shortness of breath"], pain=4)
    b = check_in(live, "Ben Demo", ["Chest pain"], pain=5)
    live.post(f"/live/{a['id']}/priority", json={"priority": 3})
    live.post(f"/live/{b['id']}/priority", json={"priority": 2})
    for hr, spo2, pain in [(92, 98, 4), (101, 96, 5), (110, 94, 6)]:
        assert live.post(f"/live/{a['id']}/vitals", json={"hr": hr, "spo2": spo2, "pain": pain}).status_code == 200

    q = live.get("/live/queue").json()
    t = by_ticket(q)
    assert q["queue"][0]["ticket"] == "W-01"
    assert t["W-01"]["reassessment_signal"] and t["W-01"]["trajectory"] == "persistent_change"
    # Human priority and the official line are unchanged.
    assert t["W-01"]["priority"] == 3 and t["W-01"]["line_position"] == 2
    assert t["W-02"]["line_position"] == 1
    assert q["flagged"] == 1 and q["awaiting_triage"] == 0


def test_reassessment_reaches_patient_and_recheck_clears_it(live):
    a = check_in(live, "Ana Demo", ["Dizziness"], pain=3)
    r = live.post(f"/live/{a['id']}/reassess", json={"actor": "Charge nurse"})
    assert r.json()["confirmed"]
    assert live.get(f"/checkin/{a['id']}").json()["stage"] == "recheck_requested"
    live.post(f"/live/{a['id']}/vitals", json={"hr": 88})
    assert live.get(f"/checkin/{a['id']}").json()["stage"] == "awaiting_triage"


def test_patient_report_feeds_atria(live):
    a = check_in(live, "Ana Demo", ["Headache"], pain=3)
    s = live.post(f"/checkin/{a['id']}/report", json={"pain": 6, "feeling": "worse"}).json()
    assert s["last_update"]
    v = by_ticket(live.get("/live/queue").json())["W-01"]
    assert v["deltas"]["pain"] == 3
    assert "Patient-reported worsening in notes" in v["reasons"]
    assert live.post(f"/checkin/{a['id']}/report", json={}).status_code == 422


def test_call_in_leaves_queue(live):
    a = check_in(live, "Ana Demo", ["Fever"])
    live.post(f"/live/{a['id']}/call", json={"actor": "Charge nurse"})
    assert live.get("/live/queue").json()["waiting"] == 0
    assert live.get(f"/checkin/{a['id']}").json()["stage"] == "called"
    assert live.post(f"/live/{a['id']}/vitals", json={"hr": 90}).status_code == 409


def test_live_ask_uses_priority_labels(live):
    a = check_in(live, "Ana Demo", ["Shortness of breath"], pain=4)
    for hr, spo2 in [(92, 98), (101, 96), (110, 94)]:
        live.post(f"/live/{a['id']}/vitals", json={"hr": hr, "spo2": spo2})
    out = live.post("/live/ask", json={"question": "Who should be reassessed next?", "checkin_id": a["id"]}).json()
    assert out["provider"] == "fallback"  # no Gemini key in tests
    assert "W-01" in out["answer"] and out["queue_version"].startswith("live@")


def test_validation(live):
    assert live.post("/checkin", json={"name": "X", "symptoms": []}).status_code == 422
    assert live.post("/checkin", json={"name": "X", "symptoms": ["Cough"], "pain": 11}).status_code == 422
    assert live.get(f"/checkin/{uuid.uuid4()}").status_code == 404
    assert live.get("/checkin/not-a-uuid").status_code == 422
    a = check_in(live, "Ana Demo", ["Cough"])
    assert live.post(f"/live/{a['id']}/vitals", json={"spo2": 120}).status_code == 422
    assert live.post(f"/live/{a['id']}/priority", json={"priority": 5}).status_code == 422


def test_acknowledge_and_raise_priority_moves_patient_up(live):
    a = check_in(live, "Ana Demo", ["Shortness of breath"], pain=4)
    b = check_in(live, "Ben Demo", ["Chest pain"], pain=5)
    live.post(f"/live/{a['id']}/priority", json={"priority": 3})
    live.post(f"/live/{b['id']}/priority", json={"priority": 2})
    for hr, spo2 in [(92, 98), (101, 96), (110, 94)]:
        live.post(f"/live/{a['id']}/vitals", json={"hr": hr, "spo2": spo2})
    q = live.get("/live/queue").json()
    assert by_ticket(q)["W-01"]["alert_active"] and q["alerts"] == 1

    r = live.post(f"/live/{a['id']}/acknowledge", json={"actor": "Charge nurse", "priority": 1})
    assert r.json()["audit_entry"]["reason"] == "Acknowledged Atria flag; priority 3 -> 1"
    t = by_ticket(live.get("/live/queue").json())
    assert t["W-01"]["priority"] == 1 and t["W-01"]["line_position"] == 1
    assert t["W-02"]["line_position"] == 2
    assert not t["W-01"]["alert_active"] and t["W-01"]["acknowledged_by"] == "Charge nurse"
    assert live.get(f"/checkin/{a['id']}").json()["line_position"] == 1

    # A newer worsening reading re-opens the alert.
    live.post(f"/live/{a['id']}/vitals", json={"hr": 121, "spo2": 91})
    assert by_ticket(live.get("/live/queue").json())["W-01"]["alert_active"]


def test_sample_waiting_room_tells_the_bay_4_story(live):
    state = live.post("/live/sample/load").json()
    assert state["loaded"] and state["cursor"] == 0
    q = live.get("/live/queue").json()
    assert q["waiting"] == 8 and q["awaiting_triage"] == 0
    names = {v["name"]: v for v in q["queue"]}
    assert names["Maya Patel"]["priority"] == 3 and names["Daniel Reyes"]["priority"] == 2
    assert names["Grace Kim"]["waiting_minutes"] >= 29  # backdated arrival

    while not live.post("/live/sample/next").json()["done"]:
        pass
    q = live.get("/live/queue").json()
    top = q["queue"][0]
    assert top["name"] == "Maya Patel" and top["alert_active"]
    assert top["priority"] == 3  # Atria never changes priority
    assert live.post("/live/reset").json()["removed"] == 8
    assert live.post("/live/sample/next").status_code == 409


def test_rush_beds_full_then_discharge_and_assign_next_in_line(client):
    beds = client.post("/live/rush/load").json()
    assert (beds["occupied"], beds["free"]) == (6, 0)
    q = client.get("/live/queue").json()
    assert q["waiting"] == 10 and q["awaiting_triage"] == 10
    assert all(p["suggested_priority"] for p in q["queue"])
    assert q["beds"]["next_up"] is None  # nobody approved yet

    by_name = {p["name"]: p for p in q["queue"]}
    for p in q["queue"]:  # nurse approves every suggestion
        client.post(f"/live/{p['id']}/priority", json={"priority": p["suggested_priority"]})
    james = by_name["James Miller"]
    assert client.get("/live/beds").json()["next_up"]["id"] == james["id"]  # Priority 1 first

    assert client.post(f"/live/{james['id']}/bed", json={}).status_code == 409  # no free bed
    freed = client.post("/live/beds/Bed 2/discharge", json={}).json()
    assert freed["free"] == 1
    roomed = client.post(f"/live/{james['id']}/bed", json={}).json()
    assert roomed["bed"] == "Bed 2" and roomed["status"] == "called"

    status = client.get(f"/checkin/{james['id']}").json()
    assert (status["stage"], status["bed"]) == ("called", "Bed 2")
    after = client.get("/live/queue").json()
    assert after["waiting"] == 9 and after["beds"]["free"] == 0
    assert client.post(f"/live/{james['id']}/bed", json={}).status_code == 409  # already roomed
