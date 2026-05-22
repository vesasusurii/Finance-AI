import path from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const brandingDir = path.resolve(repoRoot, "branding");
const srcDir = path.resolve(__dirname, "./src");

export default defineConfig({
  // VITE_* from frontend/.env (use empty API base in dev for same-origin proxy)
  envDir: __dirname,
  plugins: [
    react(),
    tailwindcss(),
    tsconfigPaths({ projects: ["./tsconfig.app.json"] }),
  ],
  resolve: {
    alias: [
      { find: "@/", replacement: `${srcDir}/` },
      { find: "@brand", replacement: brandingDir },
    ],
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    fs: {
      allow: [path.resolve(__dirname, ".."), brandingDir],
    },
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
