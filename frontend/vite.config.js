import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 5173(프론트)에서 /api 로 부르면 → 8000(FastAPI 백엔드)로 프록시된다.
// 백엔드 라우트는 /itda, /notices, /inquiries 처럼 /api 접두사가 없으므로
// rewrite로 /api 를 떼고 전달한다. (즉 프론트는 8000을 몰라도 되고 5173만 쓴다)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
