import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import {defineConfig} from "vite";

export default defineConfig({
  base: "/react/",
  plugins: [react(), tailwindcss()],
  root: "frontend",
  build: {
    outDir: "../src/firelaw_api/static/react",
    emptyOutDir: true,
  },
});
