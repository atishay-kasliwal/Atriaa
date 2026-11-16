import { ImageResponse } from "next/og";

export const alt = "Atria waiting room prototype";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div style={{ display: "flex", width: "100%", height: "100%", padding: 80, flexDirection: "column", justifyContent: "space-between", background: "#f8fafc", color: "#0f172a" }}>
      <div style={{ fontSize: 40, color: "#075985" }}>Atria · Waiting room prototype</div>
      <div style={{ fontSize: 76, lineHeight: 1.05, maxWidth: 920 }}>See what changes while patients wait.</div>
      <div style={{ fontSize: 26, color: "#475569" }}>Patient check-in. Nurse-led priority. Reassessment alerts.</div>
    </div>,
    size,
  );
}
