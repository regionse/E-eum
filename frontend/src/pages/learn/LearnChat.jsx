import { useState, useRef, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useToast, Modal } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import { chatItda, saveMap, loadItdaDraft, saveItdaDraft } from '../../api/learn.js'
import { BAD_WORDS } from '../../utils/text.js'

// 잇다 대화 — 관심·가치를 말하면 AI가 대화로 이해해 '방향(직업)'을 잡고,
// 그 직업의 자격증(≤3) + 무료강좌 + 국비훈련 안내를 미래설계지도로 그려준다.
//  · 대화(이해)는 백엔드 LLM이, 결과(직업·자격·강좌)는 코드가 정한다. (자유로운 상담 + 갇힌 출력)
//  · 선고가 아니라 안내 — "이런 방향이 맞아 보여요" (2026-07-29 NCS 원툴)
const GREET = { role: 'bot', kind: 'text', text: '어떤 일이 잘 맞을지 같이 찾아봐요. 관심 있는 것이나 좋아하는 걸 편하게 말해주세요 — 막연해도 괜찮아요.' }
const GOAL_EXAMPLES = ['나무나 식물을 다루는 일', '컴퓨터로 뭔가 만드는 일', '사람에게 도움이 되는 일']
export default function LearnChat() {
  const toast = useToast()
  const loc = useLocation()
  const { user } = useAuth()
  const uid = user?.user_id                          // ★ 대화 draft를 사용자별로 분리(계정 섞임 방지)
  const rs = loc.state?.goal ? loc.state : null      // '이어서하기'로 들어온 경우(복원된 세션+지도)
  const draft = loadItdaDraft(uid)                   // 이 사용자의 보관 대화만 복원. '새 지도/이어서하기'는 LearnHub가 비운다.
  const [msgs, setMsgs] = useState(() => draft ? draft.msgs
    : rs
    ? [{ role: 'bot', kind: 'text', text: '저장한 지도를 이어서 볼게요 — 더 이야기하면 방향을 다듬을 수 있어요.' },
       { role: 'bot', kind: 'goal', goal: rs.goal, alternatives: [] }]
    : [GREET])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)      // 응답 대기(입력 잠금 + 로딩)
  const [warn, setWarn] = useState('')         // 빈 입력 경고
  const [mapped, setMapped] = useState(draft ? !!draft.mapped : !!rs)
  const [askSave, setAskSave] = useState(null) // 저장할 목표 또는 null
  const [saving, setSaving] = useState(false)
  const [chatZoom, setChatZoom] = useState(1)  // 채팅 내용(글자·카드까지) 확대·축소 — ＋/－
  const endRef = useRef(null)
  const sidRef = useRef(null)
  if (!sidRef.current) sidRef.current = draft?.sid || rs?.sid || ('itda-' + Math.random().toString(36).slice(2))
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])
  useEffect(() => {   // 새로고침·중간이탈에도 이어지도록 마지막 대화를 이 사용자 키에 저장
    saveItdaDraft(uid, { sid: sidRef.current, msgs, mapped })
  }, [msgs, mapped, uid])

  const push = (m) => setMsgs((p) => [...p, m])

  // 발화 전송 → 백엔드 상담 한 턴 (물어보거나 / 결과 카드)
  const send = async (raw) => {
    if (busy) return
    const q = (raw ?? input).trim(); setWarn('')
    if (!q) { setWarn('내용을 입력해 주세요.'); return }
    setInput('')
    const meaningful = q.replace(/[^가-힣a-zA-Z]/g, '')
    if (!meaningful || /^[ㄱ-ㅎㅏ-ㅣ\s]+$/.test(q)) {
      push({ role: 'me', kind: 'text', text: q })
      push({ role: 'bot', kind: 'text', text: '앗, 잘 이해하지 못했어요. 관심 있는 분야나 좋아하는 걸 말로 적어주시겠어요?' })
      return
    }
    push({ role: 'me', kind: 'text', text: q })
    if (BAD_WORDS.some((w) => q.includes(w))) {
      push({ role: 'bot', kind: 'text', text: '그런 쪽은 도와드리기 어려워요. 되고 싶은 모습이나 관심 있는 걸 들려주세요.' })
      return
    }
    setBusy(true)
    const sid = sidRef.current                 // 이 요청이 속한 세션 — 응답 전 '새 목표'로 바뀌면 버린다
    try {
      const res = await chatItda(sid, q)
      if (sid !== sidRef.current) return
      if (res.type === 'result') {
        if (res.reply) push({ role: 'bot', kind: 'text', text: res.reply })
        push({ role: 'bot', kind: 'goal', goal: res.goal, alternatives: res.alternatives || [] })
        setMapped(true)
      } else {
        push({ role: 'bot', kind: 'text', text: res.reply })
      }
    } catch {
      if (sid === sidRef.current)
        push({ role: 'bot', kind: 'text', text: '잠시 문제가 생겼어요. 잠깐 뒤 다시 말씀해 주세요.' })
    } finally {
      if (sid === sidRef.current) setBusy(false)
    }
  }

  // 저장 — 백엔드가 세션에 캐시한 '마지막 카드'를 담는다 → session_id 만 넘기면 됨.
  const doSave = async () => {
    setAskSave(null); setSaving(true)
    try {
      const r = await saveMap(sidRef.current)
      toast.show(`미래설계지도에 저장했어요 · ${r.job}`)
    } catch (e) {
      toast.show(e?.message || '저장에 실패했어요. 로그인 상태를 확인해 주세요.')
    } finally { setSaving(false) }
  }

  return (
    <div className="container page" style={{ maxWidth: 960 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 18, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <h1 style={{ fontSize: 24, letterSpacing: '-.02em', margin: 0 }}>🌱 잇다</h1>
          <p className="muted" style={{ fontSize: 14, margin: '4px 0 0' }}>대화하듯 관심을 말하면, 어울리는 방향과 그 길(자격증·강좌·국비훈련)을 그려드려요.</p>
        </div>
        <Link to="/learn" className="btn btn-ghost btn-lg" style={{ flexShrink: 0 }}>← 잇다 홈</Link>
      </div>
      <RequireLogin axis="잇다">
        <div className="card card-pad">
          <div className="row" style={{ justifyContent: 'flex-start', marginBottom: 10 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, border: '1.5px solid var(--teal-200)', background: 'var(--teal-50)', borderRadius: 999, padding: '4px 6px' }}>
              <span style={{ fontSize: 12.5, fontWeight: 800, color: 'var(--teal-700)', padding: '0 6px' }}>글자 크기</span>
              <button aria-label="작게" disabled={chatZoom <= 0.8}
                onClick={() => setChatZoom((z) => Math.max(0.8, +(z - 0.15).toFixed(2)))}
                style={{ width: 30, height: 30, borderRadius: 999, border: '1.5px solid var(--teal-300)', background: '#fff', color: 'var(--teal-700)', fontSize: 18, fontWeight: 800, lineHeight: 1, cursor: 'pointer' }}>－</button>
              <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--ink)', minWidth: 42, textAlign: 'center' }}>{Math.round(chatZoom * 100)}%</span>
              <button aria-label="크게" disabled={chatZoom >= 1.6}
                onClick={() => setChatZoom((z) => Math.min(1.6, +(z + 0.15).toFixed(2)))}
                style={{ width: 30, height: 30, borderRadius: 999, border: '1.5px solid var(--teal-300)', background: '#fff', color: 'var(--teal-700)', fontSize: 18, fontWeight: 800, lineHeight: 1, cursor: 'pointer' }}>＋</button>
            </div>
          </div>
          <div className="chat-wrap" role="log" aria-live="polite"
            style={{ height: 500, fontSize: 15.5, zoom: chatZoom }}>
            {msgs.map((m, i) => (
              <ChatItem key={i} m={m} onSave={(g) => setAskSave(g)} />
            ))}
            {busy && <TypingBubble />}
            <div ref={endRef} />
          </div>

          {msgs.length <= 1 && <Examples items={GOAL_EXAMPLES} onPick={send} />}
          {warn && <p role="alert" style={{ color: '#c0392b', fontSize: 14, margin: '10px 0 0' }}>⚠ {warn}</p>}
          <div className="chat-input">
            <input className="input" disabled={busy} value={input}
              aria-label="관심사 입력"
              style={{ fontSize: 15.5, padding: '13px 15px' }}
              placeholder={mapped ? '더 이야기하거나, 다른 관심을 말해도 돼요…' : '관심 있는 것을 자유롭게 적어주세요…'}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) send() }} />
            <button className="btn btn-primary" style={{ fontSize: 15 }} onClick={() => send()} disabled={busy}>보내기</button>
          </div>
          <p className="hint" style={{ marginTop: 10 }}>답변은 AI가 하는 것이라 확실하지 않을 수 있어요. 오류가 생기면 문의 부탁드려요!</p>
        </div>
        {toast.node}
        {askSave && (
          <Modal title="이 지도를 저장할까요?" onClose={() => setAskSave(null)}
            actions={<>
              <button className="btn btn-ghost" onClick={() => setAskSave(null)}>취소</button>
              <button className="btn btn-primary" onClick={doSave} disabled={saving}>{saving ? '저장 중…' : '저장'}</button>
            </>}>
            <p className="muted" style={{ marginTop: 0 }}>잇다 홈의 “내 미래설계지도”에 저장되고, 언제든 이어서 볼 수 있어요.</p>
          </Modal>
        )}
      </RequireLogin>
    </div>
  )
}

