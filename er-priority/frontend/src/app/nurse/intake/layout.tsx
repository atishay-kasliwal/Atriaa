import type { Metadata } from "next";

export const metadata: Metadata = {"title": "Front-desk check-in", "description": "Enter a synthetic patient into the Atria waiting room on their behalf."};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
