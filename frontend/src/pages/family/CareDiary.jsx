import { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHead, Empty } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import { useFamily, fmtBoardTime, TODAY } from '../../store/family.jsx'

const PER = 10
const AUTHORS = ['전체', '나', '어머니']
const PERIODS = ['전체', '이번 달', '최근 7일']

const summarize = (body) => {
  const first = body.split('\n')[0]
  const rest = body.includes('\n')
  if (first.length > 44) return first.slice(0, 44) + '…'
  return rest ? first + ' …' : first
}
// TODAY(2026-07-07) 기준 최근 7일 / 이번 달 필터
const inPeriod = (date, period) => {
  if (period === '전체') return true
  if (period === '이번 달') return date.slice(0, 7) === TODAY.slice(0, 7)
  const diff = (new Date(`${TODAY}T00:00:00`) - new Date(`${date}T00:00:00`)) / 86400000
  return diff >= 0 && diff <= 6
}

// AI 분석 mock (SHA-202③): 최근 7일 돌봄일지에서 복약 누락·본문 신호어를 추려 지원서비스를 제안.
//  실제 서비스에선 '지난 주' 일지와 비교해 LLM이 이상징후를 판단한다.
const SIGNALS = [
  { words: ['아파', '아프', '통증', '열', '어지', '넘어', '붓', '숨'],
    label: '통증·건강 이상 신호', service: '재가 방문진료·장기요양', desc: '집으로 찾아오는 진료·요양으로 건강 상태를 살펴요' },
  { words: ['불면', '잠', '우울', '힘들', '지쳐', '외로', '눈물'],
    label: '수면·정서 신호', service: '정신건강복지센터 상담', desc: '무료 심리상담·사례관리로 마음을 돌봐요' },
  { words: ['식사', '안 먹', '못 먹', '입맛', '굶'],
    label: '식사·영양 신호', service: '재가노인 영양·식사 지원', desc: '끼니를 챙기기 어려울 때 식사를 지원해요' },
]

function analyzeDiary(records) {
  const recent = records.filter((r) => {
    const diff = (new Date(`${TODAY}T00:00:00`) - new Date(`${r.date}T00:00:00`)) / 86400000
    return diff >= 0 && diff <= 6
  })
  const base = recent.length ? recent : records
  const missed = base.reduce((n, r) => n + ['m', 'l', 'd'].filter((k) => r.meds && r.meds[k] === false).length, 0)
  const findings = []
  if (missed >= 2) findings.push({ label: `복약 누락 ${missed}회`, service: '방문간호·복약지도', desc: '간호사가 방문해 약 복용을 도와요' })
  SIGNALS
    .map((s) => ({ ...s, count: base.filter((r) => s.words.some((w) => r.body.includes(w))).length }))
    .filter((s) => s.count > 0)
    .sort((a, b) => b.count - a.count)
    .forEach((s) => findings.push({ label: `${s.label} ${s.count}건`, service: s.service, desc: s.desc }))
  return { count: base.length, anomaly: findings.length > 0, findings }
}

function ConnectPrompt() {
  return (
    <div className="card card-pad center" style={{ maxWidth: 460, margin: '0 auto', padding: 'var(--sp-7)' }}>
      <div style={{ fontSize: 40 }}>🔗</div>
      <h3 style={{ margin: '12px 0 8px' }}>가족과 연결하면 볼 수 있어요</h3>
      <p className="muted">돌봄일지는 연결된 가족만 열람할 수 있어요.</p>
      <Link to="/family" className="btn btn-primary" style={{ marginTop: 18 }}>가족편지로 가기</Link>
    </div>
  )
}

