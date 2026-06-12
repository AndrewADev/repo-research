import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The SPA talks to the FastAPI backend (`repo-research serve`, default :8000).
// Proxy the API and the AG-UI agent stream so the browser stays same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/agent": "http://localhost:8000",
    },
  },
});
