import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listNotices } from '../../api/content.js'
import { useAsync, Async, PageHead, useToast } from '../../components/ui/index.jsx'

const TYPES = ['전체', '공지사항', '업데이트', '이벤트']
const STATUSES = ['전체', '활성', '비활성']
const typeBadge = { 공지사항: 'badge-gray', 업데이트: 'badge-teal', 이벤트: 'badge-amber' }
const PER = 10

export default function AdminNotices() {
  const nav = useNavigate()
  const toast = useToast()
  const state = useAsync(() => listNotices(), [])
  const [rows, setRows] = useState([])
  useEffect(() => { if (state.data) setRows(state.data.map((n) => ({ ...n }))) }, [state.data])

  const [type, setType] = useState('전체')
  const [statusF, setStatusF] = useState('전체')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)

  const toggleStatus = (id) => {
    const cur = rows.find((n) => n.id === id)
    const next = cur?.status === '활성' ? '비활성' : '활성'
    setRows((prev) => prev.map((n) => (n.id === id ? { ...n, status: next } : n)))
    toast.show(`게시 상태를 '${next}'로 바꿨어요`)
  }

  const filtered = rows.filter((n) =>
    (type === '전체' || n.type === type) &&
    (statusF === '전체' || n.status === statusF) &&
    (!query || n.title.includes(query) || n.body.includes(query))
  )
  const pages = Math.max(1, Math.ceil(filtered.length / PER))
  const cur = Math.min(page, pages)
  const view = filtered.slice((cur - 1) * PER, cur * PER)
  const runSearch = () => { setQuery(q.trim()); setPage(1) }

  return (
    <div>
      <PageHead title="공지사항 관리" sub="공지·업데이트·이벤트를 등록하고 관리해요."
        right={<button className="btn btn-primary btn-sm" onClick={() => nav('/admin/notices/new')}>+ 등록</button>} />

      <div className="row" style={{ gap: 8, marginBottom: 'var(--sp-4)', flexWrap: 'wrap' }}>
        <select className="select" style={{ width: 'auto' }} value={type} onChange={(e) => { setType(e.target.value); setPage(1) }}>
          {TYPES.map((t) => <option key={t} value={t}>유형 · {t}</option>)}
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
              <thead><tr><th style={{ width: 54 }}>No</th><th style={{ width: 92 }}>유형</th><th>제목</th><th style={{ width: 112 }}>작성일</th><th style={{ width: 88 }}>조회</th><th style={{ width: 90 }}>상태</th></tr></thead>
              <tbody>
                {view.length === 0 ? (
                  <tr><td colSpan={6} className="muted center" style={{ padding: 20 }}>조건에 맞는 공지가 없어요.</td></tr>
                ) : view.map((n) => (
                  <tr key={n.id}>
                    <td className="muted">{n.id.replace('N-', '')}</td>
                    <td><span className={`badge ${typeBadge[n.type]}`}>{n.type}</span></td>
                    <td>
                      <button onClick={() => nav(`/admin/notices/${n.id}`)}
                        style={{ fontWeight: 600, background: 'none', border: 0, padding: 0, cursor: 'pointer', color: 'var(--ink)', textAlign: 'left', textDecoration: 'underline', textDecorationColor: 'var(--teal-200)' }}>{n.title}</button>
                    </td>
                    <td className="muted">{n.date}</td>
                    <td className="muted">{n.views}</td>
                    <td>
                      <button onClick={() => toggleStatus(n.id)} title="클릭하면 활성/비활성 전환"
                        className={`badge ${n.status === '활성' ? 'badge-teal' : 'badge-gray'}`}
                        style={{ cursor: 'pointer', border: 0 }}>{n.status}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Async>
      </div>

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
      {toast.node}
    </div>
  )
}
