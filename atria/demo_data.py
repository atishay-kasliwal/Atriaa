"""Fixed synthetic fixture. Intake labels are not clinically validated assignments."""

SCENARIO = "er-reassessment-v1"
BASE_TIME = "2026-10-19T10:02:00Z"
COMMON = {"bp_sys": 120, "bp_dia": 78, "temp_c": 36.8, "rr": 18}
PATIENTS = (
    {"patient_id": "bay7", "bay": "Bay 7", "arrival_time": "2026-10-19T09:41:00Z",
     "initial_triage": 2, "hr": 104, "spo2": 95, "pain": 5, "initial_review": True},
    {"patient_id": "bay4", "bay": "Bay 4", "arrival_time": BASE_TIME,
     "initial_triage": 3, "hr": 92, "spo2": 98, "pain": 4},
    {"patient_id": "bay9", "bay": "Bay 9", "arrival_time": "2026-10-19T08:10:00Z",
     "initial_triage": 4, "hr": 78, "spo2": 98, "pain": 2},
    {"patient_id": "bay2", "bay": "Bay 2", "arrival_time": "2026-10-19T09:26:00Z",
     "initial_triage": 3, "hr": 84, "spo2": 98, "pain": 3},
)
# Every batch includes explicit new observations for all four patients.
BATCHES = (
    ("2026-10-19T10:18:00Z", {"bay4": {"hr": 101, "spo2": 96, "pain": 5},
                               "bay2": {"hr": 106, "spo2": 94, "pain": 3}}),
    ("2026-10-19T10:25:00Z", {"bay4": {"hr": 110, "spo2": 94, "pain": 6}}),
    ("2026-10-19T10:36:00Z", {"bay4": {"hr": 121, "spo2": 91, "pain": 7,
                                             "symptom": "Synthetic report: symptoms feel worse than intake."}}),
)
