import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getInquiry } from '../../api/content.js'
import { useAsync, Async, PageHead, useToast } from '../../components/ui/index.jsx'

const statusBadge = { 접수: 'badge-gray', 처리중: 'badge-amber', 답변완료: 'badge-teal' }

// ADQNA-002 · 문의 상세 (별도 페이지) — 팝업이 아니라 화면으로
export default function AdminInquiryDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const toast = useToast()
  const state = useAsync(() => getInquiry(id), [id])

  return (
    <div>
      <PageHead title="문의 상세" sub="문의 내용을 확인하고 답변을 등록해요."
        right={<button className="btn btn-ghost btn-sm" onClick={() => nav('/admin/inquiries')}>← 목록으로</button>} />
      <Async state={state}>
        {(q) => q
          ? <Detail q={q} onList={() => nav('/admin/inquiries')}
              onSaved={(msg) => { toast.show(msg); nav('/admin/inquiries') }} />
          : <div className="card card-pad muted center">문의를 찾을 수 없어요.</div>}
      </Async>
      {toast.node}
    </div>
  )
}

function Detail({ q, onList, onSaved }) {
  const done = q.status === '답변완료'
  const [editing, setEditing] = useState(!done) // 답변완료면 읽기모드로 시작 · 미답변이면 바로 작성
  const [answer, setAnswer] = useState(q.answer || '')

  const submit = () => {
    if (!answer.trim()) return
    onSaved(done ? '답변이 수정되었어요' : '답변이 등록되었어요 (상태: 답변완료)')
  }

  return (
    <div className="card card-pad" style={{ maxWidth: 720 }}>
      <div className="row" style={{ gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <span className="badge badge-gray">{q.type}</span>
        <span className={`badge ${statusBadge[q.status]}`}>{q.status}</span>
        <span className="muted" style={{ fontSize: 13, marginLeft: 'auto' }}>문의번호 {q.id} · {q.date}</span>
      </div>
      <h3 style={{ margin: '2px 0 12px', fontSize: 18 }}>{q.title}</h3>
      <div style={{ background: 'var(--bg)', borderRadius: 10, padding: 14, fontSize: 14.5, color: 'var(--ink-soft)', marginBottom: 18, whiteSpace: 'pre-wrap' }}>{q.body}</div>

      <div className="field">
        <label>관리자 답변{!done && <span className="req">*</span>}</label>
        {editing ? (
          <textarea className="textarea" value={answer} onChange={(e) => setAnswer(e.target.value)}
            placeholder="답변을 입력하세요" style={{ minHeight: 140 }} />
        ) : (
          <div style={{ border: '1px solid var(--line)', borderRadius: 10, padding: 14, fontSize: 14.5, color: 'var(--ink)', minHeight: 60, whiteSpace: 'pre-wrap' }}>
            {q.answer || <span className="muted">등록된 답변이 없어요.</span>}
          </div>
        )}
      </div>

      <div className="row" style={{ gap: 8, marginTop: 8 }}>
        {done && !editing ? (
          // 답변완료 상태: [수정] [목록으로]
          <>
            <button className="btn btn-primary" onClick={() => setEditing(true)}>수정</button>
            <button className="btn btn-ghost" onClick={onList}>목록으로</button>
          </>
        ) : (
          // 미답변(접수·처리중) 또는 수정 중: [답변 등록/수정 완료] [목록으로]
          <>
            <button className="btn btn-primary" onClick={submit} disabled={!answer.trim()}>{done ? '수정 완료' : '답변 등록'}</button>
            <button className="btn btn-ghost" onClick={onList}>목록으로</button>
          </>
        )}
      </div>
    </div>
  )
}
