"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NurseProvider, useNurse } from "../../lib/nurse";

const NAV = [
    { href: "/nurse", icon: "▤", label: "Waiting room" },
    { href: "/nurse/ask", icon: "✦", label: "Ask Atria" },
    { href: "/nurse/intake", icon: "＋", label: "Front-desk check-in" },
    { href: "/nurse/trends", icon: "∿", label: "Vitals trends" },
];

const CRUMBS: Record<string, string> = {
    "/nurse": "Waiting room",
    "/nurse/ask": "Ask Atria",
    "/nurse/intake": "Front-desk check-in",
    "/nurse/trends": "Vitals trends",
};

function Shell({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const { queue, error } = useNurse();
    const count = (href: string) =>
        href === "/nurse" ? queue?.waiting : href === "/nurse/ask" ? queue?.alerts || undefined : undefined;

    return (
        <main className="app-shell">
            <aside className="sidebar">
                <Link href="/" className="brand brand-link">
                    <div className="brand-mark">+</div>
                    <div>
                        <div className="brand-name">ER Priority</div>
                        <div className="brand-subtitle">Nurse station</div>
                    </div>
                </Link>

                <div className="nav-label">NURSE STATION</div>
                {NAV.map((item) => {
                    const n = count(item.href);
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`nav-item ${pathname === item.href ? "active" : ""}`}
                        >
                            <span className="nav-icon">{item.icon}</span>
                            {item.label}
                            {n !== undefined && <span className="nav-count">{n}</span>}
                        </Link>
                    );
                })}

                <div className="sidebar-bottom">
                    <div className={`sidebar-indicator ${error ? "offline" : ""}`} />
                    <div>
                        <strong>{error ? "Connection lost" : "Live"}</strong>
                        <span>Made-up demo patients only</span>
                    </div>
                </div>
            </aside>

            <section className="main-panel">
                <header className="topbar">
                    <div className="breadcrumb">
                        Nurse station <span>/</span> {CRUMBS[pathname] ?? ""}
                    </div>
                    <div className="top-status">
                        <span className={`status-dot ${error ? "offline" : ""}`} />
                        {error ? "Reconnecting…" : "Updating every 3 s"}
                    </div>
                </header>

                <div className="content">
                    <div className="safety-banner">
                        <span className="safety-icon">ⓘ</span>
                        <div>
                            <strong>Human review required</strong>
                            <p>
                                This prototype does not diagnose patients or determine clinical priority. Nurses assign
                                priority; Atria only flags change since check-in for a nurse to review.
                            </p>
                        </div>
                    </div>

                    {children}

                    <footer>
                        <span>ER Priority with Atria · Hackathon prototype</span>
                        <span>Not for clinical use</span>
                    </footer>
                </div>
            </section>
        </main>
    );
}

export default function NurseLayout({ children }: { children: React.ReactNode }) {
    return (
        <NurseProvider>
            <Shell>{children}</Shell>
        </NurseProvider>
    );
}
