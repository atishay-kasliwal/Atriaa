"""Sentry wiring for the Atria backend. Does nothing unless SENTRY_DSN is set.

Usage in main.py, after the FastAPI app is created:

    from observability import init_observability
    init_observability(app)

Wrap meaningful work (coordinators, Gemini calls, store queries) in spans so the
Bay 4 trace shows real steps:

    from observability import span
    with span("atria.coordinator", "waiting_room_coordinator"):
        ...
"""
import os
from contextlib import contextmanager

import sentry_sdk

_enabled = False


def init_observability(app) -> bool:
    global _enabled
    dsn = os.environ.get("SENTRY_DSN")
    if dsn:
        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "local"),
            release=os.environ.get("SENTRY_RELEASE"),
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "1.0")),
            # Demo data is synthetic, but keep request bodies and user info out anyway.
            send_default_pii=False,
        )
        sentry_sdk.set_tag("service", "atria-backend")
        sentry_sdk.set_tag("demo", "synthetic")
        _enabled = True
    return _enabled


def sentry_enabled() -> bool:
    return _enabled


@contextmanager
def span(op: str, name: str, **data):
    with sentry_sdk.start_span(op=op, name=name) as s:
        for key, value in data.items():
            s.set_data(key, value)
        yield s
