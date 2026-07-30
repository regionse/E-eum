import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { findId, resetPassword } from '../../api/auth.js'
import { Modal } from '../../components/ui/index.jsx'
import AuthShell from './AuthShell.jsx'
import { sanitizeId, formatBirth, okBirth, formatPhone, okPhone } from '../../utils/form.js'

export default function FindPw() {
  const nav = useNavigate()
  const [phase, setPhase] = useState('verify') // verify → reset
  const [form, setForm] = useState({ id: '', birth: '', phone: '', pw: '', pw2: '' })
  const [err, setErr] = useState({})
  const [done, setDone] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  // 본인확인 — 형식 검사 후, find-id 로 (생년월일+전화)→아이디를 찾아 입력한 아이디와 일치해야 통과.
  //  (스토리보드 AUTH-003: 검증 통과해야 재설정 단계로. 이전엔 형식만 보고 넘어가 '막 눌러도 진행'됐음)
  const verify = async (e) => {
    e.preventDefault()
    const er = {}
    if (!/^[A-Za-z0-9]{4,10}$/.test(form.id)) er.id = '아이디는 영문+숫자 4~10자예요'
    if (!okBirth(form.birth)) er.birth = '생년월일 8자리를 입력해주세요 (예: 2004-03-15)'
    if (!okPhone(form.phone)) er.phone = '연락처 형식이 올바르지 않아요 (예: 010-1234-5678)'
    setErr(er)
    if (Object.keys(er).length) return
    setVerifying(true)
    try {
      const { id } = await findId({ birth: form.birth, phone: form.phone })
      if (id !== form.id) {
        setErr({ submit: '입력하신 정보와 일치하는 회원이 없어요. 다시 확인해 주세요.' })
        return
      }
      setErr({})
      setPhase('reset')
    } catch {
      setErr({ submit: '일치하는 회원 정보를 찾을 수 없어요. 정보를 다시 확인해 주세요.' })
    } finally {
      setVerifying(false)
    }
  }
  const reset = async (e) => {
    e.preventDefault()
    const er = {}
    if (!/^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,10}$/.test(form.pw))
      er.pw = '비밀번호는 영문·숫자·특수문자 포함 8~10자예요'
    if (form.pw !== form.pw2) er.pw2 = '비밀번호가 일치하지 않아요'
    setErr(er)
    if (Object.keys(er).length) return
    try {
      // 본인확인(아이디+생년월일+전화번호) + 새 비밀번호 변경을 한 번에 (백엔드가 검증)
      await resetPassword({ id: form.id, birth: form.birth, phone: form.phone, newPw: form.pw })
      setDone(true)
    } catch (e2) {
      // DB와 안 맞으면 본인확인 단계로 되돌리고 안내
      setPhase('verify')
      setErr({ submit: e2?.message || '일치하는 회원 정보를 찾을 수 없어요. 정보를 다시 확인해주세요.' })
    }
  }

  return (
    <AuthShell title="비밀번호 찾기" sub={phase === 'verify' ? '본인 확인 정보를 입력해주세요.' : '새 비밀번호를 설정해주세요.'}
      foot={<Link to="/login" style={{ color: 'var(--teal-600)', fontWeight: 700 }}>로그인으로 돌아가기</Link>}>
      {phase === 'verify' ? (
        <form onSubmit={verify}>
          <div className="field"><label>아이디<span className="req">*</span></label>
            <input className={`input ${err.id ? 'error' : ''}`} placeholder="영문+숫자 4~10자" maxLength={10} value={form.id} onChange={(e) => setForm((f) => ({ ...f, id: sanitizeId(e.target.value) }))} />{err.id && <span className="err">{err.id}</span>}</div>
          <div className="field"><label>생년월일<span className="req">*</span></label>
            <input className={`input ${err.birth ? 'error' : ''}`} placeholder="2004-03-15" maxLength={10} inputMode="numeric" value={form.birth} onChange={(e) => setForm((f) => ({ ...f, birth: formatBirth(e.target.value) }))} />{err.birth && <span className="err">{err.birth}</span>}</div>
          <div className="field"><label>전화번호<span className="req">*</span></label>
            <input className={`input ${err.phone ? 'error' : ''}`} placeholder="010-0000-0000" maxLength={13} inputMode="numeric" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: formatPhone(e.target.value) }))} />{err.phone && <span className="err">{err.phone}</span>}</div>
          {err.submit && <p className="err" style={{ marginTop: 4, marginBottom: 8 }}>{err.submit}</p>}
          <button className="btn btn-primary btn-block btn-lg" disabled={verifying}>{verifying ? '확인 중…' : '다음'}</button>
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
