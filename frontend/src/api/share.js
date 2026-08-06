//  ★ 2026-08-06 — 주소와 토큰은 client.js 하나에서 가져온다.
//    (예전엔 이 파일이 VITE_API_BASE_URL 과 localStorage 를 «따로» 읽었다 —
//     client.js 와 환경변수 이름이 달라 배포 때 갈라지는 구조였다)
import { API_BASE, getToken } from './client.js'

//  ★ 2026-08-06 — **로그인 토큰을 실어 보낸다.**
//    왜 필요한가: 백엔드 나누다 라우터가 가족방·가족편지·초대코드·주간분석에
//    Depends(get_current_user) 를 걸었다(router.py 의 get_verified_user_id 주석).
//    그 주석은 「프론트(api/client.js)는 이미 Bearer 토큰을 싣고 있으므로 화면 수정
//    없이 막힌다」고 적었는데, **나누다 화면은 client.js 를 안 썼다.**
//    이 파일이 자체 request 를 갖고 있고 여기엔 Authorization 이 없었다
//    → 그날부터 가족편지가 전부 401 이 됐다.
async function request(path, options = {}) {
  const token = getToken()

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
    body: JSON.stringify({
      user_id: userId,
      relationships,
    }),
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
    body: JSON.stringify({
      user_id: userId,
      care_group_id: careGroupId,
    }),
  })
}

export function joinCareGroup({
  userId,
  inviteCode,
  relationships,
}) {
  return request('/invite-codes/join', {
    method: 'POST',
    body: JSON.stringify({
      user_id: userId,
      invite_code: inviteCode.toUpperCase(),
      relationships: relationships || null,
    }),
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
    body: JSON.stringify({
      user_id: userId,
      care_group_id: careGroupId,
      content,
    }),
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

// 기존 ResourceMap.jsx가 아직 사용하는 호환 함수입니다.
// ResourceMap 화면을 실제 최종 추천 기관 화면으로 교체하면
// 이 함수는 삭제할 수 있습니다.
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

    // 기존 mock 지도 핀 화면이 깨지지 않도록 하는 임시 좌표입니다.
    // 실제 위도·경도가 아니며 다음 지도 연결 단계에서 제거합니다.
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
      body: JSON.stringify({
        latitude,
        longitude,
      }),
    },
  )
}

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