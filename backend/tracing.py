"""Optional Sentry spans; no-ops when observability is unavailable."""
from contextlib import contextmanager

try:
    from observability import span
except ImportError:  # sentry-sdk not installed
    @contextmanager
    def span(op, name, **data):
        yield None
