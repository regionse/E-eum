import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHead } from '../components/ui/index.jsx'
import RequireLogin from '../components/RequireLogin.jsx'

// ALA-001 · 알림 — 알림 내역 + 이상징후 알림 (홈 > 알림)
// mock 데이터. 실제로는 돌봄일지 분석·제도 등록·문의 답변 등에서 생성됨.
const ALERTS = [
  { id: 'A1', author: '나', date: '2026-07-07', text: '저녁 약을 아직 체크하지 않았어요. 오늘 복약을 확인해 주세요.', anomaly: true },
  { id: 'A2', author: '가족', date: '2026-07-06', text: '어머니가 돌봄일지에 “무릎이 아프다”고 남기셨어요.', anomaly: false },
  { id: 'A3', author: '나', date: '2026-07-05', text: '이번 주 복약 누락이 지난주보다 늘었어요. 이상징후로 표시됐어요.', anomaly: true },
  { id: 'A4', author: '나', date: '2026-07-04', text: '내 조건에 맞는 새 지원제도가 등록됐어요.', anomaly: false },
]

export default function Alerts() {
  const [openAnomaly, setOpenAnomaly] = useState(true)

  return (
    <div className="container page" style={{ maxWidth: 720 }}>
      <PageHead title="🔔 알림" sub="돌봄 알림과 이상징후를 한곳에서 확인해요."
        right={<Link to="/" className="btn btn-ghost btn-sm">← 홈</Link>} />
      <RequireLogin axis="알림">
        <div className="stack" style={{ gap: 12 }}>
          {ALERTS.map((a) => (
            <div key={a.id} className="card card-pad" style={{ border: `1px solid ${a.anomaly ? 'var(--teal-300)' : 'var(--line)'}` }}>
              <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6, gap: 8 }}>
                <span className="row" style={{ gap: 8 }}>
                  <span className={`badge ${a.author === '나' ? 'badge-teal' : 'badge-gray'}`}>{a.author}</span>
                  {a.anomaly && <span className="badge badge-amber">이상징후</span>}
                </span>
                <span className="muted" style={{ fontSize: 13 }}>{a.date}</span>
              </div>
              <p style={{ lineHeight: 1.6 }}>{a.text}</p>
            </div>
          ))}
        </div>

        {/* 이상징후 알림 — 접기/펼치기 (돌봄일지 AI 분석과 연동되는 요약) */}
        <div className="card card-pad" style={{ marginTop: 14, border: '1px solid var(--teal-200)' }}>
          <div className="row" style={{ justifyContent: 'space-between', gap: 10 }}>
            <b>⚠️ 이상징후 알림</b>
            <button className="btn btn-ghost btn-sm" onClick={() => setOpenAnomaly((v) => !v)}>{openAnomaly ? '닫기' : '열기'}</button>
          </div>
          {openAnomaly && (
            <div style={{ marginTop: 12 }}>
              <p className="muted" style={{ lineHeight: 1.7 }}>
                지난 주 돌봄일지와 비교해 <b>복약 누락 증가</b> · <b>통증 호소 반복</b> 신호가 보여요. 필요한 지원서비스를 확인해 보세요.
              </p>
              <div className="row" style={{ gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                <Link to="/family/diary" className="btn btn-ghost btn-sm">돌봄일지 AI 분석 보기 →</Link>
                <Link to="/share/map" className="btn btn-ghost btn-sm">가까운 기관 찾기 →</Link>
              </div>
              <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>* 데모용 · 실제로는 돌봄일지 분석 결과와 연동돼요.</p>
            </div>
          )}
        </div>
      </RequireLogin>
    </div>
  )
}
