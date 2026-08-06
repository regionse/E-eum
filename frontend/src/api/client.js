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

// ── 백엔드 주소 (2026-07-31 · AWS 배포 대비) ──────────────────────────────
//  개발: 값이 없으면 '/api' → vite 개발서버가 8000 으로 프록시한다(지금까지와 동일).
//  배포: vite 개발서버가 없으므로 프록시도 없다. 그대로 두면 프론트가 백엔드를 못 찾아 전부 실패한다.
//        빌드할 때 VITE_API_BASE 를 주면 그 주소로 부른다.
//          예) VITE_API_BASE=https://api.우리도메인.com  npm run build
//  ★★ 2026-08-06 — **export 한다. 백엔드 주소를 정하는 곳은 여기 하나뿐이다.**
//    왜: api/share.js·mypage.js 와 pages/share/ResourceMap.jsx 가 각자
//      `import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'`
//    을 갖고 있었다. **환경변수 이름이 여기(VITE_API_BASE)와 달랐고**, 기본값도
//    프록시(/api)가 아니라 8000 직결이었다.
//    개발 중에는 둘 다 우연히 동작해서 안 드러난다 — 배포 빌드에서 한쪽만
//    설정하면 **화면 절반이 죽는다.** 이름이 둘이면 반드시 하나를 빠뜨린다.
//    ⇒ 상수를 내보내고, 쓰는 쪽은 전부 이걸 import 한다.
export const API_BASE = (import.meta.env?.VITE_API_BASE || '/api').replace(/\/$/, '')

// 진짜 백엔드(FastAPI) fetch 래퍼.
// 토큰이 있으면 Bearer 로 싣고,
// 백엔드 detail 문구를 그대로 올린다.
export async function request(
  path,
  {
    method = 'GET',
    body,
    timeout = 60000,

    // 추가된 부분:
    // 호출한 화면에서 요청을 취소할 때 사용하는 signal
    signal,
  } = {},
) {
  const token = getToken()

  // 기존 타임아웃용 AbortController
  const ctrl = new AbortController()

  // 추가된 부분:
  // 화면에서 취소한 것인지 구분하기 위한 값
  let abortedByCaller = false

  // 추가된 부분:
  // PolicyFind.jsx에서 전달한 signal이 중단되면
  // 기존 ctrl도 중단시켜 실제 fetch를 취소한다.
  const abortFromCaller = () => {
    abortedByCaller = true
    ctrl.abort()
  }

  // 추가된 부분:
  // 이미 중단된 signal일 수도 있으므로 먼저 확인한다.
  if (signal?.aborted) {
    abortFromCaller()
  } else {
    signal?.addEventListener(
      'abort',
      abortFromCaller,
      {
        once: true,
      },
    )
  }

  // 기존 타임아웃 처리
  const timer = setTimeout(
    () => ctrl.abort(),
    timeout,
  )

  let res

  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,

      headers: {
        'Content-Type': 'application/json',

        ...(token
          ? {
            Authorization: `Bearer ${token}`,
          }
          : {}),
      },

      body: body
        ? JSON.stringify(body)
        : undefined,

      // 기존 ctrl.signal 그대로 사용
      signal: ctrl.signal,
    })
  } catch (e) {
    // 추가된 부분:
    // 사용자가 추천 중단 버튼을 누른 경우에는
    // AbortError를 그대로 전달한다.
    //
    // PolicyFind.jsx가 이 오류를 확인하고
    // 오류 문구 없이 입력 폼으로 돌아간다.
    if (
      e.name === 'AbortError'
      && abortedByCaller
    ) {
      throw e
    }

    // 기존 오류 처리 그대로 유지
    throw new Error(
      e.name === 'AbortError'
        ? '서버 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요.'
        : '서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.',
    )
  } finally {
    clearTimeout(timer)
    // 추가된 부분:
    // 요청이 끝나면 이벤트 리스너도 제거한다.
    signal?.removeEventListener(
      'abort',
      abortFromCaller,
    )
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
        msg =
          typeof j.detail === 'string'
            ? j.detail
            : Array.isArray(j.detail)
              ? (
                j.detail[0]?.msg
                || msg
              )
              : typeof j.detail === 'object'
                ? (
                  j.detail.message
                  || msg
                )
              : msg
      }
    } catch {
      // 응답 본문 없음
    }

    throw new Error(msg)
  }

  // 기존 성공 응답 처리 그대로 유지
  return res.json()
}