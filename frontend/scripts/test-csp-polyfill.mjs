import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import vm from "node:vm";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const inlineScript = readFileSync(
  path.join(root, "scripts", "csp-polyfill-inline.js"),
  "utf8",
).trim();

const indexHtml = readFileSync(path.join(root, "index.html"), "utf8");
const scriptMatch = indexHtml.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) {
  console.error("index.html is missing inline CSP polyfill script");
  process.exit(1);
}

const indexInline = scriptMatch[1];
if (indexInline !== inlineScript) {
  console.error("index.html inline CSP polyfill does not match scripts/csp-polyfill-inline.js");
  console.error("Expected length:", inlineScript.length, "Got:", indexInline.length);
  process.exit(1);
}

const hash = createHash("sha256").update(inlineScript, "utf8").digest("base64");
const expectedDirective = `'sha256-${hash}'`;
const cspConf = readFileSync(
  path.resolve(root, "..", "infra", "nginx", "csp.conf"),
  "utf8",
);

if (!cspConf.includes(expectedDirective)) {
  console.error(`infra/nginx/csp.conf is missing ${expectedDirective}`);
  console.error("Run: npm run csp:hash");
  process.exit(1);
}

const elementProto = {
  setAttribute(name, value) {
    if (typeof name === "string" && typeof value === "string" && name.startsWith("on")) {
      throw new Error("CSP blocked inline event handler");
    }
  },
};

const sandbox = {
  console,
  document: {
    createElement() {
      return Object.create(elementProto);
    },
  },
  Object,
  Element: { prototype: elementProto },
};

vm.createContext(sandbox);
vm.runInContext(inlineScript, sandbox);

try {
  sandbox.document.createElement("div").setAttribute("oninput", "return;");
} catch (error) {
  console.error("Inline CSP polyfill failed:", error.message);
  process.exit(1);
}

console.log("CSP polyfill inline script, hash, and nginx policy are in sync");
