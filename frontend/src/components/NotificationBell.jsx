import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { getUnreadNotificationCount } from '../api/notifications.js'
import { useAuth } from '../store/auth.jsx'

const NOTIFICATIONS_CHANGED_EVENT = 'notifications:changed'


export default function NotificationBell() {
  const auth = useAuth()
  const userId =
    auth.userId ??
    auth.user?.user_id ??
    auth.user?.userId ??
    auth.user?.id ??
    null
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    if (!userId) {
      setUnreadCount(0)
      return undefined
    }

    let active = true

    const refresh = async () => {
      try {
        const result = await getUnreadNotificationCount(userId)
        if (active) setUnreadCount(result.unread_count)
      } catch {
        // 헤더 전체를 깨뜨리지 않도록 알림 조회 실패는 조용히 처리한다.
      }
    }

    refresh()
    const timer = window.setInterval(refresh, 30000)
    const handleNotificationsChanged = () => {
      // 목록 화면에서 읽음 처리한 결과를 30초 폴링 전에 바로 반영한다.
      setUnreadCount(0)
      refresh()
    }
    window.addEventListener(
      NOTIFICATIONS_CHANGED_EVENT,
      handleNotificationsChanged,
    )

    return () => {
      active = false
      window.clearInterval(timer)
      window.removeEventListener(
        NOTIFICATIONS_CHANGED_EVENT,
        handleNotificationsChanged,
      )
    }
  }, [userId])

  if (!userId) return null

  return (
    <Link
      to="/notifications"
      aria-label={`알림 ${unreadCount}개`}
      title="알림"
      style={{
        position: 'relative',
        display: 'inline-flex',
        width: 42,
        height: 42,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: '50%',
        textDecoration: 'none',
        fontSize: 22,
      }}
    >
      🔔
      {unreadCount > 0 && (
        <span
          style={{
            position: 'absolute',
            top: 0,
            right: 0,
            minWidth: 19,
            height: 19,
            padding: '0 5px',
            borderRadius: 10,
            background: '#ef4444',
            color: '#fff',
            fontSize: 11,
            fontWeight: 800,
            lineHeight: '19px',
            textAlign: 'center',
          }}
        >
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </Link>
  )
}