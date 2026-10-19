"""Ask Atria: grounded Gemini explanations with a labeled deterministic fallback."""
import os
import re
from typing import Optional

import core
from tracing import span

DEFAULT_MODELS = ("gemini-3.5-flash", "gemini-flash-latest")

RULES = """You are Atria's explanation assistant for a SYNTHETIC ER waiting-room reassessment demo.
Rules you must follow strictly:
- Use only the evidence below. Never invent patient facts, numbers or timestamps.
- Never diagnose, prescribe treatment or recommend a specific clinical action. A nurse decides.
- Keep initial intake severity (ESI or Priority, set by humans, never changed by Atria) distinct from current trajectory.
- The Attention Queue is separate from the official triage queue.
- If evidence is mixed or insufficient, say "evidence is mixed or limited; human review recommended".
- Cite bay names, values with units and HH:MM UTC times from the evidence, and mention the queue version once.
- Answer in at most 5 short sentences or bullets."""


class Assistant:
    def __init__(self, api_key: Optional[str], models: Optional[list[str]] = None):
        self.api_key = api_key
        self.models = models or [m for m in (os.environ.get("GEMINI_MODEL"), *DEFAULT_MODELS) if m]
        self.models = list(dict.fromkeys(self.models))
        self._client = None
        self._config = None

    def client(self):
        # Keep one client alive; inline clients get closed before use.
        if self._client is None and self.api_key:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self.api_key,
                # Fail fast (no SDK retries) so the labeled fallback appears within the demo.
                http_options=types.HttpOptions(
                    timeout=int(os.environ.get("GEMINI_TIMEOUT_MS", "12000")),
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            # MINIMAL keeps Ask Atria answers to a few seconds; LOW measured up to ~9 s.
            level = os.environ.get("GEMINI_THINKING_LEVEL", "MINIMAL").upper()
            self._config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level=getattr(types.ThinkingLevel, level)),
            )
        return self._client

    def generate(self, prompt: str) -> tuple[Optional[str], Optional[str], list[str]]:
        errors = []
        client = self.client()
        if client is None:
            return None, None, ["GEMINI_API_KEY not configured"]
        for model in self.models:
            try:
                with span("ai.gemini", "generate_content", model=model):
                    try:
                        res = client.models.generate_content(model=model, contents=prompt, config=self._config)
                    except Exception as exc:
                        # Some models reject thinking_level; retry once without config.
                        if "thinking" not in str(exc).lower():
                            raise
                        res = client.models.generate_content(model=model, contents=prompt)
                if res.text:
                    return res.text.strip(), model, errors
                errors.append(f"{model}: empty response")
            except Exception as exc:  # provider errors are reported, never hidden
                errors.append(f"{model}: {type(exc).__name__}: {str(exc)[:160]}")
        return None, None, errors

    def ask(self, question: str, queue: dict, detail: Optional[dict] = None) -> dict:
        evidence = evidence_text(queue, detail)
        answer, model, errors = self.generate(f"{RULES}\n\nEVIDENCE\n{evidence}\n\nQUESTION: {question}\n")
        unmatched = ungrounded_numbers(answer, evidence) if answer else []
        base = {
            "queue_version": queue["queue_version"],
            "as_of": queue["as_of"],
            "evidence_ids": [v["bay"] for v in queue["queue"]],
        }
        if answer and not unmatched:
            return {**base, "answer": answer, "provider": "gemini", "model": model, "grounding": {"checked": True, "unmatched_numbers": []}}
        reason = (
            f"Gemini answer cited numbers not in evidence ({', '.join(unmatched[:5])}); replaced with sourced fallback."
            if answer else "Gemini unavailable; showing deterministic sourced fallback."
        )
        return {
            **base,
            "answer": fallback_answer(question, queue),
            "provider": "fallback",
            "model": None,
            "notice": reason,
            "provider_errors": errors,
            "grounding": {"checked": bool(answer), "unmatched_numbers": unmatched},
        }


# ---------- evidence ----------

def _vals(point: dict) -> str:
    parts = []
    if point.get("hr") is not None:
        parts.append(f"HR {point['hr']} bpm")
    if point.get("spo2") is not None:
        parts.append(f"SpO2 {point['spo2']}%")
    if point.get("pain") is not None:
        parts.append(f"pain {point['pain']}/10")
    return ", ".join(parts) or "no measurements"


def severity(v: dict) -> str:
    """Human intake label: ESI in the replay, Priority 1-3 for live check-ins."""
    if v.get("initial_triage") is None:
        return "priority not yet assigned"
    return f"{v.get('severity_label', 'ESI')} {v['initial_triage']}"


