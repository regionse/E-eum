// 관리자 · 대시보드/회원/관리자 계정/정책 최신화
import {
  request,
} from './client.js'


// =========================================================
// 관리자 · 회원 관리
// =========================================================


export function listAdminUsers() {
  return request(
    '/admin/users',
  )
}


export function updateAdminUserStatus(
  userId,
  status,
) {
  return request(
    `/admin/users/${userId}/status`,
    {
      method: 'PATCH',
      body: {
        status,
      },
    },
  )
}


// =========================================================
// 관리자 · 관리자 계정 관리
// =========================================================


export function listAdminAccounts() {
  return request(
    '/admin/accounts',
  )
}


export function updateAdminAccountStatus(
  userId,
  status,
) {
  return request(
    `/admin/accounts/${userId}/status`,
    {
      method: 'PATCH',
      body: {
        status,
      },
    },
  )
}


// =========================================================
// 덜다 · 정책 데이터 최신화
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
export function getPolicySyncResult(
  executionId,
) {
  return request(
    `/admin/policy-sync/${executionId}`,
  )
}


// =========================================================
// 잇다 · 임베딩 현황
// =========================================================


export function getItdaSyncStatus() {
  return request(
    '/admin/itda-sync/latest',
  )
}


/**
 * 진로 데이터 최신화를 백그라운드로 시작한다.
 * 202 로 바로 돌아오고, 진행 상황은 getItdaSyncRun() 을 폴링해서 본다.
 * 이미 돌고 있으면 새로 시작하지 않고 그 실행의 상태를 돌려준다.
 */
export function startItdaSync() {
  return request(
    '/admin/itda-sync',
    {
      method: 'POST',
    },
  )
}


/**
 * 최신화 진행 현황 (단계별 상태·퍼센트). 한 번도 안 돌렸으면 status='idle'.
 */
export function getItdaSyncRun() {
  return request(
    '/admin/itda-sync/run',
  )
}


// =========================================================
// 관리자 · 대시보드
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