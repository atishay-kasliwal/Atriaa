import os
import sys
from pathlib import Path

os.environ["ATRIA_STORE"] = "memory"
os.environ["GEMINI_API_KEY"] = ""
os.environ["TIGER_DATABASE_URL"] = ""  # tests never touch Tiger
os.environ["SENTRY_DSN"] = ""  # empty, not unset: main.py would reload it from .env.local
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as c:
        c.post("/demo/reset")
        yield c


def play(c, steps=None):
    total = c.get("/demo/state").json()["total_events"]
    for _ in range(total if steps is None else steps):
        c.post("/demo/next")
    return c.get("/queue").json()


def by_bay(queue):
    return {v["bay"]: v for v in queue["queue"]}
