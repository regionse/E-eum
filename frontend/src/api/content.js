// 공지사항 · 문의
import {
  delay,
  mockResolve,
  request,
} from './client.js'

import {
  inquiries,
} from '../mock/db.js'


// =========================================================
// 공지사항 공통 Query String 생성
// =========================================================

function buildNoticeQuery({
  page = 1,
  size = 10,
  category = '',
  keyword = '',
} = {}) {
  const params = new URLSearchParams()

  params.set(
    'page',
    String(page),
  )

  params.set(
    'size',
    String(size),
  )

  if (
    category
    && category !== '전체'
  ) {
    params.set(
      'category',
      category,
    )
  }

  const cleanedKeyword = keyword.trim()

  if (cleanedKeyword) {
    params.set(
      'keyword',
      cleanedKeyword,
    )
  }

  return `?${params.toString()}`
}


// =========================================================
// 사용자 공지사항 API
// =========================================================

/**
 * 사용자 공지사항 목록 조회
 *
 * 활성 상태인 공지만 조회한다.
 *
 * 응답:
 * {
 *   items: [],
 *   total: 0,
 *   page: 1,
 *   size: 10,
 *   total_pages: 0
 * }
 */
export function listNotices({
  page = 1,
  size = 10,
  category = '',
  keyword = '',
} = {}) {
  const query = buildNoticeQuery({
    page,
    size,
    category,
    keyword,
  })

  return request(
    `/notices${query}`,
  )
}


/**
 * 사용자 공지사항 상세 조회
 *
 * 상세 조회 시 백엔드에서 조회수가 1 증가한다.
 */
export function getNotice(
  noticeId,
) {
  return request(
    `/notices/${noticeId}`,
  )
}


// =========================================================
// 관리자 공지사항 API
// =========================================================

/**
 * 관리자 공지사항 목록 조회
 *
 * 활성·비활성 공지를 모두 조회한다.
 * 관리자 토큰이 필요하다.
 */
export function listAdminNotices({
  page = 1,
  size = 10,
  category = '',
  keyword = '',
} = {}) {
  const query = buildNoticeQuery({
    page,
    size,
    category,
    keyword,
  })

  return request(
    `/admin/notices${query}`,
  )
}


/**
 * 관리자 공지사항 상세 조회
 *
 * 활성·비활성 상태와 관계없이 조회한다.
 */
export function getAdminNotice(
  noticeId,
) {
  return request(
    `/admin/notices/${noticeId}`,
  )
}


/**
 * 관리자 공지사항 등록
 *
 * data:
 * {
 *   notice_category,
 *   notice_title,
 *   notice_content
 * }
 */
export function createAdminNotice(
  data,
) {
  return request(
    '/admin/notices',
    {
      method: 'POST',
      body: {
        notice_category:
          data.notice_category,

        notice_title:
          data.notice_title,

        notice_content:
          data.notice_content,
      },
    },
  )
}


/**
 * 관리자 공지사항 수정
 *
 * 활성·비활성 상태는 이 API에서 수정하지 않는다.
 */
export function updateAdminNotice(
  noticeId,
  data,
) {
  return request(
    `/admin/notices/${noticeId}`,
    {
      method: 'PUT',
      body: {
        notice_category:
          data.notice_category,

        notice_title:
          data.notice_title,

        notice_content:
          data.notice_content,
      },
    },
  )
}


/**
 * 관리자 공지사항 활성·비활성 변경
 */
export function updateAdminNoticeStatus(
  noticeId,
  noticeStatus,
) {
  return request(
    `/admin/notices/${noticeId}/status`,
    {
      method: 'PATCH',
      body: {
        notice_status:
          noticeStatus,
      },
    },
  )
}


// =========================================================
// 문의 API
// - 문의 백엔드 연동 전까지 기존 Mock 유지
// =========================================================

export function listInquiries() {
  return mockResolve(
    inquiries,
    500,
  )
}


export function getInquiry(
  id,
) {
  return mockResolve(
    () => inquiries.find(
      (inquiry) =>
        String(inquiry.id) === String(id),
    ),
    400,
  )
}


export async function submitInquiry(
  data,
) {
  await delay(700)

  inquiries.unshift({
    id: Date.now(),
    status: '접수',
    answer: '',
    date: '2026-07-07',
    ...data,
  })

  return {
    ok: true,
  }
}

