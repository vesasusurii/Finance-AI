import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const themeInit = readFileSync(path.join(root, "public", "theme-init.js"), "utf8");

const required = [
  'defineProperty(document, "oninput"',
  "setAttribute(\"oninput\", \"return;\")",
];

for (const snippet of required) {
  if (!themeInit.includes(snippet)) {
    console.error(`theme-init.js is missing CSP polyfill marker: ${snippet}`);
    process.exit(1);
  }
}

console.log("CSP polyfill markers present in theme-init.js");
