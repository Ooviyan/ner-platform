import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
} from "node:fs";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const dashboardRoot = fileURLToPath(new URL(".", import.meta.url));

// mock-data/ is a sibling of dashboard/, owned jointly by the team and never
// written to from here. This plugin exposes it at /mock-data during `vite dev`
// and copies it into dashboard/dist/mock-data during `vite build`, without
// ever touching the source folder itself.
const mockDataDir = resolve(dashboardRoot, "..", "mock-data");

const MIME_TYPES: Record<string, string> = {
  ".json": "application/json",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
};

function copyDirRecursive(src: string, dest: string) {
  mkdirSync(dest, { recursive: true });
  for (const entry of readdirSync(src, { withFileTypes: true })) {
    const srcPath = join(src, entry.name);
    const destPath = join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDirRecursive(srcPath, destPath);
    } else {
      copyFileSync(srcPath, destPath);
    }
  }
}

function serveRootMockData(): Plugin {
  return {
    name: "serve-root-mock-data",
    configureServer(server) {
      server.middlewares.use("/mock-data", (req, res, next) => {
        if (!req.url || (req.method && req.method !== "GET" && req.method !== "HEAD")) {
          next();
          return;
        }

        const requestedPath = decodeURIComponent(req.url.split("?")[0] ?? "");
        const filePath = normalize(join(mockDataDir, requestedPath));

        // Guard against path traversal escaping mock-data/.
        if (!filePath.startsWith(mockDataDir)) {
          next();
          return;
        }

        // A real 404 here (rather than falling through to Vite's SPA HTML
        // fallback) keeps `fetch()`/`<img>` failures honest — e.g. reports.json
        // referencing a photo file mock-data doesn't actually ship should fail
        // as a missing file, not silently resolve as an HTML document.
        if (!existsSync(filePath) || !statSync(filePath).isFile()) {
          res.statusCode = 404;
          res.end("Not found");
          return;
        }

        const contentType = MIME_TYPES[extname(filePath).toLowerCase()] ?? "application/octet-stream";
        res.setHeader("Content-Type", contentType);
        res.setHeader("Cache-Control", "no-cache");
        res.end(readFileSync(filePath));
      });
    },
    closeBundle() {
      if (!existsSync(mockDataDir)) return;
      const outDir = resolve(dashboardRoot, "dist", "mock-data");
      copyDirRecursive(mockDataDir, outDir);
    },
  };
}

export default defineConfig({
  plugins: [react(), serveRootMockData()],
  server: {
    port: 3000,
    strictPort: true,
  },
});
