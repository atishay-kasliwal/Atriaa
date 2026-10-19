"use client";

import { useEffect, useState } from "react";

type Facility = { name: string; services: string; address: string; city: string; county: string; lat: number; lon: number };
type Overview = { facilities: Facility[]; source: { publisher: string; dataset: string; item_url: string; source_last_edited: string } };

// Demo location for "our" ER: downtown Raleigh.
const HERE = { lat: 35.7796, lon: -78.6382 };

function miles(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
    const r = (d: number) => (d * Math.PI) / 180;
    const h =
        Math.sin(r(b.lat - a.lat) / 2) ** 2 +
        Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(r(b.lon - a.lon) / 2) ** 2;
    return 3958.8 * 2 * Math.asin(Math.sqrt(h));
}

// Shown when every bed is taken: the nearest emergency facilities from Wake County's
// public GIS data. The dataset has no live capacity, so staff still call ahead.
export default function NearbyERs() {
    const [data, setData] = useState<Overview | null>(null);
    const [error, setError] = useState("");

    useEffect(() => {
        fetch("/api/raleigh/overview", { cache: "no-store" })
            .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`))))
            .then(setData)
            .catch((e) => setError(e.message));
    }, []);

    if (error) return <p className="form-error">Nearby ER list unavailable: {error}</p>;
    if (!data) return null;
    const nearest = data.facilities
        .filter((f) => /emergency|trauma/i.test(f.services))
        .map((f) => ({ ...f, dist: miles(HERE, f) }))
        .sort((a, b) => a.dist - b.dist)
        .slice(0, 4);

    return (
        <div className="nearby-ers">
            <div className="nearby-head">
                <strong>All beds full · nearest emergency departments</strong>
                <span className="dashboard-patient">
                    Real public data: {data.source.publisher}, &quot;{data.source.dataset}&quot; (updated{" "}
                    {data.source.source_last_edited}). Live capacity isn&apos;t published, so call ahead before
                    diverting.
                </span>
            </div>
            <div className="nearby-grid">
                {nearest.map((f) => (
                    <a
                        key={f.name}
                        className="nearby-card"
                        href={`https://www.google.com/maps/search/?api=1&query=${f.lat},${f.lon}`}
                        target="_blank"
                        rel="noreferrer"
                    >
                        <strong>{f.name}</strong>
                        <span className="dashboard-patient">
                            {f.dist.toFixed(1)} mi · {f.services}
                        </span>
                        <span className="dashboard-patient">
                            {f.address}, {f.city}
                        </span>
                    </a>
                ))}
            </div>
        </div>
    );
}
