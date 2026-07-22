import { Link } from 'react-router-dom'
import { useAuth } from '../store/auth.jsx'

// 회원 전용 영역 게이트 (스토리보드 WEL-200: 비회원 진입 시 로그인 유도)
export default function RequireLogin({ axis = '이 기능', children }) {
  const { user } = useAuth()
  if (user) return children
  return (
    <div className="card card-pad center" style={{ maxWidth: 460, margin: '0 auto', padding: 'var(--sp-7)' }}>
      <div style={{ fontSize: 40 }}>🔒</div>
      <h3 style={{ margin: '12px 0 8px' }}>로그인이 필요해요</h3>
      <p className="muted">{axis}은(는) 익명으로 안전하게 제공돼요.<br />로그인 후 이용할 수 있어요.</p>
      <div className="row" style={{ gap: 10, justifyContent: 'center', marginTop: 20 }}>
        <Link to="/login" className="btn btn-primary">로그인</Link>
        <Link to="/signup" className="btn btn-ghost">회원가입</Link>
      </div>
    </div>
  )
}
