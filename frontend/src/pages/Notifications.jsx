import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../api/notifications.js'
import { useAuth } from '../store/auth.jsx'

const NOTIFICATIONS_CHANGED_EVENT = 'notifications:changed'


function formatDate(value) {
  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}


export default function Notifications() {
  const auth = useAuth()
  const userId =
    auth.userId ??
    auth.user?.user_id ??
    auth.user?.userId ??
    auth.user?.id ??
    null
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadNotifications = async () => {
    if (!userId) {
      setItems([])
      setUnreadCount(0)
      setError('로그인 사용자 정보를 확인할 수 없습니다.')
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError('')
      const result = await getNotifications({ userId })
      setItems(result.items)
      setUnreadCount(result.unread_count)

      // 알림 목록에 들어온 것 자체를 모든 알림을 확인한 것으로 처리한다.
      if (result.unread_count > 0) {
        await markAllNotificationsRead(userId)
        setItems((previous) =>
          previous.map((item) => ({ ...item, is_read: true })),
        )
        setUnreadCount(0)
        window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT))
      }
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadNotifications()
  }, [userId])

  const openNotification = async (notification) => {
    try {
      if (!notification.is_read) {
        await markNotificationRead({
          notificationId: notification.notification_id,
          userId,
        })
        window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT))
      }
      navigate(notification.target_url)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  const readAll = async () => {
    try {
      await markAllNotificationsRead(userId)
      setItems((previous) =>
        previous.map((item) => ({ ...item, is_read: true })),
      )
      setUnreadCount(0)
      window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT))
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <div className="container page">
      <div
        className="row"
        style={{ justifyContent: 'space-between', marginBottom: 20 }}
      >
        <div>
          <h1>알림</h1>
          <p className="muted">새 공지와 가족편지 소식을 확인하세요.</p>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={readAll}
          disabled={unreadCount === 0}
        >
          모두 읽음
        </button>
      </div>

      {error && <div className="callout-warn">{error}</div>}

      <div className="card">
        {loading ? (
          <div className="center muted" style={{ padding: 48 }}>
            알림을 불러오는 중이에요.
          </div>
        ) : items.length === 0 ? (
          <div className="center muted" style={{ padding: 48 }}>
            아직 도착한 알림이 없어요.
          </div>
        ) : (
          items.map((notification) => (
            <button
              key={notification.notification_id}
              type="button"
              onClick={() => openNotification(notification)}
              style={{
                width: '100%',
                display: 'flex',
                gap: 14,
                alignItems: 'flex-start',
                padding: '18px 20px',
                border: 0,
                borderBottom: '1px solid var(--line)',
                background: notification.is_read
                  ? '#fff'
                  : 'var(--teal-50)',
                color: 'inherit',
                textAlign: 'left',
                cursor: 'pointer',
              }}
            >
              <span style={{ fontSize: 24 }}>
                {notification.notification_type === 'NOTICE'
                  ? '📢'
                  : '💌'}
              </span>
              <span style={{ flex: 1 }}>
                <span style={{ display: 'block', fontWeight: 800 }}>
                  {notification.title}
                </span>
                <span
                  className="muted"
                  style={{ display: 'block', marginTop: 5 }}
                >
                  {notification.content}
                </span>
                <span
                  className="muted"
                  style={{ display: 'block', marginTop: 8, fontSize: 12 }}
                >
                  {formatDate(notification.created_at)}
                </span>
              </span>
              {!notification.is_read && (
                <span
                  aria-label="읽지 않음"
                  style={{
                    width: 8,
                    height: 8,
                    marginTop: 8,
                    borderRadius: '50%',
                    background: '#ef4444',
                  }}
                />
              )}
            </button>
          ))
        )}
      </div>
    </div>
  )
}