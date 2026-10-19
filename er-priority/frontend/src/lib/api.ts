import type { AskAnswer, BedBoard, CheckInStatus, LiveQueue, NearbyData, PriorityLevel, SampleState } from "../types";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`/api${path}`, {
        ...init,
        headers: { "content-type": "application/json", ...init?.headers },
        cache: "no-store",
    });
    if (!res.ok) {
        let detail = `${res.status}`;
        try {
            const body = await res.json();
            detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        } catch {
            // keep the status code
        }
        throw new Error(detail);
    }
    return res.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown) =>
    call<T>(path, { method: "POST", body: JSON.stringify(body) });

const STAFF = { actor: "Charge nurse" };

export const api = {
    checkIn: (body: {
        name: string;
        date_of_birth: string | null;
        symptoms: string[];
        notes: string;
        pain: number | null;
    }) => post<{ id: string; ticket: string }>("/checkin", body),
    status: (id: string) => call<CheckInStatus>(`/checkin/${id}`),
    report: (id: string, body: { pain?: number; feeling?: "worse" | "same" | "better" }) =>
        post<CheckInStatus>(`/checkin/${id}/report`, body),

    queue: () => call<LiveQueue>("/live/queue"),
    setPriority: (id: string, priority: PriorityLevel | null) =>
        post(`/live/${id}/priority`, { priority }),
    recordVitals: (id: string, body: { hr?: number; spo2?: number; pain?: number }) =>
        post(`/live/${id}/vitals`, body),
    requestReassessment: (id: string) =>
        post(`/live/${id}/reassess`, { ...STAFF, reason: "Atria flagged change since check-in" }),
    acknowledge: (id: string, priority?: PriorityLevel) =>
        post(`/live/${id}/acknowledge`, { ...STAFF, priority: priority ?? null }),
    callIn: (id: string) => post(`/live/${id}/call`, STAFF),
    assignBed: (id: string, bed?: string) => post(`/live/${id}/bed`, { ...STAFF, bed: bed ?? null }),
    discharge: (bed: string) => post<BedBoard>(`/live/beds/${encodeURIComponent(bed)}/discharge`, STAFF),
    loadRush: () => post<BedBoard>("/live/rush/load", {}),
    ask: (question: string, checkinId?: string) =>
        post<AskAnswer>("/live/ask", { question, checkin_id: checkinId || null }),
    reset: () => post<{ removed: number }>("/live/reset", {}),

    nearby: () => call<NearbyData>("/raleigh/overview"),
    sampleState: () => call<SampleState>("/live/sample"),
    loadSample: () => post<SampleState>("/live/sample/load", {}),
    sampleNext: () => post<SampleState>("/live/sample/next", {}),
};

export function since(iso: string | null | undefined): string {
    if (!iso) return "—";
    const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
    return mins < 1 ? "just now" : `${mins} min ago`;
}

export function clock(iso: string | null | undefined): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
