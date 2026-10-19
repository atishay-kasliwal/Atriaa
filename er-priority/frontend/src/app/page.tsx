import Link from "next/link";

const STEPS = [
    { n: "1", title: "Patient checks in", body: "On their phone or at the front desk: symptoms and a pain score." },
    { n: "2", title: "Nurse sets priority", body: "Priority 1–3 is always a human decision. The patient sees their place in line." },
    { n: "3", title: "Atria watches the wait", body: "Re-checks and the patient's own updates. Atria flags anyone who worsens on every reading." },
    { n: "4", title: "Nurse acts", body: "Request a re-check, acknowledge the alert, raise priority. The patient's phone updates." },
];

export default function Home() {
    return (
        <main className="home">
            <header className="home-top">
                <div className="patient-brand">
                    <div className="brand-mark">+</div>
                    <div>
                        <div className="patient-brand-name">ER Priority</div>
                        <div className="dashboard-patient">with Atria reassessment</div>
                    </div>
                </div>
            </header>

            <section className="home-hero">
                <p className="eyebrow">EMERGENCY WAITING ROOM</p>
                <h1>See who&apos;s getting worse while they wait.</h1>
                <p>
                    Triage happens once, at the door. Atria keeps watching after that, so a patient whose readings
                    slowly worsen doesn&apos;t get lost behind people who arrived sicker.
                </p>
            </section>

            <section className="home-roles">
                <Link href="/checkin" className="role-card">
                    <span className="role-icon">＋</span>
                    <strong>I&apos;m a patient</strong>
                    <span>Check in, see your place in line, and tell staff if you feel worse.</span>
                    <em>Check in →</em>
                </Link>
                <Link href="/nurse" className="role-card role-card-dark">
                    <span className="role-icon">▤</span>
                    <strong>Nurse station</strong>
                    <span>Set priority, record re-checks, act on Atria alerts, and ask Atria why.</span>
                    <em>Open the waiting room →</em>
                </Link>
            </section>

            <section className="home-steps">
                {STEPS.map((s) => (
                    <div className="home-step" key={s.n}>
                        <span>{s.n}</span>
                        <strong>{s.title}</strong>
                        <p>{s.body}</p>
                    </div>
                ))}
            </section>

            <p className="form-disclaimer home-foot">
                Not a medical device. Atria never diagnoses, changes priority or decides treatment. A nurse does.
            </p>
        </main>
    );
}
