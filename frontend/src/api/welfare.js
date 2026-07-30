import { request } from './client.js'

// 인증 기능이 실제 백엔드와 연결되기 전까지
// 덜다 API 테스트에 사용할 사용자 ID
export const TEST_USER_ID = 3

/**
 * AI 맞춤 정책 추천 실행
 *
 * 최초 요청:
 * follow_up_answers: []
 *
 * 추가 질문 답변 후 재요청:
 * follow_up_answers에 기존 답변을 누적해서 전달
 */
export function recommendPolicies(
  input,
  {
    userId = TEST_USER_ID,
    signal,
  } = {},
) {
  return request(
    `/policy-recommendations/users/${userId}`,
    {
      method: 'POST',
      body: input,
      signal,
    },
  )
}

/**
 * 덜다 메인 화면 데이터
 *
 * 최근 추천 이력 최대 3건
 * 즐겨찾기 정책 최대 5건
 * 인기 정책 최대 5건
 */
export function getWelfareMain(
  userId = TEST_USER_ID,
) {
  return request(
    `/policy-recommendations/users/${userId}/main`,
  )
}

/**
 * 최근 정책 추천 이력
 */
export function getPolicyRecommendationHistory(
  userId = TEST_USER_ID,
) {
  return request(
    `/policy-recommendations/users/${userId}`,
  )
}

/**
 * 특정 추천 이력의 상세 결과
 */
export function getPolicyRecommendationDetail(
  recommendationId,
  userId = TEST_USER_ID,
) {
  return request(
    `/policy-recommendations/users/${userId}/${recommendationId}`,
  )
}

/**
 * 정책 단건 상세 조회
 */
export function getPolicyDetail(
  policyId,
  userId = TEST_USER_ID,
) {
  return request(
    `/policy-recommendations/users/${userId}/policies/${policyId}`,
  )
}

/**
 * 즐겨찾기 정책 목록
 */
export function getPolicyFavorites(
  userId = TEST_USER_ID,
) {
  return request(
    `/policy-recommendations/users/${userId}/favorites`,
  )
}

/**
 * 정책 즐겨찾기 추가
 */
export function addPolicyFavorite(
  policyId,
  userId = TEST_USER_ID,
) {
  return request(
    `/policy-recommendations/users/${userId}/favorites/${policyId}`,
    {
      method: 'POST',
    },
  )
}

/**
 * 정책 즐겨찾기 해제
 */
export function deletePolicyFavorite(
  policyId,
  userId = TEST_USER_ID,
) {
  return request(
    `/policy-recommendations/users/${userId}/favorites/${policyId}`,
    {
      method: 'DELETE',
    },
  )
}
