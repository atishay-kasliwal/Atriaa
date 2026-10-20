import PatientIntake from "../../components/PatientIntake";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "Patient check-in",
    description: "Check into Atria's synthetic waiting room and follow your ticket from your phone.",
};

// Patient-facing check-in (open on a phone or from a QR code). No staff navigation.
export default function PatientCheckInPage() {
    return (
        <main id="main" tabIndex={-1} className="patient-shell patient-checkin">
            <Link href="/" className="patient-brand brand-link">
                <div className="brand-mark">+</div>
                <div>
                    <div className="patient-brand-name">Atria</div>
                    <div className="dashboard-patient">Waiting room check-in</div>
                </div>
            </Link>
            <div className="content">
                <PatientIntake />
            </div>
        </main>
    );
}
