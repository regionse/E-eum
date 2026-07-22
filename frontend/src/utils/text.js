// 부적절어 필터(u57) + 무의미 입력 감지 — 잇다·덜다 챗봇 공용
export const BAD_WORDS = ['바보', '멍청', '나쁜 놈', '죽어', '꺼져', '개새', '병신']

export function hasBadWord(text = '') {
  return BAD_WORDS.some((w) => text.includes(w))
}

// 너무 짧거나(2자 미만) 자모·같은 글자 반복 등 의미 없는 입력
export function isMeaningless(text = '') {
  const t = text.trim()
  if (t.length < 2) return true
  if (/^[ㄱ-ㅎㅏ-ㅣ\s]+$/.test(t)) return true          // 자음/모음만 (ㅋㅋ, ㅏㅏ)
  if (/^(.)\1{2,}$/.test(t.replace(/\s/g, ''))) return true // 같은 글자 3회 이상 반복 (ㅎㅎㅎ, ...)
  return false
}
