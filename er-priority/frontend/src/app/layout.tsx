
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ER Priority | Emergency Intake Demo",
  description: "ER patient intake and human-review dashboard demo",
};

export default function RootLayout({
                                     children,
                                   }: Readonly<{
  children: React.ReactNode;
}>) {
  return (
      // Browser extensions (e.g. autofill) add attributes to <html> before React loads.
      <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
      </html>
  );
}
