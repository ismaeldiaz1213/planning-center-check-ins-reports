import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api':         'http://localhost:8000',
      '/previews':    'http://localhost:8000',
      '/ibl_logo.png':'http://localhost:8000',
    },
  },
  build: {
    // Local builds write directly into backend/static/ so FastAPI can serve them.
    // The Dockerfile overrides --outDir at build time.
    outDir: resolve(__dirname, '../backend/static'),
    emptyOutDir: true,
  },
})
