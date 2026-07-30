// 관리자 · 대시보드 / 회원 / 덜다 정책 최신화
import { mockResolve, request } from './client.js'
import {
  dashboardKpis, aiTrend, featureUsage,
  adminUsers, adminAccounts,
} from '../mock/db.js'

// ── 대시보드·회원 (mock) ────────────────────────────────────────────
//  대시보드는 2026-07-30 복구했다 — '/admin 첫 화면을 회원관리로' 요청을
//  대시보드 삭제로 잘못 처리했던 것을 되돌림. 첫 화면은 회원관리, 대시보드는 그 아래 메뉴.
export function getDashboard() {
  return mockResolve(() => ({ kpis: dashboardKpis, aiTrend, featureUsage }), 600)
}

export function listAdminUsers() { return mockResolve(adminUsers, 500) }
export function listAdminAccounts() { return mockResolve(adminAccounts, 500) }


// ── 덜다 · 정책 데이터 최신화 (실제 백엔드 · 팀원 작업) ──────────────
//  중앙부처 정책 API 조회 → 서울·경기 크롤링 → 변경분 임베딩을 백그라운드로 시작한다.
//  백엔드: Backend/app/delda/ (policy_sync_orchestrator)
export function startPolicySync() {
  return request('/admin/policy-sync', { method: 'POST' })
}

// 가장 최근 실행 결과. 실행 이력이 없으면 result 는 null.
export function getLatestPolicySyncResult() {
  return request('/admin/policy-sync/latest')
}

// 실행 ID 별 진행 상태 — api_syncing · crawling · embedding · completed · completed_with_failures
export function getPolicySyncResult(executionId) {
  return request(`/admin/policy-sync/${executionId}`)
}
