import type { Metadata } from "next";
import { Motion } from "@/components/Motion";
import { site } from "@/data/site";
import { switzer } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: { default: "Atria | Waiting room prototype", template: "%s | Atria" },
  description: site.description,
  // Patient tickets and staff workspaces are not public search content.
  robots: { index: false, follow: false },
  openGraph: { type: "website", siteName: site.name, title: "Atria | Waiting room prototype", description: site.description },
  twitter: { card: "summary_large_image" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={switzer.variable} suppressHydrationWarning>
      <body>
        <a className="skip-link" href="#main">Skip to content</a>
        <noscript><p className="noscript-notice">Turn on JavaScript to submit check-ins, see live updates, and use the nurse station.</p></noscript>
        {children}
        <Motion />
      </body>
    </html>
  );
}
