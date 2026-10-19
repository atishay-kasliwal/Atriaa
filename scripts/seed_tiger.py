"""Seed Tiger with 30 days of synthetic ER waiting-room vitals, then compress old chunks.

    .venv/bin/python scripts/seed_tiger.py            # ~30 days, ~1,500 patients
    .venv/bin/python scripts/seed_tiger.py --days 7

All data is synthetic (run_id = 'history'). Re-running replaces the history rows.
"""
import argparse
import os
import random
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
    """One synthetic patient per visit: a few hours of re-checks every 10-20 min."""
    start = datetime.now(timezone.utc) - timedelta(days=days)
    t = start
    while t < datetime.now(timezone.utc) - timedelta(hours=1):
        # Busier afternoons/evenings: arrivals every 8-40 minutes depending on the hour.
        busy = 1.0 if 12 <= t.hour <= 23 else 2.5
        t += timedelta(minutes=rng.uniform(8, 25) * busy)
        pid = uuid.uuid4()
        worsening = rng.random() < 0.12
        hr, spo2, pain = rng.randint(70, 105), rng.randint(95, 100), rng.randint(1, 7)
        at = t
        for i in range(rng.randint(3, 14)):
            yield (at, pid, "history", f"history:{pid}:{i}", hr, spo2, pain)
            at += timedelta(minutes=rng.uniform(10, 20))
            if worsening:
                hr, spo2, pain = hr + rng.randint(2, 7), max(84, spo2 - rng.randint(0, 2)), min(10, pain + rng.randint(0, 1))
            else:
                hr, spo2, pain = hr + rng.randint(-4, 4), min(100, max(93, spo2 + rng.randint(-1, 1))), max(0, pain + rng.randint(-1, 1))


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
        cur.execute((ROOT / "tiger" / "schema.sql").read_text())
        cur.execute("DELETE FROM vitals WHERE run_id = 'history'")
        with cur.copy("COPY vitals (observed_at, patient_id, run_id, event_key, hr, spo2, pain) FROM STDIN") as copy:
            for r in rows:
                copy.write_row(r)
        print(f"inserted {len(rows):,} readings over {args.days} days")

        cur.execute("CALL refresh_continuous_aggregate('vitals_5m', NULL, NULL)")
        cur.execute("CALL refresh_continuous_aggregate('vitals_hourly', NULL, NULL)")
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
