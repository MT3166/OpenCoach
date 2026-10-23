import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()], base: '/',
  server: { proxy: {
    '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    '/health': { target: 'http://127.0.0.1:8000', changeOrigin: false },
  } },
  build: { outDir: 'dist', assetsDir: 'static/h5' },
})
