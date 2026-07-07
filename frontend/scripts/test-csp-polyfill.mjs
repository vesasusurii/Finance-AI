import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import vm from "node:vm";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const themeInit = readFileSync(path.join(root, "public", "theme-init.js"), "utf8");

const required = [
  'defineProperty(document, "oninput"',
  "isInlineEventHandlerAttribute",
  "Element.prototype.setAttribute",
];

for (const snippet of required) {
  if (!themeInit.includes(snippet)) {
    console.error(`theme-init.js is missing CSP polyfill marker: ${snippet}`);
    process.exit(1);
  }
}

const elementProto = {
  setAttribute(name, value) {
    if (name === "oninput" && typeof value === "string") {
      throw new Error("CSP blocked inline event handler");
    }
    if (name === "onclick" && typeof value === "string") {
      throw new Error("CSP blocked inline event handler");
    }
  },
};

const sandbox = {
  console,
  localStorage: {
    getItem: () => null,
  },
  window: {
    matchMedia: () => ({ matches: false }),
  },
  document: {
    documentElement: { classList: { add() {} } },
    createElement() {
      return Object.create(elementProto);
    },
  },
  Object,
  Element: { prototype: elementProto },
};

sandbox.window.document = sandbox.document;
vm.createContext(sandbox);
vm.runInContext(themeInit, sandbox);

for (const [name, value] of [
  ["oninput", "return;"],
  ["onclick", "doSomething()"],
]) {
  try {
    sandbox.document.createElement("div").setAttribute(name, value);
  } catch (e) {
    console.error(`Inline handler ${name} was not neutralised:`, e.message);
    process.exit(1);
  }
}

console.log("CSP polyfill blocks inline on* setAttribute probes");
