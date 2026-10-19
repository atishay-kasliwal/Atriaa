import { api } from "./api";
import type { AskAnswer } from "../types";

// Answers to the suggested questions are fetched once, in the background, when the
// nurse station opens, so clicking one during a busy shift (or a demo) is instant.
export const SUGGESTED = [
    "Who should be re-checked next?",
    "Who changed most since check-in?",
    "Has anyone with a lower priority started changing?",
    "What changed since check-in for this patient?",
];

const ROOM_QUESTIONS = SUGGESTED.slice(0, 3); // the last one needs a patient
const FRESH_MS = 10 * 60 * 1000;
const cache = new Map<string, { at: number; answer: Promise<AskAnswer> }>();

const key = (q: string, patientId?: string) => `${patientId ?? ""}|${q.trim().toLowerCase()}`;

export function askCached(question: string, patientId?: string): Promise<AskAnswer> {
    const k = key(question, patientId);
    const hit = cache.get(k);
    if (hit && Date.now() - hit.at < FRESH_MS) return hit.answer;
    const answer = api.ask(question, patientId);
    cache.set(k, { at: Date.now(), answer });
    answer
        .then((a) => {
            // A fallback (model unavailable) is kept briefly, so Gemini is retried soon.
            if (a.provider !== "gemini") cache.set(k, { at: Date.now() - FRESH_MS + 30_000, answer });
        })
        .catch(() => cache.delete(k)); // don't keep failures
    return answer;
}

let warmed = false;
export function warmAskCache() {
    if (warmed) return;
    warmed = true;
    // One at a time, so the model isn't hit with several calls at once.
    ROOM_QUESTIONS.reduce<Promise<unknown>>(
        (prev, q) => prev.then(() => askCached(q).catch(() => undefined)),
        Promise.resolve()
    );
}
