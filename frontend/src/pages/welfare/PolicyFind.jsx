import {
  useEffect,
  useRef,
  useState,
} from 'react'
import {
  Link,
  useLocation,
  useNavigate,
} from 'react-router-dom'

import {
  recommendPolicies,
  searchPolicyByName,
} from '../../api/welfare.js'
import RequireLogin from '../../components/RequireLogin.jsx'
import { PageHead } from '../../components/ui/index.jsx'
import { useAuth } from '../../store/auth.jsx'

const CURRENT_LIFE_STATUS_OPTIONS = [
  ['student', '학생'],
  ['job_seeker', '구직 중'],
  ['employee', '직장인'],
  ['self_employed', '자영업·프리랜서'],
  ['care_focused', '가족 돌봄에 집중 중'],
  ['resting', '쉬고 있음'],
  ['other', '기타'],
]

const CARE_RECIPIENT_OPTIONS = [
  ['parent', '부모님'],
  ['grandparent', '조부모님'],
  ['sibling', '형제·자매'],
  ['spouse', '배우자'],
  ['child', '자녀'],
  ['other_family', '기타 가족'],
]

const CARE_DURATION_OPTIONS = [
  ['under_6_months', '6개월 미만'],
  ['6_to_12_months', '6개월~1년'],
  ['1_to_3_years', '1~3년'],
  ['3_to_5_years', '3~5년'],
  ['5_years_or_more', '5년 이상'],
  ['unknown', '잘 모르겠어요'],
]

const DAILY_CARE_TIME_OPTIONS = [
  ['under_2_hours', '2시간 미만'],
  ['2_to_4_hours', '2~4시간'],
  ['4_to_8_hours', '4~8시간'],
  ['8_hours_or_more', '8시간 이상'],
  ['varies', '날마다 달라요'],
]

const FINANCIAL_BURDEN_OPTIONS = [
  ['very_high', '매우 부담돼요'],
  ['high', '부담되는 편이에요'],
  ['normal', '보통이에요'],
  ['low', '부담이 적어요'],
  ['unknown', '잘 모르겠어요'],
]

const NEEDED_SUPPORT_OPTIONS = [
  ['living_expense', '생활비'],
  ['housing', '주거'],
  ['medical', '의료비'],
  ['care_service', '돌봄 서비스'],
  ['mental_health', '심리·정신건강'],
  ['employment', '취업'],
  ['education', '교육'],
  ['legal_admin', '법률·행정'],
  ['unknown', '잘 모르겠어요'],
]

const CARE_ACTIVITY_OPTIONS = [
  ['housework', '식사·청소 등 가사'],
  ['hospital_accompaniment', '병원 동행'],
  ['medication_health', '복약·건강 관리'],
  ['mobility_hygiene', '이동·위생 도움'],
  ['emotional_support', '정서적 지원'],
  ['financial_support', '생활비 부담'],
  ['other', '기타 도움'],
  ['hard_to_classify', '구분하기 어려워요'],
]

const LOADING_STEPS = [
  {
    title: '상황 분석 중',
    description: '입력하신 생활 상태와 돌봄 상황을 이해하고 있어요.',
  },
  {
    title: '정책 검색 중',
    description: '회원님의 조건과 관련된 지원 정책을 찾고 있어요.',
  },
  {
    title: '적합도 판단 중',
    description: '정책별 자격조건과 지원 내용을 비교하고 있어요.',
  },
]

const EMPTY_FORM = {
  current_life_status: '',
  care_recipient: '',
  care_duration: '',
  daily_care_time: '',
  financial_burden: '',
  needed_support_types: [],
  care_activities: [],
  additional_context: '',
}

function validateForm(form) {
  const errors = {}

  if (!form.current_life_status) {
    errors.current_life_status =
      '현재 주된 생활 상태를 선택해 주세요.'
  }

  if (!form.care_recipient) {
    errors.care_recipient =
      '주로 돌보는 가족을 선택해 주세요.'
  }

  if (!form.care_duration) {
    errors.care_duration =
      '가족을 돌본 기간을 선택해 주세요.'
  }

  if (!form.daily_care_time) {
    errors.daily_care_time =
      '하루 평균 돌봄 시간을 선택해 주세요.'
  }

  if (!form.financial_burden) {
    errors.financial_burden =
      '경제적 부담 정도를 선택해 주세요.'
  }

  if (
    !Array.isArray(form.needed_support_types)
    || form.needed_support_types.length === 0
  ) {
    errors.needed_support_types =
      '현재 필요한 지원을 한 가지 이상 선택해 주세요.'
  }

  return errors
}

