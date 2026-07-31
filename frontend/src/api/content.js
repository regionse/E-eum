// 공지사항 · 문의
import {
  request,
} from './client.js'


// =========================================================
// 공지사항 Query String
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


export function getAdminNotice(
  noticeId,
) {
  return request(
    `/admin/notices/${noticeId}`,
  )
}


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
// 문의 Query String
// =========================================================

function buildInquiryQuery({
  page = 1,
  size = 10,
  inquiry_type = '',
  inquiry_status = '',
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

  if (inquiry_type) {
    params.set(
      'inquiry_type',
      inquiry_type,
    )
  }

  if (inquiry_status) {
    params.set(
      'inquiry_status',
      inquiry_status,
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
// 사용자 문의 API
// =========================================================

export function listInquiries({
  page = 1,
  size = 10,
} = {}) {
  const query = buildInquiryQuery({
    page,
    size,
  })

  return request(
    `/inquiries${query}`,
  )
}


export function getInquiry(
  inquiryId,
) {
  return request(
    `/inquiries/${inquiryId}`,
  )
}


export function submitInquiry(
  data,
) {
  return request(
    '/inquiries',
    {
      method: 'POST',

      body: {
        inquiry_type:
          data.inquiry_type,

        inquiry_title:
          data.inquiry_title,

        inquiry_content:
          data.inquiry_content,
      },
    },
  )
}


export function deleteInquiry(
  inquiryId,
) {
  return request(
    `/inquiries/${inquiryId}`,
    {
      method: 'DELETE',
    },
  )
}


// =========================================================
// 관리자 문의 API
// =========================================================

export function listAdminInquiries({
  page = 1,
  size = 10,
  inquiry_type = '',
  inquiry_status = '',
  keyword = '',
} = {}) {
  const query = buildInquiryQuery({
    page,
    size,
    inquiry_type,
    inquiry_status,
    keyword,
  })

  return request(
    `/admin/inquiries${query}`,
  )
}


export function getAdminInquiry(
  inquiryId,
) {
  return request(
    `/admin/inquiries/${inquiryId}`,
  )
}


export function updateAdminInquiryStatus(
  inquiryId,
  inquiryStatus,
) {
  return request(
    `/admin/inquiries/${inquiryId}/status`,
    {
      method: 'PATCH',

      body: {
        inquiry_status:
          inquiryStatus,
      },
    },
  )
}


export function createAdminInquiryAnswer(
  inquiryId,
  answerContent,
) {
  return request(
    `/admin/inquiries/${inquiryId}/answer`,
    {
      method: 'POST',

      body: {
        inquiry_answer_content:
          answerContent,
      },
    },
  )
}


export function updateAdminInquiryAnswer(
  inquiryId,
  answerContent,
) {
  return request(
    `/admin/inquiries/${inquiryId}/answer`,
    {
      method: 'PATCH',

      body: {
        inquiry_answer_content:
          answerContent,
      },
    },
  )
}