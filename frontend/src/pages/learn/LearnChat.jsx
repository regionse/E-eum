import { useState, useRef, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useToast, Modal } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { useAuth } from '../../store/auth.jsx'
import { chatItda, saveMap, loadItdaDraft, saveItdaDraft, clearItdaDraft } from '../../api/learn.js'
import { BAD_WORDS } from '../../utils/text.js'

// 잇다 대화 — 관심·가치를 말하면 AI가 대화로 이해해 '방향(직업)'을 잡고,
// 그 직업의 자격증(≤3) + 무료강좌 + 국비훈련 안내를 미래설계지도로 그려준다.
//  · 대화(이해)는 백엔드 LLM이, 결과(직업·자격·강좌)는 코드가 정한다. (자유로운 상담 + 갇힌 출력)
//  · 선고가 아니라 안내 — "이런 방향이 맞아 보여요" (2026-07-29 NCS 원툴)
//  ★ 첫인사 교체(2026-08-04) — 예전 문구는 인사 없이 곧장 «관심 있는 것이나 좋아하는 걸
//    말해주세요» 였다. **첫마디부터 숙제를 내는 셈**이고, 그 숙제는 여유가 있어야 풀린다.
//    우리 사용자는 하루 2시간 자며 주 7일 일하기도 한다(월드비전 2024 심층면접).
//    ⇒ 인사만 하고, 질문은 누구나 답할 수 있는 것 하나로 연다(백엔드 _ASK_Q 와 같은 결).
const GREET = { role: 'bot', kind: 'text', greet: 'hello', text: '안녕하세요, 교육·상담을 맡은 잇다예요.\n요즘 뭐 하고 지내세요? 일이든 돌봄이든, 하고 계신 걸 그대로 말씀해 주셔도 돼요.' }
//  '이어서하기'로 들어왔을 때의 머리말. 위 GREET 과 똑같이 **우리가 쓴 안내문**이라 같은 규칙을 받는다.
const RESUME_GREET = { role: 'bot', kind: 'text', greet: 'resume', text: '저장한 지도를 이어서 볼게요 — 더 이야기하면 방향을 다듬을 수 있어요.' }
const GOAL_EXAMPLES = ['나무나 식물을 다루는 일', '컴퓨터로 뭔가 만드는 일', '사람에게 도움이 되는 일']

