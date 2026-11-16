"use client";

import {useState} from "react";
import {useRouter} from "next/navigation";
import {api} from "../lib/api";

const SYMPTOMS = [
    "Chest pain",
    "Shortness of breath",
    "Fever",
    "Headache",
    "Dizziness",
    "Nausea/vomiting",
    "Abdominal pain",
    "Weakness",
    "Bleeding",
    "Injury/fall",
    "Cough",
    "Other",
];

const PAIN_WORDS = ["No pain", "Mild", "Mild", "Mild", "Moderate", "Moderate", "Moderate", "Severe", "Severe", "Severe", "Worst possible"];

function painTier(n: number) {
    return n <= 3 ? "pain-low" : n <= 6 ? "pain-mid" : "pain-high";
}

type PatientIntakeProps = {
    // "staff": front desk checking someone in; "patient": the patient on their own phone.
    variant?: "staff" | "patient";
};

export default function PatientIntake({variant = "patient"}: PatientIntakeProps) {
    const router = useRouter();
    const staff = variant === "staff";
    const [name, setName] = useState("");
    const [dateOfBirth, setDateOfBirth] = useState("");
    const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
    const [notes, setNotes] = useState("");
    const [pain, setPain] = useState("");
    const [message, setMessage] = useState("");
    const [submitting, setSubmitting] = useState(false);

    function toggleSymptom(symptom: string) {
        setSelectedSymptoms((current) =>
            current.includes(symptom)
                ? current.filter((item) => item !== symptom)
                : [...current, symptom]
        );
    }

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (selectedSymptoms.length === 0) {
            setMessage("Select at least one symptom.");
            return;
        }

        setSubmitting(true);
        setMessage("");
        try {
            const {id} = await api.checkIn({
                name: name.trim(),
                date_of_birth: dateOfBirth || null,
                symptoms: selectedSymptoms,
                notes: notes.trim(),
                pain: pain === "" ? null : Number(pain),
            });
            // The patient lands on their own place-in-line page.
            router.push(`/status/${id}`);
        } catch (error) {
            setMessage(`Check-in failed: ${(error as Error).message}. Please tell the front desk.`);
            setSubmitting(false);
        }
    }

    const painValue = pain === "" ? null : Number(pain);

    return (
        <div className="intake-layout">
            <section className="intake-main">
                <div className="page-heading">
                    <div>
                        <p className="eyebrow">{staff ? "FRONT DESK" : "EMERGENCY CHECK-IN"}</p>
                        <h1>{staff ? "Check in a patient" : "Check in"}</h1>
                        <p>
                            {staff
                                ? "Takes under a minute. The patient joins the waiting room and gets a ticket to follow their place in line."
                                : "Tell us how you're feeling. You'll get a ticket and can follow your place in line from your phone."}
                        </p>
                    </div>
                </div>

                <form className="intake-form" onSubmit={handleSubmit}>
                    <div className="form-section">
                        <h2><span className="step-num">1</span>{staff ? "Patient" : "About you"}</h2>
                        <div className="form-grid">
                            <label className="form-field">
                                <span>Full name</span>
                                <input
                                    type="text"
                                    value={name}
                                    onChange={(event) => setName(event.target.value)}
                                    placeholder="First and last name"
                                    autoComplete="name"
                                    required
                                />
                            </label>

                            <label className="form-field">
                                <span>Date of birth</span>
                                <input
                                    type="date"
                                    value={dateOfBirth}
                                    onChange={(event) => setDateOfBirth(event.target.value)}
                                    max={new Date().toISOString().split("T")[0]}
                                    required
                                />
                            </label>
                        </div>
                    </div>

                    <div className="form-section">
                        <div className="section-row">
                            <h2><span className="step-num">2</span>Symptoms</h2>
                            <span className="section-count">
                                {selectedSymptoms.length ? `${selectedSymptoms.length} selected` : "Select all that apply"}
                            </span>
                        </div>
                        <div className="symptom-grid">
                            {SYMPTOMS.map((symptom) => (
                                <label className="symptom-option" key={symptom}>
                                    <input
                                        type="checkbox"
                                        checked={selectedSymptoms.includes(symptom)}
                                        onChange={() => toggleSymptom(symptom)}
                                    />
                                    <span>{symptom}</span>
                                </label>
                            ))}
                        </div>
                    </div>

                    <div className="form-section">
                        <div className="section-row">
                            <h2><span className="step-num">3</span>Pain right now</h2>
                            <span className={`section-count ${painValue !== null ? painTier(painValue) : ""}`}>
                                {painValue !== null ? `${painValue}/10 · ${PAIN_WORDS[painValue]}` : "0 to 10"}
                            </span>
                        </div>
                        <div className="pain-scale" role="radiogroup" aria-label="Pain score">
                            {Array.from({length: 11}, (_, n) => (
                                <label key={n} className={`pain-option ${pain === String(n) ? `selected ${painTier(n)}` : ""}`}>
                                    <input
                                        type="radio"
                                        name="pain"
                                        value={n}
                                        checked={pain === String(n)}
                                        onChange={() => setPain(String(n))}
                                    />
                                    <span>{n}</span>
                                </label>
                            ))}
                        </div>
                        <div className="pain-ends">
                            <span>0: No pain</span>
                            <span>4 to 6: Moderate</span>
                            <span>10: Worst possible</span>
                        </div>
                    </div>

                    <div className="form-section">
                        <h2><span className="step-num">4</span>Anything else?</h2>
                        <label className="form-field">
                            <span className="sr-only">Notes</span>
                            <textarea
                                value={notes}
                                onChange={(event) => setNotes(event.target.value)}
                                placeholder={staff ? "When it started, medications, allergies…" : "When it started, medications, allergies… (optional)"}
                                rows={3}
                            />
                        </label>
                    </div>

                    {message && (
                        <p role="status" className="intake-message">
                            {message}
                        </p>
                    )}

                    <div className="submit-row">
                        <p className="form-disclaimer">
                            A nurse reviews every check-in and sets priority. Nothing here is a diagnosis.
                        </p>
                        <button type="submit" className="primary-button" disabled={submitting}>
                            {submitting ? "Checking in…" : staff ? "Check in patient" : "Check in"}
                        </button>
                    </div>
                </form>
            </section>
        </div>
    );
}
