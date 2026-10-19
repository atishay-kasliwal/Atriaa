export type PriorityLevel = 1 | 2 | 3;

export const PRIORITY_LABELS: Record<PriorityLevel, string> = {
    1: "Priority 1 — High",
    2: "Priority 2 — Medium",
    3: "Priority 3 — Low",
};

export const PRIORITIES: PriorityLevel[] = [1, 2, 3];

export type Trajectory =
    | "persistent_change"
    | "mixed_change"
    | "transient_change"
    | "stable"
    | "insufficient_data";

export type Readings = {
    hr: number | null;
    spo2: number | null;
    pain: number | null;
    observed_at: string | null;
};

// One waiting patient on the staff dashboard (GET /live/queue).
export type LivePatient = {
    id: string;
    ticket: string;
    name: string;
    date_of_birth: string | null;
    symptoms: string[];
    notes: string | null;
    priority: PriorityLevel | null;
    line_position: number | null;
    attention_position: number;
    checked_in_at: string;
    waiting_minutes: number;
    reassessment_requested_at: string | null;
    trajectory: Trajectory;
    reassessment_signal: boolean;
    consensus: string;
    reasons: string[];
    ordering_reason: string;
    intake: Readings;
    current: Readings;
    deltas: { hr: number | null; spo2: number | null; pain: number | null };
    readings: number;
};

export type LiveQueue = {
    queue: LivePatient[];
    as_of: string;
    queue_version: string;
    waiting: number;
    awaiting_triage: number;
    flagged: number;
};

// What a patient sees after checking in (GET /checkin/{id}).
export type CheckInStatus = {
    id: string;
    ticket: string;
    name: string;
    symptoms: string[];
    checked_in_at: string;
    waited_minutes: number;
    status: "waiting" | "called";
    stage: "awaiting_triage" | "waiting" | "recheck_requested" | "called";
    line_position?: number | null;
    ahead?: number | null;
    line?: { ticket: string; you: boolean }[];
    awaiting_triage_count?: number;
    total_waiting?: number;
    last_update?: string | null;
};

export type AskAnswer = {
    answer: string;
    provider: "gemini" | "fallback";
    model: string | null;
    queue_version: string;
    as_of: string;
    notice?: string;
};
