import { useState } from 'react'
import { getDashboard } from '../../api/admin.js'
import { useAsync, Async, PageHead } from '../../components/ui/index.jsx'

// 간단한 SVG 꺾은선
function LineChart({ data }) {
  const w = 520, h = 180, pad = 28
  const max = Math.max(...data.map((d) => d.v))
  const pts = data.map((d, i) => {
    const x = pad + (i * (w - pad * 2)) / (data.length - 1)
    const y = h - pad - ((d.v / max) * (h - pad * 2))
    return [x, y]
  })
  const path = pts.map((p, i) => (i ? 'L' : 'M') + p[0] + ' ' + p[1]).join(' ')
  const area = `${path} L${pts[pts.length - 1][0]} ${h - pad} L${pts[0][0]} ${h - pad} Z`
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%' }}>
      <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="var(--teal-300)" stopOpacity=".4" /><stop offset="100%" stopColor="var(--teal-300)" stopOpacity="0" />
      </linearGradient></defs>
      <path d={area} fill="url(#g)" />
      <path d={path} fill="none" stroke="var(--teal-500)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      {pts.map((p, i) => (
        <g key={i}>
          <circle cx={p[0]} cy={p[1]} r="4" fill="#fff" stroke="var(--teal-500)" strokeWidth="2" />
          <text x={p[0]} y={h - 8} textAnchor="middle" fontSize="10" fill="var(--muted)">{data[i].d}</text>
        </g>
      ))}
    </svg>
  )
}
function BarChart({ data }) {
  const max = Math.max(...data.map((d) => d.v))
  return (
    <div className="stack" style={{ gap: 12 }}>
      {data.map((d) => (
        <div key={d.name}>
          <div className="row" style={{ justifyContent: 'space-between', fontSize: 13.5, marginBottom: 4 }}>
            <span>{d.name}</span><b>{d.v}</b>
          </div>
          <div style={{ height: 10, background: 'var(--teal-50)', borderRadius: 999 }}>
            <div style={{ width: `${(d.v / max) * 100}%`, height: '100%', background: 'var(--teal-400)', borderRadius: 999 }} />
          </div>
        </div>
      ))}
    </div>
  )
}

const PERIODS = ['최근 7일', '최근 30일', '최근 3개월', '1년']

export default function Dashboard() {
  const state = useAsync(() => getDashboard(), [])
  const [period, setPeriod] = useState('최근 7일')

  return (
    <div>
      <PageHead title="대시보드" sub="서비스 지표 한눈에 보기"
        right={<select className="select" style={{ width: 'auto' }} value={period} onChange={(e) => setPeriod(e.target.value)}>
          {PERIODS.map((p) => <option key={p} value={p}>기간 · {p}</option>)}
        </select>} />
      <Async state={state}>
        {(d) => (
          <>
            <div className="grid kpi-grid" style={{ marginBottom: 'var(--sp-5)' }}>
              {[
                ['총 사용자 수', d.kpis.totalUsers],
                ['오늘 로그인한 회원 수', d.kpis.todayLogins],
                ['API 호출 실패 횟수', d.kpis.apiFailures],
                ['오늘 AI 추천 실행 횟수', d.kpis.aiRuns],
              ].map(([l, n]) => (
                <div key={l} className="card kpi"><div className="n">{n.toLocaleString()}</div><div className="l">{l}</div></div>
              ))}
            </div>

            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 'var(--sp-4)' }}>
              <div className="card card-pad">
                <b style={{ display: 'block', marginBottom: 12 }}>AI 서비스 이용 추이</b>
                <LineChart data={d.aiTrend} />
              </div>
              <div className="card card-pad">
                <b style={{ display: 'block', marginBottom: 12 }}>기능별 AI 호출 횟수</b>
                <BarChart data={d.featureUsage} />
              </div>
            </div>

            <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>조회 시간 · 2026-07-16 15:00 (기간: {period})</p>
          </>
        )}
      </Async>
    </div>
  )
}
