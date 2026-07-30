import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { PageHead, useToast, Modal } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { chatItda, resetItda, saveMap } from '../../api/learn.js'
import { BAD_WORDS } from '../../utils/text.js'

// 잇다 대화 — 관심·가치를 말하면 AI가 대화로 이해해 '자격증 목표'를 잡고,
// 그 자격증에 맞는 무료강좌(또는 훈련 안내) + 시험일을 미래설계지도로 그려준다.
//  · 대화(이해)는 백엔드의 LLM이, 결과(자격증·강좌·시험일)는 코드가 정한다. (자유로운 상담 + 갇힌 출력)
const GREET = { role: 'bot', kind: 'text', text: '어떤 일이 잘 맞을지 같이 찾아봐요. 관심 있는 것이나 좋아하는 걸 편하게 말해주세요.' }
const GOAL_EXAMPLES = ['나무나 식물을 다루는 일', '컴퓨터로 뭔가 만드는 일', '사람에게 도움이 되는 일']

export default function LearnChat() {
  const toast = useToast()
  const [msgs, setMsgs] = useState([GREET])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)      // 응답 대기(입력 잠금 + 로딩)
  const [warn, setWarn] = useState('')         // 빈 입력 경고
  const [turn, setTurn] = useState(0)          // 백엔드가 알려주는 대화 턴
  const [maxTurn, setMaxTurn] = useState(3)
  const [mapped, setMapped] = useState(false)  // 자격증 목표가 나온 뒤
  const [askSave, setAskSave] = useState(null) // 저장할 목표 또는 null
  const endRef = useRef(null)
  const sidRef = useRef(null)
  if (!sidRef.current) sidRef.current = 'itda-' + Math.random().toString(36).slice(2)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  const push = (m) => setMsgs((p) => [...p, m])

  // 발화 전송 → 백엔드 상담 한 턴 (물어보거나 / 자격증 결과)
  const send = async (raw) => {
    if (busy) return
    const q = (raw ?? input).trim(); setWarn('')
    if (!q) { setWarn('내용을 입력해 주세요.'); return }
    setInput('')
    const meaningful = q.replace(/[^가-힣a-zA-Z]/g, '')
    if (!meaningful || /^[ㄱ-ㅎㅏ-ㅣ\s]+$/.test(q)) {
      push({ role: 'me', kind: 'text', text: q })
      push({ role: 'bot', kind: 'text', text: '잘 이해하지 못했어요. 관심 있는 분야나 좋아하는 것들을 말로 적어주시겠어요?' })
      return
    }
    push({ role: 'me', kind: 'text', text: q })
    if (BAD_WORDS.some((w) => q.includes(w))) {
      push({ role: 'bot', kind: 'text', text: '저는 교육 강좌 추천 AI봇이라 그런 쪽은 도와드리기 어려워요. ㅠㅡㅠ 되고 싶은 모습이나 관심 있는 걸 들려주세요.' })
      return
    }
    setBusy(true)
    try {
      const res = await chatItda(sidRef.current, q)
      if (res.type === 'result') {
        if (res.reply) push({ role: 'bot', kind: 'text', text: res.reply })
        push({ role: 'bot', kind: 'goal', goal: res.goal, alternatives: res.alternatives || [] })
        setMapped(true)
      } else {
        // 'ask' 또는 'blocked' — 봇의 말만 표시
        push({ role: 'bot', kind: 'text', text: res.reply })
      }
      if (typeof res.turn === 'number') setTurn(res.turn)
      if (typeof res.max_turn === 'number') setMaxTurn(res.max_turn)
    } catch {
      push({ role: 'bot', kind: 'text', text: '죄송해요. 저희 측에 잠시 문제가 생겼어요. 잠깐 뒤 다시 말씀해 주세요.' })
    } finally {
      setBusy(false)
    }
  }

  const reset = async () => {
    await resetItda(sidRef.current)
    sidRef.current = 'itda-' + Math.random().toString(36).slice(2)
    setMsgs([GREET]); setInput(''); setTurn(0); setMapped(false); setWarn('')
  }

  const doSave = async () => {
    const goal = askSave; setAskSave(null)
    await saveMap({ goalLabel: goal.cert, weeksText: goal.exam, courses: (goal.courses || []).map((t) => ({ title: t })) })
    toast.show('미래설계지도를 저장했어요')
  }

  return (
    <div className="container page" style={{ maxWidth: 760 }}>
      <PageHead title="🌱 잇다" sub="대화하듯 관심을 말하면, 뜻을 읽어 자격증 목표와 배움 지도를 그려드려요."
        right={
          <div className="row" style={{ gap: 6 }}>
            {msgs.length > 1 && <button className="btn btn-plain btn-sm" onClick={reset}>🔄 새 목표</button>}
            <Link to="/learn" className="btn btn-ghost btn-sm">← 잇다 홈</Link>
          </div>
        } />
      <RequireLogin axis="잇다">
        <div className="card card-pad">
          <div className="chat-wrap">
            {msgs.map((m, i) => (
              <ChatItem key={i} m={m} onSave={(g) => setAskSave(g)} />
            ))}
            {busy && <TypingBubble />}
            <div ref={endRef} />
          </div>

          {msgs.length <= 1 && <Examples items={GOAL_EXAMPLES} onPick={send} />}
          {warn && <p style={{ color: '#c0392b', fontSize: 13, margin: '10px 0 0' }}>⚠ {warn}</p>}
          <div className="chat-input">
            <input className="input" disabled={busy} value={input}
              placeholder={mapped ? '더 이야기하거나, 다른 관심을 말해도 돼요…' : '관심 있는 것을 자유롭게 적어주세요…'}
              onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()} />
            <button className="btn btn-primary" onClick={() => send()} disabled={busy}>보내기</button>
          </div>
          <p className="hint" style={{ marginTop: 10 }}>대화는 익명으로 처리돼요. 이해는 AI가, 강좌·시험일은 실제 데이터에서 가져와요.</p>
        </div>
        {toast.node}
        {askSave && (
          <Modal title="이 지도를 저장할까요?" onClose={() => setAskSave(null)}
            actions={<>
              <button className="btn btn-ghost" onClick={() => setAskSave(null)}>취소</button>
              <button className="btn btn-primary" onClick={doSave}>저장</button>
            </>}>
            <p className="muted" style={{ marginTop: 0 }}>잇다 홈의 “내 미래설계지도”에 저장되고, 언제든 이어서 볼 수 있어요.</p>
          </Modal>
        )}
      </RequireLogin>
    </div>
  )
}

