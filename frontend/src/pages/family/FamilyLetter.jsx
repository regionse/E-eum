import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHead, useToast } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import { useFamily, fmtTimelineTime } from '../../store/family.jsx'

const MAX = 500

// FAM-001 빈 상태 — 연결된 가족이 없을 때
function EmptyState() {
  return (
    <div className="card card-pad center" style={{ maxWidth: 520, margin: '0 auto', padding: 'var(--sp-7)' }}>
      <div style={{ fontSize: 44 }}>🔗</div>
      <h3 style={{ margin: '14px 0 6px' }}>아직 연결된 가족이 없어요</h3>
      <p className="muted">가족과 연결하면 함께 돌봄을 기록할 수 있어요.<br />기록은 연결된 가족만 볼 수 있어요.</p>
      <div className="row" style={{ gap: 10, justifyContent: 'center', marginTop: 22, flexWrap: 'wrap' }}>
        <Link to="/family/connect" className="btn btn-primary">가족 초대하기</Link>
        <Link to="/family/join" className="btn btn-ghost">초대 코드 입력</Link>
      </div>
    </div>
  )
}

export default function FamilyLetter() {
  const [saving, setSaving] = useState(false)
  const { familyLinked } = useAuth()
  const { records, addRecord, refreshFamily } = useFamily()
  const toast = useToast()
  const [body, setBody] = useState('')
  const [error, setError] = useState('')

  // 테스트 데이터처럼 미래 날짜가 있어도 가장 최신 기록일을 기준으로
  // 해당 날짜를 포함한 최근 7일치만 가족편지 메인 화면에 표시한다.
  const weeklyRecords = useMemo(() => {
    const datedRecords = records
      .map((record) => ({
        record,
        timestamp: new Date(`${record.date}T00:00:00`).getTime(),
      }))
      .filter(({ timestamp }) => Number.isFinite(timestamp))

    if (datedRecords.length === 0) {
      return []
    }

    const latestTimestamp = Math.max(
      ...datedRecords.map(({ timestamp }) => timestamp),
    )
    const startTimestamp = latestTimestamp - 6 * 24 * 60 * 60 * 1000

    return datedRecords
      .filter(
        ({ timestamp }) =>
          timestamp >= startTimestamp && timestamp <= latestTimestamp,
      )
      .sort((a, b) => b.timestamp - a.timestamp)
      .map(({ record }) => record)
  }, [records])

  // 다른 가족이 작성한 최신 편지를 화면에 들어올 때 다시 불러온다.
  useEffect(() => {
    refreshFamily().catch(() => {
      // 조회 오류는 FamilyProvider의 error 상태에서 관리한다.
    })
  }, [refreshFamily])

  const canSubmit = body.trim().length > 0

  const submit = async () => {
    const content = body.trim()

    if (!content) {
      setError(
        '돌봄 기록을 한 줄 이상 입력해주세요.',
      )
      return
    }

    if (saving) {
      return
    }

    setSaving(true)
    setError('')

    try {
      await addRecord(content)

      setBody('')
      toast.show('돌봄 기록을 남겼어요')
    } catch (requestError) {
      setError(
        requestError.message ??
        '돌봄 기록 저장에 실패했습니다.',
      )
    } finally {
      setSaving(false)
    }
  }

  const onChange = (e) => {
    setBody(e.target.value.slice(0, MAX))
    if (error) setError('')
  }

  // [기록 남기기] — 입력 카드 우하단. 공백 제외 1자 이상일 때 활성
  const submitBtn = (
    <button
      className="btn btn-primary btn-sm"
      onClick={submit}
      disabled={
        !familyLinked ||
        !canSubmit ||
        saving
      }
    >
      {saving ? '저장 중...' : '기록 남기기'}
    </button>
  )

  return (
    <div className="container page">
      {/* 설명(PageHead)도 아래 컨텐츠와 같은 760 컬럼에 맞춰 가운데 정렬 — 왼쪽 치우침 교정 */}
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <PageHead title="💌 가족편지" sub="가족이 함께 남기는 돌봄 기록 — 이 기록이 곧 ‘돌봄일지’예요." right={
          <Link
            to="/family/connect"
            className="btn btn-ghost btn-sm"
          >
            가족 연결
          </Link>
        }/>
      </div>
      <RequireLogin axis="가족편지">
        {!familyLinked ? <EmptyState /> : (
          <div style={{ maxWidth: 760, margin: '0 auto' }}>
            {/* 오늘의 돌봄 기록 입력 + 타임라인(= 돌봄일지) — 오늘의 약·안내 제거, 단일 컬럼 */}
            <section style={{ minWidth: 0 }}>
              <div className="card card-pad" style={{ marginBottom: 16 }}>
                <h3 style={{ marginBottom: 10 }}>오늘의 돌봄 기록</h3>
                <input
                  className={`input ${error ? 'error' : ''}`}
                  placeholder="오늘의 돌봄을 한 줄로 남겨주세요 (예: 점심 약 드렸어요)"
                  value={body}
                  onChange={onChange}
                  onKeyDown={(event) => {
                    if (
                      event.key === 'Enter' &&
                      !event.nativeEvent.isComposing
                    ) {
                      event.preventDefault()
                      submit()
                    }
                  }}
                  maxLength={MAX}
                />
                <div className="row" style={{ justifyContent: 'space-between', marginTop: 10, gap: 12 }}>
                  {error
                    ? <span style={{ color: 'var(--danger)', fontSize: 13, fontWeight: 600 }}>⚠ {error}</span>
                    : <span className="hint">가족에게 공유돼요 · 작성자·시각은 자동으로 기록돼요</span>}
                  <div className="row" style={{ gap: 10, flexShrink: 0 }}>
                    <span className="muted" style={{ fontSize: 12.5 }}>{body.length}/{MAX}</span>
                    {submitBtn}
                  </div>
                </div>
              </div>

              <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10, gap: 12 }}>
                <span style={{ fontWeight: 700 }}>돌봄 기록 <span className="muted" style={{ fontWeight: 500, fontSize: 13.5 }}>· 그대로 돌봄일지가 돼요</span></span>
                <Link to="/family/diary" className="btn btn-ghost btn-sm">전체보기 ›</Link>
              </div>

              <div className="stack" style={{ gap: 12 }}>
                {weeklyRecords.map((r) => (
                  <div key={r.id} className="card card-pad">
                    <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6, gap: 8 }}>
                      <span className={`badge ${r.author === '나' ? 'badge-teal' : 'badge-gray'}`}>{r.author}</span>
                      <span className="muted" style={{ fontSize: 13 }}>{fmtTimelineTime(r)}</span>
                    </div>
                    <p style={{ maxHeight:65, overflowY:'auto', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{r.body}</p>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
      </RequireLogin>
      {toast.node}
    </div>
  )
}