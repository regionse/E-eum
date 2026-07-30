import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHead, useToast, Modal } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { popularPolicies } from '../../mock/db.js'
import { getFavs, getRecoSessions, hasUsed, toggleFav, isFav } from '../../store/history.js'

// 인기 정책 한 줄 (오른쪽 즐겨찾기 별)
function PopularRow({ p, onFav, favActive }) {
  return (
    <Link to={`/welfare/policy/${p.id}`} className="list-row">
      <div className="row" style={{ gap: 12, minWidth: 0 }}>
        <span className="badge badge-teal">제도</span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700 }}>{p.name}</div>
          <div className="muted" style={{ fontSize: 13 }}>{p.provider}{p.favCount ? ` · ⭐ ${p.favCount.toLocaleString()}` : ''}</div>
        </div>
      </div>
      <button className="btn btn-plain btn-sm" onClick={(e) => onFav(e, p)} aria-label="즐겨찾기">{favActive ? '★' : '☆'}</button>
    </Link>
  )
}

// 섹션 헤더 (제목 + 전체보기)
function SectionHead({ title, onAll }) {
  return (
    <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
      <h3 style={{ fontSize: 17 }}>{title}</h3>
      {onAll && <button className="btn btn-plain btn-sm" onClick={onAll}>전체보기 ›</button>}
    </div>
  )
}

const CARD_GRID = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12, marginBottom: 'var(--sp-6)' }

