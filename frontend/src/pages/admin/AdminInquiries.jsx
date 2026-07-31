import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  listAdminInquiries,
} from '../../api/content.js'

import {
  useAsync,
  Async,
  PageHead,
} from '../../components/ui/index.jsx'


const statusBadge = {
  접수: 'badge-gray',
  '처리 중': 'badge-amber',
  답변완료: 'badge-teal',
}

const TYPES = [
  '전체',
  '계정',
  '덜다',
  '잇다',
  '나누다',
  '기타',
]

const STATUSES = [
  '전체',
  '접수',
  '처리 중',
  '답변완료',
]

const PER = 10


export default function AdminInquiries() {
  const nav = useNavigate()

  const [cat, setCat] = useState('전체')
  const [statusF, setStatusF] = useState('전체')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)

  const state = useAsync(
    () => listAdminInquiries({
      page,
      size: PER,

      inquiry_type:
        cat === '전체'
          ? ''
          : cat,

      inquiry_status:
        statusF === '전체'
          ? ''
          : statusF,

      keyword: query,
    }),
    [
      page,
      cat,
      statusF,
      query,
    ],
  )

  const rows =
    state.data?.items ?? []

  const total =
    state.data?.total ?? 0

  const totalPages =
    state.data?.total_pages ?? 0

  const currentPage = Math.min(
    page,
    Math.max(1, totalPages),
  )


  const runSearch = () => {
    setQuery(q.trim())
    setPage(1)
  }


  return (
    <div>
      <PageHead
        title="문의 관리"
        sub="사용자 문의를 확인하고 답변을 등록해요."
      />

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
          value={cat}
          onChange={(event) => {
            setCat(event.target.value)
            setPage(1)
          }}
        >
          {TYPES.map((type) => (
            <option
              key={type}
              value={type}
            >
              유형 · {type}
            </option>
          ))}
        </select>

        <select
          className="select"
          style={{
            width: 'auto',
          }}
          value={statusF}
          onChange={(event) => {
            setStatusF(event.target.value)
            setPage(1)
          }}
        >
          {STATUSES.map((status) => (
            <option
              key={status}
              value={status}
            >
              상태 · {status}
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
          value={q}
          onChange={(event) => {
            setQ(event.target.value)
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

      <div
        className="card"
        style={{
          overflowX: 'auto',
        }}
      >
        <Async state={state}>
          {() => (
            <table className="tbl">
              <thead>
                <tr>
                  <th
                    style={{
                      width: 60,
                    }}
                  >
                    번호
                  </th>

                  <th>제목</th>

                  <th
                    style={{
                      width: 110,
                    }}
                  >
                    유형
                  </th>

                  <th
                    style={{
                      width: 112,
                    }}
                  >
                    문의일
                  </th>

                  <th
                    style={{
                      width: 104,
                    }}
                  >
                    상태
                  </th>
                </tr>
              </thead>

              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="muted center"
                      style={{
                        padding: 20,
                      }}
                    >
                      조건에 맞는 문의가 없어요.
                    </td>
                  </tr>
                ) : (
                  rows.map((inquiry) => (
                    <tr
                      key={inquiry.inquiry_id}
                      style={{
                        cursor: 'pointer',
                      }}
                      onClick={() => {
                        nav(
                          `/admin/inquiries/${inquiry.inquiry_id}`,
                        )
                      }}
                    >
                      <td className="muted">
                        {inquiry.inquiry_id}
                      </td>

                      <td
                        style={{
                          fontWeight: 600,
                          textDecoration: 'underline',
                          textDecorationColor:
                            'var(--teal-200)',
                        }}
                      >
                        {inquiry.inquiry_title}
                      </td>

                      <td
                        className="muted"
                        style={{
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {inquiry.inquiry_type}
                      </td>

                      <td className="muted">
                        {inquiry.inquiry_created_at
                          ?.slice(0, 10)}
                      </td>

                      <td>
                        <span
                          className={
                            `badge ${
                              statusBadge[
                                inquiry.inquiry_status
                              ] || 'badge-gray'
                            }`
                          }
                          style={{
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {inquiry.inquiry_status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </Async>
      </div>

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
          총 {total}건
        </span>

        {totalPages > 1 && (
          <div
            className="pager"
            style={{
              margin: 0,
            }}
          >
            <button
              type="button"
              onClick={() => {
                setPage(
                  Math.max(
                    1,
                    currentPage - 1,
                  ),
                )
              }}
              disabled={currentPage === 1}
            >
              ‹
            </button>

            {Array.from(
              {
                length: totalPages,
              },
              (_, index) => index + 1,
            ).map((pageNumber) => (
              <button
                type="button"
                key={pageNumber}
                className={
                  pageNumber === currentPage
                    ? 'on'
                    : ''
                }
                onClick={() => {
                  setPage(pageNumber)
                }}
              >
                {pageNumber}
              </button>
            ))}

            <button
              type="button"
              onClick={() => {
                setPage(
                  Math.min(
                    totalPages,
                    currentPage + 1,
                  ),
                )
              }}
              disabled={
                currentPage === totalPages
              }
            >
              ›
            </button>
          </div>
        )}
      </div>
    </div>
  )
}