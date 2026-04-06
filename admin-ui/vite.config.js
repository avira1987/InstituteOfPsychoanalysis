import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// development: از http://localhost:3000/ — production build: زیر مسیر /anistito/ روی سرور
export default defineConfig(({ mode }) => ({
  base: mode === 'development' ? '/' : '/anistito/',
  plugins: [react()],
  server: {
    // جدا از پورت API (معمولاً 3000 با uvicorn یا Docker) تا پروکسی به خودِ Vite نخورد
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:3000',
        changeOrigin: true,
      },
      '/anistito/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:3000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/anistito/, ''),
      },
    },
  },
}))
