import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  listAdminNotices,
  updateAdminNoticeStatus,
} from '../../api/content.js'

import {
  Async,
  PageHead,
  useAsync,
  useToast,
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
// 관리자 공지사항 목록
// =========================================================
export default function AdminNotices() {
  const navigate = useNavigate()
  const toast = useToast()

  const [
    category,
    setCategory,
  ] = useState('전체')

  // 검색창에 현재 입력한 값
  const [
    keywordInput,
    setKeywordInput,
  ] = useState('')

  // 실제 API 요청에 사용하는 검색어
  const [
    keyword,
    setKeyword,
  ] = useState('')

  const [
    page,
    setPage,
  ] = useState(1)

  // 상태 변경 중인 공지 ID
  const [
    changingNoticeId,
    setChangingNoticeId,
  ] = useState(null)


  // =========================================================
  // 관리자 공지 목록 조회
  // - 활성·비활성 공지를 모두 조회
  // =========================================================
  const state = useAsync(
    () => listAdminNotices({
      page,
      size: PAGE_SIZE,
      category,
      keyword,
    }),
    [
      page,
      category,
      keyword,
    ],
  )


  // =========================================================
  // 카테고리 변경
  // =========================================================
  const changeCategory = (
    nextCategory,
  ) => {
    setCategory(nextCategory)
    setPage(1)
  }


  // =========================================================
  // 검색
  // =========================================================
  const runSearch = () => {
    setKeyword(
      keywordInput.trim(),
    )

    setPage(1)
  }


  // =========================================================
  // 공지 활성·비활성 변경
  // =========================================================
  const toggleStatus = async (
    notice,
  ) => {
    const nextStatus =
      !notice.notice_status

    const nextStatusText =
      nextStatus
        ? '활성'
        : '비활성'

    const confirmed = window.confirm(
      `이 공지를 ${nextStatusText} 상태로 변경할까요?`,
    )

    if (!confirmed) {
      return
    }

    setChangingNoticeId(
      notice.notice_id,
    )

    try {
      await updateAdminNoticeStatus(
        notice.notice_id,
        nextStatus,
      )

      toast.show(
        `게시 상태를 '${nextStatusText}'로 변경했어요.`,
      )

      state.reload()

    } catch (error) {
      toast.show(
        error.message
        || '상태 변경에 실패했어요.',
      )

    } finally {
      setChangingNoticeId(null)
    }
  }


  // =========================================================
  // 페이지 변경
  // =========================================================
  const changePage = (
    nextPage,
  ) => {
    setPage(nextPage)

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }


  return (
    <div>
      <PageHead
        title="공지사항 관리"
        sub="공지·업데이트·이벤트를 등록하고 관리해요."
        right={(
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => {
              navigate(
                '/admin/notices/new',
              )
            }}
          >
            + 등록
          </button>
        )}
      />


      {/* 검색 및 카테고리 영역 */}
      <div
        className="row"
        style={{
          gap: 8,
          marginBottom: 'var(--sp-4)',
          flexWrap: 'wrap',
        }}
      >
        <select
          className="select"
          style={{
            width: 'auto',
          }}
          value={category}
          onChange={(event) => {
            changeCategory(
              event.target.value,
            )
          }}
        >
          {CATEGORIES.map((item) => (
            <option
              key={item}
              value={item}
            >
              유형 · {item}
            </option>
          ))}
        </select>

        <div
          style={{
            flex: 1,
            minWidth: 12,
          }}
        />

        <input
          className="input"
          style={{
            maxWidth: 240,
          }}
          placeholder="제목·내용 검색"
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


      {/* 관리자 공지 목록 */}
      <div
        className="card"
        style={{
          overflowX: 'auto',
        }}
      >
        <Async state={state}>
          {(data) => {
            const notices =
              data?.items ?? []

            return (
              <table className="tbl">
                <thead>
                  <tr>
                    <th
                      style={{
                        width: 64,
                      }}
                    >
                      No
                    </th>

                    <th
                      style={{
                        width: 110,
                      }}
                    >
                      유형
                    </th>

                    <th>
                      제목
                    </th>

                    <th
                      style={{
                        width: 120,
                      }}
                    >
                      작성일
                    </th>

                    <th
                      style={{
                        width: 100,
                      }}
                    >
                      상태
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {notices.length === 0 ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="muted center"
                        style={{
                          padding: 20,
                        }}
                      >
                        조건에 맞는 공지가 없어요.
                      </td>
                    </tr>
                  ) : (
                    notices.map((notice) => {
                      const isChanging =
                        changingNoticeId
                        === notice.notice_id

                      return (
                        <tr
                          key={notice.notice_id}
                        >
                          <td className="muted">
                            {notice.notice_id}
                          </td>

                          <td>
                            <span
                              className={
                                `badge ${
                                  CATEGORY_BADGE[
                                    notice.notice_category
                                  ] ?? 'badge-gray'
                                }`
                              }
                              style={{
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {notice.notice_category}
                            </span>
                          </td>

                          <td>
                            <button
                              type="button"
                              onClick={() => {
                                navigate(
                                  `/admin/notices/${notice.notice_id}`,
                                )
                              }}
                              style={{
                                fontWeight: 600,
                                background: 'none',
                                border: 0,
                                padding: 0,
                                cursor: 'pointer',
                                color: 'var(--ink)',
                                textAlign: 'left',
                                textDecoration:
                                  'underline',
                                textDecorationColor:
                                  'var(--teal-200)',
                              }}
                            >
                              {notice.notice_title}
                            </button>
                          </td>

                          <td className="muted">
                            {formatDate(
                              notice.created_at,
                            )}
                          </td>

                          <td>
                            <button
                              type="button"
                              className={
                                `badge ${
                                  notice.notice_status
                                    ? 'badge-teal'
                                    : 'badge-gray'
                                }`
                              }
                              style={{
                                cursor:
                                  isChanging
                                    ? 'wait'
                                    : 'pointer',
                                border: 0,
                                whiteSpace: 'nowrap',
                              }}
                              disabled={isChanging}
                              title="클릭하면 활성·비활성 상태가 변경됩니다."
                              onClick={() => {
                                toggleStatus(
                                  notice,
                                )
                              }}
                            >
                              {isChanging
                                ? '변경 중'
                                : (
                                  notice.notice_status
                                    ? '활성'
                                    : '비활성'
                                )}
                            </button>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            )
          }}
        </Async>
      </div>


      {/* 전체 건수 및 페이지네이션 */}
      {!state.loading
        && !state.error
        && state.data && (
        <div
          className="row"
          style={{
            justifyContent:
              'space-between',
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
                disabled={
                  state.data.page === 1
                }
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
                    changePage(
                      pageNumber,
                    )
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

      {toast.node}
    </div>
  )
}