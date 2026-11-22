import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` on 5173 proxies /api to FastAPI on 8000.
// Build: `npm run build` writes dist/, which FastAPI serves on 8000 (no Node needed to play).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
