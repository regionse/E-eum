import {
  Link,
  useParams,
} from 'react-router-dom'

import {
  getNotice,
} from '../../api/content.js'

import {
  Async,
  useAsync,
} from '../../components/ui/index.jsx'


const CATEGORY_BADGE = {
  공지사항: 'badge-gray',
  업데이트: 'badge-teal',
  이벤트: 'badge-amber',
}


// =========================================================
// 날짜 표시 형식
// 예: 2026-07-30T12:30:00 → 2026. 07. 30.
// =========================================================
function formatDate(value) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleDateString(
    'ko-KR',
    {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    },
  )
}


// =========================================================
// 사용자 공지사항 상세
// =========================================================
export default function NoticeDetail() {
  const {
    id,
  } = useParams()

  const state = useAsync(
    () => getNotice(id),
    [id],
  )

  return (
    <div
      className="container page"
      style={{
        maxWidth: 760,
      }}
    >
      <Async
        state={state}
        empty={(
          <div className="empty">
            공지사항을 찾을 수 없어요.
          </div>
        )}
      >
        {(notice) => (
          <>
            <Link
              to="/notice"
              className="btn btn-plain btn-sm"
              style={{
                marginBottom: 12,
              }}
            >
              ← 목록으로
            </Link>

            <article className="card card-pad">
              <span
                className={
                  `badge ${
                    CATEGORY_BADGE[
                      notice.notice_category
                    ] ?? 'badge-gray'
                  }`
                }
              >
                {notice.notice_category}
              </span>

              <h1
                className="section-title"
                style={{
                  margin: '12px 0 8px',
                  wordBreak: 'keep-all',
                }}
              >
                {notice.notice_title}
              </h1>

              <div
                className="row muted"
                style={{
                  gap: 16,
                  fontSize: 13.5,
                  borderBottom:
                    '1px solid var(--line)',
                  paddingBottom: 14,
                  flexWrap: 'wrap',
                }}
              >
                <span>
                  작성일{' '}
                  {formatDate(
                    notice.created_at,
                  )}
                </span>

                <span>
                  조회수 {notice.view_cnt ?? 0}
                </span>
              </div>

              <div
                style={{
                  marginTop: 18,
                  color: 'var(--ink-soft)',
                  lineHeight: 1.8,
                  whiteSpace: 'pre-wrap',
                  overflowWrap: 'break-word',
                }}
              >
                {notice.notice_content}
              </div>
            </article>
          </>
        )}
      </Async>
    </div>
  )
}