export default function CareDiary() {
  const { familyLinked } = useAuth()
  const { records } = useFamily()
  const nav = useNavigate()
  const [author, setAuthor] = useState('전체')
  const [period, setPeriod] = useState('전체')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [aiOpen, setAiOpen] = useState(true)
  const analysis = useMemo(() => analyzeDiary(records), [records])

  const filtered = useMemo(() => records.filter((r) =>
    (author === '전체' || r.author === author) &&
    inPeriod(r.date, period) &&
    (!query || r.body.toLowerCase().includes(query.toLowerCase()))
  ), [records, author, period, query])

  const pages = Math.max(1, Math.ceil(filtered.length / PER))
  const cur = Math.min(page, pages)
  const rows = filtered.slice((cur - 1) * PER, cur * PER)

  const apply = (patch) => { setPage(1); patch() }
  const runSearch = () => apply(() => setQuery(q.trim()))

  return (
    <div className="container page">
      <PageHead title="📔 돌봄일지"
        sub="가족이 남긴 돌봄 기록 전체 · 행을 누르면 전체 내용을 볼 수 있어요."
        right={<Link to="/family" className="btn btn-ghost btn-sm">← 가족편지</Link>} />
      <RequireLogin axis="돌봄일지">
        {!familyLinked ? <ConnectPrompt /> : (
          <>
            {/* 필터 */}
            <div className="row" style={{ gap: 8, marginBottom: 'var(--sp-4)', flexWrap: 'wrap' }}>
              <select className="select" style={{ width: 'auto' }} value={author}
                onChange={(e) => apply(() => setAuthor(e.target.value))}>
                {AUTHORS.map((a) => <option key={a} value={a}>작성자 · {a}</option>)}
              </select>
              <select className="select" style={{ width: 'auto' }} value={period}
                onChange={(e) => apply(() => setPeriod(e.target.value))}>
                {PERIODS.map((p) => <option key={p} value={p}>기간 · {p}</option>)}
              </select>
              <div style={{ flex: 1, minWidth: 12 }} />
              <input className="input" style={{ maxWidth: 220 }} placeholder="내용 검색"
                value={q} onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && runSearch()} />
              <button className="btn btn-ghost btn-sm" onClick={runSearch}>검색</button>
            </div>

            {/* 게시판 */}
            <div className="card" style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th style={{ width: 150 }}>날짜·시각</th>
                    <th style={{ width: 96 }}>작성자</th>
                    <th>돌봄 내용</th>
                    <th style={{ width: 32 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr><td colSpan={4}><Empty icon="🔍">조건에 맞는 기록이 없어요.</Empty></td></tr>
                  ) : rows.map((r) => (
                    <tr key={r.id} style={{ cursor: 'pointer' }} onClick={() => nav(`/family/diary/${r.id}`)}>
                      <td className="muted" style={{ whiteSpace: 'nowrap' }}>{fmtBoardTime(r)}</td>
                      <td><span className={`badge ${r.author === '나' ? 'badge-teal' : 'badge-gray'}`}>{r.author}</span></td>
                      <td style={{ fontWeight: 500 }}>{summarize(r.body)}</td>
                      <td className="muted" style={{ textAlign: 'right' }}>›</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 페이지네이션 */}
            <div className="row" style={{ justifyContent: 'space-between', marginTop: 'var(--sp-4)', flexWrap: 'wrap', gap: 10 }}>
              <span className="muted" style={{ fontSize: 13.5 }}>총 {filtered.length}건</span>
              {pages > 1 && (
                <div className="pager" style={{ margin: 0 }}>
                  <button onClick={() => setPage(Math.max(1, cur - 1))} disabled={cur === 1}>‹</button>
                  {Array.from({ length: pages }, (_, i) => i + 1).map((p) => (
                    <button key={p} className={p === cur ? 'on' : ''} onClick={() => setPage(p)}>{p}</button>
                  ))}
                  <button onClick={() => setPage(Math.min(pages, cur + 1))} disabled={cur === pages}>›</button>
                </div>
              )}
            </div>
            {/* AI 분석 (SHA-202③) — 지난 주 일지와 비교해 이상징후 → 지원서비스 추천. 닫기/열기 */}
            <div className="card card-pad" style={{ marginTop: 'var(--sp-4)', border: '1px solid var(--teal-200)' }}>
              <div className="row" style={{ justifyContent: 'space-between', gap: 10 }}>
                <span style={{ fontWeight: 800, display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  AI 분석
                  {analysis.count > 0 && (
                    <span className={`badge ${analysis.anomaly ? 'badge-amber' : 'badge-gray'}`}>
                      {analysis.anomaly ? '이상징후' : '안정'}
                    </span>
                  )}
                </span>
                <button className="btn btn-ghost btn-sm" onClick={() => setAiOpen((v) => !v)}>{aiOpen ? '닫기' : '열기'}</button>
              </div>

              {aiOpen && (
                <div style={{ marginTop: 14 }}>
                  {analysis.count === 0 ? (
                    <p className="muted">아직 분석할 돌봄 기록이 없어요. 기록이 쌓이면 지난 주와 비교해 이상징후를 알려드려요.</p>
                  ) : (
                    <>
                      <p className="muted" style={{ marginBottom: 12 }}>
                        최근 7일 돌봄 기록 <b>{analysis.count}건</b>을 지난 주와 비교했어요.
                      </p>
                      {analysis.anomaly ? (
                        <div style={{ display: 'grid', gap: 12 }}>
                          {/* 여러 건이 잡혀도 가장 우선순위 높은 1건만 노출 (복약 누락 > 신호 count 순) */}
                          {analysis.findings.slice(0, 1).map((f, i) => (
                            <div key={i} className="callout-warn">
                              <div style={{ fontWeight: 700, marginBottom: 4 }}>⚠️ 이상징후 · {f.label}</div>
                              <div style={{ fontSize: 14.5 }}>
                                추천 지원서비스 — <b>{f.service}</b><br />
                                <span className="muted">{f.desc}</span>
                              </div>
                              <Link to="/share/map" className="btn btn-ghost btn-sm" style={{ marginTop: 10 }}>가까운 기관 찾기 →</Link>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p style={{ lineHeight: 1.7 }}>최근 기록에서 특별한 이상징후는 보이지 않아요. 지금처럼 꾸준히 기록해 주세요. 🌿</p>
                      )}
                      <p className="muted" style={{ marginTop: 14, fontSize: 12.5 }}>
                        * 데모용 분석이에요. 실제 서비스에선 지난 주 돌봄일지와 비교해 AI가 이상징후를 판단하고 맞춤 지원서비스를 추천해요.
                      </p>
                    </>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </RequireLogin>
    </div>
  )
}
