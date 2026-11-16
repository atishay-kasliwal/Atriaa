import type { Metadata } from "next";

export const metadata: Metadata = {"title": "Vitals trends", "description": "Review stored vital sign trends and waiting room history in the Atria prototype."};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
