import { useState } from 'react'
import {
  Link,
  useNavigate,
} from 'react-router-dom'

import {
  submitInquiry,
} from '../../api/content.js'

import {
  Modal,
  PageHead,
  useToast,
} from '../../components/ui/index.jsx'

import {
  useAuth,
} from '../../store/auth.jsx'


const TYPES = [
  '계정',
  '덜다',
  '잇다',
  '나누다',
  '기타',
]


export default function Inquiry() {
  const {
    user,
  } = useAuth()

  const navigate = useNavigate()
  const toast = useToast()

  const [form, setForm] = useState({
    inquiry_type: '계정',
    inquiry_title: '',
    inquiry_content: '',
  })

  const [errors, setErrors] = useState({})
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)


  const handleChange = (
    field,
  ) => (
    event,
  ) => {
    setForm((current) => ({
      ...current,
      [field]: event.target.value,
    }))

    setErrors((current) => ({
      ...current,
      [field]: '',
    }))
  }


  const validate = () => {
    const nextErrors = {}

    if (!form.inquiry_title.trim()) {
      nextErrors.inquiry_title =
        '문의 제목을 입력해주세요.'
    }

    if (!form.inquiry_content.trim()) {
      nextErrors.inquiry_content =
        '문의 내용을 입력해주세요.'
    }

    setErrors(nextErrors)

    return (
      Object.keys(nextErrors).length === 0
    )
  }


  const submit = async () => {
    if (!validate() || busy) {
      return
    }

    setBusy(true)

    try {
      await submitInquiry({
        inquiry_type:
          form.inquiry_type,

        inquiry_title:
          form.inquiry_title.trim(),

        inquiry_content:
          form.inquiry_content.trim(),
      })

      setDone(true)
    } catch (error) {
      toast.error?.(
        error.message
        || '문의 등록에 실패했습니다.',
      )
    } finally {
      setBusy(false)
    }
  }


  if (!user) {
    return (
      <div
        className="container page"
        style={{
          maxWidth: 640,
        }}
      >
        <PageHead
          title="문의하기"
          sub="문의 등록은 로그인 후 이용할 수 있어요."
        />

        <div className="card card-pad">
          <p
            className="muted"
            style={{
              marginTop: 0,
            }}
          >
            로그인한 사용자의 정보로 문의가
            등록됩니다.
          </p>

          <Link
            to="/login"
            className="btn btn-primary btn-block"
          >
            로그인하기
          </Link>
        </div>
      </div>
    )
  }


  return (
    <div
      className="container page"
      style={{
        maxWidth: 640,
      }}
    >
      <PageHead
        title="문의하기"
        sub={`${
          user.nickname
          || user.username
          || '회원'
        } 님으로 문의를 남겨요.`}
        right={
          <Link
            to="/inquiry/list"
            className="btn btn-ghost btn-sm"
          >
            문의 내역
          </Link>
        }
      />

      <div className="card card-pad">
        <div className="field">
          <label>
            문의 유형
            <span className="req">*</span>
          </label>

          <select
            className="select"
            value={form.inquiry_type}
            onChange={handleChange(
              'inquiry_type',
            )}
          >
            {TYPES.map((type) => (
              <option
                key={type}
                value={type}
              >
                {type}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>
            문의 제목
            <span className="req">*</span>
          </label>

          <input
            className={
              `input ${
                errors.inquiry_title
                ? 'error'
                : ''
              }`
            }
            placeholder="제목을 입력하세요"
            value={form.inquiry_title}
            onChange={handleChange(
              'inquiry_title',
            )}
            maxLength={100}
          />

          {errors.inquiry_title && (
            <span className="err">
              {errors.inquiry_title}
            </span>
          )}
        </div>

        <div className="field">
          <label>
            문의 내용
            <span className="req">*</span>
          </label>

          <textarea
            className={
              `textarea ${
                errors.inquiry_content
                ? 'error'
                : ''
              }`
            }
            placeholder="문의 내용을 입력하세요"
            value={form.inquiry_content}
            onChange={handleChange(
              'inquiry_content',
            )}
          />

          {errors.inquiry_content && (
            <span className="err">
              {errors.inquiry_content}
            </span>
          )}
        </div>

        <button
          type="button"
          className="btn btn-primary btn-block btn-lg"
          onClick={submit}
          disabled={busy}
        >
          {busy
            ? '보내는 중…'
            : '문의 보내기'}
        </button>
      </div>

      {done && (
        <Modal
          title="문의가 등록되었습니다"
          actions={
            <>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() =>
                  navigate('/inquiry/list')
                }
              >
                문의 내역
              </button>

              <button
                type="button"
                className="btn btn-primary"
                onClick={() =>
                  navigate('/')
                }
              >
                확인
              </button>
            </>
          }
        >
          <p>
            관리자 답변은 문의 내역에서
            확인할 수 있어요.
          </p>
        </Modal>
      )}

      {toast.node}
    </div>
  )
}