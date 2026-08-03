import { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHead, Empty } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import {
  useFamily,
  fmtBoardTime,
  TODAY,
} from '../../store/family.jsx'
import { analyzeWeeklyCare, recommendFacility, getCurrentPosition,} from '../../api/share.js'



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
  const [recommendation, setRecommendation] = useState(null)
  const { familyLinked } = useAuth()
  const { records, careGroupId } = useFamily()
  const nav = useNavigate()
  const [author, setAuthor] = useState('전체')
  const [period, setPeriod] = useState('전체')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')

  const [page, setPage] = useState(1)
  const [aiOpen, setAiOpen] = useState(true)

  const [analysisResult, setAnalysisResult] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState('')


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
  const handleAnalyze = async () => {
    if (!careGroupId) {
      setAnalysisError('연결된 가족방이 없습니다.')
      return
    }

    try {
      setAnalyzing(true)
      setAnalysisError('')
      setAnalysisResult(null)
      setRecommendation(null)

      // 1. 주간 분석
      const analysis = await analyzeWeeklyCare({
        careGroupId,
        
      })

      setAnalysisResult(analysis)
      setAiOpen(true)

      // 2. 이상징후가 없으면 기관을 추천하지 않음
      if (!analysis.anomaly_flag) {
        return
      }

      // 3. 현재 위치 확인
      const position = await getCurrentPosition()

      // 4. 가장 가까운 기관 추천
      const facility = await recommendFacility({
        careGroupId,
        latitude: position.latitude,
        longitude: position.longitude,
      })

      setRecommendation({
        ...facility,
        user_latitude: position.latitude,
        user_longitude: position.longitude,
      })
    } catch (error) {
      setAnalysisError(
        error.message || '주간 분석 및 기관 추천에 실패했습니다.',
      )
    } finally {
      setAnalyzing(false)
    }
  }

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
            {/* 실제 주간 돌봄 분석 */}
            <div
              className="card card-pad"
              style={{
                marginTop: 'var(--sp-4)',
                border: '1px solid var(--teal-200)',
              }}
            >
              <div
                className="row"
                style={{
                  justifyContent: 'space-between',
                  gap: 10,
                }}
              >
                <span
                  style={{
                    fontWeight: 800,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  AI 주간 분석

                  {analysisResult && (
                    <span
                      className={`badge ${
                        analysisResult.anomaly_flag
                          ? 'badge-amber'
                          : 'badge-gray'
                      }`}
                    >
                      {analysisResult.anomaly_flag
                        ? '이상징후'
                        : '안정'}
                    </span>
                  )}
                </span>

                <div className="row" style={{ gap: 8 }}>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleAnalyze}
                    disabled={analyzing || records.length === 0}
                  >
                    {analyzing ? '분석 중...' : '이번 주 분석'}
                  </button>

                  {analysisResult && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setAiOpen((value) => !value)}
                    >
                      {aiOpen ? '닫기' : '열기'}
                    </button>
                  )}
                </div>
              </div>

              {records.length === 0 && (
                <p className="muted" style={{ marginTop: 14 }}>
                  아직 분석할 돌봄 기록이 없습니다.
                </p>
              )}

              {analysisError && (
                <div
                  className="callout-warn"
                  style={{ marginTop: 14 }}
                >
                  {analysisError}
                </div>
              )}

              {aiOpen && analysisResult && (
                <div style={{ marginTop: 14 }}>
                  <p style={{ lineHeight: 1.7 }}>
                    {analysisResult.summary ||
                      '주간 요약 내용이 없습니다.'}
                  </p>

                  <div
                    className={
                      analysisResult.anomaly_flag
                        ? 'callout-warn'
                        : ''
                    }
                    style={{ marginTop: 12 }}
                  >
                    <strong>
                      {analysisResult.anomaly_flag
                        ? '⚠️ 이상징후가 감지되었습니다.'
                        : '🌿 특별한 이상징후가 감지되지 않았습니다.'}
                    </strong>

                    {analysisResult.anomaly_detail && (
                      <p
                        className="muted"
                        style={{ marginTop: 8, lineHeight: 1.7 }}
                      >
                        {analysisResult.anomaly_detail}
                      </p>
                    )}
                  </div>

                  {recommendation && (
                    <div
                      className="card card-pad"
                      style={{ marginTop: 14 }}
                    >
                      <h3 style={{ marginBottom: 10 }}>
                        추천 지원 기관
                      </h3>

                      <p style={{ fontWeight: 700 }}>
                        {recommendation.facility_name}
                      </p>

                      {recommendation.recommendation_reason && (
                        <p
                          className="muted"
                          style={{ marginTop: 8, lineHeight: 1.7 }}
                        >
                          {recommendation.recommendation_reason}
                        </p>
                      )}

                      <p className="muted" style={{ marginTop: 8 }}>
                        {recommendation.address ||
                          recommendation.map_address ||
                          '주소 정보 없음'}
                      </p>

                      {recommendation.phone && (
                        <p className="muted">
                          전화번호: {recommendation.phone}
                        </p>
                      )}

                      <Link
                        to="/share/map"
                        state={{ recommendation }}
                        className="btn btn-primary btn-sm"
                        style={{ marginTop: 12 }}
                      >
                        가까운 지원 기관 확인 →
                      </Link>
                    </div>
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
