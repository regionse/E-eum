import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listInquiries } from '../../api/content.js'
import { useAsync, Async, PageHead } from '../../components/ui/index.jsx'

const statusBadge = { 접수: 'badge-gray', 처리중: 'badge-amber', 답변완료: 'badge-teal' }
const STATUSES = ['전체', '접수', '처리중', '답변완료']
const PER = 10

export default function AdminInquiries() {
  const nav = useNavigate()
  const state = useAsync(() => listInquiries(), [])
  const [rows, setRows] = useState([])
  useEffect(() => { if (state.data) setRows(state.data) }, [state.data])

  const [cat, setCat] = useState('전체')
  const [statusF, setStatusF] = useState('전체')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)

  const cats = ['전체', ...Array.from(new Set(rows.map((r) => r.type)))]
  const filtered = rows.filter((r) =>
    (cat === '전체' || r.type === cat) &&
    (statusF === '전체' || r.status === statusF) &&
    (!query || r.title.includes(query) || r.body.includes(query))
  )
  const pages = Math.max(1, Math.ceil(filtered.length / PER))
  const cur = Math.min(page, pages)
  const view = filtered.slice((cur - 1) * PER, cur * PER)
  const runSearch = () => { setQuery(q.trim()); setPage(1) }

  return (
    <div>
      <PageHead title="문의 관리" sub="사용자 문의를 확인하고 답변을 등록해요." />

      <div className="row" style={{ gap: 8, marginBottom: 'var(--sp-4)', flexWrap: 'wrap' }}>
        <select className="select" style={{ width: 'auto' }} value={cat} onChange={(e) => { setCat(e.target.value); setPage(1) }}>
          {cats.map((c) => <option key={c} value={c}>유형 · {c}</option>)}
        </select>
        <select className="select" style={{ width: 'auto' }} value={statusF} onChange={(e) => { setStatusF(e.target.value); setPage(1) }}>
          {STATUSES.map((s) => <option key={s} value={s}>상태 · {s}</option>)}
        </select>
        <div style={{ flex: 1, minWidth: 12 }} />
        <input className="input" style={{ maxWidth: 240 }} placeholder="제목·내용 검색" value={q}
          onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && runSearch()} />
        <button className="btn btn-ghost btn-sm" onClick={runSearch}>검색</button>
      </div>

      <div className="card" style={{ overflowX: 'auto' }}>
        <Async state={state}>
          {() => (
            <table className="tbl">
              <thead><tr><th style={{ width: 60 }}>번호</th><th>제목</th><th style={{ width: 110 }}>유형</th><th style={{ width: 112 }}>문의일</th><th style={{ width: 96 }}>상태</th></tr></thead>
              <tbody>
                {view.length === 0 ? (
                  <tr><td colSpan={5} className="muted center" style={{ padding: 20 }}>조건에 맞는 문의가 없어요.</td></tr>
                ) : view.map((r) => (
                  <tr key={r.id} style={{ cursor: 'pointer' }} onClick={() => nav(`/admin/inquiries/${r.id}`)}>
                    <td className="muted">{r.id}</td>
                    <td style={{ fontWeight: 600, textDecoration: 'underline', textDecorationColor: 'var(--teal-200)' }}>{r.title}</td>
                    <td className="muted">{r.type}</td>
                    <td className="muted">{r.date}</td>
                    <td><span className={`badge ${statusBadge[r.status]}`}>{r.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Async>
      </div>

      <div className="row" style={{ justifyContent: 'space-between', marginTop: 'var(--sp-4)', flexWrap: 'wrap', gap: 10 }}>
        <span className="muted" style={{ fontSize: 13.5 }}>총 {filtered.length}건 · 미답변 {rows.filter((r) => r.status !== '답변완료').length}건</span>
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
    </div>
  )
}
