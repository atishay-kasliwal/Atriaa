import assistant
import scenario
from conftest import by_bay, play

BAY4 = scenario.pid(4)


def test_reset_shows_all_eight_with_intake_only(client):
    q = client.get("/queue").json()
    assert len(q["queue"]) == 8
    assert all(v["trajectory"] == "insufficient_data" for v in q["queue"])
    assert q["queue_version"].endswith(".v0")
    assert q["official_triage_unchanged"] is True


def test_bay4_rises_above_bay7_and_intake_unchanged(client):
    start = by_bay(client.get("/queue").json())
    assert start["Bay 7"]["attention_position"] < start["Bay 4"]["attention_position"]
    end = by_bay(play(client))
    assert end["Bay 4"]["attention_position"] == 1
    assert end["Bay 4"]["trajectory"] == "persistent_change"
    assert end["Bay 4"]["initial_triage"] == 3 and end["Bay 7"]["initial_triage"] == 2
    assert end["Bay 7"]["trajectory"] == "stable"
    assert end["Bay 4"]["current"] == end["Bay 4"]["current"] | {"hr": 121, "spo2": 91, "pain": 7}


def test_long_wait_and_resolved_spike_do_not_dominate(client):
    end = by_bay(play(client))
    assert end["Bay 2"]["trajectory"] == "stable" and end["Bay 2"]["attention_position"] > 2
    assert end["Bay 9"]["trajectory"] == "stable"
    assert end["Bay 9"]["agents"]["trend"]["resolved_deviations"]


def test_bay9_spike_is_transient_while_it_lasts(client):
    sched = scenario.schedule()
    spike = next(i for i, e in enumerate(sched) if e["patient_id"] == scenario.pid(6) and e["hr"] == 115)
    q = by_bay(play(client, spike + 1))
    assert q["Bay 9"]["trajectory"] == "transient_change"


def test_replay_is_deterministic_across_resets(client):
    first = [(v["bay"], v["trajectory"]) for v in play(client)["queue"]]
    client.post("/demo/reset")
    second = [(v["bay"], v["trajectory"]) for v in play(client)["queue"]]
    assert first == second


def test_reset_drops_previous_run_events(client):
    play(client, 10)
    client.post("/demo/reset")
    q = client.get("/queue").json()
    assert all(len(v["series"]["hr"]) == 1 for v in q["queue"])


def test_next_after_complete_is_noop(client):
    play(client)
    state = client.post("/demo/next").json()
    assert state["status"] == "complete" and state["cursor"] == state["total_events"]


def test_previous_position_tracks_movement(client):
    play(client)
    v = by_bay(client.get("/queue").json())["Bay 4"]
    assert v["previous_position"] is not None


def test_action_is_audited_idempotent_and_run_scoped(client):
    body = {"actor": "Nurse (demo)", "action": "request_reassessment", "reason": "test", "idempotency_key": "k1"}
    r1 = client.post(f"/patient/{BAY4}/action", json=body).json()
    r2 = client.post(f"/patient/{BAY4}/action", json=body).json()
    assert r1["confirmed"] and not r1["duplicate"] and r2["duplicate"]
    ev = client.get(f"/patient/{BAY4}/evidence").json()
    assert [a["action"] for a in ev["audit_log"]] == ["request_reassessment"]
    assert any(t["type"] == "human_action" for t in ev["timeline"])
    client.post("/demo/reset")
    assert client.get(f"/patient/{BAY4}/evidence").json()["audit_log"] == []


def test_action_rejects_unknown_patient_and_action(client):
    assert client.post("/patient/nope/action", json={"actor": "a", "action": "acknowledge"}).status_code == 404
    assert client.post(f"/patient/{BAY4}/action", json={"actor": "a", "action": "discharge"}).status_code == 422


def test_ask_without_gemini_returns_labeled_sourced_fallback(client):
    play(client)
    r = client.post("/ask", json={"question": "Why did Bay 4 move above Bay 7?"}).json()
    assert r["provider"] == "fallback" and r["notice"]
    for fact in ("121", "91", "10:36", "ESI 3", "ESI 2", r["queue_version"]):
        assert fact in r["answer"]


def test_grounding_check_rejects_invented_numbers(client, monkeypatch):
    play(client)
    monkeypatch.setattr(
        assistant.Assistant, "generate",
        lambda self, prompt: ("Bay 4 HR is 140 bpm and SpO2 85%.", "fake-model", []),
    )
    r = client.post("/ask", json={"question": "What changed with Bay 4?"}).json()
    assert r["provider"] == "fallback"
    assert "140" in r["grounding"]["unmatched_numbers"]


def test_grounded_model_answer_passes(client, monkeypatch):
    play(client)
    monkeypatch.setattr(
        assistant.Assistant, "generate",
        lambda self, prompt: ("Bay 4 HR rose from 92 to 121 bpm by 10:36.", "fake-model", []),
    )
    r = client.post("/ask", json={"question": "What changed with Bay 4?"}).json()
    assert r["provider"] == "gemini" and r["model"] == "fake-model"


def test_raleigh_overview_snapshot_is_real_public_data(client):
    r = client.get("/raleigh/overview").json()
    assert r["label"] == "REAL PUBLIC DATA"
    assert r["summary"]["total"] == 22 and r["summary"]["wake_county"] == 10
    assert r["source"]["publisher"] == "Wake County GIS"
