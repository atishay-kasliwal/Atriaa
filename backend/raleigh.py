"""Real public healthcare-resource context for Raleigh / Wake County.

Source: Wake County GIS, "Hospitals, Wake County and Surrounding" (ArcGIS
Feature Service). This is REAL PUBLIC DATA and is kept separate from the
SYNTHETIC patient data. It contains no capacity or wait information.
"""
import json
import threading
import time
from collections import Counter
from pathlib import Path

import httpx

SERVICE_URL = "https://services1.arcgis.com/a7CWfuGP5ZnLYE7I/arcgis/rest/services/Hospitals/FeatureServer/0"
ITEM_URL = "https://data-wake.opendata.arcgis.com/datasets/673dadf4790546729cf84adb5e0e43e9"
SNAPSHOT = Path(__file__).resolve().parent / "data" / "wake_hospitals.geojson"
SNAPSHOT_RETRIEVED = "2026-10-19"
SOURCE_LAST_EDITED = "2025-08-18"
LIVE_TTL_SECONDS = 3600

_lock = threading.Lock()
_live: dict = {"at": 0.0, "data": None}


def _facilities(geojson: dict) -> list[dict]:
    out = []
    for f in geojson.get("features", []):
        p = f.get("properties", {})
        lon, lat = f["geometry"]["coordinates"][:2]
        out.append({
            "name": p.get("NAME"),
            "facility_type": p.get("FACILITY"),
            "services": p.get("SERVICES"),
            "address": p.get("ADDRESS"),
            "city": p.get("CITY"),
            "county": p.get("COUNTY"),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
        })
    return sorted(out, key=lambda x: (x["county"] != "Wake", x["county"] or "", x["name"] or ""))


def _fetch_live() -> dict:
    res = httpx.get(
        f"{SERVICE_URL}/query",
        params={"where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson"},
        timeout=10,
    )
    res.raise_for_status()
    data = res.json()
    if not data.get("features"):
        raise ValueError("live query returned no features")
    return data


def overview(live: bool = False) -> dict:
    data, mode, error = None, "snapshot", None
    if live:
        with _lock:
            fresh = _live["data"] is not None and time.time() - _live["at"] < LIVE_TTL_SECONDS
            if not fresh:
                try:
                    _live.update(at=time.time(), data=_fetch_live())
                except Exception as exc:
                    error = f"{type(exc).__name__}: {str(exc)[:120]}"
            if _live["data"] is not None:
                data, mode = _live["data"], "live"
    if data is None:
        data = json.loads(SNAPSHOT.read_text())

    facilities = _facilities(data)
    by_county = Counter(f["county"] for f in facilities)
    return {
        "label": "REAL PUBLIC DATA",
        "source": {
            "publisher": "Wake County GIS",
            "dataset": "Hospitals, Wake County and Surrounding",
            "service_url": SERVICE_URL,
            "item_url": ITEM_URL,
            "mode": mode,
            "snapshot_retrieved": SNAPSHOT_RETRIEVED,
            "source_last_edited": SOURCE_LAST_EDITED,
            "live_error": error,
        },
        "summary": {
            "total": len(facilities),
            "wake_county": by_county.get("Wake", 0),
            "by_county": dict(sorted(by_county.items(), key=lambda kv: -kv[1])),
            "trauma_listed": sum(1 for f in facilities if "trauma" in (f["services"] or "").lower()),
            "freestanding_or_other": sum(1 for f in facilities if f["facility_type"] == "Other"),
        },
        "facilities": facilities,
        "limitations": [
            "Facility locations and listed services only; no realtime capacity, wait times or diversion status.",
            "Names and fields are shown as published by the source and may be out of date.",
            "The Atria waiting room is a fictional synthetic ED, not any facility listed here.",
        ],
    }
