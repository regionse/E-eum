import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { adminLogin } from '../../api/auth.js'
import { useAuth } from '../../store/auth.jsx'

export default function AdminLogin() {
  const nav = useNavigate()
  const { adminLogin: setAdmin } = useAuth()
  const [form, setForm] = useState({ id: '', pw: '' })
  const [err, setErr] = useState({})
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    const er = {}
    if (!form.id) er.id = '아이디를 입력해주세요'
    if (!form.pw) er.pw = '비밀번호를 입력해주세요'
    setErr(er)
    if (Object.keys(er).length) return
    setBusy(true)
    try {
      const a = await adminLogin(form)
      setAdmin(a); nav('/admin/users') // 로그인 후 첫 화면 = 회원관리 (스토리보드 a06)
    } catch (e2) { setErr({ pw: e2.message }) } finally { setBusy(false) }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'var(--teal-800)' }}>
      <div className="card card-pad" style={{ width: 380 }}>
        <div className="brand" style={{ justifyContent: 'center', marginBottom: 4 }}><span className="dot" />이음 <span style={{ fontSize: 13, color: 'var(--muted)', fontWeight: 700 }}>ADMIN</span></div>
        <p className="center muted" style={{ marginBottom: 20, fontSize: 14 }}>관리자 전용 로그인</p>
        <form onSubmit={submit}>
          <div className="field"><label>아이디<span className="req">*</span></label>
            <input className={`input ${err.id ? 'error' : ''}`} value={form.id} onChange={set('id')} />{err.id && <span className="err">{err.id}</span>}</div>
          <div className="field"><label>비밀번호<span className="req">*</span></label>
            <input type="password" className={`input ${err.pw ? 'error' : ''}`} placeholder="••••••••" value={form.pw} onChange={set('pw')} />{err.pw && <span className="err">{err.pw}</span>}</div>
          <button className="btn btn-primary btn-block btn-lg" disabled={busy}>{busy ? '로그인 중…' : '로그인'}</button>
        </form>
        <p className="hint center" style={{ marginTop: 12 }}>관리자 권한(<code>is_admin</code>) 계정으로 로그인하세요.</p>
        <div className="center" style={{ marginTop: 12 }}><Link to="/" className="muted" style={{ fontSize: 13 }}>← 사용자 사이트로</Link></div>
      </div>
    </div>
  )
}
