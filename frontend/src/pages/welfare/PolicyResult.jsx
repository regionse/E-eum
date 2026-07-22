import { useState, useEffect, useRef } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { findPolicies } from '../../api/welfare.js'
import { useAsync, Async, Loading, FitBadge, PageHead, useToast } from '../../components/ui/index.jsx'
import { toggleFav, isFav, addRecoSession } from '../../store/history.js'

// WEL-103 · 맞춤 지원 정책 결과 (이해한 상황 · 추천/결과없음 · 재상담)
export default function PolicyResult() {
  const { state: input } = useLocation()
  const nav = useNavigate()
  const state = useAsync(() => findPolicies(input || {}), [])
  const toast = useToast()
  const [, force] = useState(0)
  const saved = useRef(false)

  // 실제 추천이 성공하면(결과보기 재렌더는 제외) 최근 정책 추천 이력에 저장 (WEL-101)
  useEffect(() => {
    if (saved.current || !input || input.replay) return
    if (state.data && state.data.result === 'ok') {
      saved.current = true
      const d = new Date()
      const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      addRecoSession('welfare', { id: `RS-${d.getTime()}`, date, count: state.data.policies.length, input })
    }
  }, [state.data]) // eslint-disable-line

  const onFav = (p) => {
    const added = toggleFav('welfare', { id: p.id, name: p.name, provider: p.provider, tags: p.tags })
    toast.show(added ? '즐겨찾기에 담았어요' : '즐겨찾기에서 뺐어요')
    force((n) => n + 1)
  }

  return (
    <div className="container page" style={{ maxWidth: 780 }}>
      <PageHead title="맞춤 지원 정책 추천 결과" sub="입력하신 상황을 바탕으로 규칙에 맞춰 추려낸 정책이에요."
        right={<Link to="/welfare/policy" className="btn btn-ghost btn-sm">조건 다시 입력</Link>} />

      <Async state={state}
        loading={<Loading title="AI가 맞춤 정책을 찾고 있어요" sub="입력하신 정보를 분석 중이에요. 잠시만 기다려주세요." steps={['정보 분석', '자격 규칙 대조', '정책 정리']} />}>
        {(res) => (
          <div className="stack" style={{ gap: 14 }}>
            {/* AI가 이해한 현재 상황 */}
            <div className="card card-pad" style={{ background: 'var(--teal-50)', borderColor: 'var(--teal-100)' }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--teal-700)', marginBottom: 4 }}>🧠 AI가 이해한 현재 상황</div>
              <div style={{ fontSize: 14 }}>{res.understood}</div>
            </div>

            {res.result === 'none' ? (
              <NoResult reason={res.reason} />
            ) : (
              <>
                <div className="muted" style={{ fontSize: 13.5 }}>회원님의 상황을 분석해 가장 적합한 순서로 추천했어요.</div>
                {res.policies.map((p) => <PolicyCard key={p.id} p={p} onFav={onFav} favActive={isFav('welfare', p.id)} />)}

                <div className="row" style={{ gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginTop: 4 }}>
                  <Link to="/welfare/policy" className="btn btn-ghost btn-sm">조건 다시 입력하기</Link>
                  <button className="btn btn-ghost btn-sm"
                    onClick={() => nav('/welfare/policy', { state: { chat: true, ...(input || {}) } })}>AI와 다시 상담하기</button>
                  <a href="tel:129" className="btn btn-plain btn-sm">☎ 보건복지 상담센터 129</a>
                </div>
              </>
            )}
          </div>
        )}
      </Async>
      {toast.node}
    </div>
  )
}

function PolicyCard({ p, onFav, favActive }) {
  return (
    <div className="card card-pad card-hover">
      <div className="row" style={{ justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
        <h3 style={{ fontSize: 18 }}>{p.name}</h3>
        <span className="row" style={{ gap: 6 }}>
          <FitBadge fit={p.fit} />
          <button className="btn btn-plain btn-sm" onClick={() => onFav(p)} aria-label="즐겨찾기">{favActive ? '★' : '☆'}</button>
        </span>
      </div>
      <p className="muted" style={{ marginBottom: 10 }}>{p.summary}</p>
      <div style={{ background: 'var(--teal-50)', borderRadius: 10, padding: '10px 14px', marginBottom: 12 }}>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--teal-700)', marginBottom: 4 }}>추천 이유</div>
        <ul>{p.reasons.map((r) => <li key={r} style={{ fontSize: 14, color: 'var(--ink-soft)' }}>· {r}</li>)}</ul>
      </div>
      <div className="row" style={{ justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
        <span className="row muted" style={{ gap: 12, fontSize: 13.5 }}>
          <span>{p.provider}</span><span style={{ fontWeight: 700, color: 'var(--teal-700)' }}>{p.amount}</span>
        </span>
        <span className="row" style={{ gap: 8 }}>
          <Link to={`/welfare/policy/${p.id}`} className="btn btn-ghost btn-sm">상세보기</Link>
          <a href={p.applyUrl} target="_blank" rel="noreferrer" className="btn btn-primary btn-sm">신청하기 ↗</a>
        </span>
      </div>
    </div>
  )
}

// WEL-103 · 결과 없음 — 지어내지 않고, 사유 + 다른 도움 경로
function NoResult({ reason }) {
  return (
    <div className="card card-pad">
      <div style={{ fontWeight: 700, marginBottom: 6 }}>죄송해요. 입력하신 조건과 정확히 일치하는 정책을 찾지 못했어요.</div>
      <div style={{ background: 'var(--teal-50)', borderRadius: 10, padding: '10px 14px', margin: '8px 0 14px' }}>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--teal-700)', marginBottom: 4 }}>AI 분석 결과</div>
        <div style={{ fontSize: 14 }}>{reason}</div>
        <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 6 }}>조건을 수정하거나 추가 정보를 입력하시면 추천 가능한 정책을 다시 찾아드릴 수 있어요.</div>
      </div>
      <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 8 }}>다른 도움 받기</div>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <Link to="/welfare/policy" className="btn btn-primary btn-sm">조건 다시 입력하기</Link>
        <Link to="/share/map" className="btn btn-ghost btn-sm">나누다 기관 찾기 →</Link>
        <a href="tel:129" className="btn btn-plain btn-sm">☎ 보건복지 상담센터 129</a>
      </div>
    </div>
  )
}
