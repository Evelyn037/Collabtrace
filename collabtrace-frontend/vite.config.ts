import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173 },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/zrender/')) return 'renderer'
          if (id.includes('/node_modules/echarts/')) return 'charts'
          if (id.includes('/node_modules/react') || id.includes('/node_modules/scheduler/')) return 'react'
          if (id.includes('/node_modules/axios/')) return 'api'
          if (id.includes('/node_modules/lucide-react/')) return 'icons'
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.tsx',
    css: true,
  },
})
