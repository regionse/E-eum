import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { PageHead, useToast } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import { useFamily } from '../../store/family.jsx'
import { familyMembers } from '../../mock/db.js'

const TTL = 300 // 코드 유효시간 5:00 (스토리보드 SHA-303)
const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

export default function FamilyConnect() {
  const { familyLinked, unlinkFamily } = useAuth()
  const { inviteCode, regenerateCode } = useFamily()
  const toast = useToast()
  const [left, setLeft] = useState(TTL)

  // 만료 카운트다운
  useEffect(() => {
    if (left <= 0) return
    const t = setInterval(() => setLeft((s) => (s <= 1 ? 0 : s - 1)), 1000)
    return () => clearInterval(t)
  }, [left <= 0])

  const expired = left <= 0

  const copy = async () => {
    if (expired) return
    try { await navigator.clipboard.writeText(inviteCode) } catch { /* noop */ }
    toast.show('초대 코드를 복사했어요')
  }
  const regen = () => {
    regenerateCode()
    setLeft(TTL)
    toast.show('새 초대 코드를 만들었어요')
  }

  return (
    <div className="container page">
      <PageHead title="가족 연결" sub="함께 돌보는 가족을 초대해요 · 서로 이음 회원이면 코드로 이어져요."
        right={<Link to="/family/join" className="btn btn-ghost btn-sm">초대 코드 입력 ›</Link>} />
      <RequireLogin axis="가족편지">
        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-5)', alignItems: 'start' }}>

          {/* 내 초대 코드 */}
          <div className="card card-pad">
            <h3 style={{ marginBottom: 4 }}>내 초대 코드</h3>
            <p className="muted" style={{ fontSize: 13.5, marginBottom: 14 }}>가족에게 전달하면 상대가 입력해 연결돼요.</p>

            <div className="center" style={{
              background: expired ? '#f6f7f9' : 'var(--teal-50)',
              border: `1.5px solid ${expired ? 'var(--line)' : 'var(--teal-200)'}`,
              borderRadius: 'var(--radius)', padding: '22px 16px', marginBottom: 12,
            }}>
              <span style={{
                fontSize: 34, fontWeight: 800, letterSpacing: 10, paddingLeft: 10,
                color: expired ? 'var(--muted)' : 'var(--teal-700)',
                textDecoration: expired ? 'line-through' : 'none',
              }}>{inviteCode}</span>
            </div>

            <p className="center" style={{ fontSize: 14, marginBottom: 16, color: expired ? 'var(--danger)' : 'var(--ink-soft)', fontWeight: 600 }}>
              {expired ? '⏱ 만료됐어요 · 새 코드를 만들어 주세요' : <>⏱ <b>{fmt(left)}</b> 후 만료 · 1회용</>}
            </p>

            <div className="row" style={{ gap: 10 }}>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={copy} disabled={expired}>코드 복사</button>
              <button className="btn btn-ghost" style={{ flex: 1 }} onClick={regen}>새 코드 만들기</button>
            </div>
            <p className="hint" style={{ marginTop: 12 }}>코드를 어머니에게 전달 → 어머니가 입력하면 연결돼요. 전화번호 등 개인정보는 노출되지 않아요.</p>
          </div>

          {/* 연결된 가족 */}
          <div className="card card-pad">
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
              <h3>연결된 가족</h3>
              {familyLinked && <span className="badge badge-teal">연결됨</span>}
            </div>
            <p className="muted" style={{ fontSize: 13.5, marginBottom: 14 }}>함께 돌봄일지를 남기는 가족이에요.</p>

            {!familyLinked ? (
              <div className="center" style={{ padding: 'var(--sp-6) var(--sp-3)' }}>
                <div style={{ fontSize: 40 }}>👪</div>
                <p className="muted" style={{ marginTop: 10 }}>아직 연결된 가족이 없어요.<br />코드를 공유해 초대하세요.</p>
              </div>
            ) : (
              <>
                <div className="stack" style={{ gap: 10 }}>
                  <div className="list-row" style={{ padding: '10px 4px', borderBottom: '1px solid var(--line)' }}>
                    <span className="row" style={{ gap: 10 }}>
                      <span style={{ fontSize: 24 }}>🧑</span>
                      <span><b>나</b> <span className="muted" style={{ fontSize: 13 }}>· 본인</span></span>
                    </span>
                  </div>
                  {familyMembers.map((m) => (
                    <div key={m.id} className="list-row" style={{ padding: '10px 4px', borderBottom: 'none' }}>
                      <span className="row" style={{ gap: 10 }}>
                        <span style={{ fontSize: 24 }}>{m.emoji}</span>
                        <span><b>{m.name}</b> <span className="muted" style={{ fontSize: 13 }}>· {m.relation}</span></span>
                      </span>
                    </div>
                  ))}
                </div>
                <div className="row" style={{ gap: 10, marginTop: 16 }}>
                  <Link to="/family" className="btn btn-primary" style={{ flex: 1 }}>가족편지로 가기</Link>
                  <button className="btn btn-danger" onClick={() => { unlinkFamily(); toast.show('연결을 해제했어요') }}>연결 해제</button>
                </div>
              </>
            )}
          </div>
        </div>
      </RequireLogin>
      {toast.node}
    </div>
  )
}
