import PatientIntake from "../../components/PatientIntake";

// Patient-facing check-in (open on a phone or from a QR code). No staff navigation.
export default function PatientCheckInPage() {
    return (
        <main className="patient-shell patient-checkin">
            <div className="patient-brand">
                <div className="brand-mark">+</div>
                <div>
                    <div className="patient-brand-name">ER Priority</div>
                    <div className="dashboard-patient">Waiting room check-in</div>
                </div>
            </div>
            <div className="content">
                <PatientIntake />
            </div>
        </main>
    );
}
