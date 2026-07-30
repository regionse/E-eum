import { useState } from 'react'
import { Link } from 'react-router-dom'
import { findId } from '../../api/auth.js'
import { Modal } from '../../components/ui/index.jsx'
import AuthShell from './AuthShell.jsx'
import { formatBirth, okBirth, formatPhone, okPhone } from '../../utils/form.js'

export default function FindId() {
  const [form, setForm] = useState({ birth: '', phone: '' })
  const [err, setErr] = useState({})
  const [result, setResult] = useState(null)
  const [notFound, setNotFound] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    const er = {}
    if (!okBirth(form.birth)) er.birth = '생년월일 8자리를 입력해주세요 (예: 2004-03-15)'
    if (!okPhone(form.phone)) er.phone = '연락처 형식이 올바르지 않아요 (예: 010-1234-5678)'
    setErr(er)
    if (Object.keys(er).length) return
    try {
      const { id } = await findId(form)
      setResult(id)
    } catch { setNotFound(true) }
  }

  return (
    <AuthShell title="아이디 찾기" sub="본인 확인 정보를 입력해주세요."
      foot={<Link to="/login" style={{ color: 'var(--teal-600)', fontWeight: 700 }}>로그인으로 돌아가기</Link>}>
      <form onSubmit={submit}>
        <div className="field"><label>생년월일<span className="req">*</span></label>
          <input className={`input ${err.birth ? 'error' : ''}`} placeholder="2004-03-15" maxLength={10} inputMode="numeric"
            value={form.birth} onChange={(e) => setForm((f) => ({ ...f, birth: formatBirth(e.target.value) }))} />{err.birth && <span className="err">{err.birth}</span>}</div>
        <div className="field"><label>전화번호<span className="req">*</span></label>
          <input className={`input ${err.phone ? 'error' : ''}`} placeholder="010-0000-0000" maxLength={13} inputMode="numeric"
            value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: formatPhone(e.target.value) }))} />{err.phone && <span className="err">{err.phone}</span>}</div>
        <button className="btn btn-primary btn-block btn-lg">아이디 찾기</button>
      </form>
      {result && (
        <Modal title="아이디 찾기 완료" onClose={() => setResult(null)}
          actions={<Link to="/login" className="btn btn-primary btn-block">로그인</Link>}>
          <p>회원님의 아이디는 <b style={{ color: 'var(--teal-700)' }}>{result}</b> 입니다.</p>
        </Modal>
      )}
      {notFound && (
        <Modal title="찾을 수 없어요" onClose={() => setNotFound(false)}
          actions={<button className="btn btn-ghost btn-block" onClick={() => setNotFound(false)}>닫기</button>}>
          <p>일치하는 회원 정보를 찾을 수 없습니다. 입력한 정보를 다시 확인해주세요.</p>
        </Modal>
      )}
    </AuthShell>
  )
}
