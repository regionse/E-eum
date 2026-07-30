// 인증 · 회원 — 실제 백엔드(/auth) 연동, JWT (2026-07-28)
//  로그인/가입/관리자로그인은 진짜 FastAPI를 친다. 토큰은 client.js가 저장·전송한다.
//  아이디 찾기·비밀번호 재설정도 백엔드 연동 완료(/auth/find-id · /auth/reset-password).
import { request, setToken, clearToken } from './client.js'

// 로그인 → JWT 토큰 저장 → 내 정보(/auth/me) 반환
export async function login({ id, pw }) {
  if (!id || !pw) throw new Error('아이디와 비밀번호를 입력해주세요.')
  const { access_token } = await request('/auth/login', {
    method: 'POST', body: { username: id, password: pw },
  })
  setToken(access_token)
  return request('/auth/me')                       // 사용자 객체 {user_id, username, is_admin, ...}
}

// 회원가입 — 화면 폼(form + 약관)을 백엔드 스키마로 매핑
export function signup(data) {
  const a = data.agree || {}
  return request('/auth/signup', {
    method: 'POST',
    body: {
      username: data.id,
      password: data.pw,
      phone_number: data.phone || null,
      birthdate: data.birth || null,               // "YYYY-MM-DD" (input type=date)
      region_sido: data.region || null,
      is_terms_agreed: !!a.tos,
      is_privacy_agreed: !!a.privacy,
      is_location_agreed: !!a.location,
      is_alarm_agreed: !!a.alarm,
    },
  })
}

// 관리자 로그인 — 같은 /auth/login. is_admin 아니면 토큰 버리고 거부.
export async function adminLogin({ id, pw }) {
  if (!id || !pw) throw new Error('아이디와 비밀번호를 입력해주세요.')
  const { access_token } = await request('/auth/login', {
    method: 'POST', body: { username: id, password: pw },
  })
  setToken(access_token)
  const me = await request('/auth/me')
  if (!me.is_admin) {
    clearToken()
    throw new Error('관리자 권한이 없는 계정입니다.')
  }
  return me
}

// 아이디 찾기 — 생년월일+전화번호 → { id } (백엔드 /auth/find-id, 2026-07-29)
//  birth 는 "YYYY-MM-DD"(input type=date).
export async function findId({ birth, phone }) {
  if (!birth || !phone) throw new Error('생년월일과 전화번호를 입력해주세요.')
  const r = await request('/auth/find-id', {
    method: 'POST', body: { birthdate: birth, phone_number: phone },
  })
  return { id: r.username }
}

// 비밀번호 재설정 — 아이디+생년월일+전화번호 본인확인 → 새 비밀번호 (백엔드 /auth/reset-password)
export function resetPassword({ id, birth, phone, newPw }) {
  return request('/auth/reset-password', {
    method: 'POST',
    body: { username: id, birthdate: birth, phone_number: phone, new_password: newPw },
  })
}

// 내 정보 수정 — 비밀번호 확인 후 연락처·지역 변경 (마이페이지, 백엔드 PATCH /auth/me) → 갱신된 user 반환
export function updateMe({ password, phone, region }) {
  return request('/auth/me', {
    method: 'PATCH',
    body: { password, phone_number: phone, region_sido: region },
  })
}
