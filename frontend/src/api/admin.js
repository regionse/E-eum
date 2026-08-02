// 관리자 · 대시보드/회원/정책 최신화
import {
  mockResolve,
  request,
} from './client.js'

import {
  // dashboardKpis,
  // aiTrend,
  // featureUsage,
  adminUsers,
  adminAccounts,
} from '../mock/db.js'


// =========================================================
// 기존 관리자 mock API
// =========================================================


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
 */
export function getLatestPolicySyncResult() {
  return request(
    '/admin/policy-sync/latest',
  )
}

/**
 * 실행 ID에 해당하는 정책 최신화 상태를 조회한다.
 */
export function getPolicySyncResult(executionId) {
  return request(
    `/admin/policy-sync/${executionId}`,
  )
}


// =========================================================
// 관리자 · 잇다 임베딩 현황 (2026-08-02)
// =========================================================

/**
 * 잇다 임베딩 현황을 조회한다.
 *  { last_api_sync, last_embedding,
 *    cert_total, job_total, course_total,
 *    cert_embedded, course_embedded, failed_recent,
 *    runs: [{ target, finished_at, fetched, inserted, updated, embedded, status, message }] }
 *
 * 값은 배치가 돌 때 기록한 사실이다(itda_sync_log + content_hash).
 * 화면이 계산하지 않는다 — '언제 무엇이 바뀌었나'가 남아야 하기 때문.
 */
export function getItdaSyncStatus() {
  return request(
    '/admin/itda-sync/latest',
  )
}


// =========================================================
// 관리자 대시보드 API
// =========================================================
export function getDashboard(
  period = '7d',
) {
  return request(
    `/admin/dashboard?period=${
      encodeURIComponent(period)
    }`,
  )
}