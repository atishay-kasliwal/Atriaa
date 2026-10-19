"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api, clock, since } from "../../../lib/api";
import type { CheckInStatus } from "../../../types";
import Link from "next/link";

type Feeling = "better" | "same" | "worse";

const STAGE_COPY: Record<CheckInStatus["stage"], { title: string; body: string; tone: string }> = {
    awaiting_triage: {
        title: "Waiting for a triage nurse",
        body: "A nurse will review your symptoms and set your priority. Your place in line appears after that.",
        tone: "stage-pending",
    },
    waiting: {
        title: "You're in line",
        body: "Staff set the order by medical priority, so your place can change as other patients arrive.",
        tone: "stage-waiting",
    },
    recheck_requested: {
        title: "A nurse wants to re-check you",
        body: "Please stay close to the front desk. Someone will call your ticket shortly.",
        tone: "stage-recheck",
    },
    called: {
        title: "You've been called in",
        body: "Please go to the front desk and show your ticket.",
        tone: "stage-called",
    },
};

export default function CheckInStatusPage() {
    const { id } = useParams<{ id: string }>();
    const [status, setStatus] = useState<CheckInStatus | null>(null);
    const [error, setError] = useState("");
    const [feeling, setFeeling] = useState<Feeling | "">("");
    const [pain, setPain] = useState("");
    const [sending, setSending] = useState(false);
    const [sent, setSent] = useState("");
    const [movedUp, setMovedUp] = useState<{ from: number; to: number } | null>(null);
    const lastPosition = useRef<number | null>(null);

    const load = useCallback(async () => {
        try {
            const next = await api.status(id);
            const prev = lastPosition.current;
            const pos = next.line_position ?? null;
            if (prev != null && pos != null && pos < prev) setMovedUp({ from: prev, to: pos });
            lastPosition.current = pos;
            setStatus(next);
            setError("");
        } catch (e) {
            setError((e as Error).message);
        }
    }, [id]);

    useEffect(() => {
        const first = setTimeout(load, 0);
        const timer = setInterval(load, 4000);
        return () => {
            clearTimeout(first);
            clearInterval(timer);
        };
    }, [load]);

    async function sendUpdate() {
        if (!feeling && pain === "") return;
        setSending(true);
        try {
            setStatus(
                await api.report(id, {
                    ...(feeling ? { feeling } : {}),
                    ...(pain !== "" ? { pain: Number(pain) } : {}),
                })
            );
            setSent(`Sent at ${clock(new Date().toISOString())}. Staff can see it now.`);
            setFeeling("");
            setPain("");
        } catch (e) {
            setSent(`Could not send: ${(e as Error).message}. Please tell the front desk.`);
        } finally {
            setSending(false);
        }
    }

    if (error && !status) {
        return (
            <main className="patient-shell">
                <div className="patient-card">
                    <h1>Check-in not found</h1>
                    <p className="dashboard-subtitle">Please ask the front desk for help.</p>
                </div>
            </main>
        );
    }
    if (!status) {
        return (
            <main className="patient-shell">
                <div className="patient-card">Loading your check-in…</div>
            </main>
        );
    }

    const copy = STAGE_COPY[status.stage];
    const waiting = status.status === "waiting";

    return (
        <main className="patient-shell">
            <Link href="/" className="patient-brand brand-link">
                <div className="brand-mark">+</div>
                <div>
                    <div className="patient-brand-name">ER Priority</div>
                    <div className="dashboard-patient">Waiting room check-in</div>
                </div>
            </Link>

            <section className="patient-card">
                <p className="eyebrow">YOUR TICKET</p>
                <div className="ticket-row">
                    <div className="ticket-code">{status.ticket}</div>
                    <div>
                        <strong className="patient-name">{status.name}</strong>
                        <span className="dashboard-patient">
                            Checked in {clock(status.checked_in_at)} · waiting {status.waited_minutes} min
                        </span>
                    </div>
                </div>

                <div className={`stage-banner ${copy.tone}`} role="status">
                    <strong>{copy.title}</strong>
                    <p>{copy.body}</p>
                </div>

                {movedUp && waiting && (
                    <div className="stage-banner stage-called" role="status">
                        <strong>You&apos;ve been moved up to #{movedUp.to}</strong>
                        <p>A nurse reviewed your updates and changed your place in line (was #{movedUp.from}).</p>
                    </div>
                )}

                {status.stage !== "awaiting_triage" && status.line_position != null && (
                    <div className="line-summary">
                        <div>
                            <span>Your place</span>
                            <strong>#{status.line_position}</strong>
                        </div>
                        <div>
                            <span>Ahead of you</span>
                            <strong>{status.ahead}</strong>
                        </div>
                        <div>
                            <span>Waiting for triage</span>
                            <strong>{status.awaiting_triage_count}</strong>
                        </div>
                    </div>
                )}

                {waiting && status.line && status.line.length > 0 && (
                    <div className="line-strip" aria-label="Current line by ticket">
                        {status.line.map((t, i) => (
                            <span key={t.ticket} className={`line-chip ${t.you ? "you" : ""}`}>
                                {i + 1}. {t.you ? `You (${t.ticket})` : t.ticket}
                            </span>
                        ))}
                    </div>
                )}
                {waiting && (
                    <p className="form-disclaimer">
                        Tickets only. Other patients&apos; names and symptoms are never shown.
                    </p>
                )}
            </section>

            {waiting && (
                <section className="patient-card">
                    <h2>How are you feeling now?</h2>
                    <p className="dashboard-subtitle">
                        Your update goes straight to the nurses&apos; dashboard.
                    </p>

                    <div className="feeling-row">
                        {(["better", "same", "worse"] as Feeling[]).map((f) => (
                            <button
                                key={f}
                                type="button"
                                className={`feeling-option feeling-${f} ${feeling === f ? "selected" : ""}`}
                                onClick={() => setFeeling(feeling === f ? "" : f)}
                            >
                                {f === "better" ? "Better" : f === "same" ? "About the same" : "Worse"}
                            </button>
                        ))}
                    </div>

                    <p className="field-caption">Pain right now (0–10)</p>
                    <div className="pain-scale">
                        {Array.from({ length: 11 }, (_, n) => (
                            <button
                                key={n}
                                type="button"
                                className={`pain-option ${pain === String(n) ? "selected" : ""}`}
                                onClick={() => setPain(pain === String(n) ? "" : String(n))}
                            >
                                <span>{n}</span>
                            </button>
                        ))}
                    </div>

                    <button
                        type="button"
                        className="primary-button send-update"
                        disabled={sending || (!feeling && pain === "")}
                        onClick={sendUpdate}
                    >
                        {sending ? "Sending…" : "Send update to staff"}
                    </button>
                    {sent && <p className="intake-message">{sent}</p>}
                    {status.last_update && (
                        <p className="form-disclaimer">Last update {since(status.last_update)}.</p>
                    )}
                </section>
            )}

            <div className="safety-banner">
                <span className="safety-icon">!</span>
                <div>
                    <strong>Feeling much worse?</strong>
                    <p>
                        Tell the front desk right away. Don&apos;t wait for this page. This demo
                        doesn&apos;t diagnose, and only staff decide your priority.
                    </p>
                </div>
            </div>
        </main>
    );
}
