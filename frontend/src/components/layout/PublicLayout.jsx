import { NavLink, Link, Outlet } from 'react-router-dom'
import { useAuth } from '../../store/auth.jsx'

/*
 * 전체메뉴 = 페이지 흐름도 '전체메뉴' 반영
 *  - 비로그인 → 소개 · 공지 · 문의  +  [로그인] [회원가입]
 *  - 로그인   → 소개 · 공지 · 문의  +  [마이페이지 ▾] [🔔 알림] [로그아웃]
 *      · 마이페이지에 마우스를 올리면 → 덜다 · 잇다 · 나누다가 세로로 펼쳐지고(아코디언)
 *      · 각 축에 마우스를 올리면 → 그 "우측"에 세부 메뉴가 뜬다(flyout)
 */

// mock 알림 — 실제 알림 기능이 붙기 전까지 쓰는 예시 데이터
const NOTIS = [
  { id: 1, txt: '내 조건에 맞는 새 지원제도가 등록됐어요', time: '방금' },
  { id: 2, txt: '문의하신 내용에 답변이 달렸어요', time: '1시간 전' },
]

function NotiBell() {
  return (
    <div className="noti-wrap">
      <Link to="/alerts" className="noti-btn" aria-label="알림">
        🔔{NOTIS.length > 0 && <span className="noti-dot" />}
      </Link>
      <div className="noti-menu">
        <div className="grp">알림</div>
        {NOTIS.length === 0 ? (
          <div className="noti-empty">새 알림이 없어요</div>
        ) : (
          NOTIS.map((n) => (
            <div key={n.id} className="noti-item">
              <span className="noti-txt">{n.txt}</span>
              <span className="noti-time">{n.time}</span>
            </div>
          ))
        )}
        <Link to="/alerts" style={{ display: 'block', padding: '9px 14px', fontSize: 13, fontWeight: 700, color: 'var(--teal-700)', borderTop: '1px solid var(--line)' }}>알림 전체보기 →</Link>
      </div>
    </div>
  )
}

// 마이페이지 ▾ (hover 시 계정 + 3축 아코디언, 각 축 hover 시 우측 flyout)
function MyPageMenu() {
  return (
    <div className="mypage-wrap">
      <NavLink to="/mypage" className="btn btn-soft" style={{ fontSize: 15 }}>마이페이지 ▾</NavLink>
      <div className="mypage-menu">
        <div className="grp">계정</div>
        <Link to="/mypage">내정보</Link>
        <Link to="/mypage/consent">동의관리</Link>
        <Link to="/mypage/withdraw">회원탈퇴</Link>
        {/* 서비스(잇다·덜다·나누다)는 상단 메뉴/홈에서 진입 — 마이페이지 드롭다운에서 제거(2026-07-29) */}
      </div>
    </div>
  )
}

export function Header() {
  const { user, logout } = useAuth()
  return (
    <header className="header">
      <div className="container">
        <Link to="/" className="brand"><span className="dot" />이음</Link>

        {/* 공통 메뉴 — 로그인 여부와 무관하게 항상 노출 */}
        <nav className="gnb">
          <NavLink to="/welfare">덜다</NavLink>
          <NavLink to="/learn">잇다</NavLink>
          <NavLink to="/share">나누다</NavLink>
          <span className="gnb-sep" />
          <NavLink to="/about">소개</NavLink>
          <NavLink to="/notice">공지</NavLink>
          <NavLink to="/inquiry">문의</NavLink>
        </nav>

        <div className="gnb-right">
          {user ? (
            <>
              <MyPageMenu />
              <NotiBell />
              <button className="btn btn-plain" style={{ fontSize: 14.5, padding: '9px 16px' }} onClick={logout}>로그아웃</button>
            </>
          ) : (
            <Link to="/login" className="btn btn-primary">로그인</Link>
          )}
        </div>
      </div>
    </header>
  )
}

export function Footer() {
  return (
    <footer className="footer">
      <div className="container">
        <div className="brand">이음</div>
        <div className="footer-links">
          <a href="tel:0263530336">가족돌봄청년 지원 전담기구 ☎ 02-6353-0336~9</a>
        </div>
        <div className="credit">© 2026 이음 · 가족돌봄청년 통합 돌봄 파트너</div>
      </div>
    </footer>
  )
}

export default function PublicLayout() {
  return (
    <>
      <Header />
      <main><Outlet /></main>
      <Footer />
    </>
  )
}
