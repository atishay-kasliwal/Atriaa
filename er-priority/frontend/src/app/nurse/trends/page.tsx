"use client";

import { useCallback, useEffect, useState } from "react";

type Trend = {
    patient_id: string;
    label: string;
    source: "live" | "replay";
    readings: number;
    hr_first: number | null;
    hr_last: number | null;
    spo2_first: number | null;
    spo2_min: number | null;
    pain_max: number | null;
    hr_series: number[] | null;
};
type Trends = { patients: Trend[]; query_ms: number; source: string };
type Hour = { hour: string; readings: number; hr_avg: number | null; spo2_min: number | null; low_spo2_buckets: number };
type Load = { hours: Hour[]; query_ms: number; source: string };
type Stats = {
    readings: number;
    patients: number;
    since: string | null;
    chunks: number;
    compressed_chunks: number;
    total_bytes: number;
    compression_before_bytes: number | null;
    compression_after_bytes: number | null;
    compression_ratio: number | null;
    query_ms: number;
};

async function get<T>(path: string): Promise<T> {
    const res = await fetch(`/api${path}`, { cache: "no-store" });
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(typeof body.detail === "string" ? body.detail : `${res.status}`);
    }
    return res.json() as Promise<T>;
}

const kib = (b: number | null | undefined) =>
    b == null ? "–" : b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.round(b / 1024)} KB`;

function Spark({ values }: { values: number[] }) {
    if (values.length < 2) return <span className="field-caption">–</span>;
    const lo = Math.min(...values) - 2;
    const hi = Math.max(...values) + 2;
    const pts = values
        .map((v, i) => `${(i / (values.length - 1)) * 96 + 2},${28 - ((v - lo) / (hi - lo)) * 24}`)
        .join(" ");
    const rising = values[values.length - 1] - values[0] >= 10;
    return (
        <svg width="100" height="30" aria-hidden="true">
            <polyline points={pts} fill="none" stroke={rising ? "var(--red)" : "var(--primary)"} strokeWidth="2" />
        </svg>
    );
}

function LoadChart({ hours }: { hours: Hour[] }) {
    if (!hours.length) return <p className="field-caption">No history yet. Run scripts/seed_tiger.py.</p>;
    const max = Math.max(...hours.map((h) => h.readings), 1);
    const w = 100 / hours.length;
    return (
        <svg viewBox="0 0 100 40" preserveAspectRatio="none" style={{ width: "100%", height: 160 }} role="img"
            aria-label="Readings per hour">
            {hours.map((h, i) => (
                <rect key={h.hour} x={i * w} width={Math.max(w - 0.1, 0.05)} y={40 - (h.readings / max) * 38}
                    height={(h.readings / max) * 38}
                    fill={h.low_spo2_buckets > 0 ? "var(--amber)" : "var(--primary)"}>
                    <title>{`${new Date(h.hour).toLocaleString()} · ${h.readings} readings · ${h.low_spo2_buckets} low-SpO2`}</title>
                </rect>
            ))}
        </svg>
    );
}

export default function TrendsPage() {
    const [trends, setTrends] = useState<Trends | null>(null);
    const [load, setLoad] = useState<Load | null>(null);
    const [stats, setStats] = useState<Stats | null>(null);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        try {
            const [t, l, s] = await Promise.all([
                get<Trends>("/tiger/trends?hours=24"),
                get<Load>("/tiger/load?days=7"),
                get<Stats>("/tiger/stats"),
            ]);
            setTrends(t);
            setLoad(l);
            setStats(s);
            setError(null);
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
    }, []);

    useEffect(() => {
        refresh();
        const id = setInterval(refresh, 5000);
        return () => clearInterval(id);
    }, [refresh]);

    return (
        <section className="dashboard-main">
            <div className="dashboard-title-row">
                <div>
                    <p className="eyebrow">TIGER DATA · TIMESCALEDB</p>
                    <h1>Vitals trends</h1>
                    <p className="dashboard-subtitle">
                        Every reading is also written to a Tiger Data hypertable. These views come from continuous
                        aggregates, so they stay fast as history grows.
                    </p>
                </div>
            </div>

            {error && <p className="form-error">{error}</p>}

            <div className="dashboard-stats stats-four">
                <div className="dashboard-stat stat-total">
                    <span>Readings stored</span>
                    <strong>{stats ? stats.readings.toLocaleString() : "–"}</strong>
                    <small>{stats ? `${stats.patients.toLocaleString()} patients` : ""}</small>
                </div>
                <div className="dashboard-stat stat-reviewed">
                    <span>Compression</span>
                    <strong>{stats?.compression_ratio ? `${stats.compression_ratio}×` : "–"}</strong>
                    <small>
                        {kib(stats?.compression_before_bytes)} → {kib(stats?.compression_after_bytes)}
                    </small>
                </div>
                <div className="dashboard-stat stat-pending">
                    <span>Chunks</span>
                    <strong>{stats ? `${stats.compressed_chunks}/${stats.chunks}` : "–"}</strong>
                    <small>compressed / total (1 day each)</small>
                </div>
                <div className="dashboard-stat stat-recheck">
                    <span>Trend query</span>
                    <strong>{trends ? `${trends.query_ms} ms` : "–"}</strong>
                    <small>from {trends?.source ?? "vitals_5m"}</small>
                </div>
            </div>

            <section className="dashboard-section">
                <div className="section-heading">
                    <div>
                        <h2>Who is changing (last 24 h)</h2>
                        <p>Change in heart rate since the first reading, from 5-minute buckets. Largest rise first.</p>
                    </div>
                </div>
                <div className="patient-table-wrap">
                    <table className="patient-table">
                        <thead>
                            <tr>
                                <th>Patient</th>
                                <th>Source</th>
                                <th>Readings</th>
                                <th>HR first → last</th>
                                <th>HR trend</th>
                                <th>SpO2 first → lowest</th>
                                <th>Max pain</th>
                            </tr>
                        </thead>
                        <tbody>
                            {trends?.patients.length ? (
                                trends.patients.map((p) => (
                                    <tr key={`${p.source}:${p.patient_id}`}>
                                        <td className="patient-name">{p.label}</td>
                                        <td>{p.source}</td>
                                        <td>{p.readings}</td>
                                        <td>
                                            {p.hr_first ?? "–"} → {p.hr_last ?? "–"}
                                            {p.hr_first != null && p.hr_last != null && (
                                                <strong> ({p.hr_last - p.hr_first >= 0 ? "+" : ""}
                                                    {Math.round(p.hr_last - p.hr_first)})</strong>
                                            )}
                                        </td>
                                        <td><Spark values={p.hr_series ?? []} /></td>
                                        <td>{p.spo2_first ?? "–"} → {p.spo2_min ?? "–"}%</td>
                                        <td>{p.pain_max ?? "–"}</td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={7} className="empty-state">
                                        No readings yet. Check a patient in or start the replay.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            <section className="dashboard-section">
                <div className="section-heading">
                    <div>
                        <h2>Waiting-room load, last 7 days</h2>
                        <p>
                            Readings per hour from the hourly continuous aggregate (built on the 5-minute one).
                            Amber hours had at least one SpO2 below 92%. {load ? `${load.query_ms} ms.` : ""}
                        </p>
                    </div>
                </div>
                <LoadChart hours={load?.hours ?? []} />
                <p className="form-disclaimer">History is synthetic seed data. Not a medical device.</p>
            </section>
        </section>
    );
}
