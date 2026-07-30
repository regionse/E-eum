// ============================================================================
//  API 클라이언트
//  · request()     : 진짜 백엔드(FastAPI) fetch 래퍼 — 잇다·인증이 여기로 붙는다.
//  · mockResolve() : 아직 백엔드가 없는 화면(덜다·나누다·공지·문의)의 mock 반환용.
//  화면(pages)은 api/*.js 만 바라보므로, 백엔드가 생기면 그 반환부만 request()로 바꾸면 된다.
// ============================================================================

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

// ── JWT 토큰 저장/조회 (localStorage). request()가 자동으로 Authorization 헤더에 싣는다. ──
const TOKEN_KEY = 'eum_token'
export function setToken(t) { if (t) localStorage.setItem(TOKEN_KEY, t) }
export function getToken() { return localStorage.getItem(TOKEN_KEY) }
export function clearToken() { localStorage.removeItem(TOKEN_KEY) }

// 진짜 백엔드(FastAPI) fetch 래퍼. 토큰이 있으면 Bearer 로 싣고, 백엔드 detail 문구를 그대로 올린다.
export async function request(path, { method = 'GET', body, timeout = 60000 } = {}) {
  const token = getToken()
  // 타임아웃(2026-07-30) — 백엔드가 응답 안 하면 무한 대기 대신 실패시켜 UI가 복구되게.
  //  (무한 "불러오는 중"·"아무 일도 안 일어남" 방지 — 호출부 catch 가 빈 상태·에러를 띄운다)
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeout)
  let res
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    })
  } catch (e) {
    throw new Error(e.name === 'AbortError'
      ? '서버 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요.'
      : '서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.')
  } finally {
    clearTimeout(timer)
  }
  //  ★ 401 처리(2026-07-30 수정) — 예전엔 모든 401을 "로그인이 만료되었어요"로 뭉갰다.
  //    그래서 **로그인 화면에서 비번/아이디를 틀려도** 같은 문구가 떠서(로그인 실패도 401)
  //    사용자는 "로그인 기능이 고장났다"고 오해했다(실사용 신고).
  //    → 토큰은 정리하되, 문구는 백엔드 detail("아이디 또는 비밀번호가…")을 그대로 쓴다.
  //      토큰이 아예 없던 요청(=로그인 시도)엔 만료 문구를 쓰지 않는다.
  const wasLoggedIn = !!token
  if (res.status === 401) {
    clearToken()
  }
  if (!res.ok) {                                  // 백엔드가 준 detail(409 중복·400 약관·422 검증)을 그대로
    let msg = res.status === 401
      ? (wasLoggedIn ? '로그인이 만료되었어요. 다시 로그인해 주세요.'
                     : '아이디 또는 비밀번호를 확인해 주세요.')
      : `요청 실패 (${res.status})`
    try {
      const j = await res.json()
      if (j && j.detail) {
        msg = typeof j.detail === 'string' ? j.detail
            : Array.isArray(j.detail) ? (j.detail[0]?.msg || msg) : msg
      }
    } catch { /* 응답 본문 없음 */ }
    throw new Error(msg)
  }
  return res.json()
}
