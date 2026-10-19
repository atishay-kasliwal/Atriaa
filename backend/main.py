import os
from datetime import datetime, timezone
from typing import Literal, Optional

from dateutil import parser as dateparser
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

import google.generativeai as genai

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.0-flash")

app = FastAPI(title="Atria - ER reassessment demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- helpers ----------

def parse_dt(value: str) -> datetime:
    dt = dateparser.isoparse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def classify_trajectory(events: list[dict]) -> dict:
    """Pure, deterministic trend classification. No model involved.

    persistent_change requires at least 2 of 3 signals (HR up, SpO2 down,
    pain up) to move in the worsening direction on every consecutive step.
    A single spike that reverses does NOT count as persistent.
    """
    if len(events) < 2:
        return {
            "trajectory": "insufficient_data",
            "reassessment_signal": False,
            "deltas": {},
        }

    events = sorted(events, key=lambda e: parse_dt(e["observed_at"]))
    first, last = events[0], events[-1]

    def series(key):
        return [e[key] for e in events if e.get(key) is not None]

    def monotonic_worsening(vals, increasing: bool) -> bool:
        if len(vals) < 3:
            return False
        diffs = [b - a for a, b in zip(vals, vals[1:])]
        return all(d > 0 for d in diffs) if increasing else all(d < 0 for d in diffs)

    hr_vals, spo2_vals, pain_vals = series("hr"), series("spo2"), series("pain")

    hr_worsening = monotonic_worsening(hr_vals, increasing=True)
    spo2_worsening = monotonic_worsening(spo2_vals, increasing=False)
    pain_worsening = monotonic_worsening(pain_vals, increasing=True)
    worsening_count = sum([hr_worsening, spo2_worsening, pain_worsening])

    deltas = {
        "hr": (last.get("hr") - first.get("hr")) if first.get("hr") is not None and last.get("hr") is not None else None,
        "spo2": (last.get("spo2") - first.get("spo2")) if first.get("spo2") is not None and last.get("spo2") is not None else None,
        "pain": (last.get("pain") - first.get("pain")) if first.get("pain") is not None and last.get("pain") is not None else None,
    }

    if worsening_count >= 2:
        trajectory = "persistent_change"
    elif worsening_count == 1:
        trajectory = "transient_or_mixed"
    else:
        trajectory = "stable"

    return {
        "trajectory": trajectory,
        "reassessment_signal": worsening_count >= 2,
        "deltas": deltas,
        "signals_worsening": {"hr": hr_worsening, "spo2": spo2_worsening, "pain": pain_worsening},
        "intake": {"hr": first.get("hr"), "spo2": first.get("spo2"), "pain": first.get("pain"), "observed_at": first["observed_at"]},
        "current": {"hr": last.get("hr"), "spo2": last.get("spo2"), "pain": last.get("pain"), "observed_at": last["observed_at"]},
    }


def build_patient_view(patient: dict, events: list[dict]) -> dict:
    classification = classify_trajectory(events)
    arrival = parse_dt(patient["arrival_time"])
    waiting_minutes = int((datetime.now(timezone.utc) - arrival).total_seconds() // 60)
    return {
        "id": patient["id"],
        "bay": patient["bay"],
        "initial_triage": patient["initial_triage"],
        "chief_complaint": patient["chief_complaint"],
        "arrival_time": patient["arrival_time"],
        "waiting_minutes": waiting_minutes,
        "last_change": events[-1]["observed_at"] if events else None,
        **classification,
    }


def rank_queue(views: list[dict]) -> list[dict]:
    def sort_key(v):
        worsening_total = sum(1 for ok in v.get("signals_worsening", {}).values() if ok)
        return (
            0 if v["trajectory"] == "persistent_change" else (1 if v["trajectory"] == "transient_or_mixed" else 2),
            -worsening_total,
            -(v.get("deltas", {}).get("hr") or 0),
        )

    ordered = sorted(views, key=sort_key)
    for i, v in enumerate(ordered):
        v["attention_position"] = i + 1
    return ordered


# ---------- routes ----------

@app.get("/queue")
def get_queue():
    patients = supabase.table("patients").select("*").execute().data
    views = []
    for p in patients:
        events = supabase.table("events").select("*").eq("patient_id", p["id"]).order("observed_at").execute().data
        views.append(build_patient_view(p, events))
    return {"queue": rank_queue(views)}


@app.get("/patient/{patient_id}/evidence")
def get_evidence(patient_id: str):
    patient_res = supabase.table("patients").select("*").eq("id", patient_id).execute().data
    if not patient_res:
        raise HTTPException(404, "patient not found")
    patient = patient_res[0]
    events = supabase.table("events").select("*").eq("patient_id", patient_id).order("observed_at").execute().data
    audit = supabase.table("audit_log").select("*").eq("patient_id", patient_id).order("created_at").execute().data
    view = build_patient_view(patient, events)
    view["timeline"] = events
    view["audit_log"] = audit
    return view


class ActionRequest(BaseModel):
    actor: str
    action: Literal["acknowledge", "request_reassessment", "resolve"]
    reason: Optional[str] = None


@app.post("/patient/{patient_id}/action")
def post_action(patient_id: str, body: ActionRequest):
    patient_res = supabase.table("patients").select("id").eq("id", patient_id).execute().data
    if not patient_res:
        raise HTTPException(404, "patient not found")
    row = {
        "patient_id": patient_id,
        "actor": body.actor,
        "action": body.action,
        "reason": body.reason,
    }
    result = supabase.table("audit_log").insert(row).execute()
    return {"confirmed": True, "audit_entry": result.data[0] if result.data else row}


class AskRequest(BaseModel):
    question: str
    patient_id: Optional[str] = None


@app.post("/ask")
def post_ask(body: AskRequest):
    patients = supabase.table("patients").select("*").execute().data
    queue_summary = []
    for p in patients:
        events = supabase.table("events").select("*").eq("patient_id", p["id"]).order("observed_at").execute().data
        view = build_patient_view(p, events)
        queue_summary.append({
            "bay": view["bay"],
            "initial_triage": view["initial_triage"],
            "trajectory": view["trajectory"],
            "reassessment_signal": view["reassessment_signal"],
            "waiting_minutes": view["waiting_minutes"],
            "deltas": view.get("deltas"),
            "attention_position": None,
        })
    queue_summary = rank_queue_summary_positions(queue_summary)

    detail_text = ""
    if body.patient_id:
        detail = get_evidence(body.patient_id)
        detail_text = (
            f"\nFull timeline for {detail['bay']}: "
            + "; ".join(
                f"{e['observed_at']} HR={e.get('hr')} SpO2={e.get('spo2')} pain={e.get('pain')} note={e.get('note')}"
                for e in detail["timeline"]
            )
        )

    prompt = f"""You are Atria's explanation assistant for a synthetic ER reassessment demo.
Rules you must follow strictly:
- Only use the evidence provided below. Never invent patient facts, numbers, or timestamps.
- Never diagnose, prescribe treatment, or recommend a specific clinical action.
- Clearly distinguish a patient's initial intake severity from their current trajectory; do not imply one overrides the other.
- If the evidence is mixed or insufficient, say "evidence is mixed or limited; human review recommended" instead of guessing.
- Cite specific bay names, values, and timestamps from the evidence when relevant.

Current Attention Queue evidence (ranked by trajectory, not intake severity):
{queue_summary}
{detail_text}

Question: {body.question}

Answer concisely, grounded only in the evidence above.
"""

    response = gemini_model.generate_content(prompt)
    return {"answer": response.text}


def rank_queue_summary_positions(summary: list[dict]) -> list[dict]:
    def sort_key(v):
        order = {"persistent_change": 0, "transient_or_mixed": 1, "stable": 2, "insufficient_data": 3}
        return order.get(v["trajectory"], 3)

    ordered = sorted(summary, key=sort_key)
    for i, v in enumerate(ordered):
        v["attention_position"] = i + 1
    return ordered


@app.get("/")
def root():
    return {"status": "ok", "service": "atria-backend"}
