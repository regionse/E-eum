import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHead, useToast, Modal } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { listMaps, resumeMap, deleteMap, clearItdaDraft, loadItdaDraft } from '../../api/learn.js'
import { useAuth } from '../../store/auth.jsx'

// 저장된 미래설계지도 한 개 — 방향(직업) + 자격/강좌 수 + 이어서하기/삭제.
function MapCard({ m, onResume, onDelete, busy }) {
  const date = m.created_at ? new Date(m.created_at).toLocaleDateString('ko-KR') : ''
  return (
    <div className="card card-pad" style={{ marginBottom: 14 }}>
      <div className="row" style={{ justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <div className="row" style={{ gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span className="badge badge-teal" style={{ fontSize: 12 }}>🗺️ {m.status}</span>
            <b style={{ fontSize: 19, color: 'var(--teal-700)' }}>{m.job}</b>
            {m.group && <span className="muted" style={{ fontSize: 13.5 }}>· {m.group}</span>}
          </div>
          <div className="muted" style={{ fontSize: 13.5, marginTop: 7 }}>
            자격증 {m.n_cert}개 · 강좌 {m.n_course}개{date ? ` · ${date} 저장` : ''}
          </div>
        </div>
        <div className="row" style={{ gap: 6, flexShrink: 0 }}>
          <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => onResume(m)}>이어서하기 →</button>
          <button className="btn btn-plain btn-sm" disabled={busy} onClick={() => onDelete(m)} aria-label="지도 삭제">🗑</button>
        </div>
      </div>
    </div>
  )
}

export default function LearnHub() {
  const nav = useNavigate()
  const toast = useToast()
  const { user } = useAuth()
  const [maps, setMaps] = useState(null)   // null=로딩중, []=없음
  const [busy, setBusy] = useState(false)
  const [askDel, setAskDel] = useState(null)
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
              <MapCard key={m.map_id} m={m} busy={busy} onResume={onResume} onDelete={(x) => setAskDel(x)} />
            ))}
            <button className="btn btn-primary btn-block" style={{ marginTop: 6 }} onClick={startNew}>＋ 새 지도 그리기</button>
          </>
        )}
      </RequireLogin>

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
