import { Link } from 'react-router-dom'

// 인증 화면 공통 껍데기: 좌측 브랜드 소개 + 우측 폼
export default function AuthShell({ title, sub, children, foot }) {
  return (
    <div className="container page" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-7)', alignItems: 'center', maxWidth: 900 }}>
      <div className="auth-aside" style={{ background: 'linear-gradient(160deg,var(--teal-50),var(--sand-50))', borderRadius: 'var(--radius-lg)', padding: 'var(--sp-7)', border: '1px solid var(--line)' }}>
        <Link to="/" className="brand" style={{ fontSize: 24 }}><span className="dot" />이음</Link>
        <h2 style={{ marginTop: 16, fontSize: 24, letterSpacing: '-.02em' }}>덜다 · 잇다 · 나누다</h2>
        <p className="muted" style={{ marginTop: 8 }}>가입하면 세 가지 도움을 이어드려요.</p>
        <ul className="principle" style={{ marginTop: 20, background: 'transparent', border: 'none', padding: 0 }}>
          <li>맞춤 지원 정책을 찾아드려요</li>
          <li>목표에 맞는 무료 배움을 이어요</li>
          <li>전문가·가족과 나눠요</li>
        </ul>
      </div>
      <div>
        <h1 className="section-title" style={{ fontSize: 26 }}>{title}</h1>
        {sub && <p className="section-sub">{sub}</p>}
        <div className="card card-pad">{children}</div>
        {foot && <div className="center muted" style={{ marginTop: 16, fontSize: 14 }}>{foot}</div>}
      </div>
    </div>
  )
}
