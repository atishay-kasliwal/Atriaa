"use client";

import { Fragment, useMemo, useState } from "react";
import { api, clock, since } from "../lib/api";
import BedBoard from "./BedBoard";
import type { LivePatient, LiveQueue, PriorityLevel, Trajectory } from "../types";
import { PRIORITIES, PRIORITY_LABELS } from "../types";

type ERAdminDashboardProps = {
    queue: LiveQueue | null;
    error: string;
    refresh: () => Promise<void>;
    onGoToIntake: () => void;
    onAsk: (patient: LivePatient) => void;
};

type QueueFilter = "all" | "triage" | "flagged" | "recheck";
type SortMode = "attention" | "line";

const TRAJECTORY: Record<Trajectory, { label: string; tone: string }> = {
    persistent_change: { label: "Persistent change", tone: "traj-red" },
    mixed_change: { label: "Mixed change", tone: "traj-amber" },
    transient_change: { label: "Transient change", tone: "traj-amber" },
    stable: { label: "Stable", tone: "traj-green" },
    insufficient_data: { label: "Check-in reading only", tone: "traj-gray" },
};

function priorityClass(priority: PriorityLevel | null) {
    if (priority === 1) return "priority-high";
    if (priority === 2) return "priority-medium";
    if (priority === 3) return "priority-low";
    return "priority-unreviewed";
}

function delta(v: number | null | undefined) {
    if (v == null || v === 0) return "";
    return v > 0 ? ` (+${v})` : ` (${v})`;
}

function Vitals({ p }: { p: LivePatient }) {
    const c = p.current;
    const parts = [
        c.hr != null && `HR ${c.hr}${delta(p.deltas.hr)}`,
        c.spo2 != null && `SpO2 ${c.spo2}%${delta(p.deltas.spo2)}`,
        c.pain != null && `Pain ${c.pain}/10${delta(p.deltas.pain)}`,
    ].filter(Boolean);
    return <span className="vitals-line">{parts.length ? parts.join(" · ") : "No readings yet"}</span>;
}

function RecheckForm({ patient, onDone }: { patient: LivePatient; onDone: () => Promise<void> }) {
    const [hr, setHr] = useState("");
    const [spo2, setSpo2] = useState("");
    const [pain, setPain] = useState("");
    const [error, setError] = useState("");
    const [saving, setSaving] = useState(false);

    async function save() {
        const body = {
            ...(hr ? { hr: Number(hr) } : {}),
            ...(spo2 ? { spo2: Number(spo2) } : {}),
            ...(pain ? { pain: Number(pain) } : {}),
        };
        if (!Object.keys(body).length) {
            setError("Enter at least one reading.");
            return;
        }
        setSaving(true);
        try {
            await api.recordVitals(patient.id, body);
            await onDone();
        } catch (e) {
            setError((e as Error).message);
            setSaving(false);
        }
    }

    return (
        <div className="recheck-form" onKeyDown={(e) => e.key === "Enter" && save()}>
            <strong>Re-check {patient.ticket}</strong>
            <label>
                <span>Heart rate</span>
                <input inputMode="numeric" placeholder="bpm" value={hr} onChange={(e) => setHr(e.target.value)} autoFocus />
            </label>
            <label>
                <span>SpO2</span>
                <input inputMode="numeric" placeholder="%" value={spo2} onChange={(e) => setSpo2(e.target.value)} />
            </label>
            <label>
                <span>Pain</span>
                <input inputMode="numeric" placeholder="0–10" value={pain} onChange={(e) => setPain(e.target.value)} />
            </label>
            <button type="button" className="primary-button" disabled={saving} onClick={save}>
                {saving ? "Saving…" : "Save re-check"}
            </button>
            {error && <span className="form-error">{error}</span>}
        </div>
    );
}

