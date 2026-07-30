import {
  useState,
} from 'react'

import {
  useNavigate,
  useParams,
} from 'react-router-dom'

import {
  createAdminNotice,
  getAdminNotice,
  updateAdminNotice,
  updateAdminNoticeStatus,
} from '../../api/content.js'

import {
  Async,
  PageHead,
  useAsync,
  useToast,
} from '../../components/ui/index.jsx'


const CATEGORIES = [
  '공지사항',
  '업데이트',
  '이벤트',
]


// =========================================================
// 관리자 공지사항 등록·수정 페이지
// =========================================================
export default function AdminNoticeEdit() {
  const {
    id,
  } = useParams()

  const isEdit = Boolean(id)

  const navigate = useNavigate()
  const toast = useToast()


  // 수정일 때만 기존 공지 상세 조회
  const state = useAsync(
    () => (
      isEdit
        ? getAdminNotice(id)
        : Promise.resolve(null)
    ),
    [
      id,
      isEdit,
    ],
  )


  // 등록·수정 완료
  const handleDone = () => {
    toast.show(
      isEdit
        ? '공지사항이 수정되었어요.'
        : '공지사항이 등록되었어요.',
    )

    // 현재 Toast가 페이지 내부에 있으므로
    // 메시지를 잠시 보여준 뒤 목록으로 이동
    window.setTimeout(() => {
      navigate('/admin/notices')
    }, 700)
  }


  return (
    <div>
      <PageHead
        title={
          isEdit
            ? '공지사항 수정'
            : '공지사항 등록'
        }
        sub="공지·업데이트·이벤트를 작성해요."
        right={(
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              navigate('/admin/notices')
            }}
          >
            ← 목록
          </button>
        )}
      />

      <Async state={state}>
        {(notice) => (
          <NoticeForm
            noticeId={id}
            initial={notice}
            isEdit={isEdit}
            onDone={handleDone}
          />
        )}
      </Async>

      {toast.node}
    </div>
  )
}


