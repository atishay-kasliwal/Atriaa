import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Page not found",
  description: "This Atria page could not be found. Return to patient check-in or the nurse station.",
};

export default function NotFound() {
  return (
    <main id="main" tabIndex={-1} className="not-found">
      <p className="eyebrow">Atria · 404</p>
      <h1>This page isn&apos;t in the waiting room.</h1>
      <p>Return to Atria to choose patient check-in or the nurse station.</p>
      <Link href="/" className="primary-button">Return to Atria</Link>
    </main>
  );
}
