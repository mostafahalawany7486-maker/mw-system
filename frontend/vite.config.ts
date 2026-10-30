import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: true,
  },
  build: {
    // Vendor libraries change far less often than application code, so
    // splitting them into their own chunk lets browsers cache them
    // across deploys instead of re-downloading everything whenever any
    // app file changes. Pure build/bundling config — no runtime behavior
    // changes; route-level code splitting (see App.tsx's React.lazy
    // usage) already handles per-page chunking on top of this.
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-charts": ["recharts"],
          "vendor-i18n": ["i18next", "react-i18next", "i18next-browser-languagedetector"],
        },
      },
    },
  },
});
