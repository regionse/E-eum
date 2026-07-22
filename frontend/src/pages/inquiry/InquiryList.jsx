import { useState } from 'react'
import { Link } from 'react-router-dom'
import { listInquiries } from '../../api/content.js'
import { useAsync, Async, Modal, PageHead } from '../../components/ui/index.jsx'

const statusBadge = { 접수: 'badge-gray', 처리중: 'badge-amber', 답변완료: 'badge-teal' }

export default function InquiryList() {
  const state = useAsync(() => listInquiries(), [])
  const [open, setOpen] = useState(null)

  return (
    <div className="container page" style={{ maxWidth: 820 }}>
      <PageHead title="문의 내역" sub="문의하신 내용과 답변을 확인하세요."
        right={<Link to="/inquiry" className="btn btn-primary btn-sm">새 문의</Link>} />

      <div className="card" style={{ overflowX: 'auto' }}>
        <Async state={state}>
          {(rows) => (
            <table className="tbl">
              <thead><tr><th>번호</th><th>제목</th><th>유형</th><th>문의일</th><th>처리상태</th></tr></thead>
              <tbody>
                {rows.map((q) => (
                  <tr key={q.id} style={{ cursor: 'pointer' }} onClick={() => setOpen(q)}>
                    <td className="muted">{q.id}</td>
                    <td style={{ fontWeight: 600 }}>{q.title}</td>
                    <td className="muted">{q.type}</td>
                    <td className="muted">{q.date}</td>
                    <td><span className={`badge ${statusBadge[q.status]}`}>{q.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Async>
      </div>

      {open && (
        <Modal title={open.title} onClose={() => setOpen(null)}
          actions={<button className="btn btn-primary btn-block" onClick={() => setOpen(null)}>닫기</button>}>
          <div className="row" style={{ gap: 8, marginBottom: 12 }}>
            <span className="badge badge-gray">{open.type}</span>
            <span className={`badge ${statusBadge[open.status]}`}>{open.status}</span>
          </div>
          <div style={{ background: 'var(--bg)', borderRadius: 10, padding: 14, fontSize: 14.5, color: 'var(--ink-soft)' }}>{open.body}</div>
          {open.answer ? (
            <div style={{ background: 'var(--teal-50)', border: '1px solid var(--teal-100)', borderRadius: 10, padding: 14, marginTop: 10, fontSize: 14.5 }}>
              <div style={{ fontWeight: 700, color: 'var(--teal-700)', marginBottom: 4 }}>답변</div>
              {open.answer}
            </div>
          ) : <p className="muted" style={{ marginTop: 10, fontSize: 14 }}>아직 답변이 등록되지 않았어요.</p>}
        </Modal>
      )}
    </div>
  )
}
