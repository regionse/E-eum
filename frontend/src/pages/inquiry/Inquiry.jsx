import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { submitInquiry } from '../../api/content.js'
import { Modal, useToast, PageHead } from '../../components/ui/index.jsx'
import { useAuth } from '../../store/auth.jsx'

const TYPES = ['계정문의', '덜다', '잇다', '나누다', '기타']

export default function Inquiry() {
  const { user } = useAuth()
  const nav = useNavigate()
  const toast = useToast()
  const [form, setForm] = useState({ type: '계정문의', title: '', body: '', phone: '', pw: '' })
  const [err, setErr] = useState({})
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const validate = () => {
    const e = {}
    if (!user && !form.phone) e.phone = '전화번호를 입력해주세요.'
    if (!user && !form.pw) e.pw = '비밀번호를 입력해주세요.'
    if (!form.title) e.title = '문의 제목을 입력해주세요.'
    if (!form.body) e.body = '문의 내용을 입력해주세요.'
    setErr(e)
    return Object.keys(e).length === 0
  }
  const submit = async () => {
    if (!validate()) return
    setBusy(true)
    await submitInquiry({ title: form.title, type: form.type, body: form.body })
    setBusy(false)
    setDone(true)
  }

  return (
    <div className="container page" style={{ maxWidth: 640 }}>
      <PageHead title="문의하기" sub={user ? `${user.nickname} 님으로 문의를 남겨요.` : '비회원은 전화번호·비밀번호로 문의를 조회할 수 있어요.'}
        right={<Link to="/inquiry/list" className="btn btn-ghost btn-sm">문의 내역</Link>} />

      <div className="card card-pad">
        {!user && (
          <>
            <div className="field">
              <label>전화번호<span className="req">*</span></label>
              <input className={`input ${err.phone ? 'error' : ''}`} placeholder="01012345678" value={form.phone} onChange={set('phone')} />
              {err.phone && <span className="err">{err.phone}</span>}
            </div>
            <div className="field">
              <label>비밀번호<span className="req">*</span></label>
              <input type="password" className={`input ${err.pw ? 'error' : ''}`} placeholder="문의 조회용 비밀번호" value={form.pw} onChange={set('pw')} />
              {err.pw && <span className="err">{err.pw}</span>}
              <span className="hint">비회원 문의는 이 정보로 나중에 조회해요.</span>
            </div>
          </>
        )}
        <div className="field">
          <label>문의 유형<span className="req">*</span></label>
          <select className="select" value={form.type} onChange={set('type')}>
            {TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
        <div className="field">
          <label>문의 제목<span className="req">*</span></label>
          <input className={`input ${err.title ? 'error' : ''}`} placeholder="제목을 입력하세요" value={form.title} onChange={set('title')} />
          {err.title && <span className="err">{err.title}</span>}
        </div>
        <div className="field">
          <label>문의 내용<span className="req">*</span></label>
          <textarea className={`textarea ${err.body ? 'error' : ''}`} placeholder="문의 내용을 입력하세요" value={form.body} onChange={set('body')} />
          {err.body && <span className="err">{err.body}</span>}
        </div>
        <button className="btn btn-primary btn-block btn-lg" onClick={submit} disabled={busy}>{busy ? '보내는 중…' : '문의 보내기'}</button>
      </div>

      {done && (
        <Modal title="문의가 등록되었습니다"
          actions={<>
            <button className="btn btn-ghost" onClick={() => nav('/inquiry/list')}>문의 내역</button>
            <button className="btn btn-primary" onClick={() => nav('/')}>확인</button>
          </>}>
          <p>답변이 등록되면 알려드릴게요.</p>
        </Modal>
      )}
      {toast.node}
    </div>
  )
}
