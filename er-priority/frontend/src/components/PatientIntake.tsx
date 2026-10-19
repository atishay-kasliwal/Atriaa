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

export default function PatientIntake() {
    const router = useRouter();
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
            setMessage("Please select at least one symptom.");
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

    return (
        <div className="intake-layout">
            <section className="intake-main">
                <div className="page-heading">
                    <div>
                        <p className="eyebrow">PATIENT REGISTRATION</p>
                        <h1>Patient Intake</h1>
                        <p>Enter patient details and symptoms for human review.</p>
                    </div>
                </div>

                <form className="intake-form" onSubmit={handleSubmit}>
                    <div className="form-section">
                        <h2>Patient Information</h2>

                        <div className="form-grid">
                            <label className="form-field">
                                <span>Full name</span>
                                <input
                                    type="text"
                                    value={name}
                                    onChange={(event) => setName(event.target.value)}
                                    placeholder="Enter patient's full name"
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
                        <h2>Symptoms</h2>
                        <p className="section-description">
                            Select all symptoms reported by the patient.
                        </p>

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
                        <h2>Pain right now</h2>
                        <p className="section-description">
                            0 means no pain, 10 means the worst pain you can imagine.
                        </p>
                        <div className="pain-scale" role="radiogroup" aria-label="Pain score">
                            {Array.from({length: 11}, (_, n) => (
                                <label key={n} className={`pain-option ${pain === String(n) ? "selected" : ""}`}>
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
                    </div>

                    <div className="form-section">
                        <label className="form-field">
                            <span>Additional notes</span>
                            <textarea
                                value={notes}
                                onChange={(event) => setNotes(event.target.value)}
                                placeholder="Optional: relevant details reported by the patient"
                                rows={4}
                            />
                        </label>
                    </div>

                    {message && (
                        <p role="status" className="intake-message">
                            {message}
                        </p>
                    )}

                    <button type="submit" className="primary-button" disabled={submitting}>
                        {submitting ? "Checking in..." : "Check In Patient"}
                    </button>

                    <p className="form-disclaimer">
                        This demo records reported information only. A qualified human
                        reviewer must assess the patient and assign priority. After check-in
                        you&apos;ll see your place in line and can tell staff if you feel worse.
                    </p>
                </form>
            </section>
        </div>
    );
}
