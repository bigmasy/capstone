import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    // Browser tests run with Playwright against a started stack
    exclude: ["**/node_modules/**", "dist/**", "e2e/**"],
    setupFiles: ["./src/test/setup.ts"],
    css: { modules: { classNameStrategy: "non-scoped" } },
    env: {
      // fetch in Node cannot resolve a relative URL, so tests use an absolute one
      VITE_API_BASE_URL: "http://localhost/api/v1",
    },
  },
});