// =========================================================
// 공지사항 입력 Form
// =========================================================
function NoticeForm({
  noticeId,
  initial,
  isEdit,
  onDone,
}) {
  const [
    form,
    setForm,
  ] = useState({
    notice_category:
      initial?.notice_category
      ?? '공지사항',

    notice_title:
      initial?.notice_title
      ?? '',

    notice_content:
      initial?.notice_content
      ?? '',

    notice_status:
      initial?.notice_status
      ?? true,
  })

  const [
    errors,
    setErrors,
  ] = useState({})

  const [
    submitError,
    setSubmitError,
  ] = useState('')

  const [
    submitting,
    setSubmitting,
  ] = useState(false)


  // =========================================================
  // 입력값 변경
  // =========================================================
  const changeField = (
    field,
  ) => (
    event,
  ) => {
    const value = event.target.value

    setForm((prev) => ({
      ...prev,
      [field]: value,
    }))

    setErrors((prev) => ({
      ...prev,
      [field]: '',
    }))

    setSubmitError('')
  }


  // =========================================================
  // 입력값 검증
  // =========================================================
  const validate = () => {
    const nextErrors = {}

    if (!form.notice_title.trim()) {
      nextErrors.notice_title =
        '제목을 입력해 주세요.'
    }

    if (
      form.notice_title.trim().length > 100
    ) {
      nextErrors.notice_title =
        '제목은 100자 이하로 입력해 주세요.'
    }

    if (!form.notice_content.trim()) {
      nextErrors.notice_content =
        '내용을 입력해 주세요.'
    }

    setErrors(nextErrors)

    return (
      Object.keys(nextErrors).length === 0
    )
  }


  // =========================================================
  // 등록·수정 요청
  // =========================================================
  const submit = async (
    event,
  ) => {
    event.preventDefault()

    if (!validate()) {
      return
    }

    const payload = {
      notice_category:
        form.notice_category,

      notice_title:
        form.notice_title.trim(),

      notice_content:
        form.notice_content.trim(),
    }

    setSubmitting(true)
    setSubmitError('')

    try {
      if (isEdit) {
        // 제목·내용·카테고리 수정
        const updatedNotice =
          await updateAdminNotice(
            noticeId,
            payload,
          )

        // 활성·비활성 상태가 달라졌을 때만 별도 API 호출
        if (
          updatedNotice.notice_status
          !== form.notice_status
        ) {
          await updateAdminNoticeStatus(
            noticeId,
            form.notice_status,
          )
        }

      } else {
        // 새 공지 등록
        const createdNotice =
          await createAdminNotice(
            payload,
          )

        // 백엔드는 새 공지를 기본 활성 상태로 생성한다.
        // 등록 화면에서 비활성을 선택했다면 생성 후 상태 변경
        if (
          createdNotice.notice_status
          !== form.notice_status
        ) {
          await updateAdminNoticeStatus(
            createdNotice.notice_id,
            form.notice_status,
          )
        }
      }

      onDone()

    } catch (error) {
      setSubmitError(
        error.message
        || (
          isEdit
            ? '공지사항 수정에 실패했어요.'
            : '공지사항 등록에 실패했어요.'
        ),
      )

    } finally {
      setSubmitting(false)
    }
  }


  return (
    <form
      className="card card-pad"
      style={{
        maxWidth: 680,
      }}
      onSubmit={submit}
    >
      {/* 공지 유형 */}
      <div className="field">
        <label htmlFor="notice-category">
          유형
          <span className="req">
            *
          </span>
        </label>

        <select
          id="notice-category"
          className="select"
          value={form.notice_category}
          disabled={submitting}
          onChange={
            changeField(
              'notice_category',
            )
          }
        >
          {CATEGORIES.map((category) => (
            <option
              key={category}
              value={category}
            >
              {category}
            </option>
          ))}
        </select>
      </div>


      {/* 공지 제목 */}
      <div className="field">
        <label htmlFor="notice-title">
          제목
          <span className="req">
            *
          </span>
        </label>

        <input
          id="notice-title"
          className={
            `input ${
              errors.notice_title
                ? 'error'
                : ''
            }`
          }
          value={form.notice_title}
          maxLength={100}
          disabled={submitting}
          placeholder="제목을 입력하세요"
          onChange={
            changeField(
              'notice_title',
            )
          }
        />

        <div
          className="row"
          style={{
            justifyContent:
              'space-between',
            marginTop: 4,
          }}
        >
          <span>
            {errors.notice_title && (
              <span className="err">
                {errors.notice_title}
              </span>
            )}
          </span>

          <span
            className="muted"
            style={{
              fontSize: 12.5,
            }}
          >
            {form.notice_title.length}/100
          </span>
        </div>
      </div>


      {/* 공지 내용 */}
      <div className="field">
        <label htmlFor="notice-content">
          내용
          <span className="req">
            *
          </span>
        </label>

        <textarea
          id="notice-content"
          className={
            `textarea ${
              errors.notice_content
                ? 'error'
                : ''
            }`
          }
          value={form.notice_content}
          disabled={submitting}
          placeholder="내용을 입력하세요"
          style={{
            minHeight: 220,
            resize: 'vertical',
          }}
          onChange={
            changeField(
              'notice_content',
            )
          }
        />

        {errors.notice_content && (
          <span className="err">
            {errors.notice_content}
          </span>
        )}
      </div>


      {/* 게시 상태 */}
      <div className="field">
        <label>
          게시 상태
        </label>

        <div
          className="row"
          style={{
            gap: 8,
          }}
        >
          <button
            type="button"
            className={
              `chip ${
                form.notice_status
                  ? 'on'
                  : ''
              }`
            }
            disabled={submitting}
            onClick={() => {
              setForm((prev) => ({
                ...prev,
                notice_status: true,
              }))

              setSubmitError('')
            }}
          >
            활성
          </button>

          <button
            type="button"
            className={
              `chip ${
                !form.notice_status
                  ? 'on'
                  : ''
              }`
            }
            disabled={submitting}
            onClick={() => {
              setForm((prev) => ({
                ...prev,
                notice_status: false,
              }))

              setSubmitError('')
            }}
          >
            비활성
          </button>
        </div>

        <p
          className="muted"
          style={{
            marginTop: 8,
            fontSize: 13,
          }}
        >
          비활성 공지는 관리자 목록에는 표시되지만,
          사용자 공지사항에는 표시되지 않아요.
        </p>
      </div>


      {/* API 오류 */}
      {submitError && (
        <div
          className="err"
          style={{
            marginTop: 8,
          }}
        >
          {submitError}
        </div>
      )}


      {/* 등록·수정 버튼 */}
      <button
        type="submit"
        className="btn btn-primary btn-lg"
        style={{
          marginTop: 12,
        }}
        disabled={submitting}
      >
        {submitting
          ? (
            isEdit
              ? '수정 중...'
              : '등록 중...'
          )
          : (
            isEdit
              ? '수정 완료'
              : '등록'
          )}
      </button>
    </form>
  )
}