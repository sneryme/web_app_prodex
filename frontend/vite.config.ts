import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// usePolling: Docker Desktop на Windows не всегда пробрасывает inotify-события bind-mount'а
// (./frontend:/app в docker-compose.yml) внутрь контейнера — без polling Vite не видит
// изменения файлов на хосте и не делает HMR/перезагрузку.
export default defineConfig({
  plugins: [react()],
  server: { watch: { usePolling: true, interval: 300 } },
});