def patient_line(v: dict, full: bool = True) -> str:
    d = v["deltas"]
    lines = [
        f"[{v['bay']}] attention position {v['attention_position']}"
        + (f" (previous {v['previous_position']})" if v.get("previous_position") else "")
        + f"; intake {severity(v)} (unchanged); complaint: {v.get('chief_complaint')}",
        f"  trajectory {v['trajectory']}; consensus {v['consensus']}; reassessment signal {v['reassessment_signal']}; waiting {v['waiting_minutes']} min",
        f"  intake at {core.hhmm(v['intake']['observed_at'])}: {_vals(v['intake'])}" if v["intake"].get("observed_at") else "  no intake reading",
        f"  current (latest {core.hhmm(v['current']['observed_at'])}): {_vals(v['current'])}" if v["current"].get("observed_at") else "",
        f"  change since intake: HR {core.fmt_delta(d.get('hr'))} bpm, SpO2 {core.fmt_delta(d.get('spo2'))} points, pain {core.fmt_delta(d.get('pain'))}",
        f"  ordering reason: {v.get('ordering_reason')}",
    ]
    if full:
        for m in core.METRICS:
            pts = v["series"][m]
            if pts:
                lines.append(f"  {core.LABELS[m]} readings: " + ", ".join(f"{p['value']} at {core.hhmm(p['observed_at'])}" for p in pts))
        for r in v["agents"]["context"]["reports"]:
            lines.append(f"  note at {core.hhmm(r['observed_at'])}: \"{r['note']}\"")
        for f in v["agents"]["trend"]["findings"]:
            lines.append(f"  trend finding: {f}")
    return "\n".join(x for x in lines if x)


def evidence_text(queue: dict, detail: Optional[dict] = None) -> str:
    head = (
        f"queue_version {queue['queue_version']}; as_of {core.hhmm(queue['as_of'])} UTC; "
        f"policy {queue['policy_version']}; {queue.get('data_note', 'all data synthetic')}; open model unavailable"
    )
    body = "\n".join(patient_line(v) for v in queue["queue"])
    extra = ""
    if detail:
        acts = detail.get("audit_log") or []
        if acts:
            extra = "\nHuman actions for " + detail["bay"] + ": " + "; ".join(f"{a['action']} by {a['actor']}" for a in acts)
    return f"{head}\n{body}{extra}"


NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


def ungrounded_numbers(answer: str, evidence: str) -> list[str]:
    allowed = set(NUM.findall(evidence)) | {"1", "2", "3"}
    seen = []
    for n in NUM.findall(answer):
        if n not in allowed and n not in seen:
            seen.append(n)
    return seen


# ---------- deterministic fallback ----------

def _bays_in(question: str, queue: dict) -> list[dict]:
    found = []
    for m in re.finditer(r"bay\s*(\d+)", question, re.I):
        v = next((x for x in queue["queue"] if x["bay"].lower() == f"bay {m.group(1)}"), None)
        if v and v not in found:
            found.append(v)
    return found


def _change(v: dict) -> str:
    if not v["current"].get("observed_at"):
        return f"{v['bay']} has no readings yet."
    return (
        f"{v['bay']} (intake {severity(v)}, unchanged): intake {_vals(v['intake'])} at "
        f"{core.hhmm(v['intake']['observed_at'])}; latest {_vals(v['current'])} at {core.hhmm(v['current']['observed_at'])}; "
        f"trajectory {v['trajectory'].replace('_', ' ')}."
    )


def fallback_answer(question: str, queue: dict) -> str:
    q = queue["queue"]
    tail = f"(Queue {queue['queue_version']}, as of {core.hhmm(queue['as_of'])} UTC. A nurse decides; no diagnosis or treatment advice.)"
    bays = _bays_in(question, queue)
    if len(bays) >= 2:
        a, b = sorted(bays[:2], key=lambda v: v["attention_position"])
        return (
            f"{a['bay']} is at attention position {a['attention_position']} and {b['bay']} at {b['attention_position']}. "
            f"{a['bay']}: {a['reasons'][0]}. {b['bay']}: {b['reasons'][0]}. "
            f"Intake labels are unchanged: {a['bay']} {severity(a)}, {b['bay']} {severity(b)}.\n"
            f"{_change(a)}\n{_change(b)}\n{tail}"
        )
    if len(bays) == 1:
        v = bays[0]
        findings = v["agents"]["trend"]["findings"] + [f"note {f}" for f in v["agents"]["context"]["findings"]]
        return f"{_change(v)}\n" + "\n".join(f"- {f}" for f in findings[:4]) + f"\n{tail}"
    signalled = [v for v in q if v["reassessment_signal"]]
    if "lower" in question.lower() and "sever" in question.lower():
        changing = [v for v in q if v["trajectory"] != "stable" and v["trajectory"] != "insufficient_data" and (v["initial_triage"] or 0) >= 3]
        if not changing:
            return f"No lower-initial-severity patient shows change yet. {tail}"
        return "\n".join(_change(v) for v in changing) + f"\n{tail}"
    if "most" in question.lower():
        top = max(q, key=core.magnitude)
        return f"Largest change since intake: {_change(top)}\n{tail}"
    if signalled:
        return (
            "Reassessment signal: " + "; ".join(f"{v['bay']} (position {v['attention_position']})" for v in signalled) + ".\n"
            + "\n".join(_change(v) for v in signalled) + f"\n{tail}"
        )
    top = q[0] if q else None
    if not top:
        return f"No patients in the current run. {tail}"
    return f"No patient currently has a persistent-change signal. Top of attention queue: {_change(top)}\n{tail}"
