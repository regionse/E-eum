import { useParams, Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { getPolicy } from '../../api/welfare.js'
import { useAsync, Async, FitBadge, useToast } from '../../components/ui/index.jsx'
import { addRecent, toggleFav, isFav } from '../../store/history.js'

// WEL-104 · 맞춤 지원 정책 상세보기
export default function PolicyDetail() {
  const { id } = useParams()
  const state = useAsync(() => getPolicy(id), [id])
  const toast = useToast()
  const [, force] = useState(0)

  // 상세를 열면 최근이력에 기록 (덜다 홈의 '최근 본 제도')
  useEffect(() => {
    const p = state.data
    if (p) addRecent('welfare', { id: p.id, name: p.name, provider: p.provider, tags: p.tags })
  }, [state.data])

  const onFav = (p) => {
    const added = toggleFav('welfare', { id: p.id, name: p.name, provider: p.provider, tags: p.tags })
    toast.show(added ? '즐겨찾기에 담았어요' : '즐겨찾기에서 뺐어요')
    force((n) => n + 1)
  }

  return (
    <div className="container page" style={{ maxWidth: 720 }}>
      <Async state={state} empty={<div className="empty">정책을 찾을 수 없어요.</div>}>
        {(p) => (
          <>
            <Link to="/welfare" className="btn btn-plain btn-sm" style={{ marginBottom: 12 }}>← 목록으로</Link>
            <div className="card card-pad">
              <div className="row" style={{ justifyContent: 'space-between', gap: 10, marginBottom: 10 }}>
                <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
                  <FitBadge fit={p.fit} />
                  {p.tags.map((t) => <span key={t} className="badge badge-gray">{t}</span>)}
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => onFav(p)}>{isFav('welfare', p.id) ? '★ 즐겨찾기됨' : '☆ 즐겨찾기'}</button>
              </div>
              <h1 className="section-title" style={{ fontSize: 24 }}>{p.name}</h1>
              <p className="muted" style={{ margin: '8px 0 16px' }}>{p.summary}</p>

              {/* AI 추천 이유 */}
              <div style={{ background: 'var(--teal-50)', borderRadius: 10, padding: 14, marginBottom: 16 }}>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--teal-700)', marginBottom: 6 }}>AI 추천 이유</div>
                <ul>{p.reasons.map((r) => <li key={r} style={{ fontSize: 14, color: 'var(--ink-soft)' }}>· {r}</li>)}</ul>
              </div>

              {/* 기본 정보 */}
              <h3 style={{ fontSize: 16, marginBottom: 8 }}>기본 정보</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, padding: '14px 0', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)' }}>
                <Info label="담당 기관" value={p.provider} />
                <Info label="카테고리" value={p.category} />
                <Info label="지원 형태" value={p.supportType} />
                <Info label="지원 주기" value={p.cycle} />
                <Info label="지원 규모" value={p.amount} accent />
              </div>

              {/* 정책 상세 */}
              <h3 style={{ fontSize: 16, margin: '20px 0 8px' }}>정책 상세</h3>
              <Detail label="정책 소개" value={p.detail} />
              <Detail label="지원 대상" value={p.target} />
              <Detail label="선정 기준" value={p.criteria} />
              <Detail label="지원 내용" value={p.amount} />
              <Detail label="신청 방법" value={p.method} />
              <Detail label="문의" value={p.contact} />

              {/* 관련 서류 — pdf 있을 때만 노출(WEL-104) */}
              {p.pdfUrl && (
                <button className="btn btn-ghost btn-block" style={{ marginTop: 16 }}
                  onClick={() => toast.show('관련 서류(PDF)는 실제 연동 시 다운로드돼요 (mock)')}>
                  📄 관련 서류 다운받기
                </button>
              )}
              <a href={p.applyUrl} target="_blank" rel="noreferrer" className="btn btn-primary btn-block btn-lg" style={{ marginTop: 10 }}>신청 페이지로 이동 ↗</a>
            </div>
          </>
        )}
      </Async>
      {toast.node}
    </div>
  )
}

function Info({ label, value, accent }) {
  return (
    <div>
      <div className="muted" style={{ fontSize: 13 }}>{label}</div>
      <div style={{ fontWeight: 700, color: accent ? 'var(--teal-700)' : 'inherit' }}>{value || '—'}</div>
    </div>
  )
}

function Detail({ label, value }) {
  if (!value) return null
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 3 }}>{label}</div>
      <p style={{ color: 'var(--ink-soft)', lineHeight: 1.7, margin: 0, fontSize: 14 }}>{value}</p>
    </div>
  )
}
