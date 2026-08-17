import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Fixed, and refuses to move. Vite's default is to hop to the next free
    // port when 5173 is taken, which quietly breaks every link the backend
    // emails out: FRONTEND_URL is baked into the registrar's enrolment link at
    // the moment it is queued, so a dev server that wandered to 5177 sent
    // registrars a link to a port nothing was listening on. Failing to start
    // is easier to notice than a wrong link in someone else's inbox.
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
