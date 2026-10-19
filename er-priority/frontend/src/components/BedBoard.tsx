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
    return (
        <section className="dashboard-section bed-board">
            <div className="section-heading queue-heading">
                <div>
                    <h2>Beds</h2>
                    <p>
                        {board.free === 0
                            ? "All beds are taken. Patients wait in the official line until one frees up."
                            : next
                              ? `${board.free} free. Next in line: ${next.ticket} ${next.name} (Priority ${next.priority}).`
                              : `${board.free} free. Approve a priority to put someone in line for it.`}
                    </p>
                </div>
                <span className="patient-count">
                    {board.occupied} of {board.total} occupied
                </span>
            </div>
            <div className="bed-grid">
                {board.beds.map((b) =>
                    b.occupant ? (
                        <div className={`bed-card bed-occupied bed-p${b.occupant.priority ?? 0}`} key={b.bed}>
                            <div className="bed-card-top">
                                <strong>{b.bed}</strong>
                                <span className="bed-tag">Occupied</span>
                            </div>
                            <span className="patient-name">{b.occupant.name}</span>
                            <span className="dashboard-patient">
                                {b.occupant.ticket}
                                {b.occupant.priority ? ` · P${b.occupant.priority}` : ""} · arrived {clock(b.occupant.checked_in_at)}
                            </span>
                            <span className="dashboard-patient">{b.occupant.symptoms.join(", ")}</span>
                            <button
                                type="button"
                                className="secondary-button"
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
                                <span className="bed-tag">Available</span>
                            </div>
                            {next ? (
                                <>
                                    <span className="dashboard-patient">Next in line</span>
                                    <span className="patient-name">
                                        {next.ticket} {next.name}
                                    </span>
                                    <button
                                        type="button"
                                        className="primary-button"
                                        disabled={busy === next.id}
                                        onClick={() => onAssign(next.id, b.bed)}
                                    >
                                        Assign to {b.bed} (P{next.priority})
                                    </button>
                                </>
                            ) : (
                                <span className="dashboard-patient">No one with an approved priority is waiting.</span>
                            )}
                        </div>
                    )
                )}
            </div>
            {board.free === 0 && <NearbyERs />}
        </section>
    );
}