function ChatItem({ m, onSave }) {
  if (m.kind === 'text') return (
    <div className={`bubble ${m.role === 'me' ? 'me' : 'bot'}`}
      style={{ fontSize: 15.5, lineHeight: 1.7, padding: '12px 16px' }}>{m.text}</div>
  )
  if (m.kind === 'goal') return <GoalCard goal={m.goal} alternatives={m.alternatives} onSave={onSave} />
  return null
}

function Examples({ items, onPick }) {
  return (
    <div style={{ marginTop: 14 }}>
      <div className="muted" style={{ fontSize: 14, marginBottom: 8 }}>이렇게 말해도 돼요</div>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        {items.map((s) => <button key={s} className="chip" style={{ fontSize: 14 }} onClick={() => onPick(s)}>{s}</button>)}
      </div>
    </div>
  )
}

const THINK_STEPS = ['말씀을 읽고 있어요…', '어울리는 방향을 찾고 있어요…', '자격증·무료강좌·국비훈련을 맞춰보고 있어요…']

function TypingBubble() {
  const [i, setI] = useState(0)
  useEffect(() => {
    const t1 = setTimeout(() => setI(1), 1300)
    const t2 = setTimeout(() => setI(2), 3200)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [])
  return (
    <div className="bubble bot" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, width: 'fit-content', fontSize: 15 }}>
      <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
      {THINK_STEPS[i]}
    </div>
  )
}

