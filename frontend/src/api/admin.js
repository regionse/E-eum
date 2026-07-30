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