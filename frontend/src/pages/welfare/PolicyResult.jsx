import { useState } from 'react'
import {
  Link,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import {
  addPolicyFavorite,
  deletePolicyFavorite,
} from '../../api/welfare.js'
import {
  FitBadge,
  PageHead,
  useToast,
} from '../../components/ui/index.jsx'

const FITNESS_MAP = {
  very_high: 'best',
  high: 'good',
  medium: 'rec',
  low: 'ref',
}

const FITNESS_LABEL = {
  very_high: '매우 적합',
  high: '적합',
  medium: '추천',
  low: '참고',
}

function getEditableRequest(request) {
  if (!request) {
    return null
  }

  return {
    current_life_status:
      request.current_life_status || '',
    care_recipient:
      request.care_recipient || '',
    care_duration:
      request.care_duration || '',
    daily_care_time:
      request.daily_care_time || '',
    financial_burden:
      request.financial_burden || '',
    needed_support_types:
      request.needed_support_types || [],
    care_activities:
      request.care_activities || [],
    additional_context:
      request.additional_context || '',
  }
}

function formatCreatedAt(value) {
  if (!value) {
    return ''
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return ''
  }

  return new Intl.DateTimeFormat(
    'ko-KR',
    {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    },
  ).format(date)
}

export default function PolicyResult() {
  const { state } = useLocation()
  const navigate = useNavigate()
  const toast = useToast()

  const [response, setResponse] = useState(
    state?.response || null,
  )

  const [favoriteLoadingIds, setFavoriteLoadingIds] =
    useState([])

  const request = state?.request || null

  const goBackToInput = () => {
    navigate(
      '/welfare/policy',
      {
        state: {
          request: getEditableRequest(request),
        },
      },
    )
  }

  const toggleFavorite = async (policy) => {
    if (
      favoriteLoadingIds.includes(
        policy.policy_id,
      )
    ) {
      return
    }

    setFavoriteLoadingIds((previousIds) => [
      ...previousIds,
      policy.policy_id,
    ])

    try {
      const result = policy.is_favorite
        ? await deletePolicyFavorite(
          policy.policy_id,
        )
        : await addPolicyFavorite(
          policy.policy_id,
        )

      const updatePolicy = (item) => (
        item.policy_id === policy.policy_id
          ? {
            ...item,
            is_favorite: result.is_favorite,
          }
          : item
      )

      setResponse((previousResponse) => {
        if (
          previousResponse?.status
          === 'recommendation_completed'
        ) {
          return {
            ...previousResponse,
            recommendations:
              previousResponse.recommendations.map(
                updatePolicy,
              ),
          }
        }

        if (
          previousResponse?.status
          === 'policy_lookup_completed'
        ) {
          return {
            ...previousResponse,
            policies:
              previousResponse.policies.map(
                updatePolicy,
              ),
          }
        }

        return previousResponse
      })

      toast.show(result.message)
    } catch (error) {
      toast.show(
        error instanceof Error
          ? error.message
          : '즐겨찾기 처리에 실패했습니다.',
      )
    } finally {
      setFavoriteLoadingIds((previousIds) => (
        previousIds.filter(
          (policyId) => (
            policyId !== policy.policy_id
          ),
        )
      ))
    }
  }

  if (!response) {
    return (
      <div
        className="container page"
        style={{ maxWidth: 820 }}
      >
        <PageHead
          title="맞춤 지원 정책 추천 결과"
        />

        <div className="empty">
          <div className="ic">🗂️</div>

          <p style={{ marginTop: 8 }}>
            표시할 추천 결과가 없어요.
          </p>

          <Link
            to="/welfare/policy"
            className="btn btn-primary btn-sm"
            style={{ marginTop: 12 }}
          >
            정책 추천 시작하기
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div
      className="container page"
      style={{ maxWidth: 820 }}
    >
      <PageHead
        title="맞춤 지원 정책 추천 결과"
        sub="입력하신 상황과 실제 정책 자격조건을 바탕으로 정리한 결과예요."
        right={(
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={goBackToInput}
          >
            조건 다시 입력
          </button>
        )}
      />

      {response.status
        === 'recommendation_completed' && (
        <RecommendationCompleted
          response={response}
          favoriteLoadingIds={
            favoriteLoadingIds
          }
          onFavorite={toggleFavorite}
          onEditConditions={goBackToInput}
        />
      )}

      {response.status
        === 'policy_lookup_completed' && (
        <PolicyLookupCompleted
          response={response}
          favoriteLoadingIds={
            favoriteLoadingIds
          }
          onFavorite={toggleFavorite}
          onEditConditions={goBackToInput}
        />
      )}

      {response.status === 'no_policy_found' && (
        <NoPolicyFound
          response={response}
          onEditConditions={goBackToInput}
        />
      )}

      {response.status === 'invalid_input' && (
        <MessageResult
          icon="⚠️"
          title="입력 내용을 다시 확인해 주세요."
          message={response.message}
          extra={
            response.retry_example
              ? `입력 예시: ${response.retry_example}`
              : null
          }
          onEditConditions={goBackToInput}
        />
      )}

      {response.status === 'urgent_support' && (
        <MessageResult
          icon="🛡️"
          title="지금은 안전 확인이 먼저 필요해요."
          message={response.message}
          onEditConditions={goBackToInput}
        />
      )}

      {toast.node}
    </div>
  )
}

function RecommendationCompleted({
  response,
  favoriteLoadingIds,
  onFavorite,
  onEditConditions,
}) {
  const recommendations =
    response.recommendations || []

  return (
    <div
      className="stack"
      style={{ gap: 16 }}
    >
      <UnderstoodSituation
        text={response.understood_situation}
      />

      <div
        className="row"
        style={{
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div
            style={{
              fontSize: 18,
              fontWeight: 800,
            }}
          >
            추천 정책 {recommendations.length}개
          </div>

          <div
            className="muted"
            style={{
              marginTop: 4,
              fontSize: 13.5,
            }}
          >
            적합도가 높은 순서로 보여드려요.
          </div>
        </div>

        {response.created_at && (
          <div
            className="muted"
            style={{ fontSize: 13 }}
          >
            {formatCreatedAt(response.created_at)}
          </div>
        )}
      </div>

      {recommendations.length > 0 ? (
        recommendations.map((policy) => (
          <PolicyCard
            key={policy.policy_id}
            policy={policy}
            favoriteLoading={
              favoriteLoadingIds.includes(
                policy.policy_id,
              )
            }
            onFavorite={onFavorite}
          />
        ))
      ) : (
        <div className="empty">
          추천 결과에 포함된 정책이 없어요.
        </div>
      )}

      <ResultActions
        onEditConditions={onEditConditions}
      />
    </div>
  )
}

function PolicyLookupCompleted({
  response,
  favoriteLoadingIds,
  onFavorite,
  onEditConditions,
}) {
  const policies = response.policies || []

  return (
    <div
      className="stack"
      style={{ gap: 16 }}
    >
      <div
        className="card card-pad"
        style={{
          background: 'var(--teal-50)',
          borderColor: 'var(--teal-100)',
        }}
      >
        <div
          style={{
            fontSize: 12.5,
            fontWeight: 700,
            color: 'var(--teal-700)',
          }}
        >
          검색한 정책명
        </div>

        <div
          style={{
            marginTop: 5,
            fontSize: 17,
            fontWeight: 700,
          }}
        >
          {response.requested_policy_name}
        </div>
      </div>

      <div
        className="muted"
        style={{ fontSize: 13.5 }}
      >
        정책명이 같거나 비슷한 결과를 보여드려요.
        신청 가능 여부는 상세 자격조건을 확인해 주세요.
      </div>

      {policies.map((policy) => (
        <PolicyCard
          key={policy.policy_id}
          policy={policy}
          favoriteLoading={
            favoriteLoadingIds.includes(
              policy.policy_id,
            )
          }
          onFavorite={onFavorite}
        />
      ))}

      <ResultActions
        onEditConditions={onEditConditions}
      />
    </div>
  )
}

function UnderstoodSituation({ text }) {
  if (!text) {
    return null
  }

  return (
    <section
      className="card card-pad"
      style={{
        background: 'var(--teal-50)',
        borderColor: 'var(--teal-100)',
      }}
    >
      <div
        style={{
          fontSize: 12.5,
          fontWeight: 700,
          color: 'var(--teal-700)',
          marginBottom: 6,
        }}
      >
        AI가 이해한 현재 상황
      </div>

      <div
        style={{
          fontSize: 14.5,
          lineHeight: 1.7,
          whiteSpace: 'pre-wrap',
        }}
      >
        {text}
      </div>
    </section>
  )
}

function PolicyCard({
  policy,
  favoriteLoading,
  onFavorite,
}) {
  const categories = policy.category || []

  return (
    <article
      className="card card-pad card-hover"
    >
      <div
        className="row"
        style={{
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 14,
          marginBottom: 10,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div
            className="muted"
            style={{
              fontSize: 12.5,
              marginBottom: 4,
            }}
          >
            {policy.region}
            {' · '}
            {policy.source_name}
          </div>

          <h3
            style={{
              fontSize: 19,
              lineHeight: 1.35,
            }}
          >
            {policy.policy_name}
          </h3>
        </div>

        <div
          className="row"
          style={{
            gap: 7,
            flexShrink: 0,
          }}
        >
          {policy.fitness && (
            <span
              title={
                FITNESS_LABEL[policy.fitness]
                || '적합도'
              }
            >
              <FitBadge
                fit={
                  FITNESS_MAP[policy.fitness]
                  || 'ref'
                }
              />
            </span>
          )}

          <button
            type="button"
            className="btn btn-plain btn-sm"
            disabled={favoriteLoading}
            aria-label={
              policy.is_favorite
                ? '즐겨찾기 해제'
                : '즐겨찾기 추가'
            }
            aria-pressed={policy.is_favorite}
            onClick={() => onFavorite(policy)}
            style={{
              minWidth: 38,
              opacity: favoriteLoading
                ? 0.55
                : 1,
            }}
          >
            {favoriteLoading
              ? '…'
              : policy.is_favorite
                ? '★'
                : '☆'}
          </button>
        </div>
      </div>

      {categories.length > 0 && (
        <div
          className="row"
          style={{
            gap: 6,
            flexWrap: 'wrap',
            marginBottom: 12,
          }}
        >
          {categories.map((category) => (
            <span
              key={category}
              className="chip"
              style={{
                cursor: 'default',
                fontSize: 12,
                padding: '5px 9px',
              }}
            >
              {category}
            </span>
          ))}
        </div>
      )}

      {policy.policy_summary && (
        <p
          className="muted"
          style={{
            marginBottom: 12,
            lineHeight: 1.65,
          }}
        >
          {policy.policy_summary}
        </p>
      )}

      {policy.recommendation_reason && (
        <div
          style={{
            background: 'var(--teal-50)',
            border: '1px solid var(--teal-100)',
            borderRadius: 10,
            padding: '12px 14px',
            marginBottom: 14,
          }}
        >
          <div
            style={{
              fontSize: 12.5,
              fontWeight: 700,
              color: 'var(--teal-700)',
              marginBottom: 5,
            }}
          >
            추천 이유
          </div>

          <div
            style={{
              fontSize: 14,
              color: 'var(--ink-soft)',
              lineHeight: 1.65,
            }}
          >
            {policy.recommendation_reason}
          </div>
        </div>
      )}

      <div
        className="row"
        style={{
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          gap: 14,
          flexWrap: 'wrap',
        }}
      >
        <div
          className="stack"
          style={{ gap: 4 }}
        >
          <div
            className="muted"
            style={{ fontSize: 13.5 }}
          >
            {policy.institution_name
              || '담당 기관 확인 필요'}
          </div>

          <div
            className="row muted"
            style={{
              gap: 8,
              flexWrap: 'wrap',
              fontSize: 13,
            }}
          >
            {policy.support_type && (
              <span>
                지원 형태: {policy.support_type}
              </span>
            )}

            {policy.support_cycle && (
              <span>
                지원 주기: {policy.support_cycle}
              </span>
            )}
          </div>
        </div>

        <div
          className="row"
          style={{
            gap: 8,
            flexWrap: 'wrap',
          }}
        >
          <Link
            to={`/welfare/policy/${policy.policy_id}`}
            className="btn btn-ghost btn-sm"
          >
            상세보기
          </Link>

          {policy.detail_url && (
            <a
              href={policy.detail_url}
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary btn-sm"
            >
              공식 사이트 ↗
            </a>
          )}

          {!policy.detail_url
            && policy.guide_pdf_url && (
            <a
              href={policy.guide_pdf_url}
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary btn-sm"
            >
              안내문 보기 ↗
            </a>
          )}
        </div>
      </div>
    </article>
  )
}

function NoPolicyFound({
  response,
  onEditConditions,
}) {
  const alternativeActions =
    response.alternative_actions || []

  return (
    <div
      className="stack"
      style={{ gap: 16 }}
    >
      <UnderstoodSituation
        text={response.understood_situation}
      />

      <div className="card card-pad">
        <div
          style={{
            fontSize: 18,
            fontWeight: 800,
            marginBottom: 8,
          }}
        >
          현재 조건과 잘 맞는 정책을 찾지 못했어요.
        </div>

        <div
          style={{
            background: 'var(--teal-50)',
            border: '1px solid var(--teal-100)',
            borderRadius: 10,
            padding: '12px 14px',
            marginBottom: 16,
          }}
        >
          <div
            style={{
              fontSize: 12.5,
              fontWeight: 700,
              color: 'var(--teal-700)',
              marginBottom: 5,
            }}
          >
            AI 분석 결과
          </div>

          <div
            style={{
              fontSize: 14,
              lineHeight: 1.65,
            }}
          >
            {response.reason}
          </div>
        </div>

        {alternativeActions.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div
              style={{
                fontSize: 14,
                fontWeight: 700,
                marginBottom: 10,
              }}
            >
              다른 도움 받기
            </div>

            <div
              className="stack"
              style={{ gap: 8 }}
            >
              {alternativeActions.map(
                (action, index) => (
                  <AlternativeAction
                    key={
                      `${action.action_type}-${index}`
                    }
                    action={action}
                  />
                ),
              )}
            </div>
          </div>
        )}

        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={onEditConditions}
        >
          조건 다시 입력하기
        </button>
      </div>
    </div>
  )
}

function AlternativeAction({ action }) {
  const content = (
    <>
      <div
        style={{
          fontWeight: 700,
          fontSize: 14,
        }}
      >
        {action.title}
      </div>

      {action.description && (
        <div
          className="muted"
          style={{
            marginTop: 3,
            fontSize: 13,
          }}
        >
          {action.description}
        </div>
      )}
    </>
  )

  if (
    action.action_type === 'welfare_hotline'
    && action.phone_number
  ) {
    return (
      <a
        href={`tel:${action.phone_number}`}
        className="card"
        style={{
          display: 'block',
          padding: 13,
          textDecoration: 'none',
        }}
      >
        {content}
      </a>
    )
  }

  if (
    action.action_type === 'institution_search'
    && action.route
  ) {
    return (
      <Link
        to={action.route}
        className="card"
        style={{
          display: 'block',
          padding: 13,
          textDecoration: 'none',
        }}
      >
        {content}
      </Link>
    )
  }

  return (
    <div
      className="card"
      style={{ padding: 13 }}
    >
      {content}
    </div>
  )
}

function MessageResult({
  icon,
  title,
  message,
  extra,
  onEditConditions,
}) {
  return (
    <div
      className="card card-pad"
      style={{ textAlign: 'center' }}
    >
      <div style={{ fontSize: 32 }}>
        {icon}
      </div>

      <div
        style={{
          marginTop: 10,
          fontSize: 18,
          fontWeight: 800,
        }}
      >
        {title}
      </div>

      <div
        style={{
          marginTop: 10,
          lineHeight: 1.7,
          whiteSpace: 'pre-wrap',
        }}
      >
        {message}
      </div>

      {extra && (
        <div
          className="muted"
          style={{
            marginTop: 8,
            fontSize: 13.5,
          }}
        >
          {extra}
        </div>
      )}

      <button
        type="button"
        className="btn btn-primary btn-sm"
        style={{ marginTop: 16 }}
        onClick={onEditConditions}
      >
        다시 입력하기
      </button>
    </div>
  )
}

function ResultActions({ onEditConditions }) {
  return (
    <div
      className="row"
      style={{
        gap: 8,
        flexWrap: 'wrap',
        justifyContent: 'center',
        marginTop: 4,
      }}
    >
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        onClick={onEditConditions}
      >
        입력 내용 수정하기
      </button>

      <Link
        to="/share/map"
        className="btn btn-plain btn-sm"
      >
        나누다 기관 찾기 →
      </Link>
    </div>
  )
}