//  ★ 머리말은 '저장된 대화'가 아니라 '지금 코드의 문구'로 되살린다 (2026-08-05)
//  무슨 일이 있었나 — 8/4 에 GREET 을 새 문구로 바꿨는데 화면엔 계속 옛 문구가 나왔다.
//    옛 문구는 src 어디에도 없었다. localStorage(eum_itda_chat_<uid>)에 **대화 통째로**
//    저장돼 있었고, 아래 useState 가 draft.msgs 를 그대로 되살린 것이다.
//    즉 코드를 고쳐도 이미 한 번 들어와 본 사용자에게는 옛 인사말이 영원히 남는다.
//  왜 draft 를 통째로 버리지 않나 — '하던 대화 이어가기'는 의도된 기능이다(새로고침·중간이탈 복구).
//    버려야 할 것은 대화가 아니라 **낡아버린 우리 대사**뿐이다.
//  어떻게 — 머리말에 greet 표식을 달아두고, 되살릴 때 표식이 가리키는 지금 문구로 갈아끼운다.
//    표식이 없는 옛 draft(8/4 이전 저장분)는 위치로 판별한다 — 이 화면에서 msgs[0] 은
//    항상 봇 머리말이다(사용자 발화는 push 로 뒤에만 붙는다). 그래서 위치 판별이 안전하다.
function reviveGreet(msgs) {
  const first = msgs?.[0]
  if (!first || first.role !== 'bot' || first.kind !== 'text') return msgs   // 예상 밖 모양이면 손대지 않는다
  const fresh = (first.greet === 'resume' || String(first.text || '').startsWith('저장한 지도'))
    ? RESUME_GREET : GREET
  if (first.text === fresh.text && first.greet) return msgs                  // 이미 최신 문구
  return [fresh, ...msgs.slice(1)]
}
export default function LearnChat() {
  const toast = useToast()
  const loc = useLocation()
  const { user } = useAuth()
  const nav = useNavigate()
  const uid = user?.user_id                          // ★ 대화 draft를 사용자별로 분리(계정 섞임 방지)
  const rs = loc.state?.goal ? loc.state : null      // '이어서하기'로 들어온 경우(복원된 세션+지도)
  const draft = loadItdaDraft(uid)                   // 이 사용자의 보관 대화만 복원. '새 지도/이어서하기'는 LearnHub가 비운다.
  const [msgs, setMsgs] = useState(() => draft ? reviveGreet(draft.msgs)
    : rs
    ? [RESUME_GREET,
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
  //  ★ 스크롤 앵커링(2026-07-31) — 예전엔 새 메시지가 오면 **무조건** 맨 아래로 끌어내려서,
  //    사용자가 위로 올려 지난 카드(자격증·시험일)를 보고 있어도 강제로 튕겨 내려갔다.
  //    '이미 바닥 근처를 보고 있을 때만' 따라 내려간다(실무 표준).
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    if (nearBottom) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs, busy])
  //  ★ 2026-08-10 — 로그아웃 직후 이 effect 가 «지운 대화를 도로 저장»하고 있었다.
  //    순서: logout() 이 eum_itda_chat* 전부 삭제 → uid 가 null 로 바뀜 → deps 의 uid 가
  //    변해 effect 재실행 → 화면에 남아 있던 msgs 를 'anon' 키로 통째로 재저장.
  //    공용 PC 라면 로그아웃했는데 상담 내용(돌봄 사정)이 localStorage 에 남는다.
  //    (토큰 만료로 uid 가 내려갈 때도 같은 일이 난다 — 에이전트 검토가 잡음)
  //  ⇒ 이 화면이 열릴 때의 사용자에게만 저장한다. uid 가 바뀌었다는 건 «다른 사람» 키라는
  //    뜻이므로 그 순간부터는 쓰지 않는다.
  const uidAtMountRef = useRef(uid)
  useEffect(() => {   // 새로고침·중간이탈에도 이어지도록 마지막 대화를 이 사용자 키에 저장
    if (uid !== uidAtMountRef.current) return
    saveItdaDraft(uid, { sid: sidRef.current, msgs, mapped })
  }, [msgs, mapped, uid])
  //  언마운트 뒤에도 응답을 저장할 수 있게 최신 msgs 를 ref 로 들고 있는다(send 참고).
  const msgsRef = useRef(msgs)
  useEffect(() => { msgsRef.current = msgs }, [msgs])
  const abortRef = useRef(null)          // 진행 중인 요청(취소용)
  const wrapRef = useRef(null)           // 대화 스크롤 영역(앵커링용)

  const push = (m) => setMsgs((p) => [...p, m])

  // 발화 전송 → 백엔드 상담 한 턴 (물어보거나 / 결과 카드)
  const send = async (raw) => {
    if (busy) return
    const q = (raw ?? input).trim(); setWarn('')
    if (!q) { setWarn('내용을 입력해 주세요.'); return }
    setInput('')
    //  ★ 2026-08-10 — 여기 있던 «프론트 자체 오타 필터»(한글·라틴 없음 또는 자모만이면
    //    「앗, 잘 이해하지 못했어요」)를 지웠다. 발표 전 최종 점검에서 실측:
    //      「ㄱㄱ」 → 백엔드에 «보내지도 않고» 프론트가 오타 취급 (백엔드 게이트는 오늘
    //        자모 축약을 «말»로 받게 고쳤는데, 프론트 사본이 그대로 막고 있었다)
    //      「...」 → 침묵 신호(SILENT — 말문이 막힌 사용자를 받는 백엔드 기능)가
    //        웹 화면에서는 «한 번도 발동할 수 없었다». 프론트가 먼저 삼켰으니까.
    //    같은 판정이 두 곳에 있으면 한쪽만 고쳐지는 사고가 반복된다(오늘만 두 번째다).
    //    이 판정의 원본은 백엔드 pre_check 하나로 둔다 — VAGUE/SILENT 응답은
    //    코드가 쓰는 문구라 LLM 비용도 0이다. 왕복 한 번이 늘 뿐이다.
    push({ role: 'me', kind: 'text', text: q })
    //  ★ 자기 위해 신호는 프론트에서 막지 않는다(2026-07-30). 공유 BAD_WORDS 에 '죽어'가 있어
    //    "죽어버리고 싶어요" 같은 말이 여기서 걸려 "그런 쪽은 도와드리기 어려워요"가 떴다.
    //    백엔드가 상담 연락처를 안내하도록 그대로 보낸다. (text.js 는 덜다도 쓰므로 건드리지 않는다.)
    const flat = q.replace(/\s/g, '')
    const selfHarm = ['자살', '죽고싶', '죽어버리', '살기싫', '사라지고싶', '없어지고싶',
      '자해', '끝내고싶', '죽는게', '죽어야'].some((w) => flat.includes(w))
    if (!selfHarm && BAD_WORDS.some((w) => q.includes(w))) {
      push({ role: 'bot', kind: 'text', text: '그런 쪽은 도와드리기 어려워요. 되고 싶은 모습이나 관심 있는 걸 들려주세요.' })
      return
    }
    setBusy(true)
    //  ★ 취소(2026-07-31) — 응답이 3~10초 걸리는데 멈출 방법이 없었다.
    //    client.js 의 signal 을 쓴다(덜다에서 추가된 배관을 그대로 활용).
    const ac = new AbortController()
    abortRef.current = ac
    const sid = sidRef.current                 // 이 요청이 속한 세션 — 응답 전 '새 목표'로 바뀌면 버린다
    try {
      const res = await chatItda(sid, q, ac.signal)
      //  ★ 응답을 '먼저 저장'한다(2026-07-30) — 답을 기다리는 중에 화면을 떠나면 컴포넌트가
      //    언마운트돼 setMsgs 가 무효화되고, 그 답이 draft 에도 안 남아 영구히 사라졌다.
      //    (백엔드는 이미 처리해 슬롯을 갱신한 상태라, 사용자만 '무응답'으로 보였다.)
      //    localStorage 저장은 React 상태와 무관하므로 떠나도 살아남는다 → 돌아오면 답이 보인다.
      //  handoff — 시간·비용 이야기가 나오면 백엔드가 덜다(정책)로 건네줄 딱지를 달아준다(2026-08-04).
      const added = res.type === 'result'
        ? [...(res.reply ? [{ role: 'bot', kind: 'text', text: res.reply, handoff: res.handoff }] : []),
           { role: 'bot', kind: 'propose', goal: res.goal, alternatives: res.alternatives || [] }]
        : [{ role: 'bot', kind: 'text', text: res.reply, handoff: res.handoff,
             options: res.options || [], notes: res.option_notes || [] }]
      saveItdaDraft(uid, { sid, msgs: [...msgsRef.current, ...added], mapped })

      if (sid !== sidRef.current) return
      if (res.type === 'result') {
        //  ★ 지도를 바로 펼치지 않는다(2026-07-30) — 대화 도중 카드가 갑자기 나오면
        //    사용자가 확인할 틈 없이 결론이 던져지는(충동적인) 느낌을 준다.
        //    한 번 더 "이 방향 맞을까요?"로 확인받고, 누를 때 지도를 연다. 데이터는 이미 받아뒀다.
        if (res.reply) push({ role: 'bot', kind: 'text', text: res.reply, handoff: res.handoff })
        push({ role: 'bot', kind: 'propose', goal: res.goal, alternatives: res.alternatives || [] })
      } else {
        //  좁히기 선택지가 오면 클릭 chip 으로 그린다(2026-07-30) — 예전엔 NCS 원문을 손으로 타이핑해야 했다.
        push({ role: 'bot', kind: 'text', text: res.reply, handoff: res.handoff,
               options: res.options || [], notes: res.option_notes || [] })
      }
    } catch (e) {
      if (sid !== sidRef.current) return
      //  사용자가 직접 멈춘 것이면 오류로 취급하지 않는다(중단 안내만).
      if (e?.name === 'AbortError' || ac.signal.aborted) {
        push({ role: 'bot', kind: 'text', text: '요청을 멈췄어요. 다시 말씀해 주셔도 좋아요.' })
      } else {
        //  ★ 실패해도 사용자가 쓴 글을 되돌려준다(2026-07-31) — 예전엔 보내기 전에 지워버려
        //    긴 문장을 쓰다 네트워크가 흔들리면 통째로 다시 써야 했다. 제일 화나는 UX였다.
        setInput(q)
        push({ role: 'bot', kind: 'text', text: '잠시 문제가 생겼어요. 아래 입력창에 글이 그대로 있으니 다시 보내보세요.', retry: q })
      }
    } finally {
      if (sid === sidRef.current) { setBusy(false); abortRef.current = null }
    }
  }

  //  진행 중인 요청 취소 — 사용자가 [멈추기] 를 누를 때
  const cancel = () => { abortRef.current?.abort() }

  //  확인 카드('이 방향 맞을까요?')를 눌렀을 때 → 그 자리를 실제 지도로 바꾼다.
  //  대화 기록에 남으므로 새로고침·이어서하기에도 지도가 그대로 보인다.
  const openGoal = (proposeMsg) => {
    setMsgs((prev) => prev.map((m) => (m === proposeMsg
      ? { ...m, kind: 'goal' }
      : m)))
    setMapped(true)
  }

  // 저장 — 백엔드가 세션에 캐시한 '마지막 카드'를 담는다 → session_id 만 넘기면 됨.
  const doSave = async () => {
    setAskSave(null); setSaving(true)
    try {
      const r = await saveMap(sidRef.current)
      //  already=true 는 '이어서하기로 들어와 이미 저장된 지도' 또는 '같은 직업을 이미 저장'한 경우.
      //  예전엔 이 상황이 400 이라 "아직 저장할 결과가 없어요"만 떠서 아무 일도 안 하는 것처럼 보였다.
      toast.show(r.already ? `이미 저장된 지도예요 · ${r.job}` : `미래설계지도에 저장했어요 · ${r.job}`)
      clearItdaDraft(uid)                       // 저장했으니 임시 대화는 비운다
      setTimeout(() => nav('/learn'), 900)      // 저장 후 잇다 홈(지도 목록)으로
    } catch (e) {
      toast.show(e?.message || '저장에 실패했어요. 로그인 상태를 확인해 주세요.')
    } finally { setSaving(false) }
  }

  //  ★ 2026-08-07 — maxWidth 960 → 1240.
  //    **채팅 페이지만 사이트 기본(--maxw 1080)보다 «좁았다».**
  //    미래설계지도 카드가 세로로 길어 한 화면에 안 들어왔다(실사용 신고).
  //    카드는 .bubble(max-width 78%) 밖이라 컨테이너 폭을 그대로 쓴다 —
  //    넓히면 줄바꿈이 줄어 카드가 «짧아진다». 높이를 늘리는 것보다 효과가 크다.
  //  ⚠ 이 주석을 return( 바로 뒤에 «JSX 주석»으로 넣었다가 화면이 통째로 죽었다(500).
  //    return 이 최상위 요소를 둘 가지게 되어 파싱이 깨진다. 주석은 return «밖»에 둔다.
  return (
    <div className="container page" style={{ maxWidth: 1240 }}>
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
          {/*  높이를 화면에 맞춘다(2026-07-30) — 고정 500px 이라 작은 화면(667×714 실측)에서는
               대화창이 화면을 넘겨 '바깥 스크롤 + 안쪽 스크롤'이 겹치고, 정작 아래 빈 공간은 남았다.
               미래설계지도는 긴 카드라 좁은 창에서 계속 스크롤해야 했다. clamp 로 화면에 맞춘다.

               ★ 2026-08-07 — 최대 620 → 820. 1080p 노트북에서 620 은 카드 절반만 보였다.
               ⚠ 빼는 값(300 → 270)은 «조심해서» 줄였다. 이 위로 헤더 96 + 제목 74 +
                 글자크기 40, 아래로 입력창 60 + 안내 30 이 있다. 더 줄이면 «입력창이
                 화면 밖»으로 나간다 — 그건 지금보다 나쁘다.
               ⚠ 이 주석을 «속성 사이»에 넣었다가 파싱이 깨졌다(500). JSX 속성 목록
                 안에는 중괄호 주석을 못 쓴다. 주석은 여는 태그 «위»에 둔다.
               ⚠⚠ 2026-08-09 — **이 주석이 자기 자신을 깨뜨리고 있었다.**
                 여기에 중괄호 주석의 «닫는 기호»를 예시로 적어 뒀었다. 그게 주석을
                 그 자리에서 닫아 버려, 뒷부분이 잇다 첫 화면 인사말 «위»에 그대로
                 렌더링됐다. 브라우저로 직접 열어 보고서야 찾았다.
                 ⇒ 주석 안에 닫는 기호를 «글자로» 쓰지 마라. 고치면서 한 번 더 틀렸다. */}
          <div className="chat-wrap" role="log" aria-live="polite" ref={wrapRef}
            style={{ height: 'clamp(320px, calc(100vh - 270px), 820px)',
                     fontSize: 15.5, zoom: chatZoom }}>
            {msgs.map((m, i) => (
              <ChatItem key={i} m={m} onSave={(g) => setAskSave(g)} onOpenGoal={openGoal}
                onPick={(o) => send(o)} onRetry={send}
                //  덜다로 갈 때 대화를 버리지 않는다 — draft 는 그대로 남으므로 돌아오면 이어진다.
                onHandoff={(h) => nav(h.path || '/welfare/policy')} />
            ))}
            {busy && <TypingBubble onCancel={cancel} />}
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

// 자격증 한 줄 — 누르면 시험방법·전망이 펼쳐진다(2026-07-30).
//  DB(certification.exam_method 66% · career_outlook 35%)에 있는데 화면에 안 쓰던 데이터.
//  줄 자체는 컴팩트하게 유지하고, 궁금한 사람만 펼쳐 보게 한다.
function CertRow({ s, first }) {
  const [open, setOpen] = useState(false)
  //  entry_note 는 예전에 badge 의 title(hover) 뿐이라 **모바일에서 응시자격을 볼 방법이 없었다**(2026-07-30).
  //  이제 펼침 패널에 원문을 넣는다 — 카드에서 실제로 막히는 문이 이것이다.
  const more = s.exam_method || s.outlook || s.entry_note || s.evidence
  return (
    <div style={{ padding: '11px 0', borderTop: first ? 'none' : '1px solid var(--line)' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <b style={{ fontSize: 15.5 }}>{s.cert}</b>
        {s.grade && <span className="muted" style={{ fontSize: 12.5 }}>{s.grade}</span>}
        <span className={`badge ${s.entry_free ? 'badge-teal' : 'badge-amber'}`}
          title={s.entry_free ? '응시 조건이 없어요' : (s.entry_note || '응시자격 확인 필요')}
          style={{ fontSize: 12, cursor: s.entry_free ? 'default' : 'help' }}>
          {s.entry_free ? '조건 없음' : 'ⓘ 응시자격 확인'}
        </span>
        {s.exam && <span className="muted" style={{ fontSize: 12.5 }}>· {s.exam}</span>}
        {more && (
          <button className="btn btn-plain btn-sm" onClick={() => setOpen((v) => !v)}
            style={{ marginLeft: 'auto', fontSize: 12.5, padding: '2px 8px' }}>
            {open ? '접기' : '자세히'}
          </button>
        )}
      </div>
      {open && more && (
        <div style={{ marginTop: 9, paddingLeft: 2, display: 'grid', gap: 7 }}>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
            {s.qual_gb && <span className="muted" style={{ fontSize: 12.5 }}>구분 · {s.qual_gb}</span>}
            {/* 이 자격증을 이 직업에 이은 근거 — 'AI가 고른 게 아니라 데이터가 이었다'의 증거 */}
            {s.evidence && (
              <span className="badge badge-gray" style={{ fontSize: 11.5 }}
                title="이 자격증을 이 직업에 연결한 근거 (데이터 기준)">연결 근거 · {s.evidence}</span>
            )}
          </div>
          {!s.entry_free && s.entry_note && (
            <div style={{ fontSize: 13.5, lineHeight: 1.65 }}>
              <b style={{ fontSize: 12.5, color: 'var(--amber-700, #92400e)' }}>응시자격</b><br />
              {s.entry_note}
            </div>
          )}
          {s.exam_method && (
            <div style={{ fontSize: 13.5, lineHeight: 1.65 }}>
              <b style={{ fontSize: 12.5, color: 'var(--teal-700)' }}>시험 방법</b><br />{s.exam_method}
            </div>
          )}
          {s.outlook && (
            <div style={{ fontSize: 13.5, lineHeight: 1.65 }}>
              <b style={{ fontSize: 12.5, color: 'var(--teal-700)' }}>전망</b><br />{s.outlook}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// 지도 직전 '확인' 단계 — 방향을 제안하고, 사용자가 누를 때 비로소 지도를 펼친다.
//  대화 중 결론이 갑자기 던져지는 느낌을 없애기 위한 한 박자 (2026-07-30).
function ProposeCard({ goal, alternatives, onOpen }) {
  return (
    <div className="card card-pad" style={{ alignSelf: 'stretch', borderColor: 'var(--teal-200)' }}>
      <div style={{ fontSize: 15.5, lineHeight: 1.7 }}>
        말씀 주신 걸 들어보니, 이런 방향이 맞을 것 같아요. <b>이거 맞으실까요?</b>
      </div>

      <button className="card card-hover" onClick={onOpen}
        style={{ display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
          marginTop: 14, padding: '16px 18px', borderColor: 'var(--teal-300)',
          background: 'var(--teal-50)' }}>
        <div className="muted" style={{ fontSize: 12.5, marginBottom: 4 }}>제가 추천하는 방향</div>
        <div className="row" style={{ justifyContent: 'space-between', gap: 10, alignItems: 'center' }}>
          <b style={{ fontSize: 21, color: 'var(--teal-700)' }}>{goal.job}</b>
          {goal.group && <span className="badge badge-gray" style={{ fontSize: 12 }}>{goal.group}</span>}
        </div>
        <div style={{ fontSize: 13.5, color: 'var(--teal-700)', marginTop: 10, fontWeight: 700 }}>
          눌러서 미래설계지도 보기 →
        </div>
      </button>

      {alternatives?.length > 0 && (
        <div className="muted" style={{ fontSize: 13.5, marginTop: 12, lineHeight: 1.7 }}>
          이 방향이 아니라면 · {alternatives.join(' · ')}<br />
          <span style={{ fontSize: 13 }}>아래에 다시 말씀해 주시면 다른 방향으로 찾아드려요.</span>
        </div>
      )}
    </div>
  )
}

function ChatItem({ m, onSave, onOpenGoal, onPick, onRetry, onHandoff }) {
  if (m.kind === 'text') return (
    <div style={{ alignSelf: m.role === 'me' ? 'flex-end' : 'stretch' }}>
      <div className={`bubble ${m.role === 'me' ? 'me' : 'bot'}`}
        style={{ fontSize: 15.5, lineHeight: 1.7, padding: '12px 16px' }}>{m.text}</div>
      {/* 실패한 요청은 그 자리에서 다시 보낼 수 있게 (2026-07-31) */}
      {m.retry && (
        <button className="btn btn-ghost btn-sm" style={{ marginTop: 8 }}
          onClick={() => onRetry?.(m.retry)}>다시 보내기 ↻</button>
      )}
      {/* 덜다(정책)로 건네주기 (2026-08-04) — 시간·비용 제약은 진로 상담만으로 안 풀린다.
          대화를 끊지 않는다: 버튼일 뿐이고, 안 눌러도 진로 이야기는 그대로 이어진다. */}
      {m.handoff?.path && (
        <button className="btn btn-ghost btn-sm"
          style={{ marginTop: 9, borderColor: 'var(--teal-200)', color: 'var(--teal-700)' }}
          onClick={() => onHandoff?.(m.handoff)}>
          {m.handoff.label || '받을 수 있는 지원 찾아보기'} →
        </button>
      )}
      {/* 좁히기 선택지 — 눌러서 고른다(2026-07-30). 설명 한 줄로 NCS 원문의 뜻을 알려준다. */}
      {m.options?.length > 0 && (
        <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
          {m.options.map((o, i) => (
            <button key={o} className="card card-hover" onClick={() => onPick(o)}
              style={{ textAlign: 'left', cursor: 'pointer', padding: '11px 14px',
                width: '100%', display: 'block', borderColor: 'var(--teal-200)' }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--teal-700)' }}>{o}</div>
              {m.notes?.[i] && (
                <div className="muted" style={{ fontSize: 12.5, marginTop: 3, lineHeight: 1.5 }}>
                  {m.notes[i]}…
                </div>
              )}
            </button>
          ))}
          {/* ★ 「이 중에 없어요」 (2026-08-05)
              왜 필요한가 — SOCcer 자가코딩 실측에서 이 선택지를 **14~18%가 누른다**
                (v1 17% N=23,699 · v2 14% N=12,060 · Next Steps UK 18%).
                우리 칩엔 그 자리가 없어서, 안 맞는 사람은 아무 말이나 쓰거나 아무거나 눌렀다.
              누르면 그 문구를 그대로 보낸다 — 백엔드 none_of_these() 가 이미 알아듣고,
              **동네를 떠나지 않고** 보여준 것만 강등해 같은 슬롯으로 다시 찾는다.
                (근거: 「없음」을 고른 사람의 27~54%는 실제로 그 목록 안에 답이 있었다) */}
          <button className="card" onClick={() => onPick('이 중에 없어요')}
            style={{ textAlign: 'left', cursor: 'pointer', padding: '9px 14px',
              width: '100%', display: 'block', background: 'transparent',
              borderStyle: 'dashed' }}>
            <span className="muted" style={{ fontSize: 13.5 }}>이 중에 없어요</span>
          </button>
        </div>
      )}
    </div>
  )
  if (m.kind === 'propose') return (
    <ProposeCard goal={m.goal} alternatives={m.alternatives}
      onOpen={() => onOpenGoal(m)} />
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

// 로딩 표시 (2026-07-31)
//  응답이 걸리는 동안 '살아있다'는 신호가 필요하다.
//  ★★ 2026-08-09 실측으로 구간을 다시 잡았다 — 예전 주석의 「3~10초」는 낡았다.
//    턴 안에서 무엇이 얼마나 걸리는지 직접 쟀다(호출별):
//      일반 턴 «1.3~1.9초»   유해게이트 1.0 + 본문 1.2 를 **나란히** 돌린다(asyncio.gather)
//      카드 턴 «7.2초»       위 + 대분류 0.8 → 검색 1.7 → 고르기 1.0 → 대안검색 0.7 (순차)
//    ⇒ 예전 구간(0/3/6/10초)은 실제 진행과 어긋났다. 3초에 「정리하고 있어요」라고 했지만
//      그때는 이미 검색 중이었다. 구간을 실측에 맞춘다.
//    ⚠ 일반 턴은 «1.3초»에 끝나므로 사실상 첫 문구만 보인다. 그게 맞다 — 빠른 답에
//      단계를 보여줄 이유가 없다.
//  ※ 단계 문구를 시간으로 추측해 바꾸는 방식은 2026-07-30 에 폐기했다(실제 진행과 어긋나 산만했다).
//    대신 ①문구는 하나로 고정 ②경과 초를 실제로 세어 보여주고 ③오래 걸리면 멈출 수 있게 한다.
//    경과 시간은 추측이 아니라 사실이라 어긋날 일이 없다.
//  ★★ 기다리는 동안 무엇을 보여줄 것인가 (2026-08-05)
//    실측 문제 — 첫 턴이 간헐적으로 6~9초 걸린다.
//    근거: ACM CUI '25 (arXiv 2507.22352, N=54, 조건 1.5s/4.0s/6.5s)
//      · "latency above 4 seconds degrades quality of experience"
//      · "natural conversational fillers improve perceived response time"
//        — 4.0s 에서 p<0.01 · 6.5s 에서 p<0.0001 · 64.81%가 자연 추임새를 선호
//      · "Artificial wait indicators showed no significant improvement over
//         no filler conditions"  ← 스피너·초 카운터가 여기 해당한다
//    ⇒ 초 카운터를 앞세우지 않는다(시계를 보게 만든다). 대신 **말이 자연스럽게 이어지게** 한다.
//    ※ 참고 — Gnewuch et al. (BISE 2022, N=202): 2.3초 지연은 **초보 사용자**에게
//      오히려 사회적 실재감을 높였다(b=0.69, p<0.05). 우리 사용자는 그쪽이다.
//      그러니 목표는 0초가 아니라 「4초 선을 넘을 때 자연스럽게 말 걸기」다.
//  구간은 실측 기준이다 — 카드 턴의 실제 순서(정리 → 검색 → 고르기)와 맞춰 놓았다.
const WAIT_LINES = [
  [0, '네, 듣고 있어요…'],
  [2, '말씀해 주신 걸 정리하고 있어요…'],   // 본문 호출이 끝나갈 무렵
  [4, '비슷한 일들을 찾아보는 중이에요…'],   // 검색이 도는 구간
  [6, '어느 쪽이 맞을지 보고 있어요…'],      // 고르기(llm_pick)
  [9, '조금만요, 거의 다 됐어요…'],
]

function TypingBubble({ onCancel }) {
  const [sec, setSec] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setSec((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])
  //  지난 구간 중 마지막 문구 — 시간이 갈수록 말이 바뀐다(고정 문장은 멈춘 것처럼 보인다).
  const line = WAIT_LINES.reduce((acc, [t, s]) => (sec >= t ? s : acc), WAIT_LINES[0][1])
  return (
    <div className="bubble bot" style={{ display: 'inline-flex', alignItems: 'center',
      gap: 10, width: 'fit-content', fontSize: 15, flexWrap: 'wrap' }}>
      <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
      <span>{line}</span>
      {/* 초 카운터는 10초 넘게 걸릴 때만 — 그 전엔 시계를 보게 만들 이유가 없다 */}
      {sec >= 10 && <span className="muted" style={{ fontSize: 12.5 }}>{sec}초</span>}
      {sec >= 6 && onCancel && (
        <button className="btn btn-plain btn-sm" onClick={onCancel}
          style={{ fontSize: 12.5, padding: '2px 10px' }}>멈추기</button>
      )}
    </div>
  )
}

// 미래설계지도 카드 — '방향(직업)'이 주인공. 선고 아닌 안내(2026-07-29 NCS).
//  방향(직무+설명) → 자격증(≤3) 또는 내일배움카드 → 무료강의(K-MOOC) → 국비 실전훈련.
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
        {/* 자격증 목록 — 카드 하나에 얇은 구분선으로 붙인다.
            예전엔 자격증마다 큰 카드였고 이름과 배지 사이가 통째로 비어 한 줄을 낭비했다. */}
        {certs.length > 0 ? (
          <div className="card" style={{ padding: '2px 14px' }}>
            {certs.map((s, i) => <CertRow key={i} s={s} first={i === 0} />)}
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

      {/* ③ 배움 순서 — 무료강의(K-MOOC) → 실전(국비). 단계로 이어준다.
          (열림강의 98건은 kmooc_id·URL 이 없어 검색에 잡히지도 않았다 → DB 에서 삭제 2026-07-31) */}
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
              {/*  ★ 2026-08-07 — 세로 한 줄 → «가로로 채우는» 격자.
                   강좌 3개가 세로로 쌓여 카드가 그만큼 길어졌다(1개당 ~56px).
                   auto-fit 이라 좁은 화면에서는 자동으로 한 줄씩 = 예전과 같다.
                   280px 아래로는 제목이 깨져서 그걸 최소폭으로 잡았다. */}
              <div style={{ display: 'grid', gap: 10,
                            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
                {goal.courses.map((c, i) => (
                  <button key={i} onClick={() => setOpenCourse(c)} className="card card-hover"
                    style={{ textAlign: 'left', cursor: 'pointer', padding: '13px 16px', display: 'block', width: '100%' }}>
                    <div className="row" style={{ justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ fontSize: 15, fontWeight: 600 }}>{c.title}</div>
                      {/*  ★ 2026-08-03 — 「관련 64%」를 K-MOOC 분류로 바꿨다.
                          그 숫자는 코사인 유사도 생값이었는데, 같은 언어로 쓰인 글끼리는
                          내용이 무관해도 0.5~0.6 이 깔린다. 즉 64% 는 "64% 관련"이 아니라
                          "한국어 문서 기본값보다 조금 위"라는 뜻이라 근거 없는 확신을 팔았다.
                          (실측: 제빵 ↔ 실용아트 메이크업 0.640 vs 요양보호 ↔ 요양보호강의 0.702)
                          분류는 DB 에 실제로 있는 값이다.  */}
                      {c.classfy && (
                        <span className="badge badge-gray" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>{c.classfy}</span>
                      )}
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
