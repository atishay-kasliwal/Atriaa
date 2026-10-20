import type { Metadata } from "next";

export const metadata: Metadata = {"title": "Ask Atria", "description": "Ask for explanations based on the synthetic waiting room and recorded readings."};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
