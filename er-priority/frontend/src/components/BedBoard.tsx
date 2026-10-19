"use client";

import { clock } from "../lib/api";
import NearbyERs from "./NearbyERs";
import type { BedBoard as Board } from "../types";

type Props = {
    board: Board | undefined;
    busy: string | null;
    onAssign: (patientId: string, bed: string) => void;
    onDischarge: (bed: string) => void;
};

// Bed board: who is in each bed, and for a free bed, the next patient in the official
// line (human priority, then check-in time). The nurse confirms every assignment.
export default function BedBoard({ board, busy, onAssign, onDischarge }: Props) {
    if (!board) return null;
    const next = board.next_up;
    const firstFree = board.beds.find((b) => !b.occupant);
    return (
        <section className="dashboard-section bed-board">
            <div className="section-heading queue-heading">
                <div>
                    <h2>Beds</h2>
                    <p>
                        {board.free === 0
                            ? "All beds are taken. Patients wait in the official line until one frees up."
                            : `${board.free} of ${board.total} free. Patients are roomed in official-line order; a nurse confirms each one.`}
                    </p>
                </div>
                <div className="bed-meter" aria-label={`${board.occupied} of ${board.total} beds occupied`}>
                    <div className="bed-meter-bar">
                        {board.beds.map((b) => (
                            <i key={b.bed} className={b.occupant ? "on" : ""} />
                        ))}
                    </div>
                    <span className="patient-count">
                        {board.occupied} of {board.total} occupied
                    </span>
                </div>
            </div>

            {firstFree && next && (
                <div className="bed-next">
                    <div>
                        <span className="eyebrow">NEXT IN LINE</span>
                        <strong>
                            {next.ticket} · {next.name}
                        </strong>
                        <span className={`priority-badge priority-${next.priority === 1 ? "high" : next.priority === 2 ? "medium" : "low"}`}>
                            Priority {next.priority}
                        </span>
                    </div>
                    <button
                        type="button"
                        className="primary-button"
                        disabled={busy === next.id}
                        onClick={() => onAssign(next.id, firstFree.bed)}
                    >
                        Assign to {firstFree.bed}
                    </button>
                </div>
            )}
            {firstFree && !next && (
                <div className="bed-next bed-next-empty">
                    <span>No one with an approved priority is waiting. Set a priority in the waiting room to put a patient in line.</span>
                </div>
            )}

            <div className="bed-grid">
                {board.beds.map((b) =>
                    b.occupant ? (
                        <div className={`bed-card bed-occupied bed-p${b.occupant.priority ?? 0}`} key={b.bed}>
                            <div className="bed-card-top">
                                <strong>{b.bed}</strong>
                                {b.occupant.priority ? <span className="bed-tag">P{b.occupant.priority}</span> : null}
                            </div>
                            <span className="patient-name">{b.occupant.name}</span>
                            <span className="dashboard-patient">
                                {b.occupant.ticket} · in since {clock(b.occupant.checked_in_at)}
                            </span>
                            <button
                                type="button"
                                className="link-button"
                                disabled={busy === b.bed}
                                onClick={() => onDischarge(b.bed)}
                            >
                                Discharge
                            </button>
                        </div>
                    ) : (
                        <div className="bed-card bed-free" key={b.bed}>
                            <div className="bed-card-top">
                                <strong>{b.bed}</strong>
                                <span className="bed-tag">Free</span>
                            </div>
                            <span className="dashboard-patient">Open</span>
                            {next && (
                                <button
                                    type="button"
                                    className="link-button"
                                    disabled={busy === next.id}
                                    onClick={() => onAssign(next.id, b.bed)}
                                >
                                    Assign {next.ticket} here
                                </button>
                            )}
                        </div>
                    )
                )}
            </div>
            {board.free === 0 && <NearbyERs />}
        </section>
    );
}
