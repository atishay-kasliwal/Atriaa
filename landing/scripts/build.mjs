import { cp, mkdir, readFile, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { build } from "esbuild";
import { ensureFonts } from "./fonts.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
const output = path.join(root, "dist");
await ensureFonts(root);
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(path.join(root, "public"), output, { recursive: true });
await cp(path.join(root, "css"), path.join(output, "css"), { recursive: true });
await build({
  entryPoints: [path.join(root, "src/client.mjs")],
  outfile: path.join(output, "js/site.js"),
  bundle: true,
  minify: true,
  format: "iife",
  target: ["es2022"],
  legalComments: "eof",
});
// A deployment must never silently ship links to missing local assets.
for (const page of ["index.html", "privacy.html", "404.html"]) {
  const html = await readFile(path.join(output, page), "utf8");
  for (const match of html.matchAll(
    /(?:src|href)="(\/[^"#?]+\.(?:css|js|woff2|svg|png))"/g,
  )) {
    await readFile(path.join(output, match[1]));
  }
}
console.log("Built Atria landing assets and motion bundle.");
