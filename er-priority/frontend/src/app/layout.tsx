
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
      <html lang="en">
      <body>{children}</body>
      </html>
  );
}
