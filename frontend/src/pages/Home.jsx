import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth.jsx'

// 덜다 · 잇다 · 나누다 (전체 기능 소개)
const AXES = [
  { to: '/welfare', ic: '💧', name: '덜다', desc: '조건에 맞는 지원 제도를 찾아, 오늘을 버틸 힘을 드려요.', tag: '맞춤 정책 찾기' },
  { to: '/learn', ic: '🌱', name: '잇다', desc: '무료 강좌·자격으로 내일의 나로 이어드려요.', tag: '미래설계지도' },
  { to: '/share', ic: '🤝', name: '나누다', desc: '혼자 안고 있지 않게, 가족·전문가와 나눠요.', tag: '가족편지 · 기관연결' },
]

export default function Home() {
  const { user } = useAuth()
  const nav = useNavigate()
  const startFind = () => nav(user ? '/welfare' : '/signup')

  return (
    <>
      <section className="hero">
        <div className="container hero-inner">
          <div>
            <span className="eyebrow">덜다 · 잇다 · 나누다</span>
            <h1>가족을 돌보는 청년을 위한<br />통합 돌봄 파트너</h1>
            <p className="lead">
              흩어진 복지·교육 제도를, 청년이 닿을 수 있는 언어로.<br />
              이음이 대신 읽고 건네드려요.
            </p>
            <div className="hero-cta">
              <button className="btn btn-primary btn-lg" onClick={startFind}>내 혜택 찾기</button>
              <Link to="/about" className="btn btn-ghost btn-lg">이음 살펴보기</Link>
            </div>
          </div>
          <div className="hero-visual">🤝</div>
        </div>
      </section>

      {/* 전체 기능 소개 */}
      <section className="container" style={{ padding: 'var(--sp-6) 0 var(--sp-7)' }}>
        <div className="grid axis-grid">
          {AXES.map((a) => (
            <Link key={a.to} to={a.to} className="card card-hover axis-card" style={{ alignItems: 'center', textAlign: 'center' }}>
              <div className="ic">{a.ic}</div>
              <h3>{a.name}</h3>
              <p className="muted">{a.desc}</p>
              <div className="row" style={{ justifyContent: 'space-between', width: '100%', marginTop: 'auto', gap: 8 }}>
                <span className="badge badge-gray">{a.tag}</span>
                <span style={{ color: 'var(--teal-600)', fontWeight: 700, fontSize: 14, whiteSpace: 'nowrap' }}>바로가기 →</span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </>
  )
}
