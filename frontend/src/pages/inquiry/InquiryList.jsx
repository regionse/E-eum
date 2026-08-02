import { useState } from 'react'
import { Link } from 'react-router-dom'

import {
  getInquiry,
  listInquiries,
} from '../../api/content.js'

import {
  useAsync,
  Async,
  Modal,
  PageHead,
} from '../../components/ui/index.jsx'


const statusBadge = {
  접수: 'badge-gray',
  '처리 중': 'badge-amber',
  답변완료: 'badge-teal',
}


export default function InquiryList() {
  const state = useAsync(
    () => listInquiries(),
    [],
  )

  const [open, setOpen] = useState(null)
  const [detailLoading, setDetailLoading] =
    useState(false)


  const openDetail = async (
    inquiryId,
  ) => {
    if (detailLoading) {
      return
    }

    setDetailLoading(true)

    try {
      const inquiry = await getInquiry(
        inquiryId,
      )

      setOpen(inquiry)
    } catch (error) {
      window.alert(
        error.message
        || '문의 내용을 불러오지 못했습니다.',
      )
    } finally {
      setDetailLoading(false)
    }
  }


  return (
    <div
      className="container page"
      style={{
        maxWidth: 820,
      }}
    >
      <PageHead
        title="문의 내역"
        sub="문의하신 내용과 답변을 확인하세요."
        right={
          <Link
            to="/inquiry"
            className="btn btn-primary btn-sm"
          >
            새 문의
          </Link>
        }
      />

      <div
        className="card"
        style={{
          overflowX: 'auto',
        }}
      >
        <Async state={state}>
          {(response) => {
            const inquiries =
              response?.items ?? []

            return (
              <table className="tbl">
                <thead>
                  <tr>
                    <th>번호</th>
                    <th>제목</th>
                    <th>유형</th>
                    <th>문의일</th>
                    <th>처리상태</th>
                  </tr>
                </thead>

                <tbody>
                  {inquiries.length === 0 ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="muted"
                        style={{
                          textAlign: 'center',
                          padding: 32,
                        }}
                      >
                        등록된 문의가 없습니다.
                      </td>
                    </tr>
                  ) : (
                    inquiries.map(
                      (inquiry) => (
                        <tr
                          key={
                            inquiry.inquiry_id
                          }
                          style={{
                            cursor: detailLoading
                              ? 'wait'
                              : 'pointer',
                          }}
                          onClick={() =>
                            openDetail(
                              inquiry.inquiry_id,
                            )
                          }
                        >
                          <td className="muted">
                            {
                              inquiry.inquiry_id
                            }
                          </td>

                          <td
                            style={{
                              fontWeight: 600,
                            }}
                          >
                            {
                              inquiry
                                .inquiry_title
                            }
                          </td>

                          <td className="muted">
                            {
                              inquiry
                                .inquiry_type
                            }
                          </td>

                          <td className="muted">
                            {
                              inquiry
                                .inquiry_created_at
                                ?.slice(0, 10)
                            }
                          </td>

                          <td>
                            <span
                              className={
                                `badge ${
                                  statusBadge[
                                    inquiry
                                      .inquiry_status
                                  ]
                                  || 'badge-gray'
                                }`
                              }
                            >
                              {
                                inquiry
                                  .inquiry_status
                              }
                            </span>
                          </td>
                        </tr>
                      ),
                    )
                  )}
                </tbody>
              </table>
            )
          }}
        </Async>
      </div>

      {open && (
        <Modal
          title={open.inquiry_title}
          onClose={() =>
            setOpen(null)
          }
          actions={
            <button
              type="button"
              className="btn btn-primary btn-block"
              onClick={() =>
                setOpen(null)
              }
            >
              닫기
            </button>
          }
        >
          <div
            className="row"
            style={{
              gap: 8,
              marginBottom: 12,
            }}
          >
            <span className="badge badge-gray">
              {open.inquiry_type}
            </span>

            <span
              className={
                `badge ${
                  statusBadge[
                    open.inquiry_status
                  ]
                  || 'badge-gray'
                }`
              }
            >
              {open.inquiry_status}
            </span>
          </div>

          <div
            style={{
              background: 'var(--bg)',
              borderRadius: 10,
              padding: 14,
              fontSize: 14.5,
              color: 'var(--ink-soft)',
              whiteSpace: 'pre-wrap',
            }}
          >
            {open.inquiry_content}
          </div>

          {open.inquiry_answer_content ? (
            <div
              style={{
                background:
                  'var(--teal-50)',
                border:
                  '1px solid var(--teal-100)',
                borderRadius: 10,
                padding: 14,
                marginTop: 10,
                fontSize: 14.5,
                whiteSpace: 'pre-wrap',
              }}
            >
              <div
                style={{
                  fontWeight: 700,
                  color:
                    'var(--teal-700)',
                  marginBottom: 4,
                }}
              >
                답변
              </div>

              {
                open
                  .inquiry_answer_content
              }
            </div>
          ) : (
            <p
              className="muted"
              style={{
                marginTop: 10,
                fontSize: 14,
              }}
            >
              아직 답변이 등록되지 않았어요.
            </p>
          )}
        </Modal>
      )}
    </div>
  )
}