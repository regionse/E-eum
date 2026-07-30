import { useState } from 'react'
import { Link } from 'react-router-dom'

import { listNotices } from '../../api/content.js'
import {
  Async,
  PageHead,
  useAsync,
} from '../../components/ui/index.jsx'


const CATEGORIES = [
  '전체',
  '공지사항',
  '업데이트',
  '이벤트',
]

const CATEGORY_BADGE = {
  공지사항: 'badge-gray',
  업데이트: 'badge-teal',
  이벤트: 'badge-amber',
}

const PAGE_SIZE = 10


// =========================================================
// 날짜 표시 형식
// 예: 2026-07-30T12:30:00 → 2026.07.30
// =========================================================
function formatDate(value) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date
    .toLocaleDateString(
      'ko-KR',
      {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      },
    )
    .replace(/\.$/, '')
}


// =========================================================
// 사용자 공지사항 목록
// =========================================================
export default function NoticeList() {
  // 화면에서 선택한 카테고리
  const [
    category,
    setCategory,
  ] = useState('전체')

  // 검색창에 현재 입력 중인 값
  const [
    keywordInput,
    setKeywordInput,
  ] = useState('')

  // 실제 API 요청에 사용하는 검색 조건
  const [
    searchParams,
    setSearchParams,
  ] = useState({
    page: 1,
    size: PAGE_SIZE,
    category: '전체',
    keyword: '',
  })

  const state = useAsync(
    () => listNotices(searchParams),
    [searchParams],
  )


  // =========================================================
  // 카테고리 변경
  // =========================================================
  const changeCategory = (
    nextCategory,
  ) => {
    setCategory(nextCategory)

    setSearchParams((prev) => ({
      ...prev,
      page: 1,
      category: nextCategory,
    }))
  }


  // =========================================================
  // 검색 실행
  // =========================================================
  const runSearch = () => {
    setSearchParams((prev) => ({
      ...prev,
      page: 1,
      category,
      keyword: keywordInput.trim(),
    }))
  }


  // =========================================================
  // 페이지 변경
  // =========================================================
  const changePage = (
    nextPage,
  ) => {
    setSearchParams((prev) => ({
      ...prev,
      page: nextPage,
    }))

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }


  return (
    <div className="container page">
      <PageHead
        title="공지사항"
        sub="이음의 새 소식과 안내를 확인하세요."
      />


      {/* 검색·카테고리 영역 */}
      <div
        className="row"
        style={{
          gap: 8,
          marginBottom: 'var(--sp-4)',
          flexWrap: 'wrap',
        }}
      >
        {CATEGORIES.map((item) => (
          <button
            key={item}
            type="button"
            className={
              `chip ${
                category === item
                  ? 'on'
                  : ''
              }`
            }
            onClick={() => {
              changeCategory(item)
            }}
          >
            {item}
          </button>
        ))}

        <div style={{ flex: 1 }} />

        <input
          className="input"
          style={{
            maxWidth: 240,
          }}
          placeholder="검색어를 입력하세요"
          value={keywordInput}
          onChange={(event) => {
            setKeywordInput(
              event.target.value,
            )
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              runSearch()
            }
          }}
        />

        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={runSearch}
        >
          검색
        </button>
      </div>


      {/* 공지 목록 */}
      <div className="card">
        <Async state={state}>
          {(data) => {
            const notices = data?.items ?? []

            if (notices.length === 0) {
              return (
                <div className="empty">
                  <div className="ic">
                    🔍
                  </div>

                  <p>
                    검색 결과가 없어요.
                  </p>
                </div>
              )
            }

            return notices.map((notice) => (
              <Link
                key={notice.notice_id}
                to={`/notice/${notice.notice_id}`}
                className="list-row"
                style={{
                  display: 'flex',
                }}
              >
                <div
                  className="row"
                  style={{
                    gap: 12,
                    minWidth: 0,
                  }}
                >
                  <span
                    className={
                      `badge ${
                        CATEGORY_BADGE[
                          notice.notice_category
                        ] ?? 'badge-gray'
                      }`
                    }
                    style={{
                      flexShrink: 0,
                    }}
                  >
                    {notice.notice_category}
                  </span>

                  <span
                    style={{
                      fontWeight: 600,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {notice.notice_title}
                  </span>
                </div>

                <div
                  className="row muted"
                  style={{
                    gap: 16,
                    fontSize: 13.5,
                    flexShrink: 0,
                  }}
                >
                  <span>
                    조회 {notice.view_cnt}
                  </span>

                  <span>
                    {formatDate(
                      notice.created_at,
                    )}
                  </span>
                </div>
              </Link>
            ))
          }}
        </Async>
      </div>


      {/* 전체 건수·페이지네이션 */}
      {!state.loading && !state.error && state.data && (
        <div
          className="row"
          style={{
            justifyContent: 'space-between',
            marginTop: 'var(--sp-4)',
            flexWrap: 'wrap',
            gap: 10,
          }}
        >
          <span
            className="muted"
            style={{
              fontSize: 13.5,
            }}
          >
            총 {state.data.total ?? 0}건
          </span>

          {state.data.total_pages > 1 && (
            <div
              className="pager"
              style={{
                margin: 0,
              }}
            >
              <button
                type="button"
                disabled={state.data.page === 1}
                onClick={() => {
                  changePage(
                    state.data.page - 1,
                  )
                }}
              >
                ‹
              </button>

              {Array.from(
                {
                  length:
                    state.data.total_pages,
                },
                (_, index) => index + 1,
              ).map((pageNumber) => (
                <button
                  key={pageNumber}
                  type="button"
                  className={
                    pageNumber
                      === state.data.page
                      ? 'on'
                      : ''
                  }
                  onClick={() => {
                    changePage(pageNumber)
                  }}
                >
                  {pageNumber}
                </button>
              ))}

              <button
                type="button"
                disabled={
                  state.data.page
                  === state.data.total_pages
                }
                onClick={() => {
                  changePage(
                    state.data.page + 1,
                  )
                }}
              >
                ›
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}