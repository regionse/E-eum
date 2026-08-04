import { NavLink, Link, Outlet, useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '../../store/auth.jsx'
import { getToken } from '../../api/client.js'

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

  //  ★ 2026-08-04 — 토큰도 함께 본다. 예전엔 admin 객체만 봤다.
  //    세션이 세 군데에 나뉘어 있는데(eum_token=JWT · eum_user · eum_admin), JWT 는 공용이다.
  //    그래서 일반 사이트에서 로그아웃하거나(logout→clearToken) 24시간이 지나 401 이 한 번
  //    나면(client.js 가 clearToken) **토큰만 사라지고 eum_admin 은 남았다.**
  //    문지기가 admin 만 보니 화면은 그대로 열리고, 안의 API 호출은 헤더가 없어 전부
  //    FastAPI 기본 문구 「Not authenticated」로 떨어졌다(실측 · 회원관리 화면).
  //    ⇒ 둘 중 하나라도 없으면 로그인 화면으로 보낸다.
  if (!admin || !getToken()) return <Navigate to="/admin/login" replace />

  const onLogout = () => { adminLogout(); nav('/admin/login') }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <header className="header">
        <div className="container">
          <Link to="/admin" className="brand"><span className="dot" />이음 <span style={{ fontSize: 13, color: 'var(--muted)', fontWeight: 700 }}>ADMIN</span></Link>
          <div className="gnb-right">
            {/*  (2026-08-04) admin.role · admin.id 는 목업 시절 필드라 항상 undefined 였다
                 — 배지가 빈 채로, 아이디가 안 보인 채로 그려지고 있었다.
                 /auth/me 가 주는 실제 필드는 user_id · username · is_admin · status 다.  */}
            <span className="badge badge-teal">관리자</span>
            <span className="muted" style={{ fontSize: 14 }}>{admin.username}</span>
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
