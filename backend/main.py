import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND = BACKEND_DIR.parent / "frontend" / "index.html"
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env.local")

import raleigh  # noqa: E402
import scenario  # noqa: E402
from assistant import Assistant  # noqa: E402
from engine import SPEEDS, DemoEngine  # noqa: E402
from store import MemoryStore, StoreError, SupabaseStore  # noqa: E402
from tracing import span  # noqa: E402

log = logging.getLogger("atria")


def make_store():
    mode = os.environ.get("ATRIA_STORE", "").lower()
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if mode == "memory" or (mode != "supabase" and not (url and key)):
        return MemoryStore()
    if not (url and key):
        raise RuntimeError("ATRIA_STORE=supabase needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    return SupabaseStore(url, key)


store = make_store()
engine = DemoEngine(store)
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


# ---------- public context ----------

@app.get("/raleigh/overview")
def raleigh_overview(live: bool = False):
    return raleigh.overview(live=live)


@app.get("/health")
def health():
    return {"status": "ok", "service": "atria-backend", "store": store.name, "speeds": list(SPEEDS)}


@app.get("/")
def root():
    if FRONTEND.exists():
        return FileResponse(FRONTEND)
    return health()
