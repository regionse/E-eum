import { createContext, useContext, useState } from 'react'
import { familyRecords as seedRecords, todayMeds as seedMeds } from '../mock/db.js'

// 내가 남에게 주는 초대 코드(가족 연결 화면에 표시). 받은 코드(demoInviteCode)와는 별개.
const MY_INVITE_CODE = '501537'

// ============================================================================
//  가족편지 공유 스토어
//  가족편지에 남긴 '돌봄 기록'이 곧 '돌봄일지'다. 한 곳(records)에 담아
//  가족편지 타임라인 · 돌봄일지 게시판 · 상세가 같은 데이터를 본다.
//  (mock: 앱 세션 동안만 유지 / 나중에 api/family.js 로 교체)
// ============================================================================

export const TODAY = '2026-07-07'
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

// 상세용: "2026-07-05 (금)"
export function fmtDateWithWeekday(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`)
  return `${dateStr} (${WEEKDAYS[d.getDay()]})`
}
// 게시판용: "07-05 14:20"
export function fmtBoardTime(r) {
  return `${r.date.slice(5)} ${r.time}`
}
// 타임라인용: "오늘 14:20" / "07-05 14:20"
export function fmtTimelineTime(r) {
  return `${r.date === TODAY ? '오늘' : r.date.slice(5)} ${r.time}`
}

const MED_KEYS = ['m', 'l', 'd']
const FamilyCtx = createContext(null)

let seq = 100

export function FamilyProvider({ children }) {
  const [records, setRecords] = useState(() => seedRecords.map((r) => ({ ...r, meds: { ...r.meds } })))
  const [meds, setMeds] = useState(() =>
    MED_KEYS.reduce((acc, k, i) => ({ ...acc, [k]: !!seedMeds[i]?.taken }), {}))
  const [inviteCode, setInviteCode] = useState(MY_INVITE_CODE)

  // 오늘의 약 체크 토글 (시간 설정 없이 체크만)
  const toggleMed = (k) => setMeds((prev) => ({ ...prev, [k]: !prev[k] }))

  // 돌봄 기록 남기기 → 타임라인 최상단 추가 (그날의 약 스냅샷 포함)
  const addRecord = (rawBody) => {
    const body = rawBody.trim()
    if (!body) return null
    const now = new Date()
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
    const rec = { id: `FR-n${seq++}`, author: '나', date: TODAY, time, meds: { ...meds }, body }
    setRecords((prev) => [rec, ...prev])
    return rec
  }

  const updateRecord = (id, rawBody) => {
    const body = rawBody.trim()
    if (!body) return
    setRecords((prev) => prev.map((r) => (r.id === id ? { ...r, body } : r)))
  }

  const deleteRecord = (id) => setRecords((prev) => prev.filter((r) => r.id !== id))

  // 새 초대 코드 생성 (6자리)
  const regenerateCode = () => {
    const code = String(Math.floor(100000 + Math.random() * 900000))
    setInviteCode(code)
    return code
  }

  return (
    <FamilyCtx.Provider value={{ records, meds, inviteCode, toggleMed, addRecord, updateRecord, deleteRecord, regenerateCode }}>
      {children}
    </FamilyCtx.Provider>
  )
}

export function useFamily() {
  const ctx = useContext(FamilyCtx)
  if (!ctx) throw new Error('useFamily must be used within FamilyProvider')
  return ctx
}
