import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/auth": "http://localhost:8001",
      "/learning-coach": "http://localhost:8001",
      "/health": "http://localhost:8001"
    }
  }
});
