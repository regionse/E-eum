import { request } from './client.js'


// =========================================================
// 현재 로그인한 사용자 ID 조회
// =========================================================

function getLoggedInUserId() {
  const savedUser =
    localStorage.getItem('eum_user')

  if (!savedUser) {
    throw new Error(
      '로그인이 필요합니다. 다시 로그인해 주세요.',
    )
  }

  let user

  try {
    user = JSON.parse(savedUser)
  } catch {
    throw new Error(
      '로그인 사용자 정보를 확인할 수 없습니다. 다시 로그인해 주세요.',
    )
  }

  const userId = Number(user?.user_id)

  if (
    !Number.isInteger(userId)
    || userId < 1
  ) {
    throw new Error(
      '로그인 사용자 정보를 확인할 수 없습니다. 다시 로그인해 주세요.',
    )
  }

  return userId
}


// =========================================================
// 맞춤 정책 추천
// =========================================================

export function recommendPolicies(
  input,
  { signal } = {},
) {
  const userId = getLoggedInUserId()

  return request(
    `/policy-recommendations/users/${userId}`,
    {
      method: 'POST',
      body: input,
      signal,
      timeout: 120000,
    },
  )
}


// =========================================================
// 최근 정책 추천 이력
// =========================================================

export function getRecentPolicyRecommendations(
  { signal } = {},
) {
  const userId = getLoggedInUserId()

  return request(
    `/policy-recommendations/users/${userId}`,
    {
      signal,
    },
  )
}


// =========================================================
// 정책 추천 이력 상세
// =========================================================

export function getPolicyRecommendationDetail(
  recommendationId,
  { signal } = {},
) {
  const userId = getLoggedInUserId()

  return request(
    `/policy-recommendations/users/${userId}/${recommendationId}`,
    {
      signal,
    },
  )
}


// =========================================================
// 덜다 메인 화면
// =========================================================

export function getWelfareMain(
  { signal } = {},
) {
  const userId = getLoggedInUserId()

  return request(
    `/policy-recommendations/users/${userId}/main`,
    {
      signal,
    },
  )
}


// =========================================================
// 정책 단건 상세
// =========================================================

export function getPolicyDetail(
  policyId,
  { signal } = {},
) {
  const userId = getLoggedInUserId()

  return request(
    `/policy-recommendations/users/${userId}/policies/${policyId}`,
    {
      signal,
    },
  )
}


// 이전 코드와의 호환용 별칭
export function getPolicy(
  policyId,
  options = {},
) {
  return getPolicyDetail(
    policyId,
    options,
  )
}


// =========================================================
// 정책 즐겨찾기 목록
// =========================================================

export function getPolicyFavorites(
  { signal } = {},
) {
  const userId = getLoggedInUserId()

  return request(
    `/policy-recommendations/users/${userId}/favorites`,
    {
      signal,
    },
  )
}


// =========================================================
// 정책 즐겨찾기 추가
// =========================================================

export function addPolicyFavorite(
  policyId,
  { signal } = {},
) {
  const userId = getLoggedInUserId()

  return request(
    `/policy-recommendations/users/${userId}/favorites/${policyId}`,
    {
      method: 'POST',
      signal,
    },
  )
}


// =========================================================
// 정책 즐겨찾기 해제
// =========================================================

export function deletePolicyFavorite(
  policyId,
  { signal } = {},
) {
  const userId = getLoggedInUserId()

  return request(
    `/policy-recommendations/users/${userId}/favorites/${policyId}`,
    {
      method: 'DELETE',
      signal,
    },
  )
}