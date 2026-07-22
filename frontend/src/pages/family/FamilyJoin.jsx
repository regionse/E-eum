import { useState, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { PageHead, useToast } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import { useFamily } from '../../store/family.jsx'
import { demoInviteCode } from '../../mock/db.js'

const LEN = 6
const MAX_TRY = 5

// 데모 오류 코드 → 사유 (스토리보드 FAM-000b '이럴 때 막혀요')
const REASONS = [
  { key: 'notfound', code: '· 없는 코드', label: '코드를 찾을 수 없어요' },
  { key: 'expired', code: '· 만료', label: '만료된 코드예요' },
  { key: 'used', code: '· 사용됨', label: '이미 사용된 코드' },
  { key: 'self', code: '· 본인 코드', label: '본인 코드는 안 돼요' },
  { key: 'already', code: '· 이미 연결', label: '이미 연결된 가족' },
]
const DEMO = { '000000': 'notfound', '111111': 'expired', '222222': 'used', '444444': 'already' }
const MSG = {
  notfound: '코드를 찾을 수 없어요. 다시 확인해 주세요.',
  expired: '만료된 코드예요. 새 코드를 받아주세요.',
  used: '이미 사용된 코드예요.',
  self: '본인 코드는 안 돼요. 가족에게 받은 코드를 입력해 주세요.',
  already: '이미 연결된 가족이에요.',
}

export default function FamilyJoin() {
  const { familyLinked, linkFamily } = useAuth()
  const { inviteCode } = useFamily()
  const nav = useNavigate()
  const toast = useToast()
  const [digits, setDigits] = useState(Array(LEN).fill(''))
  const [error, setError] = useState('')
  const [fails, setFails] = useState(0)
  const refs = useRef([])

  const code = digits.join('')
  const locked = fails >= MAX_TRY
  const canConnect = code.length === LEN && !locked

  const setAt = (i, v) => {
    const d = v.replace(/\D/g, '').slice(-1)
    setDigits((prev) => { const n = [...prev]; n[i] = d; return n })
    if (error) setError('')
    if (d && i < LEN - 1) refs.current[i + 1]?.focus()
  }
  const onKey = (i, e) => {
    if (e.key === 'Backspace' && !digits[i] && i > 0) refs.current[i - 1]?.focus()
    if (e.key === 'Enter') submit()
  }
  const onPaste = (e) => {
    const txt = (e.clipboardData.getData('text') || '').replace(/\D/g, '').slice(0, LEN)
    if (!txt) return
    e.preventDefault()
    const n = Array(LEN).fill('')
    txt.split('').forEach((c, k) => { n[k] = c })
    setDigits(n)
    setError('')
    refs.current[Math.min(txt.length, LEN - 1)]?.focus()
  }

  const submit = () => {
    if (locked || code.length !== LEN) {
      if (code.length !== LEN) setError('숫자 6자리를 모두 입력해 주세요.')
      return
    }
    // 검증
    let reason = null
    if (familyLinked) reason = 'already'
    else if (code === inviteCode) reason = 'self'
    else if (code === demoInviteCode) reason = null // 성공
    else reason = DEMO[code] || 'notfound'

    if (reason) {
      const nextFails = fails + 1
      setFails(nextFails)
      setError(nextFails >= MAX_TRY ? '실패가 5회를 넘었어요. 잠시 후 다시 시도해 주세요.' : MSG[reason])
      return
    }
    // 성공
    linkFamily()
    toast.show('가족과 연결되었어요')
    nav('/family')
  }

  return (
    <div className="container page">
      <PageHead title="가족 코드 입력" sub="가족에게 받은 초대 코드 6자리를 입력하면 연결돼요."
        right={<Link to="/family/connect" className="btn btn-ghost btn-sm">내 코드 보기 ›</Link>} />
      <RequireLogin axis="가족편지">
        <div className="grid" style={{ gridTemplateColumns: '1.1fr .9fr', gap: 'var(--sp-5)', alignItems: 'start' }}>

          {/* 코드 입력 */}
          <div className="card card-pad">
            <label className="muted" style={{ display: 'block', marginBottom: 12, fontWeight: 700, color: 'var(--ink)' }}>
              초대 코드 <span className="muted" style={{ fontWeight: 500 }}>(숫자 6자리)</span>
            </label>

            <div className="row" style={{ gap: 8, justifyContent: 'space-between' }} onPaste={onPaste}>
              {digits.map((d, i) => (
                <input
                  key={i}
                  ref={(el) => (refs.current[i] = el)}
                  value={d}
                  onChange={(e) => setAt(i, e.target.value)}
                  onKeyDown={(e) => onKey(i, e)}
                  onFocus={(e) => e.target.select()}
                  disabled={locked}
                  inputMode="numeric"
                  maxLength={1}
                  aria-label={`코드 ${i + 1}번째 자리`}
                  style={{
                    width: '100%', maxWidth: 52, height: 60, textAlign: 'center',
                    fontSize: 24, fontWeight: 800, color: 'var(--ink)',
                    border: `1.5px solid ${error ? 'var(--danger)' : 'var(--line)'}`,
                    background: error ? '#fef6f6' : '#fff',
                    borderRadius: 'var(--radius-sm)', outline: 'none',
                  }}
                />
              ))}
            </div>

            {error && <p style={{ color: 'var(--danger)', fontSize: 14, fontWeight: 600, marginTop: 12 }}>⚠ {error}</p>}

            <button className="btn btn-primary btn-block" style={{ marginTop: 18 }} onClick={submit} disabled={!canConnect}>
              연결하기
            </button>

            {fails > 0 && (
              <p className="center" style={{ marginTop: 12, fontSize: 13, color: locked ? 'var(--danger)' : 'var(--muted)', fontWeight: 600 }}>
                실패 {Math.min(fails, MAX_TRY)}/{MAX_TRY}회 · {MAX_TRY}회 실패 시 잠금
              </p>
            )}
          </div>

          {/* 안내 + 오류 사유 */}
          <aside className="stack" style={{ gap: 12 }}>
            <div className="principle">
              <div style={{ fontWeight: 700, color: 'var(--teal-800)', marginBottom: 4 }}>어떻게 되나요?</div>
              <p style={{ color: 'var(--teal-800)', fontSize: 13.5, lineHeight: 1.6 }}>
                코드가 맞으면 서로의 가족편지가 이어져요. 코드로만 연결되고, 상대의 전화번호·개인정보는 보이지 않아요.
              </p>
            </div>
            <div className="card card-pad">
              <div style={{ fontWeight: 700, marginBottom: 10 }}>이럴 때 막혀요</div>
              <div className="stack" style={{ gap: 8 }}>
                {REASONS.map((r) => (
                  <div key={r.key} className="row" style={{ justifyContent: 'space-between', gap: 10, fontSize: 13.5 }}>
                    <span className="muted" style={{ flexShrink: 0 }}>{r.code}</span>
                    <span style={{ color: 'var(--ink-soft)', textAlign: 'right' }}>{r.label}</span>
                  </div>
                ))}
              </div>
              <p className="hint" style={{ marginTop: 12 }}>데모: <b>{demoInviteCode}</b> 입력 시 연결돼요.</p>
            </div>
          </aside>
        </div>
      </RequireLogin>
      {toast.node}
    </div>
  )
}