function ChatItem({ m, onSave }) {
  if (m.kind === 'text') return <div className={`bubble ${m.role === 'me' ? 'me' : 'bot'}`}>{m.text}</div>
  if (m.kind === 'goal') return <GoalCard goal={m.goal} alternatives={m.alternatives} onSave={onSave} />
  return null
}

function Examples({ items, onPick }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div className="muted" style={{ fontSize: 13, marginBottom: 6 }}>이렇게 말해도 돼요</div>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        {items.map((s) => <button key={s} className="chip" onClick={() => onPick(s)}>{s}</button>)}
      </div>
    </div>
  )
}

function TypingBubble() {
  return (
    <div className="bubble bot" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, width: 'fit-content' }}>
      <span className="spinner" style={{ width: 15, height: 15, borderWidth: 2 }} />
      들으면서 생각하고 있어요…
    </div>
  )
}

// 미래설계지도 카드 — 자격증 목표 + 시험일 + (무료강좌 또는 훈련안내) + 저장 + 덜다 연결
function GoalCard({ goal, alternatives, onSave }) {
  return (
    <div className="card card-pad" style={{ alignSelf: 'stretch' }}>
      <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
        <span className="badge badge-teal">미래설계지도</span>
        <span className="muted" style={{ fontSize: 13 }}>🎯 {goal.field}</span>
      </div>
      <div style={{ fontWeight: 800, fontSize: 18, color: 'var(--teal-700)' }}>◎ {goal.cert}</div>
      {goal.reason && <div style={{ fontSize: 13, color: 'var(--teal-700)', marginTop: 4 }}>💡 {goal.reason}</div>}
      <div className="muted" style={{ fontSize: 13.5, marginTop: 8 }}>📅 {goal.exam}</div>

      {goal.has_courses ? (
        <div style={{ marginTop: 12 }}>
          <b style={{ fontSize: 14 }}>추천 무료강좌 (K-MOOC)</b>
          {goal.courses.map((c, i) => (
            <div key={i} className="row" style={{ gap: 10, marginTop: 8, alignItems: 'flex-start' }}>
              <span className="badge badge-teal" style={{ flexShrink: 0 }}>{i + 1}</span>
              <span style={{ fontSize: 14 }}>{c}</span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ marginTop: 12, background: 'var(--teal-50)', borderRadius: 10, padding: '10px 14px', fontSize: 13.5, lineHeight: 1.6 }}>
          ⚠ {goal.guide}
        </div>
      )}

      {alternatives?.length > 0 && (
        <div className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>다른 후보: {alternatives.join(' · ')}</div>
      )}

      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn btn-primary btn-sm" onClick={() => onSave(goal)}>이 지도 저장하기</button>
      </div>

      {/* 축 연결 — 돌봄 부담을 덜어야 배울 시간이 생긴다 */}
      <Link to="/welfare" className="card card-pad card-hover" style={{ display: 'block', marginTop: 12, background: 'var(--teal-50)', borderColor: 'var(--teal-100)' }}>
        <b>🤝 배울 시간이 부족하신가요?</b>
        <span className="muted" style={{ fontSize: 13 }}> — 덜다에서 돌봄 부담을 덜어줄 지원을 찾아보세요 →</span>
      </Link>
    </div>
  )
}
