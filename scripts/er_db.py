"""Local synthetic ER database CLI; never starts legacy agents or external calls.

python -m scripts.er_db init
python -m scripts.er_db status
python -m scripts.er_db next
python -m scripts.er_db reset
"""
import argparse
import json

from atria.db import DemoDatabase


def main():
    parser = argparse.ArgumentParser(description="Atria synthetic ER SQLite database")
    parser.add_argument("command", choices=("init", "status", "next", "reset"))
    parser.add_argument("--db", help="Dedicated SQLite demo path; defaults to var/atria-demo.sqlite3")
    args = parser.parse_args()
    db = DemoDatabase(args.db)
    db.initialize()
    if args.command == "reset":
        result = db.reset()
    elif args.command == "init":
        try:
            result = db.snapshot()
        except LookupError:
            result = db.reset()
    elif args.command == "next":
        state = db.snapshot()
        result = db.next_batch(run_id=state["run_id"], expected_version=state["version"])
    else:
        result = db.snapshot()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
