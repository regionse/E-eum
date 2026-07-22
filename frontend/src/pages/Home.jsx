import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth.jsx'

// 덜다 · 잇다 · 나누다 (전체 기능 소개)
const AXES = [
  { to: '/welfare', ic: '💧', name: '덜다', desc: '조건에 맞는 지원 제도를 찾아, 오늘을 버틸 힘을 드려요.', tag: '맞춤 정책 찾기' },
  { to: '/learn', ic: '🌱', name: '잇다', desc: '무료 강좌·자격으로 내일의 나로 이어드려요.', tag: '미래설계지도' },
  { to: '/share', ic: '🤝', name: '나누다', desc: '혼자 안고 있지 않게, 가족·전문가와 나눠요.', tag: '가족편지 · 기관연결' },
]

// 자가 인식 후크 (스스로 대상인 줄 모르는 청년을 부드럽게 안내)
const SIGNS = [
  '아픈 가족을 돌보느라 학업이나 일이 자주 밀려요.',
  '병원비·약값이 부담돼요.',
  '쉴 틈 없이 돌봄과 생계를 함께 감당하고 있어요.',
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
              <Link to="/about" className="btn btn-ghost btn-lg">둘러보기</Link>
            </div>
          </div>
          <div className="hero-visual">🤝</div>
        </div>
      </section>

      {!user && (
        <section className="container" style={{ paddingTop: 'var(--sp-7)' }}>
          <div className="card card-pad" style={{ background: 'var(--teal-50)', borderColor: 'var(--teal-100)' }}>
            <h2 className="section-title" style={{ marginBottom: 4 }}>혹시, 당신도?</h2>
            <p className="section-sub">‘복지 대상자’라는 말은 낯설어도 괜찮아요. 이런 하루를 보내고 있다면 —</p>
            <div className="stack" style={{ gap: 8 }}>
              {SIGNS.map((s) => (
                <div key={s} className="row" style={{ gap: 10, color: 'var(--teal-800)' }}>
                  <span aria-hidden style={{ color: 'var(--teal-500)', fontWeight: 800 }}>✓</span>
                  <span>{s}</span>
                </div>
              ))}
            </div>
            <div className="row" style={{ gap: 12, marginTop: 'var(--sp-5)', flexWrap: 'wrap' }}>
              <button className="btn btn-primary" onClick={startFind}>받을 수 있는 지원 찾아보기</button>
              <span className="muted" style={{ fontSize: 14 }}>익명으로, 몇 가지만 답하면 돼요.</span>
            </div>
          </div>
        </section>
      )}

      {/* 전체 기능 소개 */}
      <section className="container page">
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
