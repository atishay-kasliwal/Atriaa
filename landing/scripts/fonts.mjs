import { access, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

// Switzer is self-hosted for this site's own use. Fetch original files directly
// from Fontshare at build time; do not redistribute font binaries in the repo.
export async function ensureFonts(root) {
  const weights = ["400", "500", "600", "700"];
  const directory = path.join(root, "public/fonts");
  const filename = (weight) =>
    path.join(directory, `switzer-${weight}-normal.woff2`);
  const cached = await Promise.all(
    weights.map((weight) =>
      access(filename(weight)).then(
        () => true,
        () => false,
      ),
    ),
  );
  if (cached.every(Boolean)) return;
  const response = await fetch(
    "https://api.fontshare.com/v2/css?f[]=switzer@400,500,600,700&display=swap",
    { signal: AbortSignal.timeout(20000) },
  );
  if (!response.ok)
    throw new Error(
      "Could not retrieve Switzer from Fontshare. Retry the build.",
    );
  const css = await response.text();
  await mkdir(directory, { recursive: true });
  for (const block of css.match(/@font-face\s*{[^}]+}/g) || []) {
    const weight = block.match(/font-weight:\s*(\d+)/)?.[1];
    const url = block.match(/url\(['"]?([^'")]+\.woff2)['"]?\)/)?.[1];
    if (!weights.includes(weight) || !url || /font-style:\s*italic/.test(block))
      continue;
    const file = await fetch(url.startsWith("//") ? `https:${url}` : url, {
      signal: AbortSignal.timeout(20000),
    });
    if (!file.ok)
      throw new Error(`Fontshare download failed for Switzer ${weight}.`);
    await writeFile(filename(weight), new Uint8Array(await file.arrayBuffer()));
  }
  for (const weight of weights) await access(filename(weight));
}
