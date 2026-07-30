import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login } from '../../api/auth.js'
import { useAuth } from '../../store/auth.jsx'
import AuthShell from './AuthShell.jsx'

export default function Login() {
  const nav = useNavigate()
  const { login: setUser } = useAuth()
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
      const u = await login(form)
      setUser(u)
      nav('/')
    } catch (e2) {
      setErr({ pw: e2.message })
    } finally { setBusy(false) }
  }

  return (
    <AuthShell title="로그인" sub="이음에 오신 걸 환영해요."
      foot={<>계정이 없으신가요? <Link to="/signup" style={{ color: 'var(--teal-600)', fontWeight: 700 }}>회원가입</Link></>}>
      <form onSubmit={submit}>
        <div className="field">
          <label>아이디<span className="req">*</span></label>
          <input className={`input ${err.id ? 'error' : ''}`} value={form.id} onChange={set('id')} />
          {err.id && <span className="err">{err.id}</span>}
        </div>
        <div className="field">
          <label>비밀번호<span className="req">*</span></label>
          <input type="password" className={`input ${err.pw ? 'error' : ''}`} value={form.pw} onChange={set('pw')} />
          {err.pw && <span className="err">{err.pw}</span>}
          <span className="hint">비밀번호 8자 이상</span>
        </div>
        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>{busy ? '로그인 중…' : '로그인'}</button>
      </form>
      <div className="row" style={{ justifyContent: 'center', gap: 14, marginTop: 16, fontSize: 14 }}>
        <Link to="/find-id" className="muted">아이디 찾기</Link>
        <span style={{ color: 'var(--line)' }}>|</span>
        <Link to="/find-pw" className="muted">비밀번호 찾기</Link>
      </div>
      <p className="hint center" style={{ marginTop: 14 }}>가입한 계정으로 로그인해 주세요.</p>
    </AuthShell>
  )
}
