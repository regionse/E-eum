import { useState } from 'react'
import { Link } from 'react-router-dom'
import { listNotices } from '../../api/content.js'
import { useAsync, Async, PageHead } from '../../components/ui/index.jsx'

const TYPES = ['전체', '공지사항', '업데이트', '이벤트']
const typeBadge = { 공지사항: 'badge-gray', 업데이트: 'badge-teal', 이벤트: 'badge-amber' }

export default function NoticeList() {
  const [type, setType] = useState('전체')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState({ type: '전체', q: '' })
  const state = useAsync(() => listNotices(query), [query])

  return (
    <div className="container page">
      <PageHead title="공지사항" sub="이음의 새 소식과 안내를 확인하세요." />

      <div className="row" style={{ gap: 8, marginBottom: 'var(--sp-4)', flexWrap: 'wrap' }}>
        {TYPES.map((t) => (
          <button key={t} className={`chip ${type === t ? 'on' : ''}`} onClick={() => { setType(t); setQuery({ type: t, q }) }}>{t}</button>
        ))}
        <div style={{ flex: 1 }} />
        <input className="input" style={{ maxWidth: 240 }} placeholder="검색어를 입력하세요"
          value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && setQuery({ type, q })} />
        <button className="btn btn-ghost btn-sm" onClick={() => setQuery({ type, q })}>검색</button>
      </div>

      <div className="card">
        <Async state={state} empty={<div className="empty"><div className="ic">🔍</div><p>검색 결과가 없어요.</p></div>}>
          {(rows) => rows.map((n) => (
            <Link key={n.id} to={`/notice/${n.id}`} className="list-row" style={{ display: 'flex' }}>
              <div className="row" style={{ gap: 12, minWidth: 0 }}>
                <span className={`badge ${typeBadge[n.type]}`}>{n.type}</span>
                <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{n.title}</span>
              </div>
              <div className="row muted" style={{ gap: 16, fontSize: 13.5, flexShrink: 0 }}>
                <span>조회 {n.views}</span><span>{n.date}</span>
              </div>
            </Link>
          ))}
        </Async>
      </div>
    </div>
  )
}
