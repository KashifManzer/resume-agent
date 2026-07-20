import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // dev proxy → FastAPI backend, so no CORS needed
    proxy: {
      '/health': 'http://localhost:8000',
    },
  },
})
