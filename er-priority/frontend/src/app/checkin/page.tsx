import PatientIntake from "../../components/PatientIntake";
import Link from "next/link";

// Patient-facing check-in (open on a phone or from a QR code). No staff navigation.
export default function PatientCheckInPage() {
    return (
        <main className="patient-shell patient-checkin">
            <Link href="/" className="patient-brand brand-link">
                <div className="brand-mark">+</div>
                <div>
                    <div className="patient-brand-name">ER Priority</div>
                    <div className="dashboard-patient">Waiting room check-in</div>
                </div>
            </Link>
            <div className="content">
                <PatientIntake />
            </div>
        </main>
    );
}
