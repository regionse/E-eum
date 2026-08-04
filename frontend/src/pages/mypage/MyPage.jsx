import { useEffect, useState } from 'react'
import { NavLink, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../../store/auth.jsx'
import { useToast, PageHead, Modal } from '../../components/ui/index.jsx'
import { updateMe } from '../../api/auth.js'
import {
  getUserConsents,
  updateUserConsents,
  withdrawMe,
} from '../../api/mypage.js'
import { formatPhone } from '../../utils/form.js'

const TABS = [
  { to: '/mypage', end: true, label: '내 정보' },
  { to: '/mypage/consent', label: '동의 관리' },
  { to: '/mypage/withdraw', label: '회원 탈퇴' },
]

// 내 정보 (MYP-101~104) — 수정 시 비밀번호 확인 후 연락처·지역만 변경(아이디·생년월일 불변).
//  백엔드 PATCH /auth/me 호출 → 갱신된 user 로 스토어 갱신.
function Info() {
  const { user, login } = useAuth()
  const [edit, setEdit] = useState(false)
  const [form, setForm] = useState({ phone: '', region: '', pw: '' })
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  const startEdit = () => {
    setForm({ phone: user?.phone_number || '', region: user?.region_sido || '', pw: '' })
    setErr(''); setEdit(true)
  }
  const save = async () => {
    if (!form.pw) { setErr('본인 확인을 위해 현재 비밀번호를 입력해주세요.'); return }
    setSaving(true); setErr('')
    try {
      const updated = await updateMe({ password: form.pw, phone: form.phone, region: form.region })
      login(updated)                       // 스토어·localStorage 갱신
      setEdit(false)
      toast.show('정보가 수정되었어요')
    } catch (e) {
      setErr(e?.message || '수정에 실패했어요. 비밀번호를 다시 확인해주세요.')
    } finally { setSaving(false) }
  }

  const rows = [['아이디', user?.username], ['생년월일', user?.birthdate], ['연락처', user?.phone_number], ['지역', user?.region_sido]]

  return (
    <div className="card card-pad">
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
        <h3>내 정보</h3>
        {!edit && <button className="btn btn-ghost btn-sm" onClick={startEdit}>수정</button>}
      </div>

      {!edit ? (
        rows.map(([k, v]) => (
          <div key={k} className="list-row">
            <span className="muted">{k}</span>
            <span style={{ fontWeight: 600 }}>{v || '—'}</span>
          </div>
        ))
      ) : (
        <>
          <div className="list-row"><span className="muted">아이디</span><span style={{ fontWeight: 600 }}>{user?.username}</span></div>
          <div className="list-row"><span className="muted">생년월일</span><span style={{ fontWeight: 600 }}>{user?.birthdate || '—'}</span></div>
          <div className="field" style={{ marginTop: 10 }}><label>연락처</label>
            <input className="input" placeholder="010-0000-0000" maxLength={13} inputMode="numeric"
              value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: formatPhone(e.target.value) }))} /></div>
          <div className="field"><label>지역</label>
            <input className="input" placeholder="○○시/도" value={form.region}
              onChange={(e) => setForm((f) => ({ ...f, region: e.target.value }))} /></div>
          <div className="field"><label>비밀번호 확인 <span className="req">*</span></label>
            <input type="password" className={`input ${err ? 'error' : ''}`} placeholder="본인 확인용 현재 비밀번호"
              value={form.pw} onChange={(e) => setForm((f) => ({ ...f, pw: e.target.value }))} /></div>
          {err && <p className="err">{err}</p>}
          <div className="row" style={{ justifyContent: 'flex-end', gap: 10, marginTop: 12 }}>
            <button className="btn btn-plain" onClick={() => setEdit(false)} disabled={saving}>취소</button>
            <button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? '저장 중…' : '수정 완료'}</button>
          </div>
        </>
      )}
      {toast.node}
    </div>
  )
}

// 동의 관리 (MYP-301) — 필수 2 + 선택 2(위치·알림). 위치는 나누다 SHA-100 게이트와 연동.

function requestBrowserLocationPermission() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(
        new Error(
          '이 브라우저에서는 위치정보를 사용할 수 없습니다.',
        ),
      )
      return
    }

    navigator.geolocation.getCurrentPosition(
      () => resolve(),
      (positionError) => {
        if (positionError.code === positionError.PERMISSION_DENIED) {
          reject(
            new Error(
              '브라우저에서 위치 권한을 허용해주세요.',
            ),
          )
          return
        }

        reject(
          new Error(
            '현재 위치를 확인하지 못했습니다. 잠시 후 다시 시도해주세요.',
          ),
        )
      },
      {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 300000,
      },
    )
  })
}

