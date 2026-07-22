import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth.jsx'

/*
 * 소개 페이지 (/about · 정적) — 흐름도 '소개?' 반영
 *  상단 CTA: [시작하기] · [내 혜택 찾아보기](→덜다 정보입력) · [문의하기](→문의)
 *  스크롤 섹션 4개:
 *   ① 서비스 소개 (이음이란?)  ② 가족돌봄청년 소개 (대상·통계)
 *   ③ 3축 소개 (덜다·잇다·나누다)  ④ 자료 출처
 */

// ② 대상·통계
const STATS = [
  { n: '약 18만 명', l: '정부 추정 가족돌봄청년' },
  { n: '48.7%', l: '돌봄으로 학업·진로에 어려움' },
  { n: '4곳 → 17곳', l: '가족돌봄청년 전담 지원기관 (2025→2026)' },
]

// ③ 3축
const AXES = [
  { ic: '💧', name: '덜다', desc: '조건에 맞는 지원 제도를 찾아드려요.', to: '/welfare' },
  { ic: '🌱', name: '잇다', desc: '목표에 맞는 무료 강좌·자격으로 미래설계지도를 그려드려요.', to: '/learn' },
  { ic: '🤝', name: '나누다', desc: '전문 기관과 가족을 이어, 혼자 감당하지 않게 도와요.', to: '/share' },
]

// ④ 자료 출처
const SOURCES = [
  '보건복지부 · 한국사회보장정보원(복지로)',
  '통계청 · 한국보건사회연구원 — 가족돌봄청년 실태조사',
  '국가평생교육진흥원(K-MOOC) · 한국산업인력공단(Q-Net)',
]

export default function About() {
  const { user } = useAuth()
  const nav = useNavigate()
  const start = () => nav(user ? '/welfare' : '/signup')

  return (
    <div className="container page">
      {/* 히어로 + CTA (시작하기 / 내 혜택 찾아보기 / 문의하기) */}
      <div className="center" style={{ maxWidth: 720, margin: '0 auto var(--sp-7)' }}>
        <span className="eyebrow">About · 이음 소개</span>
        <h1 className="section-title" style={{ fontSize: 32, margin: '8px 0 12px' }}>이음이 하는 일, 하지 않는 일</h1>
        <p className="muted" style={{ fontSize: 17 }}>
          이음은 제도 정책, 교육 강좌를 청년들에게 쉽게 연결시키는 <b>사이트</b>예요.
        </p>
        <div className="row" style={{ justifyContent: 'center', gap: 10, marginTop: 'var(--sp-5)', flexWrap: 'wrap' }}>
          <button className="btn btn-primary btn-lg" onClick={start}>시작하기</button>
          <Link to="/welfare/policy" className="btn btn-soft btn-lg">내 혜택 찾아보기</Link>
          <Link to="/inquiry" className="btn btn-ghost btn-lg">문의하기</Link>
        </div>
      </div>

      {/* ① 서비스 소개 (이음이란?) */}
      <section className="about-sec">
        <span className="badge badge-teal">① 서비스 소개</span>
        <h2 className="section-title" style={{ margin: '10px 0 8px' }}>이음이란?</h2>
        <p className="muted" style={{ fontSize: 15.5, maxWidth: 760 }}>
          가족을 돌보느라 정작 자신을 돌보기 어려운 청년을 위한 <b>통합 돌봄 파트너</b>예요.
          흩어진 복지·교육·돌봄 정보를 한곳에 모아 알려드려요
        </p>
        <div className="principle" style={{ marginTop: 'var(--sp-5)' }}>
          <div style={{ fontWeight: 800, color: 'var(--teal-800)', marginBottom: 8 }}>이음의 장점이에요</div>
          <ul>
            <li>간편한 몇 가지 질문으로 조건에 알맞는 정보를 찾을 수 있어요</li>
            <li>모든 데이터들은 정부 공식 데이터들로 이루어져있어요</li>
          </ul>
        </div>
      </section>

      {/* ② 가족돌봄청년 소개 (대상·통계) */}
      <section className="about-sec">
        <span className="badge badge-teal">② 가족돌봄청년이란</span>
        <h2 className="section-title" style={{ margin: '10px 0 8px' }}>누구를 위한 서비스인가요?</h2>
        <p className="muted" style={{ fontSize: 15.5, maxWidth: 760, marginBottom: 'var(--sp-5)' }}>
          장애·질병·정신건강 문제를 가진 가족을 돌보는 만 13~34세 청년을 <b>가족돌봄청년(영 케어러)</b>이라고 해요.
            돌봄의 무게를 홀로 지느라 학업·일·건강을 놓치기 쉬워요
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

      {/* ③ 3축 소개 (덜다·잇다·나누다) */}
      <section className="about-sec">
        <span className="badge badge-teal">③ 이음의 3가지 축</span>
        <h2 className="section-title" style={{ margin: '10px 0 8px' }}>덜다 · 잇다 · 나누다</h2>
        <p className="muted" style={{ fontSize: 15.5, marginBottom: 'var(--sp-5)' }}>부담은 덜고, 배움을 잇고, 마음을 나눠요.</p>
        <div className="grid axis-grid">
          {AXES.map((a) => (
            <Link key={a.name} to={a.to} className="card card-pad card-hover">
              <h3>{a.ic} {a.name}</h3>
              <p className="muted" style={{ marginTop: 6 }}>{a.desc}</p>
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
          이음의 모든 제도·통계·자료는 아래 공공기관 자료를 근거로 해요.
        </p>
        <div className="card card-pad">
          <ul className="src-list">
            {SOURCES.map((s) => <li key={s}>📄 {s}</li>)}
          </ul>
        </div>
        <p className="muted center" style={{ fontSize: 13, marginTop: 'var(--sp-4)' }}>
          * 해커톤 프로토타입 · 통계와 출처는 예시(mock)로 채워져 있어요.
        </p>
      </section>

      {/* 하단 CTA 반복 */}
      <div className="center" style={{ marginTop: 'var(--sp-7)' }}>
        <button className="btn btn-primary btn-lg" onClick={start}>지금 시작하기</button>
      </div>
    </div>
  )
}
