import { useState } from 'react'
import {
  useNavigate,
  useParams,
} from 'react-router-dom'

import {
  createAdminInquiryAnswer,
  getAdminInquiry,
  updateAdminInquiryAnswer,
} from '../../api/content.js'

import {
  useAsync,
  Async,
  PageHead,
  useToast,
} from '../../components/ui/index.jsx'


const statusBadge = {
  접수: 'badge-gray',
  '처리 중': 'badge-amber',
  답변완료: 'badge-teal',
}


// ADQNA-002 · 문의 상세
export default function AdminInquiryDetail() {
  const {
    id,
  } = useParams()

  const nav = useNavigate()
  const toast = useToast()

  const state = useAsync(
    () => getAdminInquiry(id),
    [id],
  )


  const goToList = () => {
    nav('/admin/inquiries')
  }


  const handleSaved = (
    message,
  ) => {
    toast.show(message)
    goToList()
  }


  const handleError = (
    error,
  ) => {
    toast.show(
      error.message
      || '답변 처리에 실패했습니다.',
    )
  }


  return (
    <div>
      <PageHead
        title="문의 상세"
        sub="문의 내용을 확인하고 답변을 등록해요."
        right={
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={goToList}
          >
            ← 목록으로
          </button>
        }
      />

      <Async state={state}>
        {(inquiry) =>
          inquiry ? (
            <Detail
              inquiry={inquiry}
              onList={goToList}
              onSaved={handleSaved}
              onError={handleError}
            />
          ) : (
            <div className="card card-pad muted center">
              문의를 찾을 수 없어요.
            </div>
          )
        }
      </Async>

      {toast.node}
    </div>
  )
}


function Detail({
  inquiry,
  onList,
  onSaved,
  onError,
}) {
  const done =
    inquiry.inquiry_status ===
    '답변완료'

  const [editing, setEditing] =
    useState(!done)

  const [answer, setAnswer] = useState(
    inquiry.inquiry_answer_content || '',
  )

  const [busy, setBusy] =
    useState(false)


  const submit = async () => {
    const cleanedAnswer =
      answer.trim()

    if (!cleanedAnswer || busy) {
      return
    }

    setBusy(true)

    try {
      if (done) {
        await updateAdminInquiryAnswer(
          inquiry.inquiry_id,
          cleanedAnswer,
        )

        onSaved(
          '답변이 수정되었어요.',
        )
      } else {
        await createAdminInquiryAnswer(
          inquiry.inquiry_id,
          cleanedAnswer,
        )

        onSaved(
          '답변이 등록되었어요.',
        )
      }
    } catch (error) {
      onError(error)
    } finally {
      setBusy(false)
    }
  }


  return (
    <div
      className="card card-pad"
      style={{
        maxWidth: 720,
      }}
    >
      <div
        className="row"
        style={{
          gap: 8,
          marginBottom: 10,
          flexWrap: 'wrap',
        }}
      >
        <span className="badge badge-gray">
          {inquiry.inquiry_type}
        </span>

        <span
          className={
            `badge ${
              statusBadge[
                inquiry.inquiry_status
              ] || 'badge-gray'
            }`
          }
        >
          {inquiry.inquiry_status}
        </span>

        <span
          className="muted"
          style={{
            fontSize: 13,
            marginLeft: 'auto',
          }}
        >
          문의번호 {inquiry.inquiry_id}
          {' · '}
          {inquiry.inquiry_created_at
            ?.slice(0, 10)}
        </span>
      </div>

      <h3
        style={{
          margin: '2px 0 12px',
          fontSize: 18,
        }}
      >
        {inquiry.inquiry_title}
      </h3>

      <div
        style={{
          background: 'var(--bg)',
          borderRadius: 10,
          padding: 14,
          fontSize: 14.5,
          color: 'var(--ink-soft)',
          marginBottom: 18,
          whiteSpace: 'pre-wrap',
        }}
      >
        {inquiry.inquiry_content}
      </div>

      <div className="field">
        <label>
          관리자 답변

          {!done && (
            <span className="req">*</span>
          )}
        </label>

        {editing ? (
          <textarea
            className="textarea"
            value={answer}
            onChange={(event) => {
              setAnswer(
                event.target.value,
              )
            }}
            placeholder="답변을 입력하세요"
            style={{
              minHeight: 140,
            }}
          />
        ) : (
          <div
            style={{
              border:
                '1px solid var(--line)',
              borderRadius: 10,
              padding: 14,
              fontSize: 14.5,
              color: 'var(--ink)',
              minHeight: 60,
              whiteSpace: 'pre-wrap',
            }}
          >
            {
              inquiry
                .inquiry_answer_content
              || (
                <span className="muted">
                  등록된 답변이 없어요.
                </span>
              )
            }
          </div>
        )}
      </div>

      <div
        className="row"
        style={{
          gap: 8,
          marginTop: 8,
        }}
      >
        {done && !editing ? (
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setEditing(true)
              }}
            >
              수정
            </button>

            <button
              type="button"
              className="btn btn-ghost"
              onClick={onList}
            >
              목록으로
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={submit}
              disabled={
                !answer.trim()
                || busy
              }
            >
              {busy
                ? '저장 중…'
                : done
                  ? '수정 완료'
                  : '답변 등록'}
            </button>

            <button
              type="button"
              className="btn btn-ghost"
              onClick={onList}
              disabled={busy}
            >
              목록으로
            </button>
          </>
        )}
      </div>
    </div>
  )
}