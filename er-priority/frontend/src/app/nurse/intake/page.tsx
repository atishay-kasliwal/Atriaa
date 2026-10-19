"use client";

import PatientIntake from "../../../components/PatientIntake";
import { useNurse } from "../../../lib/nurse";

// Front desk checks in a walk-in on the patient's behalf. Same form and flow as /checkin.
export default function NurseIntakePage() {
    const { queue } = useNurse();
    return (
        <div className="intake-page">
            <PatientIntake variant="staff" />
            <aside className="intake-side">
                <section className="dashboard-section side-card">
                    <p className="eyebrow">WAITING ROOM NOW</p>
                    <div className="side-stats">
                        <div><strong>{queue?.waiting ?? "–"}</strong><span>Waiting</span></div>
                        <div><strong className="tone-amber">{queue?.awaiting_triage ?? "–"}</strong><span>Need triage</span></div>
                        <div><strong className="tone-red">{queue?.alerts ?? "–"}</strong><span>Atria alerts</span></div>
                    </div>
                </section>
                <section className="dashboard-section side-card">
                    <p className="eyebrow">AFTER CHECK-IN</p>
                    <ol className="side-steps">
                        <li><strong>Ticket issued</strong><span>The patient gets a ticket number and a page to follow their place in line.</span></li>
                        <li><strong>Nurse sets priority</strong><span>The patient shows as &ldquo;Needs triage&rdquo; on the waiting room until a nurse reviews them.</span></li>
                        <li><strong>Atria keeps watching</strong><span>Re-checks and the patient&apos;s own updates are compared to this first reading.</span></li>
                    </ol>
                </section>
            </aside>
        </div>
    );
}
