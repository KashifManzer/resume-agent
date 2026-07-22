import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    // dev proxy → FastAPI backend, so no CORS needed
    proxy: {
      '/health': 'http://localhost:8000',
      '/jobs': 'http://localhost:8000',
      '/jd': 'http://localhost:8000',
    },
  },
})