function toggleMulti(values, value, exclusiveValue) {
  if (value === exclusiveValue) {
    return values.includes(value) ? [] : [value]
  }

  const nextValues = values.filter(
    (item) => item !== exclusiveValue,
  )

  return nextValues.includes(value)
    ? nextValues.filter((item) => item !== value)
    : [...nextValues, value]
}

export default function PolicyFind() {
  const navigate = useNavigate()
  const { state: routeState } = useLocation()
  const { user } = useAuth()

  const [form, setForm] = useState(() => {
    const previousRequest = routeState?.request || {}

    return {
      ...EMPTY_FORM,
      ...previousRequest,
      needed_support_types:
        previousRequest.needed_support_types || [],
      care_activities:
        previousRequest.care_activities || [],
      additional_context:
        previousRequest.additional_context || '',
    }
  })

  const [searchMode, setSearchMode] = useState(
    routeState?.searchMode === 'lookup'
      ? 'lookup'
      : 'recommend',
  )
  const [policyName, setPolicyName] = useState(
    routeState?.policyName || '',
  )

  const [mode, setMode] = useState('form')
  const [loading, setLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [error, setError] = useState('')
  const [validationErrors, setValidationErrors] =
    useState({})
  const [followUpResponse, setFollowUpResponse] =
    useState(null)
  const [followUpAnswers, setFollowUpAnswers] =
    useState([])

  const abortControllerRef = useRef(null)

  useEffect(() => {
    if (!loading) {
      setLoadingStep(0)
      return undefined
    }

    const timerId = window.setInterval(() => {
      setLoadingStep((previousStep) => (
        (previousStep + 1) % LOADING_STEPS.length
      ))
    }, 1600)

    return () => {
      window.clearInterval(timerId)
    }
  }, [loading])

  useEffect(() => (
    () => {
      abortControllerRef.current?.abort()
    }
  ), [])

  const updateField = (name, value) => {
    setForm((previousForm) => ({
      ...previousForm,
      [name]: value,
    }))

    setValidationErrors((previousErrors) => {
      if (!previousErrors[name]) {
        return previousErrors
      }

      const nextErrors = { ...previousErrors }
      delete nextErrors[name]
      return nextErrors
    })

    setError('')
  }

  const runRecommendation = async (
    answers = followUpAnswers,
  ) => {
    abortControllerRef.current?.abort()

    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    setError('')

    const requestBody = {
      ...form,
      additional_context:
        form.additional_context.trim() || null,
      follow_up_answers: answers,
    }

    try {
      const response = await recommendPolicies(
        requestBody,
        {
          signal: controller.signal,
        },
      )

      if (controller.signal.aborted) {
        return
      }

      if (response.status === 'need_more_information') {
        setFollowUpResponse(response)
        setMode('chat')
        return
      }

      if (response.status === 'invalid_input') {
        const retryExample = response.retry_example
          ? `\n예: ${response.retry_example}`
          : ''

        setError(`${response.message}${retryExample}`)

        if (response.input_stage === 'follow_up_chat') {
          setMode('chat')
        } else {
          setMode('form')
        }

        return
      }

      navigate('/welfare/policy/result', {
        state: {
          response,
          request: requestBody,
        },
      })
    } catch (requestError) {
      if (requestError?.name === 'AbortError') {
        return
      }

      setError(
        requestError instanceof Error
          ? requestError.message
          : '정책 추천 요청 중 오류가 발생했습니다.',
      )
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null
        setLoading(false)
      }
    }
  }

  const handlePolicyLookup = async (
    event,
  ) => {
    event.preventDefault()

    const cleanedPolicyName =
      policyName.trim()

    if (!cleanedPolicyName) {
      setError(
        '찾고 싶은 정책명을 입력해 주세요.',
      )
      return
    }

    abortControllerRef.current?.abort()

    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    setError('')

    try {
      const response = await searchPolicyByName(
        cleanedPolicyName,
        {
          signal: controller.signal,
        },
      )

      if (controller.signal.aborted) {
        return
      }

      navigate(
        '/welfare/policy/result',
        {
          state: {
            response,
            request: null,
            searchMode: 'lookup',
            policyName: cleanedPolicyName,
          },
        },
      )
    } catch (requestError) {
      if (requestError?.name === 'AbortError') {
        return
      }

      setError(
        requestError instanceof Error
          ? requestError.message
          : '정책 검색 중 오류가 발생했습니다.',
      )
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null
        setLoading(false)
      }
    }
  }

  const changeSearchMode = (
    nextMode,
  ) => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null

    setSearchMode(nextMode)
    setLoading(false)
    setMode('form')
    setError('')
    setValidationErrors({})
    setFollowUpAnswers([])
    setFollowUpResponse(null)
  }

  const handleSubmit = (event) => {
    event.preventDefault()

    const nextErrors = validateForm(form)

    if (Object.keys(nextErrors).length > 0) {
      setValidationErrors(nextErrors)
      setError('선택하지 않은 필수 항목을 확인해 주세요.')

      window.requestAnimationFrame(() => {
        document
          .querySelector('[data-invalid="true"]')
          ?.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
          })
      })

      return
    }

    setValidationErrors({})
    setFollowUpAnswers([])
    setFollowUpResponse(null)
    void runRecommendation([])
  }

  const handleFollowUpAnswer = (answer) => {
    const question = followUpResponse?.follow_up_question

    if (!question) {
      return
    }

    const nextAnswers = [
      ...followUpAnswers,
      {
        question_id: question.question_id,
        policy_id: question.policy_id,
        condition_key: question.condition_key,
        question: question.question,
        answer,
      },
    ]

    setFollowUpAnswers(nextAnswers)
    void runRecommendation(nextAnswers)
  }

  const returnToForm = () => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null

    setLoading(false)
    setMode('form')
    setFollowUpAnswers([])
    setFollowUpResponse(null)
    setError('')
  }

  const cancelRecommendation = () => {
    returnToForm()
    setLoadingStep(0)

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }

  const birthYear =
    user?.birthdate?.slice(0, 4)
    || '—'

  return (
    <div
      className="container page"
      style={{ maxWidth: 1040 }}
    >
      <PageHead
        title="지원 정책 찾기"
        sub="내 상황에 맞는 정책을 추천받거나, 알고 있는 정책을 이름으로 바로 찾아볼 수 있어요."
      />

      <RequireLogin axis="지원 정책 찾기">
        {!loading
          && mode !== 'chat'
          && (
            <SearchModeSelector
              searchMode={searchMode}
              onChange={changeSearchMode}
            />
          )}

        {loading ? (
          searchMode === 'lookup'
            ? (
              <PolicyLookupLoading
                onCancel={cancelRecommendation}
              />
            )
            : (
              <RecommendationLoading
                stepIndex={loadingStep}
                onCancel={cancelRecommendation}
              />
            )
        ) : searchMode === 'lookup' ? (
          <PolicyLookupForm
            policyName={policyName}
            error={error}
            onChange={(value) => {
              setPolicyName(value)
              setError('')
            }}
            onSubmit={handlePolicyLookup}
          />
        ) : mode === 'chat' && followUpResponse ? (
          <FollowUpChat
            response={followUpResponse}
            answers={followUpAnswers}
            error={error}
            onAnswer={handleFollowUpAnswer}
            onEditForm={returnToForm}
          />
        ) : (
          <form onSubmit={handleSubmit}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns:
                  'repeat(auto-fit, minmax(320px, 1fr))',
                gap: 16,
              }}
            >
              <FormSection
                number="1"
                title="기본 정보"
                description="회원정보를 바탕으로 자동 입력됩니다."
              >
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns:
                      'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: 12,
                  }}
                >
                  <ReadOnlyInfo
                    label="출생연도"
                    value={birthYear}
                  />

                  <div
                    style={{
                      padding: '14px 16px',
                      border: '1px solid var(--line)',
                      borderRadius: 12,
                      background: 'var(--bg)',
                    }}
                  >
                    <div
                      className="muted"
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                      }}
                    >
                      거주지역
                    </div>

                    <div
                      className="row"
                      style={{
                        marginTop: 5,
                        gap: 8,
                        justifyContent: 'space-between',
                      }}
                    >
                      <strong>{user?.region_sido || '—'}</strong>

                      <Link
                        to="/mypage"
                        className="btn btn-ghost btn-sm"
                      >
                        변경
                      </Link>
                    </div>
                  </div>
                </div>
              </FormSection>

              <FormSection
                number="2"
                title="현재 생활"
                description="현재 상황과 가장 가까운 항목을 선택해 주세요."
              >
                <SingleChoiceField
                  label="현재 주된 생활 상태"
                  value={form.current_life_status}
                  options={CURRENT_LIFE_STATUS_OPTIONS}
                  error={validationErrors.current_life_status}
                  onChange={(value) => updateField(
                    'current_life_status',
                    value,
                  )}
                />
              </FormSection>
            </div>

            <FormSection
              number="3"
              title="돌봄 상황"
              description="돌봄 상황에 대해 알려주세요."
              style={{ marginTop: 16 }}
            >
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns:
                    'repeat(auto-fit, minmax(260px, 1fr))',
                  gap: '4px 24px',
                }}
              >
                <SingleChoiceField
                  label="주로 돌보는 가족"
                  value={form.care_recipient}
                  options={CARE_RECIPIENT_OPTIONS}
                  error={validationErrors.care_recipient}
                  onChange={(value) => updateField(
                    'care_recipient',
                    value,
                  )}
                />

                <SingleChoiceField
                  label="가족을 돌본 기간"
                  value={form.care_duration}
                  options={CARE_DURATION_OPTIONS}
                  error={validationErrors.care_duration}
                  onChange={(value) => updateField(
                    'care_duration',
                    value,
                  )}
                />

                <SingleChoiceField
                  label="하루 평균 돌봄 시간"
                  value={form.daily_care_time}
                  options={DAILY_CARE_TIME_OPTIONS}
                  error={validationErrors.daily_care_time}
                  onChange={(value) => updateField(
                    'daily_care_time',
                    value,
                  )}
                />
              </div>

              <Divider>
                <MultiChoiceField
                  label="평소 가족에게 제공하는 도움"
                  required={false}
                  values={form.care_activities}
                  options={CARE_ACTIVITY_OPTIONS}
                  onToggle={(value) => updateField(
                    'care_activities',
                    toggleMulti(
                      form.care_activities,
                      value,
                      'hard_to_classify',
                    ),
                  )}
                />
              </Divider>
            </FormSection>

            <FormSection
              number="4"
              title="생활과 지원"
              description="현재 부담과 필요한 지원 분야를 알려주세요."
              style={{ marginTop: 16 }}
            >
              <SingleChoiceField
                label="경제적 부담 정도"
                value={form.financial_burden}
                options={FINANCIAL_BURDEN_OPTIONS}
                error={validationErrors.financial_burden}
                onChange={(value) => updateField(
                  'financial_burden',
                  value,
                )}
              />

              <Divider>
                <MultiChoiceField
                  label="현재 필요한 지원"
                  values={form.needed_support_types}
                  options={NEEDED_SUPPORT_OPTIONS}
                  error={validationErrors.needed_support_types}
                  onToggle={(value) => updateField(
                    'needed_support_types',
                    toggleMulti(
                      form.needed_support_types,
                      value,
                      'unknown',
                    ),
                  )}
                />
              </Divider>
            </FormSection>

            <FormSection
              number="5"
              title="추가 설명"
              description="선택 항목으로 표현하기 어려운 상황이 있다면 자유롭게 적어주세요."
              optional
              style={{ marginTop: 16 }}
            >
              <textarea
                className="input"
                rows={5}
                maxLength={2000}
                placeholder="예) 조부모님을 돌보며 야간 아르바이트를 하고 있어요. 어떤 지원을 받아야 할지 잘 모르겠어요. 국민취업지원제도에 대해 찾아주세요."
                value={form.additional_context}
                onChange={(event) => updateField(
                  'additional_context',
                  event.target.value,
                )}
                style={{ resize: 'vertical' }}
              />

              <div
                className="row"
                style={{
                  justifyContent: 'space-between',
                  gap: 12,
                  marginTop: 8,
                  flexWrap: 'wrap',
                }}
              >
                <span className="hint">
                  이름이나 연락처 같은 개인정보는 적지 않아도 돼요.
                </span>

                <span className="hint">
                  {form.additional_context.length}/2000
                </span>
              </div>
            </FormSection>

            <div
              className="card card-pad"
              style={{
                marginTop: 16,
                borderColor: 'var(--teal-100)',
                background: 'var(--teal-50)',
              }}
            >
              {error && (
                <div
                  className="err"
                  role="alert"
                  style={{
                    whiteSpace: 'pre-wrap',
                    marginBottom: 14,
                  }}
                >
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary btn-block btn-lg"
              >
                AI로 맞춤 정책 추천받기
              </button>

              <p
                className="hint center"
                style={{ marginTop: 10, marginBottom: 0 }}
              >
                입력값은 정책 추천에만 사용하며 별도로 저장하지 않아요.
              </p>
            </div>
          </form>
        )}
      </RequireLogin>
    </div>
  )
}

