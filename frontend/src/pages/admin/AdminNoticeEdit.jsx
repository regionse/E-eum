import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getNotice } from '../../api/content.js'
import { useAsync, Async, PageHead, useToast } from '../../components/ui/index.jsx'

const TYPES = ['공지사항', '업데이트', '이벤트']

// ADNOT-002 · 공지 등록/수정 (별도 페이지) — 모달이 아니라 화면으로
export default function AdminNoticeEdit() {
  const { id } = useParams()
  const isEdit = !!id
  const nav = useNavigate()
  const toast = useToast()
  const state = useAsync(() => (isEdit ? getNotice(id) : Promise.resolve(null)), [id])

  return (
    <div>
      <PageHead title={isEdit ? '공지사항 수정' : '공지사항 등록'} sub="공지·업데이트·이벤트를 작성해요."
        right={<button className="btn btn-ghost btn-sm" onClick={() => nav('/admin/notices')}>← 목록</button>} />
      <Async state={state}>
        {(n) => <NoticeForm initial={n} isEdit={isEdit}
          onDone={() => { toast.show(isEdit ? '수정되었어요' : '등록되었어요'); nav('/admin/notices') }} />}
      </Async>
      {toast.node}
    </div>
  )
}

function NoticeForm({ initial, isEdit, onDone }) {
  const [form, setForm] = useState({
    type: initial?.type || '공지사항',
    title: initial?.title || '',
    body: initial?.body || '',
    status: initial?.status || '활성',
  })
  const [err, setErr] = useState({})
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = () => {
    const er = {}
    if (!form.title.trim()) er.title = '제목을 입력해주세요'
    if (!form.body.trim()) er.body = '내용을 입력해주세요'
    setErr(er)
    if (Object.keys(er).length) return
    onDone() // mock: 저장은 백엔드가 (여기선 토스트 + 목록 복귀)
  }

  return (
    <div className="card card-pad" style={{ maxWidth: 680 }}>
      <div className="field"><label>유형<span className="req">*</span></label>
        <select className="select" value={form.type} onChange={set('type')}>
          {TYPES.map((t) => <option key={t}>{t}</option>)}
        </select></div>
      <div className="field"><label>제목<span className="req">*</span></label>
        <input className={`input ${err.title ? 'error' : ''}`} value={form.title} onChange={set('title')} placeholder="제목을 입력하세요" />
        {err.title && <span className="err">{err.title}</span>}</div>
      <div className="field"><label>내용<span className="req">*</span></label>
        <textarea className={`textarea ${err.body ? 'error' : ''}`} value={form.body} onChange={set('body')} placeholder="내용을 입력하세요" style={{ minHeight: 160 }} />
        {err.body && <span className="err">{err.body}</span>}</div>
      <div className="field"><label>게시 상태</label>
        <div className="row" style={{ gap: 8 }}>
          {['활성', '비활성'].map((s) => (
            <button key={s} className={`chip ${form.status === s ? 'on' : ''}`} onClick={() => setForm((f) => ({ ...f, status: s }))}>{s}</button>
          ))}
        </div></div>
      <button className="btn btn-primary btn-lg" style={{ marginTop: 8 }} onClick={submit}>{isEdit ? '수정 완료' : '등록'}</button>
    </div>
  )
}
