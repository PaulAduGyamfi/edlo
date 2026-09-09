import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev the API is reached through this proxy so no CORS or env is needed.
// In production set VITE_API_BASE to the API origin.
const API = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': API,
      '/version': API,
      '/episodes': API,
    },
  },
})
