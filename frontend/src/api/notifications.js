//  ★★ 2026-08-06 — **토큰을 못 찾고 있었다.**
//    예전 getAccessToken() 은 localStorage 에서 'access_token' · 'token' ·
//    'auth' · 'auth-storage' 를 뒤졌다. 그런데 이 프로젝트가 실제로 쓰는 키는
//    client.js 의 TOKEN_KEY = **'eum_token'** 이다 — 넷 중 어느 것도 아니다.
//    ⇒ 이 함수는 **언제나 null 을 돌려줬고**, 알림 요청에 Authorization 이 한 번도
//      안 붙었다. 지금은 알림 라우터에 get_current_user 가 없어서 드러나지 않을 뿐,
//      나누다 가족편지에 인증을 걸었을 때 터진 것과 **똑같은 사고**가 예약돼 있었다.
//    ⚠ 주소도 '/api' 로 박혀 있었다 — vite 프록시가 있는 개발에서만 맞고
//      배포 빌드에서는 프록시가 없어 그대로 깨진다. 둘 다 client.js 로 통일한다.
import { API_BASE, getToken } from './client.js'

async function request(path, options = {}) {
  const token = getToken()
  const response = await fetch(`${API_BASE}${path}`, {
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
