import { NavLink, Link, Outlet, useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '../../store/auth.jsx'

// 그룹이 있으면 서브메뉴(덜다), 없으면 단일 항목
const MENU = [
  { to: '/admin/users', label: '회원관리' },
  { to: '/admin/dashboard', label: '대시보드' },   // 첫 화면은 회원관리 · 대시보드는 그 아래(2026-07-30)
  { to: '/admin/notices', label: '공지관리' },
  { to: '/admin/inquiries', label: '문의관리' },
  { to: '/admin/welfare', label: '덜다 · 정책 임베딩' },
  { to: '/admin/learn', label: '잇다 · 임베딩 관리' },
  { to: '/admin/accounts', label: '관리자 계정' },
]

export default function AdminLayout() {
  const { admin, adminLogout } = useAuth()
  const nav = useNavigate()
  if (!admin) return <Navigate to="/admin/login" replace />

  const onLogout = () => { adminLogout(); nav('/admin/login') }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <header className="header">
        <div className="container">
          <Link to="/admin" className="brand"><span className="dot" />이음 <span style={{ fontSize: 13, color: 'var(--muted)', fontWeight: 700 }}>ADMIN</span></Link>
          <div className="gnb-right">
            <span className="badge badge-teal">{admin.role}</span>
            <span className="muted" style={{ fontSize: 14 }}>{admin.id}</span>
            <button className="btn btn-plain btn-sm" onClick={onLogout}>로그아웃</button>
          </div>
        </div>
      </header>
      <div className="container" style={{ padding: 'var(--sp-5) var(--sp-5) var(--sp-8)' }}>
        <div className="side-layout">
          <aside className="side-nav">
            {MENU.map((m) => m.children ? (
              <div key={m.label} style={{ margin: '4px 0' }}>
                <div style={{ padding: '11px 14px 4px', fontSize: 13, fontWeight: 700, color: 'var(--muted)' }}>{m.label}</div>
                {m.children.map((c) => (
                  <NavLink key={c.to} to={c.to} style={{ paddingLeft: 26 }}>· {c.label}</NavLink>
                ))}
              </div>
            ) : (
              <NavLink key={m.to} to={m.to} end={m.end}>{m.label}</NavLink>
            ))}
          </aside>
          <section style={{ minWidth: 0 }}><Outlet /></section>
        </div>
      </div>
    </div>
  )
}
