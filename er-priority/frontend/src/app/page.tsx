
"use client";

import { useState } from "react";
import PatientIntake from "../components/PatientIntake";
import ERAdminDashboard from "../components/ERAdminDashboard";
import type { PatientCase, Priority } from "../types";

export default function Home() {
    const [activeTab, setActiveTab] = useState<"intake" | "queue">("intake");
    const [cases, setCases] = useState<PatientCase[]>([]);

    function handleCheckIn(patient: PatientCase) {
        setCases((current) => [patient, ...current]);
    }

    function handleAssignPriority(id: string, priority: Priority | "") {
        setCases((current) =>
            current.map((patient) =>
                patient.id === id
                    ? {
                        ...patient,
                        priority,
                        status: priority
                            ? "Priority assigned"
                            : "Awaiting human review",
                    }
                    : patient
            )
        );
    }

    const isIntake = activeTab === "intake";

    return (
        <main className="app-shell">
            <aside className="sidebar">
                <div className="brand">
                    <div className="brand-mark">+</div>
                    <div>
                        <div className="brand-name">ER Priority</div>
                        <div className="brand-subtitle">Emergency intake demo</div>
                    </div>
                </div>

                <div className="nav-label">WORKSPACE</div>

                <button
                    type="button"
                    className={`nav-item ${isIntake ? "active" : ""}`}
                    onClick={() => setActiveTab("intake")}
                >
                    <span className="nav-icon">＋</span>
                    Patient intake
                </button>

                <button
                    type="button"
                    className={`nav-item ${!isIntake ? "active" : ""}`}
                    onClick={() => setActiveTab("queue")}
                >
                    <span className="nav-icon">▤</span>
                    ER dashboard
                    <span className="nav-count">{cases.length}</span>
                </button>

                <div className="sidebar-bottom">
                    <div className="sidebar-indicator" />
                    <div>
                        <strong>Demo environment</strong>
                        <span>Synthetic data only</span>
                    </div>
                </div>
            </aside>

            <section className="main-panel">
                <header className="topbar">
                    <div className="breadcrumb">
                        Workspace <span>/</span>{" "}
                        {isIntake ? "Patient intake" : "ER dashboard"}
                    </div>
                    <div className="top-status">
                        <span className="status-dot" />
                        Demo mode
                    </div>
                </header>

                <div className="content">
                    <div className="page-heading">
                        <div>
                            <div className="eyebrow">EMERGENCY CARE WORKSPACE</div>
                            <h1>
                                {isIntake ? "Patient intake" : "ER admin dashboard"}
                            </h1>
                            <p>
                                {isIntake
                                    ? "Check in a patient and record their reported symptoms."
                                    : "View checked-in patients and manage human-assigned priorities."}
                            </p>
                        </div>
                        <div className="heading-icon">✚</div>
                    </div>

                    <div className="safety-banner">
                        <span className="safety-icon">ⓘ</span>
                        <div>
                            <strong>Human review required</strong>
                            <p>
                                This prototype does not diagnose patients or automatically
                                determine clinical priority. Priority decisions remain with
                                the human reviewer.
                            </p>
                        </div>
                    </div>

                    {isIntake ? (
                        <PatientIntake onCheckIn={handleCheckIn} />
                    ) : (
                        <ERAdminDashboard
                            cases={cases}
                            onAssignPriority={handleAssignPriority}
                            onGoToIntake={() => setActiveTab("intake")}
                        />
                    )}

                    <footer>
                        <span>ER Priority · Hackathon prototype</span>
                        <span>Not for clinical use</span>
                    </footer>
                </div>
            </section>
        </main>
    );
}
