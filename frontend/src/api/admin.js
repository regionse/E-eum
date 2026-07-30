// 관리자 · 대시보드/회원/정책 최신화
import {
  mockResolve,
  request,
} from './client.js'

import {
  dashboardKpis,
  aiTrend,
  featureUsage,
  adminUsers,
  adminAccounts,
} from '../mock/db.js'


// =========================================================
// 기존 관리자 mock API
// =========================================================

export function getDashboard() {
  return mockResolve(
    () => ({
      kpis: dashboardKpis,
      aiTrend,
      featureUsage,
    }),
    600,
  )
}

export function listAdminUsers() {
  return mockResolve(
    adminUsers,
    500,
  )
}

export function listAdminAccounts() {
  return mockResolve(
    adminAccounts,
    500,
  )
}


// =========================================================
// 덜다 · 정책 데이터 최신화 API
// =========================================================

/**
 * 정책 데이터 최신화를 시작한다.
 *
 * 중앙부처 정책 API 조회,
 * 서울·경기 정책 크롤링,
 * 변경 정책 임베딩 작업을 백그라운드에서 시작한다.
 *
 * 응답 예시:
 * {
 *   execution_id: 12,
 *   message: '정책 데이터 최신화를 시작했습니다.'
 * }
 */
export function startPolicySync() {
  return request(
    '/admin/policy-sync',
    {
      method: 'POST',
    },
  )
}

/**
 * 가장 최근 정책 최신화 실행 결과를 조회한다.
 *
 * 응답 예시:
 * {
 *   result: {
 *     id: 12,
 *     status: 'completed',
 *     api_sync_at: '2026-07-30T10:00:00',
 *     crawling_at: '2026-07-30T10:05:00',
 *     embedding_at: '2026-07-30T10:10:00',
 *     total_policy_count: 800,
 *     new_count: 10,
 *     updated_count: 4,
 *     failed_count: 0
 *   }
 * }
 *
 * 아직 실행 이력이 없다면 result는 null이다.
 */
export function getLatestPolicySyncResult() {
  return request(
    '/admin/policy-sync/latest',
  )
}

/**
 * 실행 ID에 해당하는 정책 최신화 상태를 조회한다.
 *
 * 진행 상태:
 * - api_syncing
 * - crawling
 * - embedding
 * - completed
 * - completed_with_failures
 */
export function getPolicySyncResult(
  executionId,
) {
  return request(
    `/admin/policy-sync/${executionId}`,
  )
}