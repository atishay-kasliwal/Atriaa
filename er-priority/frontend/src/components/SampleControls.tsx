"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { SampleState } from "../types";

const PLAY_EVERY_MS = 2500;

// Demo controls: fill the waiting room with 8 fictional patients and feed in their
// scripted readings, using the same pages a real check-in uses.
export default function SampleControls({ refresh }: { refresh: () => Promise<void> }) {
    const [state, setState] = useState<SampleState | null>(null);
    const [playing, setPlaying] = useState(false);
    const [error, setError] = useState("");
    const busy = useRef(false);

    const run = useCallback(
        async (fn: () => Promise<SampleState>) => {
            if (busy.current) return;
            busy.current = true;
            try {
                const next = await fn();
                setState(next);
                setError("");
                if (next.done) setPlaying(false);
                await refresh();
            } catch (e) {
                setError((e as Error).message);
                setPlaying(false);
            } finally {
                busy.current = false;
            }
        },
        [refresh]
    );

    useEffect(() => {
        const first = setTimeout(() => api.sampleState().then(setState).catch(() => undefined), 0);
        return () => clearTimeout(first);
    }, []);

    useEffect(() => {
        if (!playing) return;
        const timer = setInterval(() => run(api.sampleNext), PLAY_EVERY_MS);
        return () => clearInterval(timer);
    }, [playing, run]);

    function load() {
        if (!window.confirm("Replace the current waiting room with the 8-patient sample?")) return;
        setPlaying(false);
        run(api.loadSample);
    }

    async function loadRush() {
        if (!window.confirm("Replace the waiting room with the ER rush: 6 beds full and 10 new arrivals?")) return;
        setPlaying(false);
        try {
            await api.loadRush();
            setState(await api.sampleState());
            setError("");
            await refresh();
        } catch (e) {
            setError((e as Error).message);
        }
    }

    const loaded = state?.loaded;
    const pct = state && state.total ? Math.round((state.cursor / state.total) * 100) : 0;

    return (
        <section className="sample-bar" aria-label="Demo controls">
            <div className="sample-copy">
                <span className="sample-tag">DEMO</span>
                <div>
                    <strong>Sample waiting room</strong>
                    <span>
                        {loaded
                            ? `Reading ${state!.cursor} of ${state!.total}${state!.done ? " · finished" : ""}`
                            : "ER rush: 6 beds full, 10 arrivals to approve. Or the 8-patient scripted sample."}
                    </span>
                </div>
            </div>
            {loaded && (
                <div className="sample-progress" aria-hidden>
                    <i style={{ width: `${pct}%` }} />
                </div>
            )}
            <div className="sample-actions">
                <button type="button" className="primary-button" onClick={loadRush}>
                    Load ER rush
                </button>
                <button type="button" className="secondary-button" onClick={load}>
                    {loaded ? "Restart sample" : "Load sample"}
                </button>
                {loaded && !state!.done && (
                    <>
                        <button
                            type="button"
                            className="primary-button"
                            onClick={() => setPlaying(!playing)}
                        >
                            {playing ? "Pause" : "▶ Play"}
                        </button>
                        <button
                            type="button"
                            className="secondary-button"
                            disabled={playing}
                            onClick={() => run(api.sampleNext)}
                        >
                            Next reading
                        </button>
                    </>
                )}
            </div>
            {error && <span className="form-error">{error}</span>}
        </section>
    );
}
