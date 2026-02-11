import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    dedupe: ['react', 'react-dom'],
  },
  server: {
    port: 3000,
    proxy: {
      // LESS specific first
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // MORE specific second (overrides /api for WebSocket)
      '/api/v1/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    }
  },
  build: {
    target: 'esnext'
  }
})