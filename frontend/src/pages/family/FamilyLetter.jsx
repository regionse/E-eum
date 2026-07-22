import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHead, useToast } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import { useFamily, fmtTimelineTime } from '../../store/family.jsx'

const MED_LABEL = { m: '아침', l: '점심', d: '저녁' }
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
  const { familyLinked } = useAuth()
  const { records, meds, toggleMed, addRecord } = useFamily()
  const toast = useToast()
  const [body, setBody] = useState('')
  const [error, setError] = useState('')

  const canSubmit = body.trim().length > 0

  const submit = () => {
    if (!body.trim()) { setError('돌봄 기록을 한 줄 이상 입력해주세요.'); return }
    addRecord(body)
    setBody('')
    setError('')
    toast.show('돌봄 기록을 남겼어요')
  }

  const onChange = (e) => {
    setBody(e.target.value.slice(0, MAX))
    if (error) setError('')
  }

  // FAM-001 우상단 [기록 남기기] — 공백 제외 1자 이상일 때 활성
  const submitBtn = (
    <button className="btn btn-primary btn-sm" onClick={submit} disabled={!familyLinked || !canSubmit}>
      기록 남기기
    </button>
  )

  return (
    <div className="container page">
      <PageHead title="💌 가족편지" sub="가족이 함께 남기는 돌봄 기록 — 이 기록이 곧 ‘돌봄일지’예요." right={submitBtn} />
      <RequireLogin axis="가족편지">
        {!familyLinked ? <EmptyState /> : (
          <div className="family-layout">
            {/* 왼쪽: 오늘의 돌봄 기록 입력 + 타임라인(= 돌봄일지) */}
            <section style={{ minWidth: 0 }}>
              <div className="card card-pad" style={{ marginBottom: 16 }}>
                <h3 style={{ marginBottom: 10 }}>오늘의 돌봄 기록</h3>
                <input
                  className={`input ${error ? 'error' : ''}`}
                  placeholder="오늘의 돌봄을 한 줄로 남겨주세요 (예: 점심 약 드렸어요)"
                  value={body}
                  onChange={onChange}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); submit() } }}
                  maxLength={MAX}
                />
                <div className="row" style={{ justifyContent: 'space-between', marginTop: 8, gap: 12 }}>
                  {error
                    ? <span style={{ color: 'var(--danger)', fontSize: 13, fontWeight: 600 }}>⚠ {error}</span>
                    : <span className="hint">가족에게 공유돼요 · 작성자·시각은 자동으로 기록돼요</span>}
                  <span className="muted" style={{ fontSize: 12.5, flexShrink: 0 }}>{body.length}/{MAX}</span>
                </div>
              </div>

              <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10, gap: 12 }}>
                <span style={{ fontWeight: 700 }}>돌봄 기록 <span className="muted" style={{ fontWeight: 500, fontSize: 13.5 }}>· 그대로 돌봄일지가 돼요</span></span>
                <Link to="/family/diary" className="btn btn-ghost btn-sm">전체보기 ›</Link>
              </div>

              <div className="stack" style={{ gap: 12 }}>
                {records.map((r) => (
                  <div key={r.id} className="card card-pad">
                    <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6, gap: 8 }}>
                      <span className={`badge ${r.author === '나' ? 'badge-teal' : 'badge-gray'}`}>{r.author}</span>
                      <span className="muted" style={{ fontSize: 13 }}>{fmtTimelineTime(r)}</span>
                    </div>
                    <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{r.body}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* 오른쪽: 오늘의 약 + 돌봄일지 안내 */}
            <aside className="side-col" style={{ minWidth: 0 }}>
              <div className="card card-pad" style={{ marginBottom: 12 }}>
                <h3 style={{ marginBottom: 6 }}>오늘의 약</h3>
                <p className="muted" style={{ fontSize: 12.5, marginBottom: 8 }}>시간 설정 없이 체크만 · 매일 자정 초기화</p>
                {['m', 'l', 'd'].map((k) => (
                  <label key={k} className="list-row" style={{ cursor: 'pointer', padding: '10px 4px' }}>
                    <span style={{ fontWeight: 600 }}>{MED_LABEL[k]} 약</span>
                    <input type="checkbox" checked={!!meds[k]} onChange={() => toggleMed(k)} />
                  </label>
                ))}
              </div>
              <div className="principle">
                <div style={{ fontWeight: 700, color: 'var(--teal-800)', marginBottom: 4 }}>📔 돌봄일지 안내</div>
                <p style={{ color: 'var(--teal-800)', fontSize: 13.5, lineHeight: 1.6 }}>
                  여기 남긴 기록이 그대로 ‘돌봄일지’로 쌓여요. 가족이 함께 확인하고, <b>전체보기</b>에서 게시판으로 한눈에 돌아볼 수 있어요.
                </p>
              </div>
            </aside>
          </div>
        )}
      </RequireLogin>
      {toast.node}
    </div>
  )
}
