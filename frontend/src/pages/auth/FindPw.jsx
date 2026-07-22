import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { resetPassword } from '../../api/auth.js'
import { Modal } from '../../components/ui/index.jsx'
import AuthShell from './AuthShell.jsx'

export default function FindPw() {
  const nav = useNavigate()
  const [phase, setPhase] = useState('verify') // verify → reset
  const [form, setForm] = useState({ id: '', birth: '', phone: '', pw: '', pw2: '' })
  const [err, setErr] = useState({})
  const [done, setDone] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const verify = (e) => {
    e.preventDefault()
    const er = {}
    if (!form.id) er.id = '아이디를 입력해주세요'
    if (!form.birth) er.birth = '생년월일을 입력해주세요'
    if (!form.phone) er.phone = '전화번호를 입력해주세요'
    setErr(er)
    if (Object.keys(er).length) return
    setPhase('reset')
  }
  const reset = async (e) => {
    e.preventDefault()
    const er = {}
    if (!form.pw) er.pw = '비밀번호를 입력해주세요'
    if (form.pw !== form.pw2) er.pw2 = '비밀번호가 일치하지 않아요'
    setErr(er)
    if (Object.keys(er).length) return
    await resetPassword(form)
    setDone(true)
  }

  return (
    <AuthShell title="비밀번호 찾기" sub={phase === 'verify' ? '본인 확인 정보를 입력해주세요.' : '새 비밀번호를 설정해주세요.'}
      foot={<Link to="/login" style={{ color: 'var(--teal-600)', fontWeight: 700 }}>로그인으로 돌아가기</Link>}>
      {phase === 'verify' ? (
        <form onSubmit={verify}>
          <div className="field"><label>아이디<span className="req">*</span></label>
            <input className={`input ${err.id ? 'error' : ''}`} placeholder="user1234" value={form.id} onChange={set('id')} />{err.id && <span className="err">{err.id}</span>}</div>
          <div className="field"><label>생년월일<span className="req">*</span></label>
            <input type="date" className={`input ${err.birth ? 'error' : ''}`} value={form.birth} onChange={set('birth')} />{err.birth && <span className="err">{err.birth}</span>}</div>
          <div className="field"><label>전화번호<span className="req">*</span></label>
            <input className={`input ${err.phone ? 'error' : ''}`} placeholder="01012345678" value={form.phone} onChange={set('phone')} />{err.phone && <span className="err">{err.phone}</span>}</div>
          <button className="btn btn-primary btn-block btn-lg">다음</button>
        </form>
      ) : (
        <form onSubmit={reset}>
          <div className="field"><label>새 비밀번호<span className="req">*</span></label>
            <input type="password" className={`input ${err.pw ? 'error' : ''}`} placeholder="••••••••" value={form.pw} onChange={set('pw')} />{err.pw && <span className="err">{err.pw}</span>}</div>
          <div className="field"><label>비밀번호 확인<span className="req">*</span></label>
            <input type="password" className={`input ${err.pw2 ? 'error' : ''}`} placeholder="••••••••" value={form.pw2} onChange={set('pw2')} />{err.pw2 && <span className="err">{err.pw2}</span>}</div>
          <button className="btn btn-primary btn-block btn-lg">비밀번호 변경</button>
        </form>
      )}
      {done && (
        <Modal title="비밀번호 변경 완료"
          actions={<button className="btn btn-primary btn-block" onClick={() => nav('/login')}>로그인</button>}>
          <p>비밀번호가 변경되었어요. 새 비밀번호로 로그인해주세요.</p>
        </Modal>
      )}
    </AuthShell>
  )
}
