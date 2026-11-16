"use client";

import { useRouter } from "next/navigation";
import AskAtria from "./AskAtria";
import { useNurse } from "../lib/nurse";

export default function AskWorkspace({ patientId }: { patientId: string }) {
  const router = useRouter();
  const { queue } = useNurse();
  return <AskAtria queue={queue} patientId={patientId}
    onPatientChange={(id) => router.replace(id ? `/nurse/ask?patient=${encodeURIComponent(id)}` : "/nurse/ask")} />;
}
