"use client";

import { useRouter } from "next/navigation";
import ERAdminDashboard from "../../components/ERAdminDashboard";
import SampleControls from "../../components/SampleControls";
import { useNurse } from "../../lib/nurse";

export default function NurseWaitingRoomPage() {
    const router = useRouter();
    const { queue, error, refresh } = useNurse();
    return (
        <>
            <SampleControls refresh={refresh} />
            <ERAdminDashboard
                queue={queue}
                error={error}
                refresh={refresh}
                onGoToIntake={() => router.push("/nurse/intake")}
                onAsk={(p) => router.push(`/nurse/ask?patient=${p.id}`)}
            />
        </>
    );
}
