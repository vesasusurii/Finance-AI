import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const inlineScript = readFileSync(
  path.join(root, "scripts", "csp-polyfill-inline.js"),
  "utf8",
).trim();

const hash = createHash("sha256").update(inlineScript, "utf8").digest("base64");
console.log(`sha256-${hash}`);
