// ★ 2026-08-06 — 주소와 토큰은 client.js 하나에서 가져온다.
import { API_BASE, getToken } from './client.js'

// 로그인 토큰과 JSON 요청을 공통으로 처리한다.
async function request(path, options = {}) {
  const token = getToken()

  // JavaScript 객체를 JSON 문자열로 변환한다.
  const isFormData =
    typeof FormData !== 'undefined' &&
    options.body instanceof FormData

  const body =
    options.body != null &&
    typeof options.body !== 'string' &&
    !isFormData
      ? JSON.stringify(options.body)
      : options.body

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    body,
    headers: {
      'Content-Type': 'application/json',
      ...(token
        ? { Authorization: `Bearer ${token}` }
        : {}),
      ...options.headers,
    },
  })

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const error = new Error(
      data?.detail ?? '요청을 처리하지 못했습니다.',
    )

    error.status = response.status
    error.data = data

    throw error
  }

  return data
}

// ============================================================
// 가족방
// ============================================================

export function createCareGroup({
  userId,
  relationships = '본인',
}) {
  return request('/care-groups', {
    method: 'POST',
    body: {
      user_id: userId,
      relationships,
    },
  })
}

export function getMyCareGroups(userId) {
  const params = new URLSearchParams({
    user_id: String(userId),
  })

  return request(`/care-groups/my?${params}`)
}

export function getCareGroupMembers({
  careGroupId,
  userId,
}) {
  const params = new URLSearchParams({
    user_id: String(userId),
  })

  return request(
    `/care-groups/${careGroupId}/members?${params}`,
  )
}

// ============================================================
// 초대코드
// ============================================================

export function createInviteCode({
  userId,
  careGroupId,
}) {
  return request('/invite-codes', {
    method: 'POST',
    body: {
      user_id: userId,
      care_group_id: careGroupId,
    },
  })
}

export function joinCareGroup({
  userId,
  inviteCode,
  relationships,
}) {
  return request('/invite-codes/join', {
    method: 'POST',
    body: {
      user_id: userId,
      invite_code: inviteCode.toUpperCase(),
      relationships: relationships || null,
    },
  })
}

// ============================================================
// 가족편지 / 돌봄일지
// ============================================================

export function createFamilyLetter({
  userId,
  careGroupId,
  content,
}) {
  return request('/family-letters', {
    method: 'POST',
    body: {
      user_id: userId,
      care_group_id: careGroupId,
      content,
    },
  })
}

export function getFamilyLetters({
  userId,
  careGroupId,
  page = 1,
  size = 10,
}) {
  const params = new URLSearchParams({
    user_id: String(userId),
    care_group_id: String(careGroupId),
    page: String(page),
    size: String(size),
  })

  return request(`/family-letters?${params}`)
}

export function getFamilyLetter({
  letterId,
  userId,
}) {
  const params = new URLSearchParams({
    user_id: String(userId),
  })

  return request(
    `/family-letters/${letterId}?${params}`,
  )
}

// ============================================================
// 지원 기관
// ============================================================

export function getSupportFacilities({
  facilityType,
  page = 1,
  size = 20,
}) {
  const params = new URLSearchParams({
    facility_type: facilityType,
    page: String(page),
    size: String(size),
  })

  return request(`/support-facilities?${params}`)
}

// 기존 ResourceMap.jsx가 아직 사용하는 호환 함수이다.
export async function listResources() {
  const facilities = await getSupportFacilities({
    facilityType: 'MENTAL_HEALTH',
    page: 1,
    size: 20,
  })

  return facilities.map((facility, index) => ({
    id: facility.facility_id,
    facilityId: facility.facility_id,
    type: '정신건강',
    name: facility.facility_name,
    dist: '거리 확인 전',
    desc:
      facility.address ??
      facility.facility_category ??
      '기관 상세정보 없음',
    phone: facility.phone ?? '정보 없음',

    // 기존 mock 지도 핀 화면을 위한 임시 좌표
    x: 15 + (index % 4) * 23,
    y: 20 + (Math.floor(index / 4) % 4) * 20,
  }))
}

export function getSupportFacilityMap(facilityId) {
  return request(
    `/support-facilities/${facilityId}/map`,
  )
}

// ============================================================
// 주간 분석 및 최종 기관 추천
// ============================================================

export function analyzeWeeklyCare({
  careGroupId,
  targetDate,
  signal,
}) {
  const params = new URLSearchParams()

  if (targetDate) {
    params.set('target_date', targetDate)
  }

  const query = params.toString()

  return request(
    `/weekly-care-analyses/${careGroupId}${
      query ? `?${query}` : ''
    }`,
    {
      method: 'POST',
      signal,
    },
  )
}

export function recommendFacility({
  careGroupId,
  latitude,
  longitude,
  signal,
}) {
  return request(
    `/weekly-care-analyses/${careGroupId}/recommend`,
    {
      method: 'POST',
      signal,
      body: {
        latitude,
        longitude,
      },
    },
  )
}

// ============================================================
// 현재 위치
// ============================================================

export function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(
        new Error(
          '이 브라우저에서는 위치 정보를 사용할 수 없습니다.',
        ),
      )
      return
    }

    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        resolve({
          latitude: coords.latitude,
          longitude: coords.longitude,
        })
      },
      () => {
        reject(
          new Error(
            '주변 기관 추천을 위해 위치 권한을 허용해 주세요.',
          ),
        )
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000,
      },
    )
  })
}

// ============================================================
// 도로 경로
// ============================================================

export function getDrivingRoute({
  originLatitude,
  originLongitude,
  destinationLatitude,
  destinationLongitude,
}) {
  const params = new URLSearchParams({
    origin_latitude: String(originLatitude),
    origin_longitude: String(originLongitude),
    destination_latitude: String(destinationLatitude),
    destination_longitude: String(destinationLongitude),
  })

  return request(`/support-facilities/route?${params}`)
}