function Consent() {
  const { userId } = useAuth()
  const [c, setC] = useState({
    tos: false,
    privacy: false,
    location: false,
    alarm: false,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [requestingLocation, setRequestingLocation] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!userId) {
      setError('로그인 사용자 정보를 확인할 수 없습니다.')
      setLoading(false)
      return
    }

    let active = true

    const loadConsents = async () => {
      try {
        setLoading(true)
        setError('')
        const result = await getUserConsents(userId)

        if (active) {
          setC({
            tos: result.is_terms_agreed,
            privacy: result.is_privacy_agreed,
            location: result.is_location_agreed,
            alarm: result.is_alarm_agreed,
          })
        }
      } catch (requestError) {
        if (active) {
          setError(
            requestError.message ||
              '동의 정보를 불러오지 못했습니다.',
          )
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    loadConsents()

    return () => {
      active = false
    }
  }, [userId])

  const items = [
    ['tos', '이용약관 동의', true],
    ['privacy', '개인정보 수집 및 이용 동의', true],
    ['location', '위치정보 서비스 이용약관', false],
    ['alarm', '알림 설정 동의', false],
  ]

  const changeConsent = async (key) => {
    if (key !== 'location') {
      setC((previous) => ({
        ...previous,
        [key]: !previous[key],
      }))
      return
    }

    // 체크 해제는 서비스 동의만 변경한다. 브라우저 권한은 보안상
    // 웹 코드에서 직접 해제할 수 없다.
    if (c.location) {
      setC((previous) => ({
        ...previous,
        location: false,
      }))
      return
    }

    try {
      setRequestingLocation(true)
      setError('')
      await requestBrowserLocationPermission()
      setC((previous) => ({
        ...previous,
        location: true,
      }))
    } catch (requestError) {
      setC((previous) => ({
        ...previous,
        location: false,
      }))
      setError(
        requestError.message ||
          '위치 권한을 요청하지 못했습니다.',
      )
    } finally {
      setRequestingLocation(false)
    }
  }

  const save = async () => {
    if (!userId || saving) return

    try {
      setSaving(true)
      setError('')
      const result = await updateUserConsents(userId, {
        is_location_agreed: c.location,
        is_alarm_agreed: c.alarm,
      })

      setC({
        tos: result.is_terms_agreed,
        privacy: result.is_privacy_agreed,
        location: result.is_location_agreed,
        alarm: result.is_alarm_agreed,
      })
      setSaved(true)
    } catch (requestError) {
      setError(
        requestError.message ||
          '동의 설정을 저장하지 못했습니다.',
      )
    } finally {
      setSaving(false)
    }
  }
  return (
    <div className="card card-pad">
      <h3 style={{ marginBottom: 12 }}>동의 관리</h3>
      {loading && (
        <p className="muted" style={{ marginBottom: 12 }}>
          동의 정보를 불러오는 중이에요.
        </p>
      )}
      {error && <p className="err">{error}</p>}
      {items.map(([k, label, req]) => (
        <label key={k} className="list-row" style={{ cursor: req ? 'default' : 'pointer' }}>
          <span>{label} <span className={req ? 'req' : 'muted'} style={{ fontSize: 13 }}>({req ? '필수' : '선택'})</span></span>
          <input
            type="checkbox"
            checked={c[k]}
            disabled={
              req || loading || saving || requestingLocation
            }
            onChange={() => changeConsent(k)}
          />
        </label>
      ))}
      <p className="callout-warn" style={{ marginTop: 16, fontSize: 14 }}>동의를 철회하시면 일부 기능이 제한될 수 있어요. <b>위치정보</b>를 끄면 나누다 기관 연결 시 다시 동의를 받아요.</p>
      <button
        className="btn btn-primary"
        style={{ marginTop: 14 }}
        onClick={save}
        disabled={loading || saving || requestingLocation}
      >
        {requestingLocation
          ? '위치 권한 확인 중…'
          : saving
            ? '저장 중…'
            : '설정 완료'}
      </button>
      {saved && (
        <Modal title="설정 완료" onClose={() => setSaved(false)}
          actions={<button className="btn btn-primary btn-block" onClick={() => setSaved(false)}>확인</button>}>
          <p className="muted">동의 관리 설정이 완료되었습니다.</p>
        </Modal>
      )}
    </div>
  )
}

// 회원 탈퇴 (MYP-601~603): 사유 선택 → 재확인 모달 → 완료 모달
const WITHDRAW_REASONS = [
  '방문을 잘 하지 않아요',
  '사이트가 이용하기 불편해요',
  '개인정보를 삭제하고 싶어요',
  '기타',
]

function Withdraw() {
  const { logout, unlinkFamily } = useAuth()
  const navigate = useNavigate()
  const [reason, setReason] = useState('')
  const [etc, setEtc] = useState('')
  const [step, setStep] = useState('form') // 'form' → 'confirm' → 'done'
  const [withdrawing, setWithdrawing] = useState(false)
  const [error, setError] = useState('')
  const canNext = reason !== '' && (reason !== '기타' || etc.trim() !== '')

  const finish = () => { logout(); unlinkFamily(); navigate('/') }

  const confirmWithdraw = async () => {
    if (!canNext || withdrawing) return

    const finalReason =
      reason === '기타'
        ? etc.trim()
        : reason

    try {
      setWithdrawing(true)
      setError('')
      await withdrawMe(finalReason)
      setStep('done')
    } catch (requestError) {
      setError(
        requestError.message ||
          '회원 탈퇴 처리에 실패했습니다.',
      )
      setStep('form')
    } finally {
      setWithdrawing(false)
    }
  }

  return (
    <div className="card card-pad">
      <h3 style={{ marginBottom: 12 }}>회원 탈퇴</h3>
      <p className="muted" style={{ marginBottom: 16, lineHeight: 1.7 }}>
        서비스에 만족을 드리지 못해 죄송해요.<br />
        탈퇴 사유를 남겨 주시면 서비스 개선에 힘쓰겠습니다.
      </p>

      <label className="muted" style={{ fontSize: 13.5 }}>탈퇴 사유</label>
      <select className="select" style={{ marginTop: 6 }} value={reason} onChange={(e) => setReason(e.target.value)}>
        <option value="" disabled>탈퇴 사유 선택</option>
        {WITHDRAW_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
      </select>

      {reason === '기타' && (
        <textarea className="textarea" style={{ marginTop: 10 }} placeholder="사유를 자유롭게 적어주세요"
          value={etc} onChange={(e) => setEtc(e.target.value.slice(0, 200))} />
      )}

      <div className="row" style={{ justifyContent: 'flex-end', marginTop: 16 }}>
        <button className="btn btn-primary" disabled={!canNext} onClick={() => setStep('confirm')}>다음</button>
      </div>

      {error && <p className="err">{error}</p>}

      {step === 'confirm' && (
        <Modal title="정말 탈퇴하시겠습니까?" onClose={() => setStep('form')}
          actions={<>
            <button className="btn btn-plain" onClick={() => setStep('form')}>취소</button>
            <button
              className="btn btn-primary"
              onClick={confirmWithdraw}
              disabled={withdrawing}
            >
              {withdrawing ? '처리 중…' : '확인'}
            </button>
          </>}>
          <p className="muted" style={{ lineHeight: 1.7 }}>
            탈퇴하면 해당 계정으로 다시 로그인할 수 없습니다. 계속 진행하시겠어요?
          </p>
        </Modal>
      )}

      {step === 'done' && (
        <Modal title="탈퇴 완료" onClose={finish}
          actions={<button className="btn btn-primary" onClick={finish}>확인</button>}>
          <p className="muted">회원 탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사해요.</p>
        </Modal>
      )}
    </div>
  )
}

export default function MyPage() {
  const { user } = useAuth()

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="container page">
      <PageHead
        title="마이페이지"
        sub={`${user.username || ''} 님, 안녕하세요.`}
      />

      <div className="side-layout">
        <aside className="side-nav">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
            >
              {tab.label}
            </NavLink>
          ))}
        </aside>

        <section style={{ minWidth: 0 }}>
          <Routes>
            <Route index element={<Info />} />
            <Route
              path="alerts"
              element={
                <Navigate
                  to="/mypage"
                  replace
                />
              }
            />
            <Route
              path="consent"
              element={<Consent />}
            />
            <Route
              path="withdraw"
              element={<Withdraw />}
            />
          </Routes>
        </section>
      </div>
    </div>
  )
}