import path from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const srcDir = path.resolve(__dirname, "./src");
const reactDir = path.resolve(__dirname, "node_modules/react");
const reactDomDir = path.resolve(__dirname, "node_modules/react-dom");

// Docker Compose mounts branding at /branding; local dev uses DOCS/branding
const brandingDir =
  process.env.VITE_BRANDING_DIR ??
  path.resolve(repoRoot, "DOCS/branding");

const isDocker = process.env.VITE_BRANDING_DIR === "/branding";

export default defineConfig({
  envDir: __dirname,
  plugins: [
    react(),
    tailwindcss(),
    tsconfigPaths({ projects: ["./tsconfig.app.json"] }),
  ],
  resolve: {
    dedupe: ["react", "react-dom", "react/jsx-runtime"],
    alias: [
      { find: "@/", replacement: `${srcDir}/` },
      { find: "@brand", replacement: brandingDir },
      { find: "react", replacement: reactDir },
      { find: "react-dom", replacement: reactDomDir },
    ],
  },
  optimizeDeps: {
    include: ["react", "react-dom", "react-router-dom"],
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    fs: {
      allow: [path.resolve(__dirname, ".."), brandingDir],
    },
    // Browser on host, Vite in Docker: WebSocket must target localhost:5173
    hmr: {
      host: "localhost",
      port: 5173,
      clientPort: 5173,
      protocol: "ws",
    },
    watch: isDocker
      ? {
          usePolling: true,
          interval: 1000,
        }
      : undefined,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
