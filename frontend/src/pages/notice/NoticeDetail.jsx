import { useParams, Link } from 'react-router-dom'
import { getNotice } from '../../api/content.js'
import { useAsync, Async } from '../../components/ui/index.jsx'

export default function NoticeDetail() {
  const { id } = useParams()
  const state = useAsync(() => getNotice(id), [id])

  return (
    <div className="container page" style={{ maxWidth: 760 }}>
      <Async state={state} empty={<div className="empty">공지를 찾을 수 없어요.</div>}>
        {(n) => (
          <>
            <Link to="/notice" className="btn btn-plain btn-sm" style={{ marginBottom: 12 }}>← 목록으로</Link>
            <div className="card card-pad">
              <span className="badge badge-teal">{n.type}</span>
              <h1 className="section-title" style={{ margin: '12px 0 8px' }}>{n.title}</h1>
              <div className="row muted" style={{ gap: 16, fontSize: 13.5, borderBottom: '1px solid var(--line)', paddingBottom: 14 }}>
                <span>작성일 {n.date}</span><span>조회수 {n.views}</span>
              </div>
              <p style={{ marginTop: 18, color: 'var(--ink-soft)', lineHeight: 1.8 }}>{n.body}</p>
            </div>
          </>
        )}
      </Async>
    </div>
  )
}
