// ============================================================================
//  API 클라이언트 — mock/real 교체 지점
//  지금은 mock 데이터를 인위적 지연과 함께 Promise로 반환한다.
//  나중에 진짜 백엔드(FastAPI)를 붙일 땐:
//    1) USE_MOCK = false 로 바꾸고
//    2) request() 안의 실제 fetch 분기를 사용하면
//    화면 코드는 그대로 둔 채 데이터 소스만 바뀐다.
// ============================================================================

export const USE_MOCK = true

// 실제 API 지연을 흉내 내 로딩 UI를 진짜처럼 검증할 수 있게 한다.
export function delay(ms = 700) {
  return new Promise((res) => setTimeout(res, ms))
}

// mock 응답 헬퍼: 지연 후 data를 resolve. (가끔 실패를 흉내 내고 싶으면 failRate 사용)
export async function mockResolve(data, ms = 700, failRate = 0) {
  await delay(ms)
  if (failRate && Math.random() < failRate) {
    throw new Error('일시적인 오류가 발생했어요. 잠시 후 다시 시도해주세요.')
  }
  // 깊은 복사로 mock 원본이 화면에서 변형되지 않게 방어
  return typeof data === 'function' ? data() : JSON.parse(JSON.stringify(data))
}

// 진짜 백엔드 붙일 때 쓸 fetch 래퍼 (지금은 미사용).
export async function request(path, { method = 'GET', body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`요청 실패 (${res.status})`)
  return res.json()
}