export default function ERAdminDashboard({ queue, error, refresh, onGoToIntake, onAsk }: ERAdminDashboardProps) {
    const [filter, setFilter] = useState<QueueFilter>("all");
    const [sort, setSort] = useState<SortMode>("attention");
    const [search, setSearch] = useState("");
    const [recheckId, setRecheckId] = useState<string | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [actionError, setActionError] = useState("");

    const patients = useMemo(() => queue?.queue ?? [], [queue]);
    const recheckRequested = patients.filter((p) => p.reassessment_requested_at).length;
    const flagged = patients.filter((p) => p.reassessment_signal);
    const alerts = flagged.filter((p) => p.alert_active);
    const acknowledged = flagged.filter((p) => !p.alert_active);

    const rows = useMemo(() => {
        const term = search.trim().toLowerCase();
        const matched = patients.filter((p) => {
            const matchesFilter =
                filter === "all" ||
                (filter === "triage" && !p.priority) ||
                (filter === "flagged" && p.reassessment_signal) ||
                (filter === "recheck" && p.reassessment_requested_at);
            const text = [p.name, p.ticket, p.date_of_birth, p.notes, ...p.symptoms].join(" ").toLowerCase();
            return matchesFilter && (!term || text.includes(term));
        });
        if (sort === "line") {
            return [...matched].sort(
                (a, b) => (a.line_position ?? 999) - (b.line_position ?? 999) || a.checked_in_at.localeCompare(b.checked_in_at)
            );
        }
        return matched;
    }, [patients, filter, search, sort]);

    async function act(id: string, fn: () => Promise<unknown>) {
        setBusy(id);
        setActionError("");
        try {
            await fn();
            await refresh();
        } catch (e) {
            setActionError((e as Error).message);
        } finally {
            setBusy(null);
        }
    }

    async function clearDemo() {
        if (!window.confirm("Remove every patient from the waiting room?")) return;
        await act("reset", () => api.reset());
    }

    return (
        <section className="dashboard-main">
            <div className="dashboard-title-row">
                <div>
                    <p className="eyebrow">EMERGENCY DEPARTMENT</p>
                    <h1>ER Patient Queue</h1>
                    <p className="dashboard-subtitle">
                        Staff set priority. Atria watches what changes after check-in and flags who may need a
                        re-check.
                    </p>
                </div>
                <div className="title-actions">
                    <button type="button" className="secondary-button" onClick={clearDemo} disabled={busy === "reset"}>
                        Clear waiting room
                    </button>
                    <button type="button" className="primary-button" onClick={onGoToIntake}>
                        + Check In Patient
                    </button>
                </div>
            </div>

            <div className="dashboard-stats stats-four">
                <div className="dashboard-stat stat-total">
                    <span>Waiting now</span>
                    <strong>{queue?.waiting ?? "–"}</strong>
                    <small>Checked in, not yet in a bed</small>
                </div>
                <div className="dashboard-stat stat-pending">
                    <span>Awaiting triage</span>
                    <strong>{queue?.awaiting_triage ?? "–"}</strong>
                    <small>Need a human priority</small>
                </div>
                <div className="dashboard-stat stat-flagged">
                    <span>Atria alerts</span>
                    <strong>{queue?.alerts ?? "–"}</strong>
                    <small>
                        Need a nurse
                        {acknowledged.length ? ` · ${acknowledged.length} acknowledged` : ""}
                    </small>
                </div>
                <div className="dashboard-stat stat-recheck">
                    <span>Re-check requested</span>
                    <strong>{recheckRequested}</strong>
                    <small>Patient has been notified</small>
                </div>
            </div>

            <BedBoard
                board={queue?.beds}
                busy={busy}
                onAssign={(id, bed) => act(id, () => api.assignBed(id, bed))}
                onDischarge={(bed) => act(bed, () => api.discharge(bed))}
            />

            {alerts.map((p) => (
                <section className="history-context atria-alert" key={p.id}>
                    <div className="history-icon">▲</div>
                    <div className="history-copy">
                        <strong>
                            Atria · {p.ticket} {p.name}: {p.reasons[0]}
                        </strong>
                        <p>
                            <Vitals p={p} />
                            {p.priority ? `${PRIORITY_LABELS[p.priority]}` : "No priority yet"} · line{" "}
                            {p.line_position ? `#${p.line_position}` : "pending triage"}. A nurse decides what happens
                            next.
                        </p>
                        <div className="alert-actions">
                            {p.reassessment_requested_at ? (
                                <span className="recheck-pending">Re-check requested {clock(p.reassessment_requested_at)}</span>
                            ) : (
                                <button
                                    type="button"
                                    className="secondary-button"
                                    disabled={busy === p.id}
                                    onClick={() => act(p.id, () => api.requestReassessment(p.id))}
                                >
                                    Request re-check
                                </button>
                            )}
                            {PRIORITIES.filter((level) => !p.priority || level < p.priority).map((level) => (
                                <button
                                    key={level}
                                    type="button"
                                    className="primary-button"
                                    disabled={busy === p.id}
                                    onClick={() => act(p.id, () => api.acknowledge(p.id, level))}
                                >
                                    Acknowledge + Priority {level}
                                </button>
                            ))}
                            <button
                                type="button"
                                className="secondary-button"
                                disabled={busy === p.id}
                                onClick={() => act(p.id, () => api.acknowledge(p.id))}
                            >
                                Acknowledge, keep priority
                            </button>
                        </div>
                    </div>
                </section>
            ))}
            {acknowledged.map((p) => (
                <section className="history-context atria-acknowledged" key={p.id}>
                    <div className="history-icon">✓</div>
                    <div className="history-copy">
                        <strong>
                            {p.ticket} {p.name}: acknowledged by {p.acknowledged_by} at {clock(p.acknowledged_at)}
                        </strong>
                        <p>
                            {p.acknowledgement?.replace("->", "→")}. Now{" "}
                            {p.priority ? PRIORITY_LABELS[p.priority] : "awaiting triage"}
                            {p.line_position ? `, #${p.line_position} in line` : ""}. Atria will flag again if a newer
                            reading keeps worsening.
                        </p>
                    </div>
                </section>
            ))}
            {alerts.length === 0 && acknowledged.length === 0 && (
                <section className="history-context">
                    <div className="history-icon">↻</div>
                    <div className="history-copy">
                        <strong>Atria is watching {queue?.waiting ?? 0} waiting patients</strong>
                        <p>
                            Readings come from staff re-checks on this page and from patients&apos; own updates on their
                            phones. No one has worsened on every reading since check-in.
                        </p>
                    </div>
                    <span className="history-connection">Live</span>
                </section>
            )}

            {(error || actionError) && (
                <p className="form-error" role="alert">
                    {actionError || `Can't reach the Atria backend: ${error}`}
                </p>
            )}

            <section className="dashboard-section">
                <div className="section-heading queue-heading">
                    <div>
                        <h2>Waiting room</h2>
                        <p>
                            {sort === "attention"
                                ? "Ordered by Atria's attention list: who changed most since check-in. Priority stays with staff."
                                : "Ordered by the official line: human priority, then check-in time."}
                        </p>
                    </div>
                    <span className="patient-count">
                        {rows.length} of {patients.length} · updated {queue ? clock(queue.as_of) : "—"}
                    </span>
                </div>

                <div className="queue-toolbar">
                    <div className="queue-filters" aria-label="Filter patient queue">
                        {(
                            [
                                ["all", `All (${patients.length})`],
                                ["triage", `Awaiting triage (${queue?.awaiting_triage ?? 0})`],
                                ["flagged", `Flagged (${flagged.length})`],
                                ["recheck", `Re-check requested (${recheckRequested})`],
                            ] as [QueueFilter, string][]
                        ).map(([key, label]) => (
                            <button
                                key={key}
                                type="button"
                                className={`queue-filter ${filter === key ? "selected" : ""}`}
                                onClick={() => setFilter(key)}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                    <div className="toolbar-right">
                        <div className="queue-filters" aria-label="Sort">
                            <button
                                type="button"
                                className={`queue-filter ${sort === "attention" ? "selected" : ""}`}
                                onClick={() => setSort("attention")}
                            >
                                Atria attention
                            </button>
                            <button
                                type="button"
                                className={`queue-filter ${sort === "line" ? "selected" : ""}`}
                                onClick={() => setSort("line")}
                            >
                                Official line
                            </button>
                        </div>
                        <input
                            className="queue-search"
                            type="search"
                            placeholder="Search patient, ticket, symptom..."
                            aria-label="Search patients"
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                        />
                    </div>
                </div>

                <div className="priority-legend">
                    <span><i className="legend-dot dot-high" /> Priority 1</span>
                    <span><i className="legend-dot dot-medium" /> Priority 2</span>
                    <span><i className="legend-dot dot-low" /> Priority 3</span>
                    <span><i className="legend-dot dot-unreviewed" /> Awaiting triage</span>
                    <span><i className="legend-dot dot-flag" /> Atria flag (separate from priority)</span>
                </div>

                {!queue && !error ? (
                    <div className="empty-state"><p>Loading waiting room…</p></div>
                ) : patients.length === 0 ? (
                    <div className="empty-state">
                        <h3>No patients checked in yet</h3>
                        <p>Patients who check in appear here with their symptoms, priority and change since check-in.</p>
                        <button type="button" className="primary-button" onClick={onGoToIntake}>
                            Open Patient Intake
                        </button>
                    </div>
                ) : rows.length === 0 ? (
                    <div className="empty-state">
                        <h3>No matching patients</h3>
                        <p>Try another search term or select a different filter.</p>
                        <button type="button" className="secondary-button" onClick={() => { setSearch(""); setFilter("all"); }}>
                            Clear filters
                        </button>
                    </div>
                ) : (
                    <div className="patient-table-wrap">
                        <table className="patient-table">
                            <thead>
                                <tr>
                                    <th>{sort === "attention" ? "Attention" : "Line"}</th>
                                    <th>Patient</th>
                                    <th>Reported symptoms</th>
                                    <th>Since check-in (Atria)</th>
                                    <th>Human-assigned priority</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((p) => {
                                    const traj = TRAJECTORY[p.trajectory];
                                    return (
                                        <Fragment key={p.id}>
                                            <tr className={`${priorityClass(p.priority)} ${p.alert_active ? "row-flagged" : ""}`}>
                                                <td className="position-cell">
                                                    <strong>
                                                        {sort === "attention" ? p.attention_position : p.line_position ?? "–"}
                                                    </strong>
                                                    <span className="dashboard-patient">
                                                        {p.line_position ? `Line #${p.line_position}` : "Triage pending"}
                                                    </span>
                                                </td>
                                                <td>
                                                    <strong className="patient-name">{p.name}</strong>
                                                    <span className="dashboard-patient">{p.ticket} · DOB {p.date_of_birth || "not provided"}</span>
                                                    <span className="dashboard-patient">
                                                        Checked in {clock(p.checked_in_at)} · {p.waiting_minutes} min
                                                    </span>
                                                </td>
                                                <td>
                                                    <div className="symptom-tags">
                                                        {p.symptoms.map((s) => (
                                                            <span className="symptom-tag" key={s}>{s}</span>
                                                        ))}
                                                    </div>
                                                    {p.notes && <p className="queue-notes">{p.notes}</p>}
                                                </td>
                                                <td>
                                                    <span className={`traj-badge ${traj.tone}`}>
                                                        {p.reassessment_signal ? "▲ " : ""}
                                                        {traj.label}
                                                    </span>
                                                    {p.reassessment_signal && !p.alert_active && (
                                                        <span className="ack-tag">✓ Acknowledged {clock(p.acknowledged_at)}</span>
                                                    )}
                                                    <Vitals p={p} />
                                                    <span className="dashboard-patient">
                                                        {p.readings} reading{p.readings === 1 ? "" : "s"} · last {since(p.current.observed_at)}
                                                    </span>
                                                    {p.trajectory !== "stable" && p.trajectory !== "insufficient_data" && (
                                                        <span className="dashboard-patient">{p.reasons[0]}</span>
                                                    )}
                                                    {p.reasons.filter((reason) => reason.startsWith("Patient-reported")).map((reason) => (
                                                        <span className="dashboard-patient" key={reason}>{reason}</span>
                                                    ))}
                                                </td>
                                                <td>
                                                    <span className={`priority-badge ${priorityClass(p.priority)}`}>
                                                        {p.priority ? PRIORITY_LABELS[p.priority] : "Awaiting triage"}
                                                    </span>
                                                    {!p.priority && p.suggested_priority && (
                                                        <div className="approve-row">
                                                            <span className="dashboard-patient">
                                                                Front desk suggests Priority {p.suggested_priority}
                                                            </span>
                                                            <button
                                                                type="button"
                                                                className="primary-button"
                                                                disabled={busy === p.id}
                                                                onClick={() => act(p.id, () => api.setPriority(p.id, p.suggested_priority))}
                                                            >
                                                                Approve P{p.suggested_priority}
                                                            </button>
                                                        </div>
                                                    )}
                                                    <select
                                                        className="priority-select"
                                                        aria-label={`Assign priority for ${p.name}`}
                                                        value={p.priority ?? ""}
                                                        disabled={busy === p.id}
                                                        onChange={(e) =>
                                                            act(p.id, () =>
                                                                api.setPriority(
                                                                    p.id,
                                                                    e.target.value ? (Number(e.target.value) as PriorityLevel) : null
                                                                )
                                                            )
                                                        }
                                                    >
                                                        <option value="">Assign priority...</option>
                                                        {PRIORITIES.map((level) => (
                                                            <option value={level} key={level}>{PRIORITY_LABELS[level]}</option>
                                                        ))}
                                                    </select>
                                                </td>
                                                <td className="action-cell">
                                                    <button
                                                        type="button"
                                                        className="secondary-button"
                                                        onClick={() => setRecheckId(recheckId === p.id ? null : p.id)}
                                                    >
                                                        {recheckId === p.id ? "Cancel" : "Record re-check"}
                                                    </button>
                                                    {p.reassessment_requested_at ? (
                                                        <span className="recheck-pending">Re-check requested {clock(p.reassessment_requested_at)}</span>
                                                    ) : (
                                                        <button
                                                            type="button"
                                                            className="secondary-button"
                                                            disabled={busy === p.id}
                                                            onClick={() => act(p.id, () => api.requestReassessment(p.id))}
                                                        >
                                                            Request re-check
                                                        </button>
                                                    )}
                                                    <button type="button" className="link-button" onClick={() => onAsk(p)}>
                                                        Ask Atria
                                                    </button>
                                                    <button
                                                        type="button"
                                                        className="link-button"
                                                        disabled={busy === p.id || !queue?.beds.free}
                                                        title={queue?.beds.free ? "Room in the first free bed" : "No free bed"}
                                                        onClick={() => act(p.id, () => api.assignBed(p.id))}
                                                    >
                                                        {queue?.beds.free ? "Assign bed" : "No free bed"}
                                                    </button>
                                                </td>
                                            </tr>
                                            {recheckId === p.id && (
                                                <tr className="recheck-row">
                                                    <td colSpan={6}>
                                                        <RecheckForm
                                                            patient={p}
                                                            onDone={async () => {
                                                                setRecheckId(null);
                                                                await refresh();
                                                            }}
                                                        />
                                                    </td>
                                                </tr>
                                            )}
                                        </Fragment>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>

            <p className="form-disclaimer">
                Colors show human-assigned priority. Atria flags change since
                check-in for a nurse to review; it never diagnoses, changes priority or decides treatment.
            </p>
        </section>
    );
}