function SearchModeSelector({
  searchMode,
  onChange,
}) {
  return (
    <div
      className="card card-pad"
      style={{
        marginBottom: 16,
      }}
    >
      <div
        style={{
          fontSize: 18,
          fontWeight: 800,
          marginBottom: 6,
        }}
      >
        어떤 방식으로 찾을까요?
      </div>

      <div
        className="muted"
        style={{
          fontSize: 13.5,
          marginBottom: 14,
        }}
      >
        맞춤 추천을 받거나 알고 있는 정책명을
        바로 검색할 수 있어요.
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns:
            'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 12,
        }}
      >
        <button
          type="button"
          className={
            searchMode === 'recommend'
              ? 'btn btn-primary'
              : 'btn btn-ghost'
          }
          onClick={() => onChange('recommend')}
          style={{
            minHeight: 54,
          }}
        >
          👤 나에게 맞는 정책 추천
        </button>

        <button
          type="button"
          className={
            searchMode === 'lookup'
              ? 'btn btn-primary'
              : 'btn btn-ghost'
          }
          onClick={() => onChange('lookup')}
          style={{
            minHeight: 54,
          }}
        >
          🔎 정책 직접 찾기
        </button>
      </div>
    </div>
  )
}

function PolicyLookupForm({
  policyName,
  error,
  onChange,
  onSubmit,
}) {
  return (
    <form onSubmit={onSubmit}>
      <div
        className="card card-pad"
        style={{
          maxWidth: 720,
          margin: '0 auto',
        }}
      >
        <div
          style={{
            fontSize: 20,
            fontWeight: 800,
          }}
        >
          정책 직접 찾기
        </div>

        <p
          className="muted"
          style={{
            margin: '6px 0 20px',
            lineHeight: 1.6,
          }}
        >
          알고 있는 정책명을 입력하면 정책을 바로 찾아드려요.
        </p>

        <label
          htmlFor="policy-name"
          style={{
            fontWeight: 700,
          }}
        >
          정책명
            <span
              style={{
                color: '#dc2626',
                marginLeft: 4,
              }}
            >
              *
            </span>
        </label>

        <input
          id="policy-name"
          type="text"
          className="input"
          value={policyName}
          maxLength={200}
          placeholder="예) 일상돌봄 서비스"
          onChange={(event) => {
            onChange(event.target.value)
          }}
          style={{
            marginTop: 8,
          }}
        />

        <div
          className="hint"
          style={{
            marginTop: 8,
          }}
        >
          정책명만 입력해주세요.
        </div>

        {error && (
          <div
            className="err"
            role="alert"
            style={{
              marginTop: 14,
              color: '#dc2626',
            }}
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          className="btn btn-primary btn-block btn-lg"
          style={{
            marginTop: 20,
          }}
        >
          정책 찾기
        </button>
      </div>
    </form>
  )
}

function PolicyLookupLoading({
  onCancel,
}) {
  return (
    <div
      className="card card-pad"
      style={{
        minHeight: 300,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
      }}
    >
      <div
        className="spinner"
        style={{
          marginBottom: 22,
        }}
      />

      <div
        style={{
          fontSize: 21,
          fontWeight: 800,
        }}
      >
        정책을 찾고 있어요
      </div>

      <div
        className="muted"
        style={{
          marginTop: 8,
        }}
      >
        입력한 정책명과 같거나 비슷한 정책을
        검색하고 있어요.
      </div>

      <button
        type="button"
        className="btn btn-ghost"
        style={{
          marginTop: 24,
        }}
        onClick={onCancel}
      >
        검색 취소
      </button>
    </div>
  )
}

function FormSection({
  number,
  title,
  description,
  optional = false,
  style,
  children,
}) {
  return (
    <section
      className="card card-pad"
      style={{ height: '100%', ...style }}
    >
      <div
        className="row"
        style={{
          gap: 10,
          alignItems: 'flex-start',
          marginBottom: 18,
        }}
      >
        <span
          aria-hidden="true"
          style={{
            width: 30,
            height: 30,
            flexShrink: 0,
            borderRadius: '50%',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--teal-700)',
            color: '#fff',
            fontSize: 14,
            fontWeight: 800,
          }}
        >
          {number}
        </span>

        <div style={{ minWidth: 0 }}>
          <div
            className="row"
            style={{
              gap: 7,
              alignItems: 'center',
              flexWrap: 'wrap',
            }}
          >
            <h2
              style={{
                margin: 0,
                fontSize: 18,
                lineHeight: 1.4,
              }}
            >
              {title}
            </h2>

            {optional && <OptionalBadge />}
          </div>

          {description && (
            <p
              className="muted"
              style={{
                margin: '4px 0 0',
                fontSize: 13,
                lineHeight: 1.5,
              }}
            >
              {description}
            </p>
          )}
        </div>
      </div>

      {children}
    </section>
  )
}

function OptionalBadge() {
  return (
    <span
      style={{
        padding: '2px 7px',
        borderRadius: 999,
        background: 'var(--bg)',
        border: '1px solid var(--line)',
        fontSize: 11,
        color: 'var(--muted)',
      }}
    >
      선택
    </span>
  )
}

function ReadOnlyInfo({ label, value }) {
  return (
    <div
      style={{
        padding: '14px 16px',
        border: '1px solid var(--line)',
        borderRadius: 12,
        background: 'var(--bg)',
      }}
    >
      <div
        className="muted"
        style={{ fontSize: 12, fontWeight: 700 }}
      >
        {label}
      </div>

      <strong style={{ display: 'block', marginTop: 5 }}>
        {value}
      </strong>
    </div>
  )
}

function Divider({ children }) {
  return (
    <div
      style={{
        borderTop: '1px solid var(--line)',
        marginTop: 4,
        paddingTop: 18,
      }}
    >
      {children}
    </div>
  )
}

function SingleChoiceField({
  label,
  value,
  options,
  error,
  onChange,
}) {
  return (
    <FieldBox error={error}>
      <label
        style={{ color: error ? '#dc2626' : undefined }}
      >
        {label} <span className="req">*</span>
      </label>

      <FieldError error={error} />

      <div
        className="row"
        style={{ gap: 8, flexWrap: 'wrap' }}
      >
        {options.map(([optionValue, optionLabel]) => (
          <button
            key={optionValue}
            type="button"
            className={`chip ${
              value === optionValue ? 'on' : ''
            }`}
            aria-pressed={value === optionValue}
            onClick={() => onChange(optionValue)}
          >
            {optionLabel}
          </button>
        ))}
      </div>
    </FieldBox>
  )
}

function MultiChoiceField({
  label,
  required = true,
  values,
  options,
  error,
  onToggle,
}) {
  return (
    <FieldBox error={error}>
      <label>
        <span
          className="row"
          style={{
            display: 'inline-flex',
            gap: 7,
            alignItems: 'center',
            flexWrap: 'wrap',
            color: error ? '#dc2626' : undefined,
          }}
        >
          <span>
            {label}
            {required && <span className="req"> *</span>}
          </span>

          {!required && <OptionalBadge />}

          <span
            className="muted"
            style={{ fontWeight: 400, fontSize: 13 }}
          >
            (복수 선택)
          </span>
        </span>
      </label>

      <FieldError error={error} />

      <div
        className="row"
        style={{ gap: 8, flexWrap: 'wrap' }}
      >
        {options.map(([optionValue, optionLabel]) => (
          <button
            key={optionValue}
            type="button"
            className={`chip ${
              values.includes(optionValue) ? 'on' : ''
            }`}
            aria-pressed={values.includes(optionValue)}
            onClick={() => onToggle(optionValue)}
          >
            {optionLabel}
          </button>
        ))}
      </div>
    </FieldBox>
  )
}

function FieldBox({ error, children }) {
  return (
    <div
      className="field"
      data-invalid={error ? 'true' : undefined}
      style={{
        padding: 12,
        borderRadius: 12,
        border: error
          ? '1px solid #ef4444'
          : '1px solid transparent',
        background: error ? '#fff7f7' : 'transparent',
        transition:
          'border-color 0.2s ease, background 0.2s ease',
      }}
    >
      {children}
    </div>
  )
}

function FieldError({ error }) {
  if (!error) {
    return null
  }

  return (
    <p
      role="alert"
      style={{
        margin: '5px 0 10px',
        color: '#dc2626',
        fontSize: 13,
        fontWeight: 600,
      }}
    >
      {error}
    </p>
  )
}

function RecommendationLoading({
  stepIndex,
  onCancel,
}) {
  const currentStep = LOADING_STEPS[stepIndex]

  return (
    <div
      className="card card-pad"
      style={{
        minHeight: 390,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
      }}
    >
      <div
        className="spinner"
        style={{ marginBottom: 24 }}
      />

      <div style={{ fontSize: 22, fontWeight: 800 }}>
        AI가 맞춤 정책을 찾고 있어요
      </div>

      <div
        key={currentStep.title}
        style={{
          marginTop: 24,
          padding: '16px 24px',
          width: '100%',
          maxWidth: 420,
          minHeight: 92,
          borderRadius: 14,
          background: 'var(--teal-50)',
          border: '1px solid var(--teal-100)',
        }}
      >
        <div
          style={{
            fontSize: 17,
            fontWeight: 800,
            color: 'var(--teal-700)',
          }}
        >
          {currentStep.title}
        </div>

        <div
          className="muted"
          style={{ marginTop: 7, fontSize: 14 }}
        >
          {currentStep.description}
        </div>
      </div>

      <div
        className="row"
        style={{
          marginTop: 20,
          gap: 8,
          justifyContent: 'center',
        }}
      >
        {LOADING_STEPS.map((step, index) => (
          <span
            key={step.title}
            aria-hidden="true"
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background:
                index === stepIndex
                  ? 'var(--teal-600)'
                  : 'var(--line)',
            }}
          />
        ))}
      </div>

      <button
        type="button"
        className="btn btn-ghost"
        style={{ marginTop: 30 }}
        onClick={onCancel}
      >
        추천 중단 후 다시 입력하기
      </button>

      <p
        className="hint center"
        style={{ marginTop: 12, marginBottom: 0 }}
      >
        중단해도 입력한 내용은 유지돼요.
      </p>
    </div>
  )
}

