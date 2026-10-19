"use client";

import { useCallback, useEffect, useState } from "react";
import PatientIntake from "../components/PatientIntake";
import ERAdminDashboard from "../components/ERAdminDashboard";
import AskAtria from "../components/AskAtria";
import { api } from "../lib/api";
import type { LivePatient, LiveQueue } from "../types";

type Tab = "intake" | "queue" | "ask";

const CRUMBS: Record<Tab, string> = {
    intake: "Patient intake",
    queue: "ER dashboard",
    ask: "Ask Atria",
};

// The scripted Bay 4 replay board served by the backend.
const REPLAY_URL = process.env.NEXT_PUBLIC_ATRIA_REPLAY_URL ?? "http://127.0.0.1:8001/";

export default function Home() {
    const [activeTab, setActiveTab] = useState<Tab>("queue");
    const [queue, setQueue] = useState<LiveQueue | null>(null);
    const [error, setError] = useState("");
    const [askPatient, setAskPatient] = useState("");

    const refresh = useCallback(async () => {
        try {
            setQueue(await api.queue());
            setError("");
        } catch (e) {
            setError((e as Error).message);
        }
    }, []);

    useEffect(() => {
        const first = setTimeout(refresh, 0);
        const timer = setInterval(refresh, 3000);
        return () => {
            clearTimeout(first);
            clearInterval(timer);
        };
    }, [refresh]);

    function askAbout(patient: LivePatient) {
        setAskPatient(patient.id);
        setActiveTab("ask");
    }

    const nav = (tab: Tab, icon: string, label: string, count?: number) => (
        <button
            type="button"
            className={`nav-item ${activeTab === tab ? "active" : ""}`}
            onClick={() => setActiveTab(tab)}
        >
            <span className="nav-icon">{icon}</span>
            {label}
            {count !== undefined && <span className="nav-count">{count}</span>}
        </button>
    );

    return (
        <main className="app-shell">
            <aside className="sidebar">
                <div className="brand">
                    <div className="brand-mark">+</div>
                    <div>
                        <div className="brand-name">ER Priority</div>
                        <div className="brand-subtitle">with Atria reassessment</div>
                    </div>
                </div>

                <div className="nav-label">WORKSPACE</div>
                {nav("intake", "＋", "Patient intake")}
                {nav("queue", "▤", "ER dashboard", queue?.waiting ?? 0)}
                {nav("ask", "✦", "Ask Atria", queue?.flagged || undefined)}

                <div className="nav-label nav-label-spaced">DEMO</div>
                <a className="nav-item" href={REPLAY_URL} target="_blank" rel="noreferrer">
                    <span className="nav-icon">▶</span>
                    Scripted replay ↗
                </a>

                <div className="sidebar-bottom">
                    <div className={`sidebar-indicator ${error ? "offline" : ""}`} />
                    <div>
                        <strong>{error ? "Backend offline" : "Connected to Atria"}</strong>
                        <span>Made-up demo patients only</span>
                    </div>
                </div>
            </aside>

            <section className="main-panel">
                <header className="topbar">
                    <div className="breadcrumb">
                        Workspace <span>/</span> {CRUMBS[activeTab]}
                    </div>
                    <div className="top-status">
                        <span className={`status-dot ${error ? "offline" : ""}`} />
                        {error ? "Reconnecting…" : "Live"}
                    </div>
                </header>

                <div className="content">
                    <div className="safety-banner">
                        <span className="safety-icon">ⓘ</span>
                        <div>
                            <strong>Human review required</strong>
                            <p>
                                This prototype does not diagnose patients or determine clinical priority. Staff assign
                                priority; Atria only flags change since check-in for a nurse to review.
                            </p>
                        </div>
                    </div>

                    {activeTab === "intake" && <PatientIntake />}
                    {activeTab === "queue" && (
                        <ERAdminDashboard
                            queue={queue}
                            error={error}
                            refresh={refresh}
                            onGoToIntake={() => setActiveTab("intake")}
                            onAsk={askAbout}
                        />
                    )}
                    {activeTab === "ask" && (
                        <AskAtria queue={queue} patientId={askPatient} onPatientChange={setAskPatient} />
                    )}

                    <footer>
                        <span>ER Priority + Atria · Hackathon prototype</span>
                        <span>Not for clinical use</span>
                    </footer>
                </div>
            </section>
        </main>
    );
}
