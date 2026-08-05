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
        //  ★ 'localhost' 가 아니라 '127.0.0.1' 이다(2026-08-04).
        //    Node 는 localhost 를 IPv6(::1) 먼저 시도하는데, uvicorn 은 127.0.0.1(IPv4)에만
        //    바인딩한다. 그래서 매 요청이 ::1 로 한 번 헛걸음(ECONNREFUSED)한 뒤 IPv4 로 넘어갔다.
        //    동작은 했지만 요청마다 지연이 붙었고, 프록시 로그에 AggregateError 가 계속 찍혔다.
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
