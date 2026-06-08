import { createServer } from "vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

const server = await createServer({
  configFile: path.join(root, "vite.config.ts"),
  server: { middlewareMode: true },
  appType: "custom",
});

await server.pluginContainer.buildStart({});

for (const id of [
  "/src/components/theme/ThemeProvider.tsx",
  "/node_modules/next-themes/dist/index.mjs",
]) {
  try {
    const result = await server.transformRequest(id);
    console.log("transform ok", id, result?.code?.slice(0, 80));
  } catch (error) {
    console.error("transform failed", id);
    console.error(error);
  }
}

await server.close();
