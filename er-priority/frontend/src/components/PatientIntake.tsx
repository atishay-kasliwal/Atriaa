"use client";

import {useState} from "react";
import type {PatientCase} from "../types";

type PatientIntakeProps = {
    onCheckIn: (patient: PatientCase) => void;
};

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

export default function PatientIntake({
                                          onCheckIn,
                                      }: PatientIntakeProps) {
    const [name, setName] = useState("");
    const [dateOfBirth, setDateOfBirth] = useState("");
    const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
    const [notes, setNotes] = useState("");
    const [message, setMessage] = useState("");

    function toggleSymptom(symptom: string) {
        setSelectedSymptoms((current) =>
            current.includes(symptom)
                ? current.filter((item) => item !== symptom)
                : [...current, symptom]
        );
    }

    function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();

        if (selectedSymptoms.length === 0) {
            setMessage("Please select at least one symptom.");
            return;
        }

        const patient: PatientCase = {
            id: `ER-${Date.now().toString().slice(-6)}`,
            name: name.trim(),
            dateOfBirth,
            symptoms: selectedSymptoms,
            notes: notes.trim(),
            submittedAt: new Date().toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
            }),
            priority: "",
            status: "Awaiting human review",
        };

        onCheckIn(patient);

        setName("");
        setDateOfBirth("");
        setSelectedSymptoms([]);
        setNotes("");
        setMessage("Patient checked in successfully.");
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

                    <button type="submit" className="primary-button">
                        Check In Patient
                    </button>

                    <p className="form-disclaimer">
                        This demo records reported information only. A qualified human
                        reviewer must assess the patient and assign priority.
                    </p>
                </form>
            </section>
        </div>
    );
}
