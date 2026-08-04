const API_PREFIX = '/api'

function getAccessToken() {
  const directKeys = ['access_token', 'token']

  for (const key of directKeys) {
    const value = localStorage.getItem(key)
    if (value) return value.replace(/^"|"$/g, '')
  }

  for (const key of ['auth', 'auth-storage']) {
    const raw = localStorage.getItem(key)
    if (!raw) continue

    try {
      const parsed = JSON.parse(raw)
      const value =
        parsed.access_token ??
        parsed.token ??
        parsed.state?.access_token ??
        parsed.state?.token
      if (value) return value
    } catch {
      // 다른 형식이면 다음 키를 확인한다.
    }
  }

  return null
}

async function request(path, options = {}) {
  const token = getAccessToken()
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token
        ? { Authorization: `Bearer ${token}` }
        : {}),
      ...options.headers,
    },
  })

  if (!response.ok) {
    let message = '알림 요청에 실패했습니다.'
    try {
      const body = await response.json()
      message = body.detail || message
    } catch {
      // JSON 응답이 아니면 기본 문구를 사용한다.
    }
    throw new Error(message)
  }

  return response.json()
}

export function getNotifications({ userId, page = 1, size = 20 }) {
  return request(
    `/notifications?user_id=${userId}&page=${page}&size=${size}`,
  )
}

export function getUnreadNotificationCount(userId) {
  return request(`/notifications/unread-count?user_id=${userId}`)
}

export function markNotificationRead({ notificationId, userId }) {
  return request(
    `/notifications/${notificationId}/read?user_id=${userId}`,
    { method: 'PATCH' },
  )
}

export function markAllNotificationsRead(userId) {
  return request(
    `/notifications/read-all?user_id=${userId}`,
    { method: 'PATCH' },
  )
}
