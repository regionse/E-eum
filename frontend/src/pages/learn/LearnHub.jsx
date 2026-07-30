import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHead, useToast, Modal } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { listMaps, getMap, resumeMap, deleteMap, clearItdaDraft, loadItdaDraft } from '../../api/learn.js'
import { useAuth } from '../../store/auth.jsx'

// 저장된 미래설계지도 한 개 — 방향(직업) + 자격/강좌 수 + 이어서하기/삭제.
//  카드 몸통을 누르면 상세 팝업이 열린다(읽기 전용). 버튼 영역은 클릭이 겹치지 않게 전파를 막는다.
function MapCard({ m, onOpen, onResume, onDelete, busy }) {
  const date = m.created_at ? new Date(m.created_at).toLocaleDateString('ko-KR') : ''
  return (
    <div className="card card-pad card-hover" style={{ marginBottom: 14, cursor: 'pointer' }}
      onClick={() => onOpen(m)} role="button" tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') onOpen(m) }}>
      <div className="row" style={{ justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <div className="row" style={{ gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span className="badge badge-teal" style={{ fontSize: 12 }}>🗺️ {m.status}</span>
            <b style={{ fontSize: 19, color: 'var(--teal-700)' }}>{m.job}</b>
            {m.group && <span className="muted" style={{ fontSize: 13.5 }}>· {m.group}</span>}
          </div>
          <div className="muted" style={{ fontSize: 13.5, marginTop: 7 }}>
            자격증 {m.n_cert}개 · 강좌 {m.n_course}개{date ? ` · ${date} 저장` : ''} · 눌러서 자세히 보기
          </div>
        </div>
        <div className="row" style={{ gap: 6, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
          <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => onResume(m)}>이어서하기 →</button>
          <button className="btn btn-plain btn-sm" disabled={busy} onClick={() => onDelete(m)} aria-label="지도 삭제">🗑</button>
        </div>
      </div>
    </div>
  )
}


// 지도 상세 팝업 — 저장해 둔 방향·자격증·강좌·국비훈련을 한눈에. 대화 카드와 같은 순서로 읽히게 구성.
function MapDetail({ data, onClose, onResume }) {
  const g = data?.goal
  if (!g) return null
  const S = ({ children }) => (
    <div className="muted" style={{ fontSize: 12.5, fontWeight: 700, letterSpacing: '.02em',
      textTransform: 'uppercase', marginBottom: 8 }}>{children}</div>
  )
  return (
    <Modal title={`🗺️ ${g.job}`} onClose={onClose}
      actions={<>
        <button className="btn btn-ghost" onClick={onClose}>닫기</button>
        <button className="btn btn-primary" onClick={() => onResume(data.mapRow)}>이어서하기 →</button>
      </>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxHeight: '60vh', overflowY: 'auto' }}>
        {/* 방향 */}
        <div>
          {g.group && <span className="badge badge-gray" style={{ fontSize: 12 }}>분야 · {g.group}</span>}
          {g.description && (
            <p style={{ fontSize: 14.5, lineHeight: 1.8, margin: '10px 0 0' }}>{g.description}</p>
          )}
        </div>

        {/* AI 추천 이유 */}
        {g.reason && (
          <div style={{ fontSize: 14, color: 'var(--teal-700)', background: 'var(--teal-50)',
            borderRadius: 10, padding: '10px 14px', lineHeight: 1.7 }}>
            <b style={{ display: 'block', marginBottom: 4 }}>AI 추천 이유</b>{g.reason}
          </div>
        )}

        {/* 자격증 — 대화 카드와 같은 컴팩트 한 줄 */}
        <div>
          <S>{g.no_cert_path ? '이 방향으로 가는 길' : `자격증 ${g.certs?.length || 0}개`}</S>
          {g.certs?.length > 0 ? (
            <div className="card" style={{ padding: '2px 14px' }}>
              {g.certs.map((s, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap',
                  padding: '10px 0', borderTop: i ? '1px solid var(--line)' : 'none' }}>
                  <b style={{ fontSize: 15 }}>{s.cert}</b>
                  {s.grade && <span className="muted" style={{ fontSize: 12.5 }}>{s.grade}</span>}
                  <span className={`badge ${s.entry_free ? 'badge-teal' : 'badge-amber'}`} style={{ fontSize: 12 }}>
                    {s.entry_free ? '조건 없음' : 'ⓘ 응시자격 확인'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted" style={{ fontSize: 14, lineHeight: 1.75, margin: 0 }}>{g.guide}</p>
          )}
        </div>

        {/* 강좌 */}
        {g.courses?.length > 0 && (
          <div>
            <S>무료 강의 {g.courses.length}개 · K-MOOC</S>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {g.courses.map((c, i) => (
                <a key={i} href={c.url} target="_blank" rel="noreferrer" className="card card-hover"
                  style={{ padding: '11px 14px', display: 'block', textDecoration: 'none' }}>
                  <div style={{ fontSize: 14.5, fontWeight: 600 }}>{c.title}</div>
                  <div className="muted" style={{ fontSize: 12.5, marginTop: 3 }}>
                    {c.professor || 'K-MOOC'} · 수강 신청 →
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* 국비 훈련 */}
        {g.hire?.url && (
          <div>
            <S>국비 실전 훈련</S>
            <div className="card" style={{ padding: '13px 15px', background: 'var(--teal-50)', borderColor: 'var(--teal-100)' }}>
              <div className="muted" style={{ fontSize: 13, marginBottom: 10, lineHeight: 1.6 }}>{g.hire.note}</div>
              <a className="btn btn-primary btn-sm" href={g.hire.url} target="_blank" rel="noreferrer">{g.hire.label} →</a>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

export default function LearnHub() {
  const nav = useNavigate()
  const toast = useToast()
  const { user } = useAuth()
  const [maps, setMaps] = useState(null)   // null=로딩중, []=없음
  const [busy, setBusy] = useState(false)
  const [askDel, setAskDel] = useState(null)
  const [detail, setDetail] = useState(null)     // 지도 상세 팝업 {goal, mapRow}
  const [askNew, setAskNew] = useState(false)
  const [draft] = useState(() => loadItdaDraft(user?.user_id))               // 진행 중인(저장 안 한) 대화
  const ongoing = !!(draft && draft.msgs && draft.msgs.length > 1)   // GREET만 있으면 진행 중 아님
  const lastMsg = ongoing ? draft.msgs[draft.msgs.length - 1] : null
  const preview = lastMsg ? (lastMsg.kind === 'goal' ? `방향: ${lastMsg.goal?.job || ''}` : String(lastMsg.text || '').slice(0, 50)) : ''
  const startNew = () => { if (ongoing) { setAskNew(true); return } clearItdaDraft(user?.user_id); nav('/learn/chat') }
  const confirmNew = () => { clearItdaDraft(user?.user_id); setAskNew(false); nav('/learn/chat') }

  const load = async () => {
    try { setMaps(await listMaps()) } catch { setMaps([]) }
  }
  useEffect(() => { if (user) load(); else setMaps([]) }, [user])   // eslint-disable-line

  const onResume = async (m) => {
    setBusy(true)
    try {
      const sid = 'itda-' + Math.random().toString(36).slice(2)
      const res = await resumeMap(m.map_id, sid)
      clearItdaDraft(user?.user_id)                                         // 이전 임시대화 비우고 저장본으로 복원
      nav('/learn/chat', { state: { sid, goal: res.goal } })   // 채팅으로 복원해 이어감
    } catch (e) { toast.show(e?.message || '이어서하기에 실패했어요') }
    finally { setBusy(false) }
  }
  //  지도 카드 클릭 → 저장된 내용을 읽기 전용으로 불러 팝업. 세션은 건드리지 않는다.
  const onOpen = async (m) => {
    setBusy(true)
    try {
      const res = await getMap(m.map_id)
      setDetail({ goal: res.goal, mapRow: m })
    } catch (e) { toast.show(e?.message || '지도를 불러오지 못했어요') }
    finally { setBusy(false) }
  }
  const doDelete = async () => {
    const m = askDel; setAskDel(null); setBusy(true)
    try { await deleteMap(m.map_id); await load(); toast.show('지도를 삭제했어요') }
    catch (e) { toast.show(e?.message || '삭제에 실패했어요') }
    finally { setBusy(false) }
  }

  return (
    <div className="container page" style={{ maxWidth: 820 }}>
      <PageHead title="🌱 잇다" sub="되고 싶은 모습을 말하면, 어울리는 방향과 그 길(자격증·강좌·국비훈련)을 지도로 그려드려요." />

      <RequireLogin axis="잇다">
        {ongoing && (
          <Link to="/learn/chat" className="card card-pad card-hover" style={{ display: 'block', marginBottom: 20, background: 'var(--teal-50)', borderColor: 'var(--teal-200)' }}>
            <div className="row" style={{ justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <div style={{ minWidth: 0 }}>
                <b style={{ color: 'var(--teal-700)', fontSize: 16 }}>🌱 진행 중인 대화</b>
                <div className="muted" style={{ fontSize: 13.5, marginTop: 6, maxWidth: 460, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{preview}</div>
              </div>
              <span className="btn btn-primary btn-sm" style={{ flexShrink: 0 }}>이어서 대화하기 →</span>
            </div>
          </Link>
        )}
        <h3 style={{ fontSize: 19, margin: '4px 0 16px' }}>내 미래설계지도</h3>
        {maps === null ? (
          <div className="muted" style={{ padding: 20 }}>불러오는 중…</div>
        ) : maps.length === 0 ? (
          <div className="card card-pad center" style={{ background: 'var(--teal-50)', borderColor: 'var(--teal-100)' }}>
            <div style={{ fontSize: 36 }}>🌱</div>
            <h3 style={{ margin: '12px 0 6px' }}>아직 그려둔 지도가 없어요</h3>
            <p className="muted" style={{ fontSize: 14.5, lineHeight: 1.7 }}>되고 싶은 모습을 말하면, 지금 위치부터 목표까지 첫 지도를 그려드릴게요.</p>
            <button className="btn btn-primary btn-lg" style={{ marginTop: 18 }} onClick={startNew}>첫 지도 그리기 →</button>
          </div>
        ) : (
          <>
            {maps.map((m) => (
              <MapCard key={m.map_id} m={m} busy={busy} onOpen={onOpen}
                onResume={onResume} onDelete={(x) => setAskDel(x)} />
            ))}
            <button className="btn btn-primary btn-block" style={{ marginTop: 6 }} onClick={startNew}>＋ 새 지도 그리기</button>
          </>
        )}
      </RequireLogin>

      {detail && (
        <MapDetail data={detail} onClose={() => setDetail(null)}
          onResume={(m) => { setDetail(null); onResume(m) }} />
      )}
      {askDel && (
        <Modal title="이 지도를 삭제할까요?" onClose={() => setAskDel(null)}
          actions={<>
            <button className="btn btn-ghost" onClick={() => setAskDel(null)}>취소</button>
            <button className="btn btn-danger" onClick={doDelete}>삭제</button>
          </>}>
          <p className="muted" style={{ marginTop: 0 }}>「{askDel.job}」 미래설계지도가 사라져요. 되돌릴 수 없어요.</p>
        </Modal>
      )}
      {askNew && (
        <Modal title="새로 시작할까요?" onClose={() => setAskNew(false)}
          actions={<>
            <button className="btn btn-ghost" onClick={() => setAskNew(false)}>취소</button>
            <button className="btn btn-primary" onClick={confirmNew}>새로 시작</button>
          </>}>
          <p className="muted" style={{ marginTop: 0 }}>진행 중인 대화가 있어요. 새로 시작하면 지금 대화가 사라져요. (저장한 미래설계지도는 그대로예요.)</p>
        </Modal>
      )}
      {toast.node}
    </div>
  )
}
