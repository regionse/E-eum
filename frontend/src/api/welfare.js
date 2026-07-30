// 덜다 · 맞춤 지원 정책 (rule 기반)
import { mockResolve } from './client.js'
import { policies } from '../mock/db.js'

const FIT_ORDER = { best: 0, good: 1, rec: 2, ref: 3 }

// "AI가 이해한 현재 상황" 한 줄 요약 (WEL-103) — 입력을 자연스러운 문장으로.
function buildUnderstood({ situations = [], needs = [], extra = '' }) {
  const realNeeds = needs.filter((n) => n !== '잘 모르겠어요')
  const a = situations.length ? situations.join(', ') : '입력하신 상황'
  const b = realNeeds.length ? `${realNeeds.join(' · ')} 지원이 필요` : '어떤 지원이 맞을지 함께 찾는 것이 필요'
  return `${a} — ${b}한 것으로 이해했어요.${extra ? ` (덧붙임: ${extra})` : ''}`
}

// 정책찾기(WEL-102 → 103): 상황·필요지원 입력 → 규칙 매칭 결과.
// 반환 result: 'ok'(추천 있음) | 'none'(결과 없음)
export function findPolicies(input = {}) {
  const { situations = [], needs = [], extra = '' } = input
  return mockResolve(() => {
    const understood = buildUnderstood({ situations, needs, extra })
    // '잘 모르겠어요'거나 미선택이면 전체에서 추려주고, 아니면 필요지원으로 매칭
    const useAll = needs.length === 0 || needs.includes('잘 모르겠어요')
    const matched = useAll
      ? policies
      : policies.filter((p) => (p.needs || []).some((n) => needs.includes(n)))

    if (matched.length === 0) {
      const miss = needs.filter((n) => n !== '잘 모르겠어요').join(', ')
      return {
        result: 'none',
        understood,
        reason: `선택하신 지원(${miss})에 딱 맞는 제도를 현재 데이터에서 찾지 못했어요. 거주지역·연령 조건이나 지원 항목을 조금 바꿔보시면 다시 찾아드릴 수 있어요.`,
      }
    }
    const sorted = [...matched].sort((a, b) => (FIT_ORDER[a.fit] ?? 9) - (FIT_ORDER[b.fit] ?? 9))
    return { result: 'ok', understood, policies: sorted }
  }, 1500)
}

export function getPolicy(id) {
  return mockResolve(() => policies.find((p) => p.id === id), 500)
}
