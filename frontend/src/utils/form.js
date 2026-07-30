// ============================================================================
//  입력 제약 공용 유틸 — 회원가입·아이디찾기·비밀번호찾기가 함께 쓴다.
//  "검증 문구만 뜨고 무한정 타이핑되던" 문제를 입력 단계에서 원천 차단한다.
// ============================================================================

// 아이디: 영문+숫자만, 10자 컷
export const sanitizeId = (v) => (v || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 10)

// 생년월일: 숫자 8자리(YYYYMMDD) → YYYY-MM-DD (연도 4자리 고정, 최대 10자)
export const formatBirth = (v) => {
  const d = (v || '').replace(/\D/g, '').slice(0, 8)
  return d.length > 6 ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6)}`
    : d.length > 4 ? `${d.slice(0, 4)}-${d.slice(4)}` : d
}
export const okBirth = (v) => /^\d{4}-\d{2}-\d{2}$/.test(v || '')

// 연락처: 실제 번호 체계로 자동 하이픈 — 휴대폰 10·11자리, 서울(02) 유선, 끝 그룹은 항상 4자리
export const formatPhone = (v) => {
  const d = (v || '').replace(/\D/g, '').slice(0, 11)
  if (d.startsWith('02')) {                                  // 서울(지역번호 2자리)
    if (d.length <= 2) return d
    if (d.length <= 6) return `${d.slice(0, 2)}-${d.slice(2)}`
    if (d.length <= 9) return `${d.slice(0, 2)}-${d.slice(2, 5)}-${d.slice(5)}`   // 02-123-4567
    return `${d.slice(0, 2)}-${d.slice(2, 6)}-${d.slice(6)}`                      // 02-1234-5678
  }
  if (d.length <= 3) return d                                // 휴대폰·기타(3자리)
  if (d.length <= 7) return `${d.slice(0, 3)}-${d.slice(3)}`
  if (d.length <= 10) return `${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6)}`    // 010-123-4567
  return `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`                        // 010-1234-5678
}
// 휴대폰 10~11자리 · 유선(02·0XX) 9~11자리
export const okPhone = (v) => {
  const d = (v || '').replace(/\D/g, '')
  if (/^01[016-9]/.test(d)) return d.length === 10 || d.length === 11
  return /^0\d/.test(d) && d.length >= 9 && d.length <= 11
}
