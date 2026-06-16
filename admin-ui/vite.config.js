import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// development: Vite روی 5173 — API معمولاً uvicorn روی 8000 (یا 3000 در Docker). با VITE_PROXY_TARGET در .env اوورراید کن.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'
  return {
    base: mode === 'development' ? '/' : '/anistito/',
    plugins: [react()],
    build: {
      chunkSizeWarningLimit: 500,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return
            if (
              id.includes('react-dom') ||
              id.includes('react-router') ||
              /node_modules[/\\]react[/\\]/.test(id)
            ) {
              return 'vendor-react'
            }
            if (id.includes('lucide-react')) return 'vendor-icons'
            if (id.includes('axios')) return 'vendor-axios'
            if (id.includes('jalaali')) return 'vendor-jalaali'
            if (id.includes('@fontsource')) return 'vendor-fonts'
          },
        },
      },
    },
    server: {
      port: 5173,
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
        '/anistito/api': {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/anistito/, ''),
        },
      },
    },
  }
})
