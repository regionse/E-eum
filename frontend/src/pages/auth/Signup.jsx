import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { signup } from '../../api/auth.js'
import { Modal } from '../../components/ui/index.jsx'
import AuthShell from './AuthShell.jsx'

const AGREEMENTS = [
  { k: 'tos', label: '이용약관 동의', required: true },
  { k: 'privacy', label: '개인정보 수집 및 이용 동의', required: true },
  { k: 'location', label: '위치정보 서비스 이용약관', required: false },
  { k: 'alarm', label: '알림설정 동의', required: false },
]

// 주소는 '시·도'까지만 수집 (스토리보드 REG-03: "주소는 시까지만 받는다")
const REGIONS = [
  '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시', '대전광역시',
  '울산광역시', '세종특별자치시', '경기도', '강원특별자치도', '충청북도', '충청남도',
  '전북특별자치도', '전라남도', '경상북도', '경상남도', '제주특별자치도',
]

export default function Signup() {
  const nav = useNavigate()
  const [step, setStep] = useState(1)
  const [agree, setAgree] = useState({})
  const [over14, setOver14] = useState(false)
  const [form, setForm] = useState({ id: '', pw: '', pw2: '', birth: '', phone: '', region: '', nickname: '', gender: '선택' })
  const [err, setErr] = useState({})
  const [done, setDone] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const allRequired = AGREEMENTS.filter((a) => a.required).every((a) => agree[a.k])
  const toggleAll = () => {
    const v = !AGREEMENTS.every((a) => agree[a.k])
    setAgree(Object.fromEntries(AGREEMENTS.map((a) => [a.k, v])))
  }

  const validateInfo = () => {
    const e = {}
    if (!form.id) e.id = '아이디를 입력해주세요'
    if (!form.pw) e.pw = '비밀번호를 입력해주세요'
    if (form.pw && form.pw !== form.pw2) e.pw2 = '비밀번호가 일치하지 않아요'
    if (!form.birth) e.birth = '생년월일을 입력해주세요'
    if (!form.phone) e.phone = '연락처를 입력해주세요'
    if (!form.region) e.region = '지역을 선택해주세요'
    if (!form.nickname) e.nickname = '닉네임을 입력해주세요'
    setErr(e)
    return Object.keys(e).length === 0
  }
  const finish = async () => {
    if (!validateInfo()) return
    await signup(form)
    setDone(true)
  }

  return (
    <AuthShell title="회원가입" sub={`4단계 중 ${step}단계`}
      foot={<>이미 계정이 있으신가요? <Link to="/login" style={{ color: 'var(--teal-600)', fontWeight: 700 }}>로그인</Link></>}>
      <div className="steps" style={{ marginBottom: 20 }}>
        {['약관동의', '연령확인', '정보입력', '완료'].map((s, i) => (
          <span key={s}><span className={`step ${step === i + 1 ? 'on' : ''}`}>{s}</span>{i < 3 && <span className="sep"> · </span>}</span>
        ))}
      </div>

      {step === 1 && (
        <>
          <label className="list-row" style={{ padding: '12px 0', cursor: 'pointer', fontWeight: 700 }}>
            약관 전체동의
            <input type="checkbox" checked={AGREEMENTS.every((a) => agree[a.k])} onChange={toggleAll} />
          </label>
          {AGREEMENTS.map((a) => (
            <label key={a.k} className="list-row" style={{ padding: '10px 0', cursor: 'pointer' }}>
              <span>{a.label} <span className={a.required ? 'req' : 'muted'} style={{ fontSize: 13 }}>({a.required ? '필수' : '선택'})</span></span>
              <input type="checkbox" checked={!!agree[a.k]} onChange={() => setAgree({ ...agree, [a.k]: !agree[a.k] })} />
            </label>
          ))}
          {!allRequired && <p className="hint" style={{ marginTop: 8 }}>필수 항목에 동의해야 다음으로 넘어갈 수 있어요.</p>}
          <button className="btn btn-primary btn-block btn-lg" style={{ marginTop: 16 }} disabled={!allRequired} onClick={() => setStep(2)}>다음</button>
        </>
      )}

      {step === 2 && (
        <>
          <div className="card-pad" style={{ background: 'var(--bg)', borderRadius: 12, marginBottom: 16 }}>
            <p style={{ fontWeight: 700, marginBottom: 8 }}>만 14세 이상이신가요?</p>
            <p className="muted" style={{ fontSize: 14 }}>이음은 개인정보 보호를 위해 만 14세 이상만 가입할 수 있어요. 만 14세 미만은 향후 공공기관 협력으로 별도 동의 체계를 갖춘 뒤 확장할 예정이에요.</p>
            <label className="row" style={{ gap: 8, marginTop: 12, cursor: 'pointer', fontWeight: 600 }}>
              <input type="checkbox" checked={over14} onChange={() => setOver14(!over14)} /> 네, 만 14세 이상입니다
            </label>
          </div>
          <div className="row" style={{ gap: 10 }}>
            <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => setStep(1)}>이전</button>
            <button className="btn btn-primary" style={{ flex: 1 }} disabled={!over14} onClick={() => setStep(3)}>다음</button>
          </div>
        </>
      )}

      {step === 3 && (
        <>
          <div className="field"><label>아이디<span className="req">*</span></label>
            <input className={`input ${err.id ? 'error' : ''}`} placeholder="영문+숫자 4~10자" value={form.id} onChange={set('id')} />{err.id && <span className="err">{err.id}</span>}</div>
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <div className="field"><label>비밀번호<span className="req">*</span></label>
              <input type="password" className={`input ${err.pw ? 'error' : ''}`} placeholder="••••••••" value={form.pw} onChange={set('pw')} />{err.pw && <span className="err">{err.pw}</span>}</div>
            <div className="field"><label>비밀번호 확인<span className="req">*</span></label>
              <input type="password" className={`input ${err.pw2 ? 'error' : ''}`} placeholder="••••••••" value={form.pw2} onChange={set('pw2')} />{err.pw2 && <span className="err">{err.pw2}</span>}</div>
          </div>
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <div className="field"><label>생년월일<span className="req">*</span></label>
              <input type="date" className={`input ${err.birth ? 'error' : ''}`} value={form.birth} onChange={set('birth')} />{err.birth && <span className="err">{err.birth}</span>}</div>
            <div className="field"><label>연락처<span className="req">*</span></label>
              <input className={`input ${err.phone ? 'error' : ''}`} placeholder="010-0000-0000" value={form.phone} onChange={set('phone')} />{err.phone && <span className="err">{err.phone}</span>}</div>
          </div>
          <div className="field"><label>지역 (시·도)<span className="req">*</span></label>
            <select className="select" value={form.region} onChange={set('region')}>
              <option value="">선택</option>
              {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>{err.region && <span className="err">{err.region}</span>}</div>
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <div className="field"><label>닉네임<span className="req">*</span></label>
              <input className={`input ${err.nickname ? 'error' : ''}`} placeholder="닉네임" value={form.nickname} onChange={set('nickname')} />{err.nickname && <span className="err">{err.nickname}</span>}</div>
            <div className="field"><label>성별</label>
              <select className="select" value={form.gender} onChange={set('gender')}><option>선택</option><option>남자</option><option>여자</option><option>선택 안함</option></select></div>
          </div>
          <div className="row" style={{ gap: 10, marginTop: 8 }}>
            <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => setStep(2)}>이전</button>
            <button className="btn btn-primary" style={{ flex: 1 }} onClick={finish}>가입 완료</button>
          </div>
        </>
      )}

      {done && (
        <Modal title="회원가입 완료 🎉"
          actions={<button className="btn btn-primary btn-block" onClick={() => nav('/login')}>로그인하러 가기</button>}>
          <p>회원가입이 완료되었어요. 이제 이음의 세 가지 도움을 이용할 수 있어요.</p>
        </Modal>
      )}
    </AuthShell>
  )
}
