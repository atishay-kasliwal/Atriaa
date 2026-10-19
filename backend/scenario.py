"""Fixed synthetic 8-patient waiting-room scenario. All data is fictional."""

DAY = "2026-10-19"


def pid(n: int) -> str:
    return f"00000000-0000-0000-0000-{n:012d}"


def t(hhmm: str) -> str:
    return f"{DAY}T{hhmm}:00Z"


# bay, id, arrival, intake ESI (illustrative), complaint, readings
# A reading is (time, hr, spo2, pain, note); the first one is the intake baseline.
PATIENTS = [
    ("Bay 7", pid(7), "10:02", 2, "Chest discomfort (synthetic demo)", [
        ("10:02", 88, 97, 5, None),
        ("10:10", 88, 97, 5, None),
        ("10:18", 89, 97, 5, None),
        ("10:25", 87, 98, 4, None),
        ("10:36", 88, 97, 5, None),
    ]),
    ("Bay 4", pid(4), "10:02", 3, "Mild shortness of breath (synthetic demo)", [
        ("10:02", 92, 98, 4, None),
        ("10:10", 96, 97, None, None),
        ("10:18", 101, 96, 5, None),
        ("10:25", 110, 94, 6, None),
        ("10:31", None, None, None, "Reports worsening breathlessness"),
        ("10:36", 121, 91, 7, None),
    ]),
    ("Bay 2", pid(5), "09:40", 3, "Ankle pain (synthetic demo)", [
        ("09:40", 78, 99, 3, None),
        ("10:12", 79, 99, 3, None),
        ("10:25", 77, 99, 2, None),
        ("10:40", 78, 99, 3, None),
    ]),
    ("Bay 9", pid(6), "10:04", 3, "Headache (synthetic demo)", [
        ("10:04", 82, 98, 3, None),
        ("10:12", 83, 98, 3, None),
        ("10:20", 115, 93, 6, "Reports sudden palpitations"),
        ("10:28", 85, 98, 3, None),
        ("10:38", 83, 98, 2, None),
    ]),
    ("Bay 1", pid(1), "09:52", 4, "Minor hand laceration (synthetic demo)", [
        ("09:52", 76, 99, 2, None),
        ("10:15", 75, 99, 2, None),
        ("10:35", 76, 99, 2, None),
    ]),
    ("Bay 3", pid(3), "09:58", 3, "Abdominal pain (synthetic demo)", [
        ("09:58", 84, 98, 5, None),
        ("10:14", 85, 98, 5, None),
        ("10:30", 84, 98, 5, None),
    ]),
    ("Bay 5", pid(2), "10:04", 2, "Dizziness (synthetic demo)", [
        ("10:04", 90, 97, 3, None),
        ("10:22", 89, 97, 3, None),
        ("10:34", 90, 98, 3, None),
    ]),
    ("Bay 6", pid(8), "10:03", 4, "Lower back pain (synthetic demo)", [
        ("10:03", 80, 98, 3, None),
        ("10:16", 81, 98, 4, None),
        ("10:27", 80, 98, 5, "Reports pain worse when sitting"),
        ("10:39", 81, 98, 6, None),
    ]),
]

PATIENT_IDS = [p[1] for p in PATIENTS]


def patient_rows() -> list[dict]:
    return [
        {"id": i, "bay": bay, "arrival_time": t(arr), "initial_triage": esi, "chief_complaint": cc}
        for bay, i, arr, esi, cc, _ in PATIENTS
    ]


def _event(patient_id: str, reading) -> dict:
    when, hr, spo2, pain, note = reading
    return {"patient_id": patient_id, "observed_at": t(when), "hr": hr, "spo2": spo2, "pain": pain, "note": note}


def intake_events() -> list[dict]:
    return [_event(i, readings[0]) for _, i, _, _, _, readings in PATIENTS]


def schedule() -> list[dict]:
    """Every post-intake event in replay order (time, then bay)."""
    bay_of = {i: bay for bay, i, *_ in PATIENTS}
    events = [_event(i, r) for _, i, _, _, _, readings in PATIENTS for r in readings[1:]]
    return sorted(events, key=lambda e: (e["observed_at"], bay_of[e["patient_id"]]))


def start_time() -> str:
    return max(t(p[2]) for p in PATIENTS)


def event_key(event: dict) -> str:
    return f"{event['patient_id']}@{event['observed_at']}"
