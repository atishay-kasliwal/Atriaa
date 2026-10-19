"""Tiger Data (TimescaleDB) mirror for the vitals time series.

Supabase stays the system of record. `TigerMirror` wraps the store and copies every
vitals event into a Tiger hypertable on a background thread, so a slow or missing
Tiger never slows down or breaks the demo. `TigerAnalytics` reads the continuous
aggregates back for the trends view. Both are off unless TIGER_DATABASE_URL is set.
"""
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

log = logging.getLogger("atria.tiger")

INSERT_SQL = """
INSERT INTO vitals (observed_at, patient_id, run_id, event_key, hr, spo2, pain)
VALUES (%(observed_at)s, %(patient_id)s, %(run_id)s, %(event_key)s, %(hr)s, %(spo2)s, %(pain)s)
ON CONFLICT (event_key, observed_at) DO NOTHING
"""


class _Conn:
    """One lazily (re)opened autocommit connection, shared under a lock."""

    def __init__(self, url: str):
        self.url = url
        self._conn = None
        self._lock = threading.Lock()

    def run(self, fn):
        import psycopg
        from psycopg.rows import dict_row

        with self._lock:
            for attempt in (1, 2):
                try:
                    if self._conn is None or self._conn.closed:
                        self._conn = psycopg.connect(self.url, autocommit=True, connect_timeout=5, row_factory=dict_row,
                                                     **password_kwargs())
                    with self._conn.cursor() as cur:
                        return fn(cur)
                except psycopg.OperationalError:
                    self._conn = None
                    if attempt == 2:
                        raise


def password_kwargs() -> dict:
    # The Tiger console's URL has no password; it may live in its own variable.
    pw = os.environ.get("TIGER_PASSWORD")
    return {"password": pw} if pw else {}


def vitals_rows(rows: list[dict]) -> list[dict]:
    return [
        {"observed_at": r["observed_at"], "patient_id": r["patient_id"], "run_id": r.get("run_id") or "unknown",
         "event_key": r.get("event_key") or f"{r['patient_id']}@{r['observed_at']}",
         "hr": r.get("hr"), "spo2": r.get("spo2"), "pain": r.get("pain")}
        for r in rows
        if any(r.get(k) is not None for k in ("hr", "spo2", "pain"))
    ]


class TigerMirror:
    """Store wrapper: every call passes through; insert_events is also copied to Tiger."""

    def __init__(self, inner, conn: _Conn):
        self._inner = inner
        self._conn = conn
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tiger")

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def insert_events(self, rows):
        out = self._inner.insert_events(rows)
        batch = vitals_rows(rows)
        if batch:
            self._pool.submit(self._write, batch)
        return out

    def _write(self, batch):
        try:
            self._conn.run(lambda cur: cur.executemany(INSERT_SQL, batch))
        except Exception:
            log.exception("tiger mirror write failed (%d rows); Supabase write already succeeded", len(batch))


class TigerAnalytics:
    def __init__(self, conn: _Conn):
        self._conn = conn

    def _timed(self, sql, params=None):
        t0 = time.perf_counter()
        rows = self._conn.run(lambda cur: cur.execute(sql, params).fetchall())
        return rows, round((time.perf_counter() - t0) * 1000, 1)

    def trends(self, run_ids: list[str], hours: int = 6) -> dict:
        """Per-patient change over the window, straight from the 5-minute aggregate."""
        rows, ms = self._timed(
            """
            SELECT run_id, patient_id,
                   sum(readings)::int                         AS readings,
                   first(hr_avg, bucket)   FILTER (WHERE hr_avg IS NOT NULL)   AS hr_first,
                   last(hr_avg, bucket)    FILTER (WHERE hr_avg IS NOT NULL)   AS hr_last,
                   first(spo2_avg, bucket) FILTER (WHERE spo2_avg IS NOT NULL) AS spo2_first,
                   min(spo2_min)                              AS spo2_min,
                   max(pain_max)                              AS pain_max,
                   min(bucket) AS first_bucket, max(bucket) AS last_bucket,
                   array_agg(hr_avg ORDER BY bucket) FILTER (WHERE hr_avg IS NOT NULL) AS hr_series
            FROM vitals_5m
            WHERE run_id = ANY(%s) AND bucket > now() - make_interval(hours => %s)
            GROUP BY run_id, patient_id
            """,
            (run_ids, hours),
        )
        return {"patients": [_jsonable(r) for r in rows], "query_ms": ms, "source": "vitals_5m"}

    def load(self, days: int = 7) -> dict:
        rows, ms = self._timed(
            """
            SELECT hour, readings::int, patient_buckets::int, hr_avg, spo2_min, low_spo2_buckets::int
            FROM vitals_hourly WHERE hour > now() - make_interval(days => %s) ORDER BY hour
            """,
            (days,),
        )
        return {"hours": [_jsonable(r) for r in rows], "query_ms": ms, "source": "vitals_hourly"}

    def stats(self) -> dict:
        def q(cur):
            out = cur.execute(
                """
                SELECT (SELECT count(*) FROM vitals)::bigint AS readings,
                       (SELECT count(DISTINCT patient_id) FROM vitals)::int AS patients,
                       (SELECT min(observed_at) FROM vitals) AS since,
                       (SELECT count(*) FROM timescaledb_information.chunks WHERE hypertable_name = 'vitals')::int AS chunks,
                       (SELECT count(*) FROM timescaledb_information.chunks
                         WHERE hypertable_name = 'vitals' AND is_compressed)::int AS compressed_chunks,
                       hypertable_size('vitals')::bigint AS total_bytes
                """
            ).fetchone()
            comp = cur.execute(
                "SELECT sum(before_compression_total_bytes)::bigint AS before, "
                "sum(after_compression_total_bytes)::bigint AS after FROM hypertable_compression_stats('vitals')"
            ).fetchone()
            return {**out, "compression_before_bytes": comp["before"], "compression_after_bytes": comp["after"]}

        t0 = time.perf_counter()
        out = self._conn.run(q)
        before, after = out["compression_before_bytes"], out["compression_after_bytes"]
        out["compression_ratio"] = round(before / after, 1) if before and after else None
        out["query_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return _jsonable(out)


def _jsonable(row: dict) -> dict:
    from decimal import Decimal

    def conv(v):
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, list):
            return [conv(x) for x in v]
        if hasattr(v, "isoformat"):
            return v.isoformat()
        if v is not None and not isinstance(v, (int, float, str, bool)):
            return str(v)
        return v

    return {k: conv(v) for k, v in row.items()}


def connect(url: Optional[str]):
    """(mirror_factory, analytics) or (None, None) when Tiger is not configured."""
    if not url:
        return None, None
    conn = _Conn(url)
    return (lambda store: TigerMirror(store, conn)), TigerAnalytics(conn)
