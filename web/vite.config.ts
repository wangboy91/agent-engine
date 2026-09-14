import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const engine = "http://127.0.0.1:8050";
const account = "http://127.0.0.1:8051";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5001,
    proxy: {
      // 账号权限服务
      "/account": {
        target: account,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/account/, ""),
      },
      // 智能体基座
      "/api": { target: engine, changeOrigin: true },
      "/skills": { target: engine, changeOrigin: true },
      "/runs": { target: engine, changeOrigin: true },
      "/health": { target: engine, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
