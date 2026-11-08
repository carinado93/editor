import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Beim Entwickeln leitet Vite /api an den Python-Motor weiter.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "dist", emptyOutDir: true },
});
