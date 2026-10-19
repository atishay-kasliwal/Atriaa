"""Seed Tiger with 30 days of synthetic ER waiting-room vitals, then compress old chunks.

    .venv/bin/python scripts/seed_tiger.py            # ~30 days, ~7,000 visits
    .venv/bin/python scripts/seed_tiger.py --days 7

All data is synthetic (run_id = 'history'). Re-running replaces the history rows.
"""
import argparse
import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")
load_dotenv(ROOT / ".env.local")


from tiger import password_kwargs  # noqa: E402


def visits(days: int, rng: random.Random):
    """One synthetic patient per visit (~250/day, a busy urban ER): re-checks every 5-15 min."""
    end = datetime.now(timezone.utc) - timedelta(minutes=30)
    t = end - timedelta(days=days)
    while t < end:
        # Busier afternoons/evenings.
        busy = 1.0 if 12 <= t.hour <= 23 else 2.5
        t += timedelta(minutes=rng.uniform(2, 6) * busy)
        pid = uuid.uuid4()
        worsening = rng.random() < 0.12
        hr, spo2, pain = rng.randint(70, 105), rng.randint(95, 100), rng.randint(1, 7)
        at = t
        for i in range(rng.randint(6, 30)):
            # Never past `end`: a future bucket would push the aggregate watermark ahead of the live demo.
            if at >= end:
                break
            yield (at, pid, "history", f"history:{pid}:{i}", hr, spo2, pain)
            at += timedelta(minutes=rng.uniform(5, 15))
            if worsening:
                hr, spo2, pain = hr + rng.randint(2, 7), max(84, spo2 - rng.randint(0, 2)), min(10, pain + rng.randint(0, 1))
            else:
                hr, spo2, pain = hr + rng.randint(-4, 4), min(100, max(93, spo2 + rng.randint(-1, 1))), max(0, pain + rng.randint(-1, 1))


def refresh(cur, view, end_offset):
    # Stop short of now, like the policy does: buckets past the watermark are computed live,
    # so a reading entered a second ago shows up. The background policy may hold a lock; retry.
    for attempt in range(10):
        try:
            cur.execute(f"CALL refresh_continuous_aggregate('{view}', NULL, now() - INTERVAL '{end_offset}')")
            return
        except psycopg.errors.LockNotAvailable:
            time.sleep(3)
    raise SystemExit(f"could not refresh {view}: a background refresh kept it locked")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    url = os.environ.get("TIGER_DATABASE_URL")
    if not url:
        raise SystemExit("TIGER_DATABASE_URL is not set (add it to .env.local)")

    rows = list(visits(args.days, random.Random(args.seed)))
    with psycopg.connect(url, autocommit=True, **password_kwargs()) as conn, conn.cursor() as cur:
        # Re-runs: decompress first so settings can change and the new history is compressed as a whole.
        if cur.execute("SELECT to_regclass('vitals')").fetchone()[0]:
            cur.execute("SELECT count(decompress_chunk(c, if_compressed => true)) FROM show_chunks('vitals') c")
        # Rebuild the aggregates each run so their watermark matches the new history.
        cur.execute("DROP MATERIALIZED VIEW IF EXISTS vitals_hourly")
        cur.execute("DROP MATERIALIZED VIEW IF EXISTS vitals_5m")
        cur.execute((ROOT / "tiger" / "schema.sql").read_text())
        cur.execute("DELETE FROM vitals WHERE run_id = 'history'")
        with cur.copy("COPY vitals (observed_at, patient_id, run_id, event_key, hr, spo2, pain) FROM STDIN") as copy:
            for r in rows:
                copy.write_row(r)
        print(f"inserted {len(rows):,} readings over {args.days} days")

        refresh(cur, "vitals_5m", "5 minutes")
        refresh(cur, "vitals_hourly", "1 hour")
        cur.execute(
            "SELECT count(compress_chunk(c, if_not_compressed => true)) "
            "FROM show_chunks('vitals', older_than => INTERVAL '2 days') c"
        )
        print(f"compressed {cur.fetchone()[0]} chunks")
        cur.execute(
            "SELECT sum(before_compression_total_bytes), sum(after_compression_total_bytes) "
            "FROM hypertable_compression_stats('vitals')"
        )
        before, after = cur.fetchone()
        if before and after:
            print(f"compression: {before / 1024:,.0f} KiB -> {after / 1024:,.0f} KiB ({before / after:.1f}x)")


if __name__ == "__main__":
    main()