// 미래설계지도 카드 — '방향(직업)'이 주인공. 선고 아닌 안내(2026-07-29 NCS).
//  방향(직무+설명) → 자격증(≤3) 또는 내일배움카드 → 무료강의(K-MOOC+열림강의) → 국비 실전훈련.
//  세로로 나눠 '다다다닥' 대신 섹션마다 숨 쉬게 배치(가독성).
function GoalCard({ goal, alternatives, onSave }) {
  const [openCourse, setOpenCourse] = useState(null)
  const certs = goal.certs || []
  return (
    <div className="card card-pad" style={{ alignSelf: 'stretch', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* 상단 */}
      <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <span className="badge badge-teal" style={{ fontSize: 12.5 }}>🗺️ 미래설계지도</span>
        {goal.group && <span className="muted" style={{ fontSize: 13.5 }}>분야 · {goal.group}</span>}
      </div>

      {/* ① 방향(직업) — 안내 톤 + NCS 설명 */}
      <div>
        <div className="muted" style={{ fontSize: 13.5, marginBottom: 6 }}>이런 방향이 맞아 보여요</div>
        <div style={{ fontWeight: 800, fontSize: 27, color: 'var(--teal-700)', lineHeight: 1.25 }}>{goal.job}</div>
        {goal.description && (
          <p style={{ fontSize: 15, lineHeight: 1.8, color: 'var(--ink)', margin: '12px 0 0' }}>{goal.description}</p>
        )}
        {goal.reason && (
          <div style={{ fontSize: 14, color: 'var(--teal-700)', marginTop: 12, background: 'var(--teal-50)', borderRadius: 10, padding: '10px 14px' }}>
            <b style={{ display: 'block', marginBottom: 4 }}>💡 AI 추천 이유</b>{goal.reason}
          </div>
        )}
      </div>

      {/* ② 자격증 — 한 개씩 깔끔한 카드 */}
      <div>
        <div className="section-title" style={{ fontSize: 16, marginBottom: 12 }}>
          {goal.no_cert_path ? '이 방향으로 가는 길' : '이 방향의 자격증'}
        </div>
        {certs.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {certs.map((s, i) => (
              <div key={i} className="card" style={{ padding: '14px 16px', borderColor: s.entry_free ? 'var(--teal-200)' : 'var(--line)' }}>
                <div className="row" style={{ gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                  <b style={{ fontSize: 16.5 }}>{s.cert}</b>
                  {s.grade && <span className="muted" style={{ fontSize: 13 }}>{s.grade}</span>}
                  <span style={{ flex: 1, minWidth: 12 }} />
                  <span className={`badge ${s.entry_free ? 'badge-teal' : 'badge-amber'}`}
                    title={s.entry_free ? '제한 없이 응시 가능' : (s.entry_note || '응시자격 확인 필요')}
                    style={{ fontSize: 12.5, cursor: s.entry_free ? 'default' : 'help' }}>
                    {s.entry_free ? '✓ 지금 바로 응시 가능' : 'ⓘ 응시자격 확인'}
                  </span>
                </div>
                {s.exam && <div className="muted" style={{ fontSize: 13.5, marginTop: 9 }}>📅 다음 시험 · {s.exam}</div>}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ background: 'var(--teal-50)', borderRadius: 12, padding: '16px 18px', fontSize: 14.5, lineHeight: 1.75 }}>
            {String(goal.guide || '').split('. ').map((s, i, arr) => (
              <p key={i} style={{ margin: i ? '6px 0 0' : 0 }}>{i === 0 ? '🌱 ' : ''}{s}{i < arr.length - 1 ? '.' : ''}</p>
            ))}
          </div>
        )}
        {alternatives?.length > 0 && (
          <div className="muted" style={{ fontSize: 13.5, marginTop: 12 }}>다른 방향도 있어요 · {alternatives.join(' · ')}</div>
        )}
      </div>

      {/* ③ 배움 순서 — 무료강의(K-MOOC) → 실전(국비). 단계로 이어준다. (열림강의는 URL 없어 제거 2026-07-29) */}
      <div>
        <div className="section-title" style={{ fontSize: 16, marginBottom: 3 }}>이 방향, 이렇게 배워나가요</div>
        <div className="muted" style={{ fontSize: 13, marginBottom: 14 }}>무료 강의로 배우고 → 국비 실전훈련까지, 순서대로 이어드려요.</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* 1 · K-MOOC 무료강의 (진짜 course_url) */}
          {goal.has_courses && (
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--teal-700)', marginBottom: 8 }}>
                1 · 무료 강의 수강 신청{' '}
                <span className="muted" style={{ fontWeight: 400, fontSize: 12.5 }}>K-MOOC · 무료</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {goal.courses.map((c, i) => (
                  <button key={i} onClick={() => setOpenCourse(c)} className="card card-hover"
                    style={{ textAlign: 'left', cursor: 'pointer', padding: '13px 16px', display: 'block', width: '100%' }}>
                    <div className="row" style={{ justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ fontSize: 15, fontWeight: 600 }}>{c.title}</div>
                      <span className="badge badge-gray" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>관련 {Math.round((c.score || 0) * 100)}%</span>
                    </div>
                    <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{c.professor || 'K-MOOC'} · 무료 강의 수강 신청 →</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 2 · 국비 실전훈련 (고용24 딥링크) */}
          {goal.hire?.url && (
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--teal-700)', marginBottom: 8 }}>2 · 국비 실전 훈련</div>
              <div className="card" style={{ padding: '14px 16px', background: 'var(--teal-50)', borderColor: 'var(--teal-100)' }}>
                <div className="muted" style={{ fontSize: 13.5, marginBottom: 11, lineHeight: 1.6 }}>{goal.hire.note}</div>
                <a className="btn btn-primary" href={goal.hire.url} target="_blank" rel="noreferrer">{goal.hire.label} →</a>
              </div>
            </div>
          )}

        </div>
        {!goal.has_courses && !goal.hire?.url && (
          <div className="muted" style={{ fontSize: 14 }}>아직 딱 맞는 강의를 못 찾았어요.</div>
        )}
      </div>

      {/* 저장 */}
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={() => onSave(goal)}>🗺️ 이 지도 저장하기</button>
      </div>

      {/* 축 연결 — 돌봄 부담을 덜어야 배울 시간이 생긴다 */}
      <Link to="/welfare" className="card card-pad card-hover" style={{ display: 'block', background: 'var(--surface)' }}>
        <b>🤝 배울 시간이 부족하신가요?</b>
        <span className="muted" style={{ fontSize: 13.5 }}> — 덜다에서 돌봄 부담을 덜어줄 지원을 찾아보세요 →</span>
      </Link>

      {openCourse && <CourseDetail course={openCourse} onClose={() => setOpenCourse(null)} />}
    </div>
  )
}

// 강좌 상세 팝업 — 우리가 가진 것만: 정보·유사도·K-MOOC 링크·출처.
function CourseDetail({ course, onClose }) {
  const pct = Math.round((course.score || 0) * 100)
  return (
    <Modal title="강좌 상세" onClose={onClose}
      actions={<>
        <button className="btn btn-ghost" onClick={onClose}>닫기</button>
        {course.url
          ? <a className="btn btn-primary" href={course.url} target="_blank" rel="noreferrer">무료 강의 수강 신청 →</a>
          : <span className="muted" style={{ fontSize: 12 }}>수강 링크 준비 중</span>}
      </>}>
      <div style={{ fontWeight: 700, fontSize: 17 }}>{course.title}</div>
      {(course.professor || course.classfy) && (
        <div className="muted" style={{ fontSize: 13.5, marginTop: 5 }}>
          {[course.professor, course.classfy].filter(Boolean).join(' · ')}
        </div>
      )}
      {pct > 0 && (
        <div style={{ background: 'var(--teal-50)', borderRadius: 10, padding: '12px 14px', marginTop: 14, fontSize: 13.5, lineHeight: 1.7 }}>
          추천 이유 · <b style={{ color: 'var(--teal-700)' }}>관련도 {pct}%</b><br />
          <span className="muted" style={{ fontSize: 12.5 }}>고른 방향과 관련도가 높은 강좌예요. 수강이 필수는 아니에요.</span>
        </div>
      )}
      <div className="muted" style={{ fontSize: 12, marginTop: 14 }}>출처: K-MOOC · 국가평생교육진흥원</div>
    </Modal>
  )
}
