import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { PageHead, Empty, Modal, useToast } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import { useFamily, fmtDateWithWeekday } from '../../store/family.jsx'

const MED_LABEL = { m: '아침', l: '점심', d: '저녁' }

export default function CareDiaryDetail() {
  const { id } = useParams()
  const { familyLinked } = useAuth()
  const { records, updateRecord, deleteRecord } = useFamily()
  const nav = useNavigate()
  const toast = useToast()
  const item = records.find((r) => r.id === id)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(item?.body || '')
  const [confirm, setConfirm] = useState(false)

  const mine = item?.author === '나'

  const backBtn = <Link to="/family/diary" className="btn btn-ghost btn-sm">← 목록</Link>

  const saveEdit = () => {
    if (!draft.trim()) return
    updateRecord(item.id, draft)
    setEditing(false)
    toast.show('돌봄 기록을 수정했어요')
  }
  const doDelete = () => {
    deleteRecord(item.id)
    toast.show('돌봄 기록을 삭제했어요')
    nav('/family/diary')
  }

  return (
    <div className="container page">
      <PageHead title="📔 돌봄일지 · 상세" sub="가족이 남긴 돌봄 기록의 전체 내용이에요." right={backBtn} />
      <RequireLogin axis="돌봄일지">
        {!familyLinked ? (
          <div className="card card-pad center" style={{ maxWidth: 460, margin: '0 auto', padding: 'var(--sp-7)' }}>
            <div style={{ fontSize: 40 }}>🔗</div>
            <h3 style={{ margin: '12px 0 8px' }}>가족과 연결하면 볼 수 있어요</h3>
            <p className="muted">돌봄일지는 연결된 가족만 열람할 수 있어요.</p>
            <Link to="/family" className="btn btn-primary" style={{ marginTop: 18 }}>가족편지로 가기</Link>
          </div>
        ) : !item ? (
          <Empty icon="🔍">기록을 찾을 수 없어요. 삭제되었거나 잘못된 주소예요.</Empty>
        ) : (
          <article className="card card-pad" style={{ maxWidth: 720, margin: '0 auto' }}>
            <div className="row" style={{ gap: 10, marginBottom: 14 }}>
              <span className={`badge ${mine ? 'badge-teal' : 'badge-gray'}`}>{item.author}</span>
              <span className="muted" style={{ fontSize: 14 }}>{fmtDateWithWeekday(item.date)} {item.time}</span>
            </div>

            {editing ? (
              <>
                <textarea className="textarea" value={draft} onChange={(e) => setDraft(e.target.value.slice(0, 500))}
                  style={{ minHeight: 160 }} autoFocus />
                <div className="row" style={{ justifyContent: 'space-between', marginTop: 6 }}>
                  <span className="muted" style={{ fontSize: 12.5 }}>{draft.length}/500</span>
                </div>
              </>
            ) : (
              <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.75, fontSize: 15.5, minHeight: 80 }}>{item.body}</p>
            )}

            {/* 그날의 약 */}
            <div style={{ marginTop: 18, background: 'var(--teal-50)', border: '1px solid var(--teal-100)', borderRadius: 'var(--radius)', padding: '12px 16px' }}>
              <span style={{ fontWeight: 700, color: 'var(--teal-800)' }}>그날의 약</span>
              <span style={{ color: 'var(--teal-800)', marginLeft: 8 }}>
                {['m', 'l', 'd'].map((k, i) => (
                  <span key={k}>
                    {i > 0 && <span className="muted"> · </span>}
                    {MED_LABEL[k]} {item.meds?.[k] ? '✓' : '✗'}
                  </span>
                ))}
              </span>
            </div>

            {/* 수정·삭제: 본인 글만 (타 가족 읽기 전용) */}
            <div className="row" style={{ justifyContent: 'flex-end', gap: 10, marginTop: 18 }}>
              {editing ? (
                <>
                  <button className="btn btn-ghost btn-sm" onClick={() => { setEditing(false); setDraft(item.body) }}>취소</button>
                  <button className="btn btn-primary btn-sm" onClick={saveEdit} disabled={!draft.trim()}>저장</button>
                </>
              ) : mine ? (
                <>
                  <button className="btn btn-ghost btn-sm" onClick={() => { setDraft(item.body); setEditing(true) }}>수정</button>
                  <button className="btn btn-danger btn-sm" onClick={() => setConfirm(true)}>삭제</button>
                </>
              ) : (
                <span className="muted" style={{ fontSize: 13 }}>다른 가족의 기록은 읽기 전용이에요</span>
              )}
            </div>
          </article>
        )}
      </RequireLogin>

      {confirm && (
        <Modal title="이 돌봄 기록을 삭제할까요?" onClose={() => setConfirm(false)}
          actions={<>
            <button className="btn btn-ghost" onClick={() => setConfirm(false)}>취소</button>
            <button className="btn btn-danger" onClick={doDelete}>삭제</button>
          </>}>
          <p>삭제하면 돌봄일지에서 사라지고 되돌릴 수 없어요.</p>
        </Modal>
      )}
      {toast.node}
    </div>
  )
}
