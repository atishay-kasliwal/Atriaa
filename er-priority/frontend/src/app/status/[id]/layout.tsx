import type { Metadata } from "next";

export const metadata: Metadata = {"title": "Your check-in", "description": "Follow your Atria demo ticket and send an update to staff."};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
