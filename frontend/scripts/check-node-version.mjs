import { pathToFileURL } from "node:url";

export function supportsNode(version) {
  if (!/^v?\d+\.\d+\.\d+$/.test(String(version))) return false;
  const parts = String(version).replace(/^v/, "").split(".").map(Number);
  if (parts.length !== 3 || !parts.every((value) => Number.isSafeInteger(value) && value >= 0)) return false;
  const [major, minor, patch] = parts;
  return major >= 26 || (major === 24 && minor >= 15) || (major === 22 && (minor > 22 || (minor === 22 && patch >= 2)));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href && !supportsNode(process.versions.node)) {
  console.error(`RuFLEX requires Node.js 22.22.2+ (22.x), 24.15+ (24.x), or 26+. Installed: ${process.versions.node}.`);
  process.exitCode = 1;
}
