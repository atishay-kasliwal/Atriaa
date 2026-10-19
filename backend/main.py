import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import date
from typing import Literal, Optional
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env.local")

import raleigh  # noqa: E402
import scenario  # noqa: E402
import tiger  # noqa: E402
from assistant import Assistant  # noqa: E402
from engine import SPEEDS, DemoEngine  # noqa: E402
from live import LiveWaitingRoom  # noqa: E402
from store import MemoryStore, StoreError, SupabaseStore  # noqa: E402
from tracing import span  # noqa: E402

log = logging.getLogger("atria")


def make_store():
    """Tiger Data is the system of record. ATRIA_STORE=memory|supabase|tiger overrides."""
    mode = os.environ.get("ATRIA_STORE", "").lower()
    tiger_url = os.environ.get("TIGER_DATABASE_URL")
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if mode == "memory":
        return MemoryStore()
    if mode == "tiger" or (mode == "" and tiger_url):
        if not tiger_url:
            raise RuntimeError("ATRIA_STORE=tiger needs TIGER_DATABASE_URL")
        from pgstore import PostgresStore

        return PostgresStore(tiger_url)
    if mode == "supabase" or (url and key):
        if not (url and key):
            raise RuntimeError("ATRIA_STORE=supabase needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        return SupabaseStore(url, key)
    return MemoryStore()


tiger_mirror, tiger_analytics = tiger.connect(os.environ.get("TIGER_DATABASE_URL"))
store = make_store()
if tiger_mirror:
    # Vitals events are also copied to the Tiger vitals hypertable for the trends view.
    store = tiger_mirror(store)
engine = DemoEngine(store)
live = LiveWaitingRoom(store)
assistant = Assistant(os.environ.get("GEMINI_API_KEY"))
_ticker: Optional[asyncio.Task] = None


async def tick(run_id: str):
    """Advance the replay on the backend clock; stops on pause, reset or completion."""
    while True:
        run = await asyncio.to_thread(engine.run)
        if not run or run["run_id"] != run_id or run["status"] != "running":
            return
        await asyncio.sleep(engine.interval(run))
        run = await asyncio.to_thread(engine.run)
        if not run or run["run_id"] != run_id or run["status"] != "running":
            return
        try:
            await asyncio.to_thread(engine.step, run_id)
        except Exception:
            log.exception("replay step failed; pausing")
            await asyncio.to_thread(engine.set_status, "paused")
            return


def ensure_ticker():
    global _ticker
    run = engine.run()
    if run and run["status"] == "running" and (_ticker is None or _ticker.done()):
        _ticker = asyncio.get_running_loop().create_task(tick(run["run_id"]))


@asynccontextmanager
async def lifespan(_app):
    run = await asyncio.to_thread(engine.run)
    if run is None and store.name == "memory":
        await asyncio.to_thread(engine.reset)
    elif run and run["status"] == "running":
        # A restarted process never resumes silently; the presenter presses Start.
        await asyncio.to_thread(engine.set_status, "paused")
    yield
    if _ticker:
        _ticker.cancel()


app = FastAPI(title="Atria - ER reassessment demo", lifespan=lifespan)

try:
    from observability import init_observability
except ImportError:
    init_observability = None
if init_observability:
    init_observability(app)

@app.exception_handler(Exception)
async def missing_table(request, exc):
    # Supabase without the check-ins migration: say what to run instead of a bare 500.
    if "PGRST205" in str(exc) and "checkins" in str(exc):
        return JSONResponse(status_code=503, content={
            "detail": "Database not set up for check-ins: run supabase/migrations/202610190005_checkins.sql"})
    if type(exc).__name__ == "UndefinedTable":
        return JSONResponse(status_code=503, content={
            "detail": "Tiger database not set up: run tiger/app_schema.sql"})
    log.exception("unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": f"server error: {type(exc).__name__}"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def demo_patient(patient_id: str):
    if patient_id not in scenario.PATIENT_IDS:
        raise HTTPException(404, "patient not found")


def require_run():
    run = engine.run()
    if not run:
        raise HTTPException(409, "no active demo run; POST /demo/reset first")
    return run


# ---------- queue and evidence ----------

@app.get("/queue")
def get_queue():
    return engine.queue()


@app.get("/patient/{patient_id}/evidence")
def get_evidence(patient_id: str):
    demo_patient(patient_id)
    view = engine.evidence(patient_id)
    if view is None:
        raise HTTPException(404, "patient not in current run")
    return view


class ActionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=80)
    action: Literal["acknowledge", "request_reassessment", "resolve"]
    reason: Optional[str] = Field(default=None, max_length=500)
    idempotency_key: Optional[str] = Field(default=None, max_length=80)
    queue_version: Optional[str] = None


@app.post("/patient/{patient_id}/action")
def post_action(patient_id: str, body: ActionRequest):
    demo_patient(patient_id)
    run = engine.run()
    key = body.idempotency_key or str(uuid.uuid4())
    existing = store.find_audit(key)
    if existing:
        return {"confirmed": True, "duplicate": True, "audit_entry": existing}
    row = {
        "patient_id": patient_id,
        "actor": body.actor,
        "action": body.action,
        "reason": body.reason,
        "run_id": run["run_id"] if run else None,
        "queue_version": body.queue_version,
        "idempotency_key": key,
    }
    try:
        with span("atria.audit", "insert_audit", action=body.action, patient_id=patient_id):
            entry = store.insert_audit(row)
    except StoreError as exc:
        raise HTTPException(502, f"audit write not confirmed: {exc}")
    except Exception as exc:
        existing = store.find_audit(key)
        if existing:
            return {"confirmed": True, "duplicate": True, "audit_entry": existing}
        raise HTTPException(502, f"audit write failed: {type(exc).__name__}")
    return {
        "confirmed": True,
        "duplicate": False,
        "audit_entry": entry,
        "note": "Audit only. Official triage, treatment and bed assignment are unchanged.",
    }


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    patient_id: Optional[str] = None


@app.post("/ask")
def post_ask(body: AskRequest):
    queue = engine.queue()
    detail = engine.evidence(body.patient_id) if body.patient_id in scenario.PATIENT_IDS else None
    return assistant.ask(body.question, queue, detail)


# ---------- demo replay (backend-owned) ----------

@app.get("/demo/state")
def demo_state():
    return engine.queue()["run"]


@app.post("/demo/reset")
async def demo_reset():
    global _ticker
    if _ticker:
        _ticker.cancel()
        _ticker = None
    await asyncio.to_thread(engine.reset)
    return await asyncio.to_thread(demo_state)


@app.post("/demo/start")
async def demo_start():
    await asyncio.to_thread(require_run)
    await asyncio.to_thread(engine.set_status, "running")
    ensure_ticker()
    return await asyncio.to_thread(demo_state)


@app.post("/demo/pause")
async def demo_pause():
    await asyncio.to_thread(require_run)
    await asyncio.to_thread(engine.set_status, "paused")
    return await asyncio.to_thread(demo_state)


@app.post("/demo/next")
async def demo_next():
    run = await asyncio.to_thread(require_run)
    await asyncio.to_thread(engine.step, run["run_id"])
    return await asyncio.to_thread(demo_state)


class SpeedRequest(BaseModel):
    speed: Literal[1, 2, 5]


@app.post("/demo/speed")
async def demo_speed(body: SpeedRequest):
    run = await asyncio.to_thread(require_run)
    await asyncio.to_thread(engine.set_status, run["status"], body.speed)
    return await asyncio.to_thread(demo_state)


# ---------- live waiting room (ER Priority intake + dashboard) ----------

class CheckInRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    date_of_birth: Optional[date] = None
    symptoms: list[str] = Field(min_length=1, max_length=12)
    notes: Optional[str] = Field(default=None, max_length=1000)
    pain: Optional[int] = Field(default=None, ge=0, le=10)


class ReportRequest(BaseModel):
    pain: Optional[int] = Field(default=None, ge=0, le=10)
    feeling: Optional[Literal["worse", "same", "better"]] = None


class PriorityRequest(BaseModel):
    priority: Optional[Literal[1, 2, 3]] = None


class VitalsRequest(BaseModel):
    hr: Optional[int] = Field(default=None, ge=20, le=250)
    spo2: Optional[int] = Field(default=None, ge=50, le=100)
    pain: Optional[int] = Field(default=None, ge=0, le=10)


class StaffActionRequest(BaseModel):
    actor: str = Field(default="Charge nurse", min_length=1, max_length=80)
    reason: Optional[str] = Field(default=None, max_length=500)


class LiveAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    checkin_id: Optional[UUID] = None


def live_checkin(checkin_id: UUID) -> dict:
    c = live.get(str(checkin_id))
    if not c:
        raise HTTPException(404, "check-in not found")
    return c


def live_waiting(checkin_id: UUID) -> dict:
    c = live_checkin(checkin_id)
    if c["status"] != "waiting":
        raise HTTPException(409, "patient has already been called in")
    return c


@app.post("/checkin")
def post_checkin(body: CheckInRequest):
    symptoms = [s.strip() for s in body.symptoms if s.strip()]
    if not symptoms:
        raise HTTPException(422, "at least one symptom is required")
    c = live.check_in(body.name.strip(), body.date_of_birth.isoformat() if body.date_of_birth else None,
                      symptoms, (body.notes or "").strip(), body.pain)
    return {"id": c["id"], "ticket": c["ticket"]}


@app.get("/checkin/{checkin_id}")
def get_checkin_status(checkin_id: UUID):
    status = live.status(str(checkin_id))
    if status is None:
        raise HTTPException(404, "check-in not found")
    return status


@app.post("/checkin/{checkin_id}/report")
def post_checkin_report(checkin_id: UUID, body: ReportRequest):
    live_waiting(checkin_id)
    if body.pain is None and body.feeling is None:
        raise HTTPException(422, "send a pain score or how you feel")
    live.report(str(checkin_id), body.pain, body.feeling)
    return live.status(str(checkin_id))


@app.get("/live/queue")
def get_live_queue():
    return live.queue()


@app.post("/live/{checkin_id}/priority")
def post_live_priority(checkin_id: UUID, body: PriorityRequest):
    live_waiting(checkin_id)
    return live.set_priority(str(checkin_id), body.priority)


@app.post("/live/{checkin_id}/vitals")
def post_live_vitals(checkin_id: UUID, body: VitalsRequest):
    live_waiting(checkin_id)
    if body.hr is None and body.spo2 is None and body.pain is None:
        raise HTTPException(422, "record at least one reading")
    return live.record_vitals(str(checkin_id), body.hr, body.spo2, body.pain)


@app.post("/live/{checkin_id}/reassess")
def post_live_reassess(checkin_id: UUID, body: StaffActionRequest):
    live_waiting(checkin_id)
    entry = live.request_reassessment(str(checkin_id), body.actor, body.reason)
    return {"confirmed": True, "audit_entry": entry,
            "note": "Audit only. Human priority and treatment are unchanged."}


class AcknowledgeRequest(BaseModel):
    actor: str = Field(default="Charge nurse", min_length=1, max_length=80)
    priority: Optional[Literal[1, 2, 3]] = None


@app.post("/live/{checkin_id}/acknowledge")
def post_live_acknowledge(checkin_id: UUID, body: AcknowledgeRequest):
    live_waiting(checkin_id)
    entry = live.acknowledge(str(checkin_id), body.actor, body.priority)
    return {"confirmed": True, "audit_entry": entry}


@app.post("/live/{checkin_id}/call")
def post_live_call(checkin_id: UUID, body: StaffActionRequest):
    live_waiting(checkin_id)
    return live.call_in(str(checkin_id), body.actor)


@app.post("/live/ask")
def post_live_ask(body: LiveAskRequest):
    queue = live.queue(include_agents=True)
    detail = None
    if body.checkin_id:
        detail = next((v for v in queue["queue"] if v["id"] == str(body.checkin_id)), None)
    return assistant.ask(body.question, queue, detail)


@app.get("/live/sample")
def get_live_sample():
    return live.sample_state()


@app.post("/live/sample/load")
def post_live_sample_load():
    return live.load_sample()


@app.post("/live/sample/next")
def post_live_sample_next():
    try:
        return live.sample_next()
    except LookupError as exc:
        raise HTTPException(409, str(exc))


@app.post("/live/reset")
def post_live_reset():
    return {"removed": live.reset()}


# ---------- public context ----------

@app.get("/raleigh/overview")
def raleigh_overview(live: bool = False):
    return raleigh.overview(live=live)


# ---------- Tiger Data time series ----------

def require_tiger():
    if not tiger_analytics:
        raise HTTPException(503, "Tiger Data is not configured (set TIGER_DATABASE_URL)")
    return tiger_analytics


def tiger_call(fn, *args):
    try:
        return fn(*args)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("tiger query failed")
        raise HTTPException(502, f"Tiger Data query failed: {type(exc).__name__}")


@app.get("/tiger/trends")
def tiger_trends(hours: int = 24):
    """Per-patient vitals change for the live waiting room and the current replay run."""
    t = require_tiger()
    run = engine.run()
    out = tiger_call(t.trends, ["live"] + ([run["run_id"]] if run else []), max(1, min(hours, 24 * 30)))
    labels = {p_id: bay for bay, p_id, *_ in scenario.PATIENTS}
    labels.update({c["id"]: f"{c['ticket']} {c.get('display_name') or ''}".strip() for c in store.list_checkins()})
    # Tiger keeps history; show only patients still on the board (cleared check-ins drop off).
    out["patients"] = [p for p in out["patients"] if p["patient_id"] in labels]
    for p in out["patients"]:
        p["label"] = labels[p["patient_id"]]
        p["source"] = "live" if p["run_id"] == "live" else "replay"
    out["patients"].sort(key=lambda p: -((p["hr_last"] or 0) - (p["hr_first"] or 0)))
    return out


@app.get("/tiger/load")
def tiger_load(days: int = 7):
    return tiger_call(require_tiger().load, max(1, min(days, 30)))


@app.get("/tiger/stats")
def tiger_stats():
    return tiger_call(require_tiger().stats)


@app.get("/health")
def health():
    return {"status": "ok", "service": "atria-backend", "store": store.name, "speeds": list(SPEEDS),
            "tiger": bool(tiger_analytics)}


@app.get("/")
def root():
    # API only. The product UI is the Next.js app in er-priority/frontend.
    return {**health(), "ui": os.environ.get("ATRIA_UI_URL", "http://localhost:3000")}
