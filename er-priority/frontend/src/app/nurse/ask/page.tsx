import AskWorkspace from "@/components/AskWorkspace";

export default async function NurseAskPage({ searchParams }: {
  searchParams: Promise<{ patient?: string | string[] }>;
}) {
  const { patient } = await searchParams;
  return <AskWorkspace patientId={typeof patient === "string" ? patient : ""} />;
}
