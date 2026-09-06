/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    // import.meta.dirname (not __dirname) so Vite's native config loader accepts this file.
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    port: 5173,
    host: true, // bind 0.0.0.0 so the container is reachable from the host
    proxy: {
      // Lets the dev client call `/api/v1/...` same-origin, which sidesteps CORS
      // entirely in development. Production uses VITE_API_BASE_URL directly.
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
