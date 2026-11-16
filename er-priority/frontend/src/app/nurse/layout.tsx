import type { Metadata } from "next";
import NurseShell from "@/components/NurseShell";

export const metadata: Metadata = {
  title: "Nurse station",
  description: "Review the synthetic waiting room, record re-checks, and manage reassessment alerts in the Atria prototype.",
};

export default function NurseLayout({ children }: { children: React.ReactNode }) {
  return <NurseShell>{children}</NurseShell>;
}
