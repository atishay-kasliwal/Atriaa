"use client";

import { useEffect, useRef, useState } from "react";
import { api, clock } from "../lib/api";
import type { AskAnswer, LiveQueue } from "../types";

type AskAtriaProps = {
    queue: LiveQueue | null;
    patientId: string;
    onPatientChange: (id: string) => void;
};

type Turn = { id: number; question: string; ticket?: string; answer?: AskAnswer; error?: string };

const SUGGESTED = [
    "Who should be re-checked next?",
    "What changed since check-in for this patient?",
    "Has anyone with a lower priority started changing?",
    "Who changed most since check-in?",
];

export default function AskAtria({ queue, patientId, onPatientChange }: AskAtriaProps) {
    const [question, setQuestion] = useState("");
    const [turns, setTurns] = useState<Turn[]>([]);
    const [asking, setAsking] = useState(false);
    const nextId = useRef(0);
    const patients = queue?.queue ?? [];
    const selected = patients.find((p) => p.id === patientId);

    // Demo: answer the two key questions as soon as the waiting room has loaded.
    const autoAsked = useRef(false);
    useEffect(() => {
        if (autoAsked.current || !queue || !queue.queue.length) return;
        autoAsked.current = true;
        // In parallel: each Gemini answer takes several seconds.
        ["Who changed most since check-in?", "Who should be re-checked next?"].forEach((q) => ask(q));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [queue]);

    async function ask(text: string) {
        const q = text.trim();
        if (!q || asking) return;
        setAsking(true);
        setQuestion("");
        const id = ++nextId.current;
        const update = (patch: Partial<Turn>) =>
            setTurns((all) => all.map((t) => (t.id === id ? { ...t, ...patch } : t)));
        setTurns((all) => [{ id, question: q, ticket: selected?.ticket }, ...all]);
        try {
            update({ answer: await api.ask(q, selected?.id) });
        } catch (e) {
            update({ error: (e as Error).message });
        }
        setAsking(false);
    }

    return (
        <section className="dashboard-main">
            <div className="dashboard-title-row">
                <div>
                    <p className="eyebrow">ATRIA ASSISTANT</p>
                    <h1>Ask Atria</h1>
                    <p className="dashboard-subtitle">
                        Plain-language answers about the live waiting room, built only from recorded readings and
                        patient updates. Atria explains; it doesn&apos;t diagnose or set priority.
                    </p>
                </div>
            </div>

            <section className="dashboard-section ask-panel">
                <div className="ask-controls">
                    <label className="form-field">
                        <span>About a patient (optional)</span>
                        <select value={patientId} onChange={(e) => onPatientChange(e.target.value)}>
                            <option value="">Whole waiting room</option>
                            {patients.map((p) => (
                                <option key={p.id} value={p.id}>
                                    {p.ticket} · {p.name}
                                    {p.reassessment_signal ? " · flagged" : ""}
                                </option>
                            ))}
                        </select>
                    </label>

                    <div className="symptom-tags">
                        {SUGGESTED.map((s) => (
                            <button key={s} type="button" className="queue-filter" onClick={() => ask(s)} disabled={asking}>
                                {s}
                            </button>
                        ))}
                    </div>

                    <div className="ask-input-row">
                        <input
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && ask(question)}
                            placeholder={selected ? `Ask about ${selected.ticket}…` : "e.g. Who should be re-checked next?"}
                            aria-label="Question for Atria"
                        />
                        <button type="button" className="primary-button" onClick={() => ask(question)} disabled={asking || !question.trim()}>
                            {asking ? "Thinking…" : "Ask"}
                        </button>
                    </div>
                </div>

                {turns.length === 0 ? (
                    <div className="empty-state">
                        <h3>No questions yet</h3>
                        <p>Pick a suggestion or type a question. Answers cite tickets, readings and times.</p>
                    </div>
                ) : (
                    <div className="ask-thread">
                        {turns.map((t) => (
                            <article className="ask-turn" key={t.id}>
                                <p className="ask-question">
                                    {t.question}
                                    {t.ticket && <span className="symptom-tag">{t.ticket}</span>}
                                </p>
                                {t.error ? (
                                    <p className="form-error">Couldn&apos;t reach Atria: {t.error}</p>
                                ) : t.answer ? (
                                    <>
                                        <div className="ask-answer">{t.answer.answer}</div>
                                        <p className="dashboard-patient">
                                            <span className={`provider-badge ${t.answer.provider}`}>
                                                {t.answer.provider === "gemini" ? `Gemini · ${t.answer.model}` : "Sourced fallback"}
                                            </span>{" "}
                                            Queue {t.answer.queue_version} · as of {clock(t.answer.as_of)}
                                            {t.answer.notice ? ` · ${t.answer.notice}` : ""}
                                        </p>
                                    </>
                                ) : (
                                    <p className="dashboard-patient">Reading the waiting room…</p>
                                )}
                            </article>
                        ))}
                    </div>
                )}
            </section>
        </section>
    );
}
