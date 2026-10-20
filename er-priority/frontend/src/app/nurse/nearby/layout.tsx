import type { Metadata } from "next";

export const metadata: Metadata = {"title": "Nearby emergency departments", "description": "Explore the emergency department directory used in the Atria prototype."};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
