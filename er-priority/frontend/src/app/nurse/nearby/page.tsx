"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "../../../lib/api";
import type { Facility, NearbyData } from "../../../types";

type Kind = "all" | "trauma" | "hospital" | "freestanding";

// Where distances are measured from. Downtown Raleigh unless the nurse picks a facility.
const DOWNTOWN = { name: "Downtown Raleigh", lat: 35.7796, lon: -78.6382 };
const RANGES = [10, 25, 50, 0];

function miles(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
    const r = 3958.8;
    const rad = (d: number) => (d * Math.PI) / 180;
    const dLat = rad(b.lat - a.lat);
    const dLon = rad(b.lon - a.lon);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
    return 2 * r * Math.asin(Math.sqrt(h));
}

const isTrauma = (f: Facility) => f.services.toLowerCase().includes("trauma");
const isFreestanding = (f: Facility) => f.facility_type !== "Hospital";

function kindLabel(f: Facility) {
    if (isTrauma(f)) return { label: "Trauma center", cls: "priority-high" };
    if (isFreestanding(f)) return { label: "Freestanding ER", cls: "priority-medium" };
    return { label: "Hospital ER", cls: "priority-low" };
}

export default function NearbyErsPage() {
    const [data, setData] = useState<NearbyData | null>(null);
    const [error, setError] = useState("");
    const [origin, setOrigin] = useState("");
    const [kind, setKind] = useState<Kind>("all");
    const [range, setRange] = useState(25);
    const [search, setSearch] = useState("");
    const [copied, setCopied] = useState("");

    useEffect(() => {
        const first = setTimeout(
            () => api.nearby().then(setData).catch((e) => setError((e as Error).message)),
            0
        );
        return () => clearTimeout(first);
    }, []);

    const facilities = useMemo(() => data?.facilities ?? [], [data]);
    const from = facilities.find((f) => f.name === origin) ?? DOWNTOWN;

    const withDistance = useMemo(
        () =>
            facilities
                .filter((f) => f.name !== origin)
                .map((f) => ({ ...f, distance: miles(from, f) }))
                .sort((a, b) => a.distance - b.distance),
        [facilities, from, origin]
    );

    const rows = useMemo(() => {
        const term = search.trim().toLowerCase();
        return withDistance.filter(
            (f) =>
                (kind === "all" ||
                    (kind === "trauma" && isTrauma(f)) ||
                    (kind === "hospital" && !isFreestanding(f) && !isTrauma(f)) ||
                    (kind === "freestanding" && isFreestanding(f))) &&
                (range === 0 || f.distance <= range) &&
                (!term || [f.name, f.city, f.county, f.address].join(" ").toLowerCase().includes(term))
        );
    }, [withDistance, kind, range, search]);

    const within15 = withDistance.filter((f) => f.distance <= 15).length;
    const nearestTrauma = withDistance.find(isTrauma);
    const nearest = withDistance[0];

    async function copy(f: Facility) {
        const text = `${f.name}, ${f.address}, ${f.city}, NC`;
        try {
            await navigator.clipboard.writeText(text);
            setCopied(f.name);
            setTimeout(() => setCopied(""), 1500);
        } catch {
            window.prompt("Copy address", text);
        }
    }

    return (
        <section className="dashboard-main">
            <div className="dashboard-title-row">
                <div>
                    <p className="eyebrow">TRANSFERS</p>
                    <h1>Nearby ERs</h1>
                    <p className="dashboard-subtitle">
                        When a patient needs a trauma center or a service you don&apos;t have, find the closest
                        emergency department and send directions.
                    </p>
                </div>
                <label className="form-field nearby-origin">
                    <span>Measure distance from</span>
                    <select className="priority-select" value={origin} onChange={(e) => setOrigin(e.target.value)}>
                        <option value="">{DOWNTOWN.name}</option>
                        {facilities.map((f) => (
                            <option key={f.name} value={f.name}>
                                {f.name}
                            </option>
                        ))}
                    </select>
                </label>
            </div>

            <div className="dashboard-stats stats-four">
                <div className="dashboard-stat stat-total">
                    <span>Emergency departments</span>
                    <strong>{data ? facilities.length : "–"}</strong>
                    <small>Wake County and surrounding</small>
                </div>
                <div className="dashboard-stat stat-reviewed">
                    <span>Within 15 miles</span>
                    <strong>{data ? within15 : "–"}</strong>
                    <small>Straight-line distance</small>
                </div>
                <div className="dashboard-stat stat-flagged">
                    <span>Nearest trauma center</span>
                    <strong>{nearestTrauma ? `${nearestTrauma.distance.toFixed(1)} mi` : "–"}</strong>
                    <small>{nearestTrauma?.name ?? "Loading…"}</small>
                </div>
                <div className="dashboard-stat stat-pending">
                    <span>Closest ER</span>
                    <strong>{nearest ? `${nearest.distance.toFixed(1)} mi` : "–"}</strong>
                    <small>{nearest?.name ?? "Loading…"}</small>
                </div>
            </div>

            {error && <p className="form-error">Couldn&apos;t load facilities: {error}</p>}

            <section className="dashboard-section">
                <div className="section-heading queue-heading">
                    <div>
                        <h2>Emergency departments by distance</h2>
                        <p>From {from.name}. Call ahead to confirm they can take the patient.</p>
                    </div>
                    <span className="patient-count">
                        {rows.length} of {withDistance.length}
                    </span>
                </div>

                <div className="queue-toolbar">
                    <div className="queue-filters" aria-label="Facility type">
                        {(
                            [
                                ["all", "All"],
                                ["trauma", "Trauma centers"],
                                ["hospital", "Hospital ERs"],
                                ["freestanding", "Freestanding ERs"],
                            ] as [Kind, string][]
                        ).map(([key, label]) => (
                            <button
                                key={key}
                                type="button"
                                className={`queue-filter ${kind === key ? "selected" : ""}`}
                                onClick={() => setKind(key)}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                    <div className="toolbar-right">
                        <div className="queue-filters" aria-label="Distance">
                            {RANGES.map((r) => (
                                <button
                                    key={r}
                                    type="button"
                                    className={`queue-filter ${range === r ? "selected" : ""}`}
                                    onClick={() => setRange(r)}
                                >
                                    {r ? `${r} mi` : "Any distance"}
                                </button>
                            ))}
                        </div>
                        <input
                            className="queue-search"
                            type="search"
                            placeholder="Search name, city, county..."
                            aria-label="Search facilities"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                </div>

                <div className="priority-legend">
                    <span><i className="legend-dot dot-high" /> Trauma center</span>
                    <span><i className="legend-dot dot-low" /> Hospital ER</span>
                    <span><i className="legend-dot dot-medium" /> Freestanding ER</span>
                </div>

                {!data && !error ? (
                    <div className="empty-state"><p>Loading emergency departments…</p></div>
                ) : rows.length === 0 ? (
                    <div className="empty-state">
                        <h3>No matching emergency departments</h3>
                        <p>Widen the distance or clear the search.</p>
                        <button type="button" className="secondary-button" onClick={() => { setRange(0); setKind("all"); setSearch(""); }}>
                            Show all
                        </button>
                    </div>
                ) : (
                    <div className="patient-table-wrap">
                        <table className="patient-table">
                            <thead>
                                <tr>
                                    <th>Distance</th>
                                    <th>Emergency department</th>
                                    <th>Type</th>
                                    <th>Address</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((f) => {
                                    const k = kindLabel(f);
                                    return (
                                        <tr key={f.name} className={k.cls}>
                                            <td className="position-cell">
                                                <strong>{f.distance.toFixed(1)}</strong>
                                                <span className="dashboard-patient">miles</span>
                                            </td>
                                            <td>
                                                <strong className="patient-name">{f.name}</strong>
                                                <span className="dashboard-patient">{f.county} County</span>
                                            </td>
                                            <td>
                                                <span className={`priority-badge ${k.cls}`}>{k.label}</span>
                                                <span className="dashboard-patient">{f.services}</span>
                                            </td>
                                            <td>
                                                <span className="vitals-line">{f.address}</span>
                                                <span className="dashboard-patient">{f.city}, NC</span>
                                            </td>
                                            <td className="action-cell">
                                                <a
                                                    className="secondary-button"
                                                    href={`https://www.google.com/maps/dir/?api=1&destination=${f.lat},${f.lon}`}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                >
                                                    Directions
                                                </a>
                                                <button type="button" className="link-button" onClick={() => copy(f)}>
                                                    {copied === f.name ? "Copied" : "Copy address"}
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>

            <p className="form-disclaimer">
                Facility list from {data?.source.publisher ?? "Wake County GIS"} open data (
                {data?.source.dataset ?? "Hospitals, Wake County and Surrounding"}), last updated{" "}
                {data?.source.source_last_edited ?? "2025-08-18"}. It lists locations and services only, not live
                capacity or wait times.
            </p>
        </section>
    );
}
