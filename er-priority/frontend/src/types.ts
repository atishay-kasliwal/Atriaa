
export type Priority =
    | "Priority 1 — High"
    | "Priority 2 — Medium"
    | "Priority 3 — Low";

export type PatientCase = {
    id: string;
    name: string;
    dateOfBirth: string;
    symptoms: string[];
    notes: string;
    submittedAt: string;
    priority: Priority | "";
    status: "Awaiting human review" | "Priority assigned";
};

export const PRIORITIES: Priority[] = [
    "Priority 1 — High",
    "Priority 2 — Medium",
    "Priority 3 — Low",
];