// WEL-101 · 덜다 메인 (첫 방문 / 기존 사용자) — 즐겨찾기·추천이력·인기 + 전체보기 모달
export default function WelfareHub() {
  const nav = useNavigate()
  const toast = useToast()
  const [, force] = useState(0) // 즐겨찾기 토글 후 리렌더
  const [modal, setModal] = useState(null)       // 'fav' | 'reco'
  const [confirmDel, setConfirmDel] = useState(null)

  const used = hasUsed('welfare')
  const favs = getFavs('welfare')
  const recos = getRecoSessions('welfare')

  const viewReco = (s) => { setModal(null); nav('/welfare/policy/result', { state: { ...s.input, replay: true } }) }
  const onFav = (e, p) => {
    e.preventDefault(); e.stopPropagation()
    const added = toggleFav('welfare', { id: p.id, name: p.name, provider: p.provider, tags: p.tags })
    toast.show(added ? '즐겨찾기에 담았어요' : '즐겨찾기에서 뺐어요')
    force((n) => n + 1)
  }
  const delFav = (p) => { toggleFav('welfare', p); setConfirmDel(null); toast.show('즐겨찾기에서 뺐어요'); force((n) => n + 1) }

  const popular = (
    <>
      <SectionHead title="🔥 많은 사용자가 즐겨찾기한 정책 TOP 5" />
      <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
        {popularPolicies.map((p) => <PopularRow key={p.id} p={p} onFav={onFav} favActive={isFav('welfare', p.id)} />)}
      </div>
    </>
  )

  return (
    <div className="container page" style={{ maxWidth: 900 }}>
      <PageHead title="💧 덜다 · AI 맞춤 정책 추천" sub="조건에 맞는 지원 제도를 찾아, 오늘을 버틸 힘을 드려요."
        right={<Link to="/welfare/policy" className="btn btn-primary btn-sm">나에게 맞는 정책 찾기 →</Link>} />

      <RequireLogin axis="덜다">
        {!used ? (
          // 첫 방문 (WEL-101 · 첫 방문): 서비스 소개 + 시작 유도 + 인기 정책
          <>
            <div className="card card-pad center" style={{ background: 'var(--teal-50)', borderColor: 'var(--teal-100)', marginBottom: 'var(--sp-6)' }}>
              <div style={{ fontSize: 34 }}>👋</div>
              <h3 style={{ margin: '10px 0 6px' }}>아직 덜다를 이용하지 않으셨어요</h3>
              <p className="muted">몇 가지만 답하면, 받을 수 있는 지원 제도를 추려드려요.</p>
              <button className="btn btn-primary btn-lg" style={{ marginTop: 16 }} onClick={() => nav('/welfare/policy')}>나에게 맞는 정책 찾기</button>
            </div>
            {popular}
          </>
        ) : (
          // 기존 사용자 (WEL-101 · 기존 사용자): 즐겨찾기 · 추천 이력 · 인기
          <>
            <SectionHead title="⭐ 나의 정책 즐겨찾기" onAll={favs.length ? () => setModal('fav') : null} />
            {favs.length === 0 ? (
              <div className="card card-pad muted" style={{ marginBottom: 'var(--sp-6)' }}>즐겨찾기한 정책이 없어요.</div>
            ) : (
              <div style={CARD_GRID}>
                {favs.slice(0, 3).map((p) => (
                  <div key={p.id} className="card card-pad">
                    <div style={{ fontWeight: 700, marginBottom: 10 }}>{p.name}</div>
                    <Link to={`/welfare/policy/${p.id}`} className="btn btn-ghost btn-sm">상세보기</Link>
                  </div>
                ))}
              </div>
            )}

            <SectionHead title="🕘 최근 정책 추천 이력" onAll={recos.length ? () => setModal('reco') : null} />
            {recos.length === 0 ? (
              <div className="card card-pad muted" style={{ marginBottom: 'var(--sp-6)' }}>아직 추천받은 이력이 없어요.</div>
            ) : (
              <div style={CARD_GRID}>
                {recos.slice(0, 3).map((s) => (
                  <div key={s.id} className="card card-pad">
                    <div className="muted" style={{ fontSize: 13 }}>{s.date}</div>
                    <div style={{ fontWeight: 700, margin: '6px 0 10px' }}>추천 정책 {s.count}건</div>
                    <button className="btn btn-ghost btn-sm" onClick={() => viewReco(s)}>결과보기</button>
                  </div>
                ))}
              </div>
            )}

            {popular}
          </>
        )}
      </RequireLogin>

      {/* 즐겨찾기 전체보기 모달 (WEL-101 · u38) */}
      {modal === 'fav' && (
        <Modal title="나의 정책 즐겨찾기" onClose={() => setModal(null)}>
          <div className="stack" style={{ gap: 6, maxHeight: '55vh', overflowY: 'auto' }}>
            {favs.map((p) => (
              <div key={p.id} className="list-row">
                <span style={{ fontWeight: 600 }}>{p.name}</span>
                <span className="row" style={{ gap: 8 }}>
                  <Link to={`/welfare/policy/${p.id}`} className="btn btn-ghost btn-sm" onClick={() => setModal(null)}>상세보기</Link>
                  <button className="btn btn-plain btn-sm" onClick={() => setConfirmDel(p)}>즐겨찾기 해제</button>
                </span>
              </div>
            ))}
          </div>
        </Modal>
      )}

      {/* 추천 이력 전체보기 모달 (WEL-101 · u39) */}
      {modal === 'reco' && (
        <Modal title="최근 정책 추천 이력" onClose={() => setModal(null)}>
          <div className="stack" style={{ gap: 6, maxHeight: '55vh', overflowY: 'auto' }}>
            {recos.map((s) => (
              <div key={s.id} className="list-row">
                <span><b>{s.date}</b> <span className="muted" style={{ marginLeft: 8 }}>맞춤 추천 정책 {s.count}건</span></span>
                <button className="btn btn-ghost btn-sm" onClick={() => viewReco(s)}>결과보기</button>
              </div>
            ))}
          </div>
        </Modal>
      )}

      {/* 즐겨찾기 해제 확인 */}
      {confirmDel && (
        <Modal title="즐겨찾기에서 삭제하시겠습니까?" onClose={() => setConfirmDel(null)}
          actions={<><button className="btn btn-plain" onClick={() => setConfirmDel(null)}>취소</button>
            <button className="btn btn-danger" onClick={() => delFav(confirmDel)}>삭제</button></>}>
          <p className="muted">{confirmDel.name}</p>
        </Modal>
      )}
      {toast.node}
    </div>
  )
}
