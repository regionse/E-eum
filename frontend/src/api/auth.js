// 인증 · 회원 (mock)
import { mockResolve, delay } from './client.js'
import { currentUser } from '../mock/db.js'

export function login({ id, pw }) {
  // mock: 아무 값이나 형식만 맞으면 통과
  if (!id || !pw) return Promise.reject(new Error('아이디와 비밀번호를 입력해주세요.'))
  return mockResolve(() => ({ ...currentUser, token: 'mock-jwt-token' }), 600)
}
export function signup(_data) {
  return mockResolve({ ok: true }, 700)
}
export function findId({ birth, phone }) {
  if (!birth || !phone) return Promise.reject(new Error('입력값을 확인해주세요.'))
  return mockResolve({ id: 'user1234' }, 700)
}
export async function resetPassword(_data) {
  await delay(600)
  return { ok: true }
}

// 관리자 로그인 — 데모용 고정 계정: 아이디 1234 / 비밀번호 1234 만 통과 (관리자 권한).
export function adminLogin({ id, pw }) {
  if (!id || !pw) return Promise.reject(new Error('아이디와 비밀번호를 입력해주세요.'))
  if (id !== '1234' || pw !== '1234') {
    return Promise.reject(new Error('아이디 또는 비밀번호가 올바르지 않습니다.'))
  }
  return mockResolve(() => ({ id, role: '관리자', token: 'mock-admin-jwt' }), 600)
}
