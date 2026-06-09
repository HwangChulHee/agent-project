import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api 요청을 FastAPI(8000)로 프록시 → 프론트는 항상 상대경로 fetch.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
