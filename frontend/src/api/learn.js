// ============================================================================
//  잇다 · 목표 문장 → 미래설계지도 추천 (임베딩 유사도 mock)
//  스토리보드 ITD-101~104 흐름을 mock으로 구현.
//  ⚠️ LLM은 강좌를 "고르지" 않는다 — 여기(수학/규칙)가 고른다. (전체흐름도 2번 원칙)
//  나중에 진짜 붙일 땐 아래 recommend/saveMap 안의 반환부만 fetch로 바꾸면 됨.
// ============================================================================
import { mockResolve, request } from './client.js'
import { learnPool, learnNear } from '../mock/db.js'

// ── 잇다 실제 백엔드 (Gemini 상담 → 자격증 목표) ──
// 다른 기능은 아직 mock이지만, 잇다는 진짜 백엔드(/itda)를 쓴다.
// 요청: {session_id, message}  응답: {type:'ask'|'result'|'blocked', reply, understanding, mode, goal, alternatives}
export function chatItda(sessionId, message) {
  return request('/itda/message', {
    method: 'POST',
    body: { session_id: sessionId, message },
  })
}

export function resetItda(sessionId) {
  return request('/itda/reset', { method: 'POST', body: { session_id: sessionId } }).catch(() => {})
}

const THRESHOLD = 0.55   // 유사도 임계값 — 이 아래면 '결과 없음'(ITD-104)
const DAILY_HOURS = 1    // 하루 가용 학습시간(기본) → 예상 주수 계산에 사용

// 목표 문장을 강좌 키워드와 겹쳐 유사도 점수를 매긴다. (임베딩 유사도의 mock)
function scoreCourses(text) {
  const t = (text || '').toLowerCase()
  return learnPool
    .map((c) => {
      const hits = c.keywords.filter((k) => t.includes(k)).length
      const sim = hits ? Math.min(0.95, +(c.baseSim + hits * 0.06).toFixed(2)) : 0
      return { ...c, hits, sim }
    })
    .filter((c) => c.sim > 0)
    .sort((a, b) => b.sim - a.sim)
}

// 대화 추천의 핵심.
//   text : 지금까지 누적된 목표 문장(되묻기 선택이 더해질수록 길어짐)
//   turn : 현재 되묻기 턴(1~3). 3턴이면 더 안 좁히고 강제로 지도를 만든다(ITD-102B).
// 반환 result: 'map'(지도) | 'narrow'(좁히기) | 'none'(결과 없음)
export function recommend({ text = '', turn = 1 } = {}) {
  return mockResolve(() => {
    const matched = scoreCourses(text)

    // 1) 임계값 미달 → 결과 없음(ITD-104). 지어내지 않는다.
    if (matched.length === 0 || matched[0].sim < THRESHOLD) {
      return { result: 'none', near: learnNear }
    }

    // 2) 여러 분야로 흩어지고 아직 3턴 미만 → 좁히기 질문(ITD-102).
    //    ⚠️ 선택지는 AI가 지어낸 게 아니라 '검색된 강좌에서 뽑은 사용자 언어'(cat).
    const cats = [...new Set(matched.map((c) => c.cat))]
    // 1위 유사도가 2위를 뚜렷이 앞서면(격차 큼) 승자가 정해진 것. 아니면 아직 애매 → 되묻기.
    const clearLead = matched.length < 2 || (matched[0].sim - matched[1].sim) >= 0.06
    if (turn < 3 && cats.length >= 2 && !clearLead) {
      return {
        result: 'narrow',
        question: '말씀 안에서 여러 갈래가 보여요. 어느 쪽이 더 끌리세요?',
        options: cats.slice(0, 3),
      }
    }

    // 3) 확정 → 미래설계지도(ITD-103). 상위 3개를 배움순서(기초→현장)로 재배열.
    const top = matched.slice(0, 3)
    const goalLabel = top[0].cat
    const ordered = [...top].sort((a, b) => a.order - b.order)
    const totalHours = ordered.reduce((s, c) => s + c.hours, 0)
    const weeks = Math.max(1, Math.round(totalHours / (DAILY_HOURS * 7)))
    return {
      result: 'map',
      goalLabel,
      weeksText: `하루 ${DAILY_HOURS}시간이면 약 ${weeks}주`,
      courses: ordered.map((c) => ({
        id: c.id, title: c.title, provider: c.provider, category: c.cat,
        hours: c.hours, reason: c.reason, url: c.url, sim: c.sim,
      })),
    }
  }, 900)
}

// 미래설계지도 저장(ITD-105C) — mock: '이어서 하기'용으로 localStorage에 저장.
export function saveMap(map) {
  return mockResolve(() => {
    try {
      localStorage.setItem('eum_learn_resume', JSON.stringify({
        goal: map.goalLabel, weeksText: map.weeksText, courses: map.courses, at: Date.now(),
      }))
    } catch { /* localStorage 불가 환경 무시 */ }
    return { ok: true }
  }, 500)
}

// 진행 중인 미래설계지도(홈 '이어서 하기'용). 없으면 null.
export function getResume() {
  try { return JSON.parse(localStorage.getItem('eum_learn_resume')) || null } catch { return null }
}
