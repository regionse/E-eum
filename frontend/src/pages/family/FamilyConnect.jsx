import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHead, useToast } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import { useFamily } from '../../store/family.jsx'
// import { familyMembers } from '../../mock/db.js'

const TTL = 600 // 코드 유효시간 10:00 (스토리보드 SHA-303)
const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

export default function FamilyConnect() {
  const { user, familyLinked } = useAuth()
  const userId =
    user?.user_id ??
    user?.userId ??
    user?.id ??
    null
  const {
    careGroupId,
    careGroupOwnerId,
    members,
    inviteCode,
    inviteExpiresAt,
    regenerateCode,
    refreshFamily,
    loading,
    error,
  } = useFamily()
  const navigate = useNavigate()
  const toast = useToast()

  const [left, setLeft] = useState(TTL)
  const [requestError, setRequestError] = useState('')
  const [memberAliases, setMemberAliases] = useState({})
  const [editingMemberId, setEditingMemberId] = useState(null)
  const [aliasDraft, setAliasDraft] = useState('')
  const safeMembers = Array.isArray(members) ? members : []
  const hasCareGroup = careGroupId != null
  const isOwner =
    hasCareGroup &&
    userId != null &&
    careGroupOwnerId != null &&
    Number(userId) === Number(careGroupOwnerId)
  const canManageInvite = !hasCareGroup || isOwner
  const aliasStorageKey =
    userId != null && careGroupId != null
      ? `family-member-aliases:${userId}:${careGroupId}`
      : null

  const expired =
    !inviteCode ||
    left <= 0

  // 만료 카운트다운
  useEffect(() => {
    if (!inviteExpiresAt) {
      setLeft(0)
      return
    }

    const updateLeft = () => {
      const seconds = Math.max(
        0,
        Math.floor(
          (new Date(inviteExpiresAt).getTime() -
            Date.now()) /
            1000,
        ),
      )

      setLeft(seconds)
    }

    updateLeft()
    const timer = setInterval(updateLeft, 1000)

    return () => clearInterval(timer)
  }, [inviteExpiresAt])

  useEffect(() => {
    if (!aliasStorageKey) {
      setMemberAliases({})
      return
    }

    try {
      const saved = localStorage.getItem(aliasStorageKey)
      setMemberAliases(saved ? JSON.parse(saved) : {})
    } catch {
      setMemberAliases({})
    }
  }, [aliasStorageKey])

  const getMemberName = (memberId) => {
    const alias = memberAliases[String(memberId)]?.trim()

    if (alias) return alias

    return Number(memberId) === Number(userId)
      ? '나'
      : `가족 ${memberId}`
  }

  const startEditingName = (memberId) => {
    setEditingMemberId(String(memberId))
    setAliasDraft(getMemberName(memberId))
  }

  const cancelEditingName = () => {
    setEditingMemberId(null)
    setAliasDraft('')
  }

  const saveMemberName = (memberId) => {
    const nextName = aliasDraft.trim().slice(0, 20)

    if (!nextName) {
      setRequestError('이름을 입력해 주세요.')
      return
    }

    if (!aliasStorageKey) {
      setRequestError('가족방 정보를 확인할 수 없습니다.')
      return
    }

    const nextAliases = {
      ...memberAliases,
      [String(memberId)]: nextName,
    }

    try {
      localStorage.setItem(
        aliasStorageKey,
        JSON.stringify(nextAliases),
      )
    } catch {
      setRequestError('변경한 이름을 저장하지 못했습니다.')
      return
    }

    setMemberAliases(nextAliases)
    setRequestError('')
    cancelEditingName()
    toast.show('내 화면에서 사용할 이름을 변경했어요')
  }

  const copy = async () => {
    if (expired) return
    try { await navigator.clipboard.writeText(inviteCode) } catch { /* noop */ }
    toast.show('초대 코드를 복사했어요')
  }
  const regen = async () => {
    try {
      setRequestError('')
      await regenerateCode()
      toast.show('새 초대 코드를 만들었어요')
    } catch (requestFailure) {
      const message =
        requestFailure.message ||
        '초대 코드를 만들지 못했습니다.'

      setRequestError(message)
      toast.show(message)
    }
  }

  const goToFamilyLetters = async () => {
    try {
      setRequestError('')
      await refreshFamily()
      navigate('/family')
    } catch (requestFailure) {
      const message =
        requestFailure.message ||
        '가족 정보를 새로 불러오지 못했습니다.'

      setRequestError(message)
      toast.show(message)
    }
  }

  return (
    <div className="container page">
      <PageHead title="가족 연결" sub="함께 돌보는 가족을 초대해요 · 서로 이음 회원이면 코드로 이어져요."
        right={!hasCareGroup ? <Link to="/family/join" className="btn btn-ghost btn-sm">초대 코드 입력 ›</Link> : null} />
      <RequireLogin axis="가족편지">
        <div className="grid" style={{
          gridTemplateColumns:
            hasCareGroup && isOwner
              ? '1fr 1fr'
              : 'minmax(0, 720px)',
          justifyContent:
            hasCareGroup && isOwner
              ? 'stretch'
              : 'center',
          gap: 'var(--sp-5)',
          alignItems: 'start',
        }}>

          {/* 내 초대 코드 */}
          {canManageInvite && (
          <div className="card card-pad">
            <h3 style={{ marginBottom: 4 }}>
              {hasCareGroup
                ? '내 초대 코드'
                : '가족 초대 시작하기'}
            </h3>
            <p className="muted" style={{ fontSize: 13.5, marginBottom: 14 }}>
              {hasCareGroup
                ? '가족에게 전달하면 상대가 입력해 연결돼요.'
                : '초대 코드를 만들면 내 가족방이 함께 생성돼요.'}
            </p>

            <div className="center" style={{
              background: expired ? '#f6f7f9' : 'var(--teal-50)',
              border: `1.5px solid ${expired ? 'var(--line)' : 'var(--teal-200)'}`,
              borderRadius: 'var(--radius)', padding: '22px 16px', marginBottom: 12,
            }}>
              <span style={{
                fontSize: 34, fontWeight: 800, letterSpacing: 10, paddingLeft: 10,
                color: expired ? 'var(--muted)' : 'var(--teal-700)',
                textDecoration: expired ? 'line-through' : 'none',
              }}>{inviteCode || '------'}</span>
            </div>

            <p className="center" style={{ fontSize: 14, marginBottom: 16, color: expired ? 'var(--danger)' : 'var(--ink-soft)', fontWeight: 600 }}>
              {expired ? '⏱ 만료됐어요 · 새 코드를 만들어 주세요' : <>⏱ <b>{fmt(left)}</b> 후 만료 · 1회용</>}
            </p>

            <div className="row" style={{ gap: 10 }}>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={copy} disabled={!inviteCode || expired || loading}>코드 복사</button>
              <button className="btn btn-ghost" style={{ flex: 1 }} onClick={regen} disabled={loading}> {loading ? '생성 중...' : inviteCode ? '새 코드 만들기' : '초대 코드 만들기'}</button>
            </div>
            {(requestError || error) && (
              <div className="callout-warn" style={{ marginTop: 12 }}>
                {requestError || error}
              </div>
            )}
            <p className="hint" style={{ marginTop: 12 }}>코드를 어머니에게 전달 → 어머니가 입력하면 연결돼요. 전화번호 등 개인정보는 노출되지 않아요.</p>
          </div>
          )}

          {/* 연결된 가족 */}
          {hasCareGroup && (
          <div className="card card-pad">
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
              <h3>연결된 가족</h3>
              {familyLinked && <span className="badge badge-teal">연결됨</span>}
            </div>
            <p className="muted" style={{ fontSize: 13.5, marginBottom: 14 }}>함께 돌봄일지를 남기는 가족이에요.</p>

            {safeMembers.length === 0 ? (
              <div className="center" style={{ padding: 'var(--sp-6) var(--sp-3)' }}>
                <div style={{ fontSize: 40 }}>👪</div>
                <p className="muted" style={{ marginTop: 10 }}>구성원 정보를 불러오지 못했어요.</p>
              </div>
            ) : (
              <>
                <div className="stack" style={{ gap: 10 }}>
                  {safeMembers.map((member) => {
                    const mine =
                      Number(member.user_id) === Number(userId)
                    const memberId = String(member.user_id)
                    const isEditing = editingMemberId === memberId

                    return (
                      <div
                        key={member.user_id}
                        className="list-row"
                        style={{
                          padding: '10px 4px',
                          borderBottom: '1px solid var(--line)',
                        }}
                      >
                        <span className="row" style={{ gap: 10, flex: 1 }}>
                          <span style={{ fontSize: 24 }}>
                            {mine ? '🧑' : '👪'}
                          </span>

                          {isEditing ? (
                            <input
                              className="input"
                              value={aliasDraft}
                              onChange={(event) =>
                                setAliasDraft(event.target.value)
                              }
                              onKeyDown={(event) => {
                                if (event.key === 'Enter') {
                                  saveMemberName(member.user_id)
                                }
                                if (event.key === 'Escape') {
                                  cancelEditingName()
                                }
                              }}
                              maxLength={20}
                              aria-label="가족 표시 이름"
                              autoFocus
                              style={{ maxWidth: 220 }}
                            />
                          ) : (
                            <b>{getMemberName(member.user_id)}</b>
                          )}
                        </span>

                        <span className="row" style={{ gap: 6 }}>
                          {isEditing ? (
                            <>
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                onClick={() => saveMemberName(member.user_id)}
                              >
                                저장
                              </button>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={cancelEditingName}
                              >
                                취소
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              onClick={() => startEditingName(member.user_id)}
                            >
                              이름 변경
                            </button>
                          )}
                        </span>
                      </div>
                    )
                  })}
                </div>
                <div className="row" style={{ gap: 10, marginTop: 16 }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ flex: 1 }}
                    onClick={goToFamilyLetters}
                    disabled={loading}
                  >
                    {loading
                      ? '새로고침 중...'
                      : '가족편지로 가기'}
                  </button>
                  
                </div>
              </>
            )}
          </div>
          )}
        </div>
      </RequireLogin>
      {toast.node}
    </div>
  )
}