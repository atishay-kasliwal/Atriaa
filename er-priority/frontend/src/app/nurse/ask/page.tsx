"use client";

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AskAtria from "../../../components/AskAtria";
import { useNurse } from "../../../lib/nurse";

function AskPage() {
    const router = useRouter();
    const params = useSearchParams();
    const { queue } = useNurse();
    const patient = params.get("patient") ?? "";
    return (
        <AskAtria
            queue={queue}
            patientId={patient}
            onPatientChange={(id) => router.replace(id ? `/nurse/ask?patient=${id}` : "/nurse/ask")}
        />
    );
}

export default function NurseAskPage() {
    return (
        <Suspense>
            <AskPage />
        </Suspense>
    );
}
