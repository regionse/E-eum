import { useState, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { PageHead, useToast } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import { useFamily } from '../../store/family.jsx'
// import { demoInviteCode } from '../../mock/db.js'

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

export default function FamilyJoin() {
  const { familyLinked } = useAuth();
  const {
    joinWithCode,
    loading,
  } = useFamily();

  const nav = useNavigate()
  const toast = useToast()
  const [digits, setDigits] = useState(Array(LEN).fill(''))
  const [error, setError] = useState('')
  const [fails, setFails] = useState(0)
  const refs = useRef([])

  const code = digits.join('')
  const locked = fails >= MAX_TRY
  const canConnect = code.length === LEN && !locked

  const setAt = (index, value) => {
    const character = value
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, '')
      .slice(-1)

    setDigits((previous) => {
      const next = [...previous]
      next[index] = character
      return next
    })

    if (error) {
      setError('')
    }

    if (character && index < LEN - 1) {
      refs.current[index + 1]?.focus()
    }
  }

  const onKey = (i, e) => {
    if (e.key === 'Backspace' && !digits[i] && i > 0) refs.current[i - 1]?.focus()
    if (e.key === 'Enter') submit()
  }
  const onPaste = (event) => {
    const text = (
      event.clipboardData.getData('text') || ''
    )
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, '')
      .slice(0, LEN)

    if (!text) {
      return
    }

    event.preventDefault()

    const next = Array(LEN).fill('')

    text.split('').forEach((character, index) => {
      next[index] = character
    })

    setDigits(next)
    setError('')

    refs.current[
      Math.min(text.length, LEN - 1)
    ]?.focus()
  }

  const submit = async (e) => {
    e.preventDefault();
    setError("");

    if (code.length !== 6) {
      setError("초대코드 6자리를 입력해주세요.");
      return;
    }

    try {
      await joinWithCode({
        code,
        relationships: relationship,
      });

      navigate("/family");
    } catch (err) {
      setError(err.message || "가족방 연결에 실패했습니다.");
    }
  

    if (familyLinked) {
      setError('이미 참여 중인 가족방이 있습니다.')
      return
    }

    try {
      await joinWithCode({
        code,
        relationships: '가족',
      })

      toast.show('가족과 연결되었어요')
      nav('/family')
    } catch (requestError) {
      const nextFails = fails + 1
      setFails(nextFails)

      if (nextFails >= MAX_TRY) {
        setError(
          '실패가 5회를 넘었어요. 잠시 후 다시 시도해 주세요.',
        )
        return
      }

      setError(requestError.message)
    }
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
              초대 코드
              <span className="muted">
                (영문·숫자 6자리)
              </span>
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
                  inputMode="text"
                  autoCapitalize="characters"
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

            <button
              className="btn btn-primary btn-block"
              style={{ marginTop: 18 }}
              onClick={submit}
              disabled={!canConnect || loading}
            >
              {loading ? '연결 중...' : '연결하기'}
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
            </div>
          </aside>
        </div>
      </RequireLogin>
      {toast.node}
    </div>
  )
}
