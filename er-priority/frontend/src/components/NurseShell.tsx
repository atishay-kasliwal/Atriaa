"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NurseProvider, useNurse } from "../lib/nurse";

const NAV = [
    { href: "/nurse", icon: "▤", label: "Waiting room" },
    { href: "/nurse/ask", icon: "✦", label: "Ask Atria" },
    { href: "/nurse/intake", icon: "＋", label: "Front-desk check-in" },
    { href: "/nurse/trends", icon: "∿", label: "Vitals trends" },
    { href: "/nurse/nearby", icon: "⌖", label: "Nearby ERs" },
];

const CRUMBS: Record<string, string> = {
    "/nurse": "Waiting room",
    "/nurse/ask": "Ask Atria",
    "/nurse/intake": "Front-desk check-in",
    "/nurse/trends": "Vitals trends",
    "/nurse/nearby": "Nearby ERs",
};

function Shell({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const { queue, error } = useNurse();
    const connection = error ? "Connection lost" : queue ? "Live" : "Connecting…";
    const count = (href: string) =>
        href === "/nurse" ? queue?.waiting : href === "/nurse/ask" ? queue?.alerts || undefined : undefined;

    return (
        <div className="app-shell">
            <aside className="sidebar">
                <Link href="/" className="brand brand-link">
                    <div className="brand-mark">+</div>
                    <div>
                        <div className="brand-name">Atria</div>
                        <div className="brand-subtitle">Nurse station</div>
                    </div>
                </Link>

                <nav aria-label="Nurse station"><div className="nav-label">NURSE STATION</div>
                {NAV.map((item) => {
                    const n = count(item.href);
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            aria-current={pathname === item.href ? "page" : undefined}
                            className={`nav-item ${pathname === item.href ? "active" : ""}`}
                        >
                            <span className="nav-icon" aria-hidden="true">{item.icon}</span>
                            {item.label}
                            {n !== undefined && <span className="nav-count">{n}</span>}
                        </Link>
                    );
                })}

                </nav><div className="sidebar-bottom">
                    <div className={`sidebar-indicator ${error ? "offline" : !queue ? "connecting" : ""}`} />
                    <div>
                        <strong>{connection}</strong>
                    </div>
                </div>
            </aside>

            <section className="main-panel">
                <header className="topbar">
                    <div className="breadcrumb">
                        Nurse station <span>/</span> {CRUMBS[pathname] ?? ""}
                    </div>
                    <div className="top-status">
                        <span className={`status-dot ${error ? "offline" : !queue ? "connecting" : ""}`} />
                        {connection}
                    </div>
                </header>

                <main id="main" tabIndex={-1} className="content">
                    {children}

                    <footer>
                        <span>Atria prototype</span>
                        <span>Not for clinical use</span>
                    </footer>
                </main>
            </section>
        </div>
    );
}

export default function NurseShell({ children }: { children: React.ReactNode }) {
    return (
        <NurseProvider>
            <Shell>{children}</Shell>
        </NurseProvider>
    );
}