function FollowUpChat({
  response,
  answers,
  error,
  onAnswer,
  onEditForm,
}) {
  const question = response.follow_up_question
  const [textAnswer, setTextAnswer] = useState('')
  const [selectedAnswers, setSelectedAnswers] =
    useState([])

  useEffect(() => {
    setTextAnswer('')
    setSelectedAnswers([])
  }, [question?.question_id])

  if (!question) {
    return (
      <div className="card card-pad">
        <div className="err">
          추가 질문 정보를 불러오지 못했습니다.
        </div>

        <button
          type="button"
          className="btn btn-ghost"
          style={{ marginTop: 12 }}
          onClick={onEditForm}
        >
          조건 입력 화면으로 돌아가기
        </button>
      </div>
    )
  }

  const options = Array.isArray(question.options)
    ? question.options
    : []

  const submitText = () => {
    const value = textAnswer.trim()

    if (value) {
      onAnswer(value)
    }
  }

  const submitMultiple = () => {
    if (selectedAnswers.length > 0) {
      onAnswer(selectedAnswers)
    }
  }

  return (
    <div className="card card-pad">
      <div
        className="row"
        style={{
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 8,
          marginBottom: 10,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 14 }}>
          🧠 AI 추가 질문
        </div>

        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={onEditForm}
        >
          ← 조건 입력 내용 수정하기
        </button>
      </div>

      {response.understood_situation && (
        <div
          style={{
            background: 'var(--teal-50)',
            borderRadius: 10,
            padding: '10px 14px',
            marginBottom: 12,
          }}
        >
          <div
            style={{
              fontSize: 12.5,
              fontWeight: 700,
              color: 'var(--teal-700)',
            }}
          >
            AI가 이해한 현재 상황
          </div>

          <div style={{ fontSize: 14, marginTop: 4 }}>
            {response.understood_situation}
          </div>
        </div>
      )}

      <div
        className="chat-wrap"
        style={{ maxHeight: 360, overflowY: 'auto' }}
      >
        {answers.map((answer) => (
          <div key={answer.question_id}>
            <div className="bubble bot">
              {answer.question}
            </div>

            <div className="bubble me">
              {Array.isArray(answer.answer)
                ? answer.answer.join(', ')
                : answer.answer}
            </div>
          </div>
        ))}

        <div className="bubble bot">
          {question.question}
        </div>
      </div>

      {error && (
        <div
          className="err"
          role="alert"
          style={{
            whiteSpace: 'pre-wrap',
            marginTop: 10,
          }}
        >
          {error}
        </div>
      )}

      {question.answer_type === 'multiple_choice' ? (
        <>
          <div
            className="row"
            style={{
              gap: 8,
              flexWrap: 'wrap',
              marginTop: 12,
            }}
          >
            {options.map((option) => (
              <button
                key={option}
                type="button"
                className={`chip ${
                  selectedAnswers.includes(option)
                    ? 'on'
                    : ''
                }`}
                onClick={() => setSelectedAnswers(
                  (previousAnswers) => (
                    previousAnswers.includes(option)
                      ? previousAnswers.filter(
                        (item) => item !== option,
                      )
                      : [...previousAnswers, option]
                  ),
                )}
              >
                {option}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="btn btn-primary btn-block"
            style={{ marginTop: 12 }}
            disabled={selectedAnswers.length === 0}
            onClick={submitMultiple}
          >
            답변 보내기
          </button>
        </>
      ) : question.answer_type === 'single_choice'
        && options.length > 0 ? (
          <div
            className="row"
            style={{
              gap: 8,
              flexWrap: 'wrap',
              marginTop: 12,
            }}
          >
            {options.map((option) => (
              <button
                key={option}
                type="button"
                className="chip"
                onClick={() => onAnswer(option)}
              >
                {option}
              </button>
            ))}
          </div>
        ) : (
          <div
            className="chat-input"
            style={{ marginTop: 12 }}
          >
            <input
              className="input"
              placeholder="답변을 입력하세요"
              value={textAnswer}
              onChange={(event) => setTextAnswer(
                event.target.value,
              )}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  submitText()
                }
              }}
            />

            <button
              type="button"
              className="btn btn-primary"
              disabled={!textAnswer.trim()}
              onClick={submitText}
            >
              전송
            </button>
          </div>
        )}

      {question.allow_skip && (
        <button
          type="button"
          className="btn btn-plain btn-sm"
          style={{ marginTop: 10 }}
          onClick={() => onAnswer('답변하지 않을게요')}
        >
          답변하지 않고 넘어가기
        </button>
      )}
    </div>
  )
}