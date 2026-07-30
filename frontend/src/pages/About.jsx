import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth.jsx'

/*
 * 소개 페이지 (/about · 정적)
 *   ① 서비스 소개  ② 가족돌봄청년  ③ 3축(덜다·잇다·나누다)  ④ 자료 출처
 */

// ② 대상·통계 (공개 실태조사 기반)
const STATS = [
  { n: '약 18만 명', l: '정부 추정 가족돌봄청년' },
  { n: '48.7%', l: '돌봄으로 학업·진로에 어려움' },
  { n: '4곳 → 17곳', l: '가족돌봄청년 전담 지원기관 (2025→2026)' },
]

// ③ 3축
const AXES = [
  { ic: '💧', name: '덜다', desc: '조건에 맞는 지원 제도를 찾아, 돌봄의 무게를 덜어드려요.', to: '/welfare' },
  { ic: '🌱', name: '잇다', desc: 'AI가 관심을 읽어 어울리는 직무·자격·무료강좌·국비훈련을 지도로 그려드려요.', to: '/learn' },
  { ic: '🤝', name: '나누다', desc: '전문 기관과 가족을 이어, 혼자 감당하지 않게 도와요.', to: '/share' },
]

// ④ 자료 출처
const SOURCES = [
  '보건복지부 · 한국사회보장정보원(복지로) — 복지 지원제도',
  '온통청년 · 고용24(HRD-Net) — 청년정책 · 국비 훈련',
  '한국산업인력공단 — NCS 직무 · 국가기술자격(Q-Net)',
  '국가평생교육진흥원(K-MOOC) — 무료 온라인 강좌',
  '통계청 · 한국보건사회연구원 — 가족돌봄청년 실태조사',
]

export default function About() {
  const { user } = useAuth()
  const nav = useNavigate()
  const start = () => nav(user ? '/welfare' : '/signup')

  return (
    <div className="container page">
      {/* 히어로 (소개만) */}
      <div className="center" style={{ maxWidth: 720, margin: '0 auto var(--sp-7)' }}>
        <span className="eyebrow">About · 이음 소개</span>
        <h1 className="section-title" style={{ fontSize: 32, margin: '8px 0 12px' }}>이음이 하는 일, 하지 않는 일</h1>
        <p className="muted" style={{ fontSize: 17, lineHeight: 1.75 }}>
          흩어진 복지·교육·돌봄 정보를, 가족을 돌보는 청년이 닿을 수 있는 언어로.<br />
          이음이 대신 읽고 이어드려요.
        </p>
      </div>

      {/* ① 서비스 소개 */}
      <section className="about-sec">
        <span className="badge badge-teal">① 서비스 소개</span>
        <h2 className="section-title" style={{ margin: '10px 0 8px' }}>이음이란?</h2>
        <p className="muted" style={{ fontSize: 15.5, maxWidth: 760, lineHeight: 1.8 }}>
          가족을 돌보느라 정작 자신을 돌보기 어려운 청년을 위한 <b>통합 돌봄 파트너</b>예요.
          복지·배움·돌봄이 여러 기관에 흩어져 찾기 어려운 것들을, 한곳에 모아 이어드려요.
        </p>
        <div className="principle" style={{ marginTop: 'var(--sp-5)' }}>
          <div style={{ fontWeight: 800, color: 'var(--teal-800)', marginBottom: 8 }}>이음이 하는 일</div>
          <ul>
            <li>몇 가지 질문만으로 내 조건에 맞는 지원제도를 찾아드려요 <b>(덜다)</b></li>
            <li>AI와 편하게 대화하면 어울리는 직무·자격·무료강좌·국비훈련을 지도로 이어드려요 <b>(잇다)</b></li>
            <li>전문 기관·가족과 이어, 혼자 감당하지 않게 나눠요 <b>(나누다)</b></li>
          </ul>
        </div>
        <div className="principle" style={{ marginTop: 'var(--sp-4)' }}>
          <div style={{ fontWeight: 800, color: 'var(--teal-800)', marginBottom: 8 }}>이음이 하지 않는 일</div>
          <ul>
            <li>지어낸 정보를 말하지 않아요 — 정책·직무·강좌는 정부 공공데이터에 근거해요</li>
            <li>당신의 사정을 앞질러 단정하지 않아요 — 방향은 대화로 함께 찾아요</li>
          </ul>
        </div>
      </section>

      {/* ② 가족돌봄청년 */}
      <section className="about-sec">
        <span className="badge badge-teal">② 가족돌봄청년이란</span>
        <h2 className="section-title" style={{ margin: '10px 0 8px' }}>누구를 위한 서비스인가요?</h2>
        <p className="muted" style={{ fontSize: 15.5, maxWidth: 760, marginBottom: 'var(--sp-5)', lineHeight: 1.8 }}>
          장애·질병·정신건강 문제를 가진 가족을 돌보는 만 13~34세 청년을 <b>가족돌봄청년(영 케어러)</b>이라고 해요.
          돌봄의 무게를 홀로 지느라 학업·일·건강을 놓치기 쉬워요.
        </p>
        <div className="grid" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
          {STATS.map((s) => (
            <div key={s.l} className="card card-pad center">
              <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--teal-700)' }}>{s.n}</div>
              <div className="muted" style={{ fontSize: 14, marginTop: 4 }}>{s.l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ③ 3축 */}
      <section className="about-sec">
        <span className="badge badge-teal">③ 이음의 3가지 축</span>
        <h2 className="section-title" style={{ margin: '10px 0 8px' }}>덜다 · 잇다 · 나누다</h2>
        <p className="muted" style={{ fontSize: 15.5, marginBottom: 'var(--sp-5)' }}>부담은 덜고, 배움을 잇고, 마음을 나눠요.</p>
        <div className="grid axis-grid">
          {AXES.map((a) => (
            <Link key={a.name} to={a.to} className="card card-pad card-hover">
              <h3>{a.ic} {a.name}</h3>
              <p className="muted" style={{ marginTop: 6, lineHeight: 1.7 }}>{a.desc}</p>
              <span className="go" style={{ color: 'var(--teal-600)', fontWeight: 700, fontSize: 14 }}>바로가기 →</span>
            </Link>
          ))}
        </div>
      </section>

      {/* ④ 자료 출처 */}
      <section className="about-sec">
        <span className="badge badge-teal">④ 자료 출처</span>
        <h2 className="section-title" style={{ margin: '10px 0 8px' }}>이 정보들은 어디서 왔나요?</h2>
        <p className="muted" style={{ fontSize: 15.5, marginBottom: 'var(--sp-4)' }}>
          이음의 제도·직무·강좌·훈련 정보는 아래 공공기관 자료를 근거로 해요.
        </p>
        <div className="card card-pad">
          <ul className="src-list">
            {SOURCES.map((s) => <li key={s}>📄 {s}</li>)}
          </ul>
        </div>
        <p className="muted center" style={{ fontSize: 13, marginTop: 'var(--sp-4)', lineHeight: 1.6 }}>
          * 잇다(직무·자격·강좌)는 실제 공공데이터로 동작해요. 일부 통계·예시 화면은 참고용으로 채워져 있어요.
        </p>
      </section>

      {/* 하단 CTA */}
      <div className="center" style={{ marginTop: 'var(--sp-7)' }}>
        <button className="btn btn-primary btn-lg" onClick={start}>내 정책 혜택 찾아보기</button>
      </div>
    </div>
  )
}
