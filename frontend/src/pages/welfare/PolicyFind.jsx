import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../store/auth.jsx'
import { PageHead } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { hasBadWord, isMeaningless } from '../../utils/text.js'

// WEL-102 · 맞춤 지원 정책 찾기 (입력 폼 ↔ 정보부족 시 챗봇 전환)
const SITUATIONS = ['가족을 돌보고 있어요', '경제적으로 어려워요', '취업을 준비하고 있어요', '학업과 돌봄을 병행하고 있어요', '심리적인 도움이 필요해요']
const NEEDS = ['생활비 지원', '의료비 지원', '돌봄 서비스', '심리 지원', '취업 지원', '교육 지원', '잘 모르겠어요']

// mock: AI가 "정책 추천에 필요한 정보가 부족"하다고 판단하는 규칙
// (데모에선 '잘 모르겠어요'를 고르면 정보부족 → 챗봇으로 전환)
const needsMoreInfo = ({ needs }) => needs.includes('잘 모르겠어요')

export default function PolicyFind() {
  const nav = useNavigate()
  const { state: nav0 } = useLocation()
  const { user } = useAuth()
  const [situations, setSituations] = useState(nav0?.situations || [])
  const [needs, setNeeds] = useState(nav0?.needs || [])
  const [extra, setExtra] = useState(nav0?.extra || '')
  const [errSit, setErrSit] = useState('')
  const [errNeed, setErrNeed] = useState('')
  const [mode, setMode] = useState(nav0?.chat ? 'chat' : 'form') // 결과창 "AI와 다시 상담하기"로 오면 챗봇부터

  const toggle = (arr, set, v) => set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v])

  const submit = () => {
    // WEL-102 에러 — 두 복수선택은 필수, 자유서술은 선택
    let ok = true
    if (situations.length === 0) { setErrSit('현재 상황을 선택해주세요.'); ok = false } else setErrSit('')
    if (needs.length === 0) { setErrNeed('현재 가장 필요한 지원을 선택해주세요.'); ok = false } else setErrNeed('')
    if (!ok) return
    // AI 분석 결과 정보가 충분하면 결과창, 부족하면 같은 페이지에서 챗봇으로 전환
    if (needsMoreInfo({ situations, needs, extra })) setMode('chat')
    else nav('/welfare/policy/result', { state: { situations, needs, extra } })
  }

  return (
    <div className="container page" style={{ maxWidth: 720 }}>
      <PageHead title="맞춤 지원 정책 찾기" sub="회원님의 기본정보를 기반으로 맞춤 정책을 찾아드립니다." />
      <RequireLogin axis="맞춤 지원 정책 찾기">
        {mode === 'chat' ? (
          <PolicyChat
            base={{ situations, needs, extra }}
            onEditForm={() => setMode('form')}
            onDone={(enriched) => nav('/welfare/policy/result', { state: { situations, needs, extra, ...enriched } })}
          />
        ) : (
          <div className="card card-pad">
            {/* 기본 정보 — 회원정보 자동 입력 (출생연도 수정불가, 거주지역 변경 가능) */}
            <div style={{ background: 'var(--teal-50)', border: '1px solid var(--teal-100)', borderRadius: 12, padding: 14, marginBottom: 20 }}>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>기본 정보 <span className="muted" style={{ fontWeight: 400 }}>· 회원정보 기반 자동 입력</span></div>
              <div className="row" style={{ gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
                <span>출생연도 <b>{user?.birth?.slice(0, 4) || '—'}</b></span>
                <span className="row" style={{ gap: 8 }}>
                  거주지역 <b>{user?.region || '—'}</b>
                  <Link to="/mypage" className="btn btn-ghost btn-sm">변경</Link>
                </span>
              </div>
            </div>

            {/* 현재 상황 (복수, 필수) */}
            <div className="field">
              <label>현재 상황 <span className="req">*</span> <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>(복수 선택)</span></label>
              <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                {SITUATIONS.map((s) => <button key={s} className={`chip ${situations.includes(s) ? 'on' : ''}`} onClick={() => toggle(situations, setSituations, s)}>{s}</button>)}
              </div>
              {errSit && <p className="err" style={{ marginTop: 8 }}>{errSit}</p>}
            </div>

            {/* 필요한 지원 (복수, 필수) */}
            <div className="field">
              <label>현재 가장 필요한 지원 <span className="req">*</span> <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>(복수 선택)</span></label>
              <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                {NEEDS.map((n) => <button key={n} className={`chip ${needs.includes(n) ? 'on' : ''}`} onClick={() => toggle(needs, setNeeds, n)}>{n}</button>)}
              </div>
              {errNeed && <p className="err" style={{ marginTop: 8 }}>{errNeed}</p>}
            </div>

            {/* 추가로 알려주고 싶은 내용 (자유서술, 선택) */}
            <div className="field">
              <label>추가로 알려주고 싶은 내용 <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>(선택)</span></label>
              <textarea className="input" rows={3} placeholder="자유롭게 작성해주세요. 예) 어머니를 돌보며 야간 아르바이트를 하고 있어요."
                value={extra} onChange={(e) => setExtra(e.target.value)} style={{ resize: 'vertical' }} />
            </div>

            <button className="btn btn-primary btn-block btn-lg" onClick={submit}>AI 추천받기</button>
            <p className="hint center" style={{ marginTop: 10 }}>입력하신 정보는 정책 추천 목적 외에는 사용되지 않아요.</p>
          </div>
        )}
      </RequireLogin>
    </div>
  )
}

// WEL-102 챗봇 — 정보가 부족할 때 AI가 부족한 정보를 순차적으로 되묻는다(선택지 + 자유입력).
// 슬라이드47: 순차 대화·선택지·자유입력·조건수정하기 / 슬라이드48: 부적절어·무의미 입력 예외처리.
const QUESTIONS = [
  { key: 'relation', q: '지금 돌보고 계신 분은 어떤 관계인가요?', choices: ['부모님', '조부모님', '형제·자매', '배우자', '기타'] },
  { key: 'hours', q: '돌봄에 쓰는 시간은 하루 어느 정도인가요?', choices: ['2시간 미만', '2~4시간', '4~8시간', '8시간 이상'] },
  { key: 'burden', q: '지금 가장 부담되는 부분을 한두 문장으로 알려주세요.', choices: [], placeholder: '예) 할머니 약값이 부담돼요' },
]
const OPENING = '입력해주신 내용을 분석해보았어요. 더 정확한 정책을 추천하려면 몇 가지만 더 여쭤볼게요.'
const CLOSING = '알려주셔서 고마워요. 이 내용으로 맞춤 정책을 다시 찾아드릴게요.'
const REDIRECT = '저는 복지 정책·지원 정보를 찾아드리는 이음 AI 어시스턴트예요. 지금 겪고 계신 돌봄 상황을 알려주시면 도움이 될 만한 정책을 찾아드릴 수 있어요!'

function PolicyChat({ base, onEditForm, onDone }) {
  const [msgs, setMsgs] = useState([])
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState({})
  const [input, setInput] = useState('')
  const started = useRef(false)
  const scroller = useRef(null)

  const push = (m) => setMsgs((prev) => [...prev, m])

  // 첫 진입: 분석 안내 + 첫 질문
  useEffect(() => {
    if (started.current) return
    started.current = true
    setMsgs([{ role: 'bot', text: OPENING }, { role: 'bot', text: QUESTIONS[0].q }])
  }, [])

  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' }) }, [msgs])

  const q = QUESTIONS[step]
  const done = step >= QUESTIONS.length

  const answer = (text) => {
    const t = text.trim()
    if (!t) return
    // 예외처리(슬라이드48): 부적절어 → 차단 / 무의미 → 예시 유도. 어느 쪽도 단계는 진행하지 않음.
    if (hasBadWord(t)) {
      push({ role: 'me', text: t })
      push({ role: 'bot', text: '부적절한 단어가 포함되어 있어 답변을 제공할 수 없어요. 바르고 고운 말을 사용해 주세요.' })
      setInput('')
      return
    }
    if (isMeaningless(t)) {
      push({ role: 'me', text: t })
      push({ role: 'bot', text: `${REDIRECT}\n예를 들어 "할머니 약값이 부담돼요."처럼 알려주시면 정책 추천에 도움이 돼요.` })
      setInput('')
      return
    }
    // 정상 답변 → 저장 후 다음 질문 또는 종료
    push({ role: 'me', text: t })
    const next = step + 1
    setAnswers((a) => ({ ...a, [q.key]: t }))
    setInput('')
    if (next < QUESTIONS.length) push({ role: 'bot', text: QUESTIONS[next].q })
    else push({ role: 'bot', text: CLOSING })
    setStep(next)
  }

  return (
    <div className="card card-pad">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>🧠 AI 추가 질문 <span className="muted" style={{ fontWeight: 400 }}>· 약 1~2분 소요</span></div>
        <button className="btn btn-ghost btn-sm" onClick={onEditForm}>← 조건 입력 내용 수정하기</button>
      </div>

      <div ref={scroller} className="chat-wrap" style={{ maxHeight: 360, overflowY: 'auto', paddingRight: 4 }}>
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.role === 'me' ? 'me' : 'bot'}`} style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>
        ))}
      </div>

      {done ? (
        <button className="btn btn-primary btn-block btn-lg" style={{ marginTop: 14 }}
          onClick={() => onDone({ chatAnswers: answers })}>정책 추천받기 →</button>
      ) : (
        <>
          {/* AI가 제시한 예상 답변 선택지 */}
          {q?.choices?.length > 0 && (
            <div className="row" style={{ gap: 8, flexWrap: 'wrap', margin: '12px 0 4px' }}>
              {q.choices.map((c) => <button key={c} className="chip" onClick={() => answer(c)}>{c}</button>)}
            </div>
          )}
          {/* 선택지로 표현이 어려우면 직접 입력 */}
          <div className="chat-input" style={{ marginTop: 10 }}>
            <input className="input" placeholder={q?.placeholder || '답변을 입력하세요'} value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && answer(input)} />
            <button className="btn btn-primary" disabled={!input.trim()} onClick={() => answer(input)}>전송</button>
          </div>
        </>
      )}
    </div>
  )
}
