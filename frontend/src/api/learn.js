// ============================================================================
//  잇다 · 대화 상담 + 미래설계지도 저장/이어서하기 (전부 백엔드 /itda)  2026-07-29
//  ⚠️ LLM은 강좌를 "고르지" 않는다 — 검색(수학/규칙)이 고른다.
//  ※ 저장/이어서하기가 localStorage mock 이던 것을 백엔드(DB itda_map)로 교체.
// ============================================================================
import { request } from './client.js'

// 요청: {session_id, message}  응답: {type, reply, understanding, mode, goal, alternatives}
//  signal — 화면에서 [멈추기] 를 눌렀을 때 요청을 취소하기 위한 것(2026-07-31).
export function chatItda(sessionId, message, signal) {
  return request('/itda/message', {
    method: 'POST', body: { session_id: sessionId, message }, signal,
  })
}

// ── 미래설계지도 (로그인 필요 · DB 저장) ─────────────────────────────
// 저장: 지금 세션의 '마지막 카드'를 백엔드가 그대로 담는다 → session_id 만 넘기면 됨.
export function saveMap(sessionId) {
  return request('/itda/map', { method: 'POST', body: { session_id: sessionId } })
}

// 내 지도 목록(최신순) — [{map_id, job, group, status, progress_step, created_at, n_cert, n_course}]
export function listMaps() {
  return request('/itda/maps')
}

// 지도 상세(읽기 전용) — 세션을 건드리지 않고 저장된 지도 내용만 → {map_id, goal}
export function getMap(mapId) {
  return request(`/itda/map/${mapId}`)
}

// 이어서하기 — 저장된 지도를 새 세션(sessionId)에 복원 → {session_id, profile, goal}
export function resumeMap(mapId, sessionId) {
  return request(`/itda/map/${mapId}/resume`, { method: 'POST', body: { session_id: sessionId } })
}

export function deleteMap(mapId) {
  return request(`/itda/map/${mapId}`, { method: 'DELETE' })
}

// ── 잇다 대화 임시보관(로컬) — 새로고침·이동에도 이어지게 · ★사용자별 분리(계정 A/B 대화 섞임 방지, 2026-07-29) ──
const _draftKey = (uid) => `eum_itda_chat_${uid ?? 'anon'}`
export function saveItdaDraft(uid, data) {
  try { localStorage.setItem(_draftKey(uid), JSON.stringify(data)) } catch { /* noop */ }
}
export function clearItdaDraft(uid) {
  try { localStorage.removeItem(_draftKey(uid)) } catch { /* noop */ }
}
export function loadItdaDraft(uid) {   // 이 사용자의 보관 대화만 복원 (다른 계정 것은 안 보임)
  try {
    const d = JSON.parse(localStorage.getItem(_draftKey(uid)) || 'null')
    return d && Array.isArray(d.msgs) && d.msgs.length ? d : null
  } catch { return null }
}
