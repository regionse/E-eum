//  ★ 2026-08-06 — 주소와 토큰은 client.js 하나에서 가져온다(share.js 와 같은 이유).
import { API_BASE, getToken } from './client.js'

async function request(path, options = {}) {
  const token = getToken()

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',

      ...(token
        ? {
            Authorization: `Bearer ${token}`,
          }
        : {}),

      ...options.headers,
    },
  })

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error(
      data?.detail ??
        '마이페이지 요청을 처리하지 못했습니다.',
    )
  }

  return data
}

// 동의 상태 조회
export function getUserConsents(userId) {
  return request(
    `/mypage/users/${userId}/consents`,
  )
}

// 위치정보·알림 동의 변경
export function updateUserConsents(
  userId,
  values,
) {
  return request(
    `/mypage/users/${userId}/consents`,
    {
      method: 'PATCH',
      body: JSON.stringify(values),
    },
  )
}

// 회원 탈퇴
export function withdrawMe(reason) {
  return request('/auth/me/withdraw', {
    method: 'POST',
    body: JSON.stringify({
      reason,
    }),
  })
}