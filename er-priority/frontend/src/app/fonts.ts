import localFont from "next/font/local";

// Downloaded from Fontshare by predev/prebuild; binaries stay out of Git.
export const switzer = localFont({
  src: [
    { path: "../../public/fonts/switzer-400-normal.woff2", weight: "400", style: "normal" },
    { path: "../../public/fonts/switzer-500-normal.woff2", weight: "500", style: "normal" },
    { path: "../../public/fonts/switzer-600-normal.woff2", weight: "600", style: "normal" },
    { path: "../../public/fonts/switzer-700-normal.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-switzer",
  display: "swap",
  preload: false,
});
