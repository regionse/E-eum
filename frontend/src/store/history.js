// 즐겨찾기 · 최근이력 — localStorage 기반 mock 저장소
// axis: 'welfare'(덜다) | 'learn'(잇다). 진짜 붙일 땐 이 파일만 API 호출로 교체.
const key = (kind, axis) => `eum_${axis}_${kind}`
const read = (k) => { try { return JSON.parse(localStorage.getItem(k)) || [] } catch { return [] } }
const write = (k, v) => localStorage.setItem(k, JSON.stringify(v))

export function getFavs(axis) { return read(key('favs', axis)) }
export function isFav(axis, id) { return getFavs(axis).some((x) => x.id === id) }
export function toggleFav(axis, item) {
  const k = key('favs', axis)
  const list = read(k)
  const exists = list.some((x) => x.id === item.id)
  const next = exists ? list.filter((x) => x.id !== item.id) : [{ ...item, at: Date.now() }, ...list]
  write(k, next)
  return !exists // true = 방금 추가됨
}
export function getRecent(axis, n = 5) { return read(key('recent', axis)).slice(0, n) }
export function addRecent(axis, item) {
  const k = key('recent', axis)
  const list = read(k).filter((x) => x.id !== item.id)
  write(k, [{ ...item, at: Date.now() }, ...list].slice(0, 20))
}

// 정책 추천 이력 — 맞춤 추천 '세션'을 저장(날짜·건수·입력값). WEL-101 최근 정책 추천 이력 + 결과 재렌더용.
export function getRecoSessions(axis) { return read(key('reco', axis)) }
export function addRecoSession(axis, session) {
  const k = key('reco', axis)
  write(k, [{ ...session, at: Date.now() }, ...read(k)].slice(0, 30))
}

// 한 번이라도 이용했는가 (즐겨찾기·최근이력·추천이력 존재) → 첫 이용자 분기
export function hasUsed(axis) {
  return getRecent(axis).length > 0 || getFavs(axis).length > 0 || read(key('reco', axis)).length > 0
}
