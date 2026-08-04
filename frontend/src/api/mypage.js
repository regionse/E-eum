const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const token = localStorage.getItem('eum_token')

  const response = await fetch(`${API_BASE_URL}${path}`, {
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