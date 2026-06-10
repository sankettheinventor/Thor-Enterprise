import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, proxy the Manager DashboardAPI (:7080) so the SPA is same-origin (no CORS, no key exposure).
const api = 'http://localhost:7080'
const proxied = ['/state', '/kanban', '/rooms', '/cards', '/audit', '/cost', '/findings',
                 '/lies', '/health', '/operator', '/approve', '/task']

export default defineConfig({
  base: '/app/', // the plane serves the cockpit (laptop + phone) under /app/
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    port: 5173,
    proxy: Object.fromEntries(proxied.map((p) => [p, { target: api, changeOrigin: true }])),
  },
})
