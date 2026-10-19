
"use client";

import { useMemo, useState } from "react";
import type { PatientCase, Priority } from "../types";
import { PRIORITIES } from "../types";

type ERAdminDashboardProps = {
    cases: PatientCase[];
    onAssignPriority: (id: string, priority: Priority | "") => void;
    onGoToIntake: () => void;
};

type QueueFilter = "all" | "awaiting" | "assigned";

function priorityClass(priority: Priority | "") {
    if (priority.startsWith("Priority 1")) return "priority-high";
    if (priority.startsWith("Priority 2")) return "priority-medium";
    if (priority.startsWith("Priority 3")) return "priority-low";
    return "priority-unreviewed";
}

export default function ERAdminDashboard({
                                             cases,
                                             onAssignPriority,
                                             onGoToIntake,
                                         }: ERAdminDashboardProps) {
    const [filter, setFilter] = useState<QueueFilter>("all");
    const [search, setSearch] = useState("");

    const awaitingReview = cases.filter(
        (patient) => patient.status === "Awaiting human review"
    ).length;

    const priorityAssigned = cases.length - awaitingReview;

    const filteredCases = useMemo(() => {
        const term = search.trim().toLowerCase();

        return cases.filter((patient) => {
            const matchesFilter =
                filter === "all" ||
                (filter === "awaiting" &&
                    patient.status === "Awaiting human review") ||
                (filter === "assigned" &&
                    patient.status === "Priority assigned");

            const searchableText = [
                patient.name,
                patient.id,
                patient.dateOfBirth,
                patient.notes,
                ...patient.symptoms,
            ]
                .join(" ")
                .toLowerCase();

            return matchesFilter && (!term || searchableText.includes(term));
        });
    }, [cases, filter, search]);

    return (
        <section className="dashboard-main">
            <div className="dashboard-title-row">
                <div>
                    <p className="eyebrow">EMERGENCY DEPARTMENT</p>
                    <h1>ER Patient Queue</h1>
                    <p className="dashboard-subtitle">
                        Review every checked-in patient, historical context, and
                        human-assigned priority.
                    </p>
                </div>

                <button
                    type="button"
                    className="primary-button"
                    onClick={onGoToIntake}
                >
                    + Check In Patient
                </button>
            </div>

            <div className="dashboard-stats">
                <div className="dashboard-stat stat-total">
                    <span>Total checked in</span>
                    <strong>{cases.length}</strong>
                    <small>All registered patients</small>
                </div>

                <div className="dashboard-stat stat-pending">
                    <span>Awaiting review</span>
                    <strong>{awaitingReview}</strong>
                    <small>Human assessment needed</small>
                </div>

                <div className="dashboard-stat stat-reviewed">
                    <span>Priority assigned</span>
                    <strong>{priorityAssigned}</strong>
                    <small>Reviewed by staff</small>
                </div>
            </div>

            <section className="history-context">
                <div className="history-icon">↻</div>
                <div className="history-copy">
                    <strong>Historical ER context</strong>
                    <p>
                        Historical encounter data is not connected yet. Once integrated,
                        this area can show retrieved prior ER visits, encounter dates,
                        documented conditions, and visit outcomes for reviewer reference.
                    </p>
                </div>
                <span className="history-connection">Not connected</span>
            </section>

            <section className="dashboard-section">
                <div className="section-heading queue-heading">
                    <div>
                        <h2>All checked-in patients</h2>
                        <p>
                            Review reported symptoms and assign priority using qualified
                            human judgment.
                        </p>
                    </div>
                    <span className="patient-count">
            {filteredCases.length} of {cases.length}
          </span>
                </div>

                <div className="queue-toolbar">
                    <div className="queue-filters" aria-label="Filter patient queue">
                        <button
                            type="button"
                            className={`queue-filter ${filter === "all" ? "selected" : ""}`}
                            onClick={() => setFilter("all")}
                        >
                            All patients ({cases.length})
                        </button>
                        <button
                            type="button"
                            className={`queue-filter ${filter === "awaiting" ? "selected" : ""}`}
                            onClick={() => setFilter("awaiting")}
                        >
                            Awaiting review ({awaitingReview})
                        </button>
                        <button
                            type="button"
                            className={`queue-filter ${filter === "assigned" ? "selected" : ""}`}
                            onClick={() => setFilter("assigned")}
                        >
                            Assigned ({priorityAssigned})
                        </button>
                    </div>

                    <input
                        className="queue-search"
                        type="search"
                        placeholder="Search patient, ID, symptom..."
                        aria-label="Search patients"
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                    />
                </div>

                <div className="priority-legend">
                    <span><i className="legend-dot dot-high" /> Priority 1</span>
                    <span><i className="legend-dot dot-medium" /> Priority 2</span>
                    <span><i className="legend-dot dot-low" /> Priority 3</span>
                    <span><i className="legend-dot dot-unreviewed" /> Awaiting review</span>
                </div>

                {cases.length === 0 ? (
                    <div className="empty-state">
                        <h3>No patients checked in yet</h3>
                        <p>
                            Checked-in patients will appear here with their reported
                            symptoms and a human priority selector.
                        </p>
                        <button
                            type="button"
                            className="primary-button"
                            onClick={onGoToIntake}
                        >
                            Open Patient Intake
                        </button>
                    </div>
                ) : filteredCases.length === 0 ? (
                    <div className="empty-state">
                        <h3>No matching patients</h3>
                        <p>Try another search term or select a different queue filter.</p>
                        <button
                            type="button"
                            className="secondary-button"
                            onClick={() => {
                                setSearch("");
                                setFilter("all");
                            }}
                        >
                            Clear filters
                        </button>
                    </div>
                ) : (
                    <div className="patient-table-wrap">
                        <table className="patient-table">
                            <thead>
                            <tr>
                                <th>Patient</th>
                                <th>Reported symptoms</th>
                                <th>Check-in time</th>
                                <th>Historical ER data</th>
                                <th>Human-assigned priority</th>
                            </tr>
                            </thead>

                            <tbody>
                            {filteredCases.map((patient) => (
                                <tr
                                    key={patient.id}
                                    className={
                                        patient.priority
                                            ? priorityClass(patient.priority)
                                            : "priority-unreviewed"
                                    }
                                >
                                    <td>
                                        <strong className="patient-name">
                                            {patient.name}
                                        </strong>
                                        <span className="dashboard-patient">
                        {patient.id}
                      </span>
                                        <span className="dashboard-patient">
                        DOB: {patient.dateOfBirth || "Not provided"}
                      </span>
                                    </td>

                                    <td>
                                        <div className="symptom-tags">
                                            {patient.symptoms.length > 0 ? (
                                                patient.symptoms.map((symptom) => (
                                                    <span className="symptom-tag" key={symptom}>
                              {symptom}
                            </span>
                                                ))
                                            ) : (
                                                <span className="dashboard-patient">
                            No symptoms recorded
                          </span>
                                            )}
                                        </div>
                                        {patient.notes && (
                                            <p className="queue-notes">{patient.notes}</p>
                                        )}
                                    </td>

                                    <td className="queue-time">
                                        {patient.submittedAt}
                                    </td>

                                    <td>
                      <span className="history-unavailable">
                        Not connected
                      </span>
                                        <span className="dashboard-patient">
                        No historical records retrieved
                      </span>
                                    </td>

                                    <td>
                      <span
                          className={`priority-badge ${priorityClass(
                              patient.priority
                          )}`}
                      >
                        {patient.priority || "Awaiting review"}
                      </span>

                                        <select
                                            className="priority-select"
                                            aria-label={`Assign priority for ${patient.name}`}
                                            value={patient.priority}
                                            onChange={(event) =>
                                                onAssignPriority(
                                                    patient.id,
                                                    event.target.value as Priority | ""
                                                )
                                            }
                                        >
                                            <option value="">Assign priority...</option>
                                            {PRIORITIES.map((priority) => (
                                                <option value={priority} key={priority}>
                                                    {priority}
                                                </option>
                                            ))}
                                        </select>

                                        <span className="dashboard-patient">
                        {patient.status}
                      </span>
                                    </td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>

            <p className="form-disclaimer">
                Hackathon demo using synthetic intake data. Historical ER records are
                not yet integrated. Colors represent human-assigned priority only;
                this dashboard does not diagnose or autonomously triage patients.
            </p>
        </section>
    );
}
