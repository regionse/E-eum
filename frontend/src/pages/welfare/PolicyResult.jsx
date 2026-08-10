import { useState, useEffect } from 'react'
import {
  Link,
  useLocation,
  useNavigate,
} from 'react-router-dom'

import {
  addPolicyFavorite,
  deletePolicyFavorite,
  getPolicyFavorites,
} from '../../api/welfare.js'

import {
  FitBadge,
  PageHead,
  useToast,
} from '../../components/ui/index.jsx'


// =========================================================
// 적합도 표시
// =========================================================

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


// =========================================================
// 공통 함수
// =========================================================

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


function getPolicySourceButtonLabel(
  sourceName,
) {
  const labels = {
    중앙부처복지서비스:
      '복지로에서 보기 ↗',

    서울복지포털:
      '서울복지포털에서 보기 ↗',

    경기청년포털:
      '경기청년포털에서 보기 ↗',
  }

  return (
    labels[sourceName]
    || '정책 제공 사이트에서 보기 ↗'
  )
}


// =========================================================
// 정책 추천 결과 페이지
// =========================================================

export default function PolicyResult() {
  const { state } = useLocation()
  const navigate = useNavigate()
  const toast = useToast()

  // PolicyFind.jsx에서 전달한 백엔드 응답
  const [response, setResponse] = useState(
    state?.response || null,
  )

  // 결과 화면에서 조건 다시 입력을 눌렀을 때
  // 기존 입력값을 복원하기 위해 사용한다.
  const request = state?.request || null

  // 정책 직접 검색 결과인지 확인한다.
  const isLookupMode =
    state?.searchMode === 'lookup'
    || response?.status
      === 'policy_lookup_completed'

  const lookupPolicyName =
    state?.policyName
    || response?.requested_policy_name
    || ''

  // 즐겨찾기 API가 처리 중인 정책 ID
  const [ favoriteLoadingIds, setFavoriteLoadingIds ] = useState([])

  // 상세 페이지에서 즐겨찾기를 변경한 뒤
  // 결과 페이지로 돌아왔을 때 현재 DB 상태와 동기화한다.
  useEffect(() => {
    let cancelled = false

    const syncFavoriteStates = async () => {
      try {
        const favoriteResponse =
          await getPolicyFavorites()

        if (cancelled) {
          return
        }

        const favoriteIds = new Set(
          (
            favoriteResponse?.favorites
            || []
          ).map(
            (favorite) => (
              favorite.policy_id
            ),
          ),
        )

        const updateFavoriteState = (
          policy,
        ) => ({
          ...policy,

          is_favorite:
            favoriteIds.has(
              policy.policy_id,
            ),
        })

        setResponse(
          (previousResponse) => {
            if (!previousResponse) {
              return previousResponse
            }

            if (
              previousResponse.status
              === 'recommendation_completed'
            ) {
              return {
                ...previousResponse,

                recommendations:
                  (
                    previousResponse
                      .recommendations
                    || []
                  ).map(
                    updateFavoriteState,
                  ),
              }
            }

            if (
              previousResponse.status
              === 'policy_lookup_completed'
            ) {
              return {
                ...previousResponse,

                policies:
                  (
                    previousResponse
                      .policies
                    || []
                  ).map(
                    updateFavoriteState,
                  ),
              }
            }

            return previousResponse
          },
        )
      } catch (syncError) {
        // 즐겨찾기 조회가 실패해도
        // 추천 결과 자체는 계속 보여준다.
        console.error(
          '즐겨찾기 상태 동기화 실패:',
          syncError,
        )
      }
    }

    void syncFavoriteStates()

    return () => {
      cancelled = true
    }
  }, [])


  // -------------------------------------------------------
  // 조건 입력 화면으로 돌아가기
  // -------------------------------------------------------

  const goBackToInput = () => {
    if (isLookupMode) {
      navigate(
        '/welfare/policy',
        {
          state: {
            searchMode: 'lookup',
            policyName: lookupPolicyName,
          },
        },
      )

      return
    }

    navigate(
      '/welfare/policy',
      {
        state: {
          request: getEditableRequest(
            request,
          ),
        },
      },
    )
  }


  // -------------------------------------------------------
  // 즐겨찾기 추가·해제
  // -------------------------------------------------------

  const toggleFavorite = async (policy) => {
    const policyId = policy.policy_id

    if (
      favoriteLoadingIds.includes(
        policyId,
      )
    ) {
      return
    }

    setFavoriteLoadingIds(
      (previousIds) => [
        ...previousIds,
        policyId,
      ],
    )

    try {
      const result = policy.is_favorite
        ? await deletePolicyFavorite(
          policyId,
        )
        : await addPolicyFavorite(
          policyId,
        )

      const updatePolicy = (item) => {
        if (
          item.policy_id !== policyId
        ) {
          return item
        }

        return {
          ...item,
          is_favorite:
            result.is_favorite,
        }
      }

      setResponse(
        (previousResponse) => {
          if (
            previousResponse?.status
            === 'recommendation_completed'
          ) {
            return {
              ...previousResponse,

              recommendations:
                (
                  previousResponse
                    .recommendations
                  || []
                ).map(updatePolicy),
            }
          }

          // 특정 정책명 검색 기능을
          // 백엔드에서 사용하는 경우를 위한 처리
          if (
            previousResponse?.status
            === 'policy_lookup_completed'
          ) {
            return {
              ...previousResponse,

              policies:
                (
                  previousResponse
                    .policies
                  || []
                ).map(updatePolicy),
            }
          }

          return previousResponse
        },
      )

      toast.show(
        result.message
        || (
          result.is_favorite
            ? '즐겨찾기에 추가했습니다.'
            : '즐겨찾기를 해제했습니다.'
        ),
      )
    } catch (error) {
      toast.show(
        error instanceof Error
          ? error.message
          : '즐겨찾기 처리에 실패했습니다.',
      )
    } finally {
      setFavoriteLoadingIds(
        (previousIds) => (
          previousIds.filter(
            (id) => id !== policyId,
          )
        ),
      )
    }
  }


  // -------------------------------------------------------
  // 전달받은 결과가 없는 경우
  // -------------------------------------------------------

  if (!response) {
    return (
      <div
        className="container page"
        style={{
          maxWidth: 820,
        }}
      >
        <PageHead
          title="맞춤 지원 정책 추천 결과"
        />

        <div className="empty">
          <div className="ic">
            🗂️
          </div>

          <p
            style={{
              marginTop: 8,
            }}
          >
            표시할 추천 결과가 없어요.
          </p>

          <Link
            to="/welfare/policy"
            className="btn btn-primary btn-sm"
            style={{
              marginTop: 12,
            }}
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
      style={{
        maxWidth: 820,
      }}
    >
      <PageHead
        title={
          isLookupMode
            ? '정책 검색 결과'
            : '맞춤 지원 정책 추천 결과'
        }
        sub={
          isLookupMode
            ? '입력한 정책명과 같거나 비슷한 정책을 찾은 결과예요.'
            : '입력하신 상황과 실제 정책 자격조건을 바탕으로 정리한 결과예요.'
        }
        right={(
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={goBackToInput}
          >
            {isLookupMode
              ? '다른 정책 찾기'
              : '조건 다시 입력'}
          </button>
        )}
      />


      {/* 정책 추천 완료 */}
      {response.status
        === 'recommendation_completed'
        && (
          <RecommendationCompleted
            response={response}
            favoriteLoadingIds={
              favoriteLoadingIds
            }
            onFavorite={
              toggleFavorite
            }
            onEditConditions={
              goBackToInput
            }
          />
        )}


      {/* 특정 정책 검색 완료 */}
      {response.status
        === 'policy_lookup_completed'
        && (
          <PolicyLookupCompleted
            response={response}
            favoriteLoadingIds={
              favoriteLoadingIds
            }
            onFavorite={
              toggleFavorite
            }
            onEditConditions={
              goBackToInput
            }
          />
        )}


      {/* 추천 정책 없음 */}
      {response.status
        === 'no_policy_found'
        && (
          <NoPolicyFound
            response={response}
            onEditConditions={
              goBackToInput
            }
            lookupMode={
              isLookupMode
            }
          />
        )}


      {/* 잘못된 입력 */}
      {response.status
        === 'invalid_input'
        && (
          <MessageResult
            icon="⚠️"
            title="입력 내용을 다시 확인해 주세요."
            message={response.message}
            extra={
              response.retry_example
                ? (
                  `입력 예시: ${response.retry_example}`
                )
                : null
            }
            onEditConditions={
              goBackToInput
            }
          />
        )}


      {/* 긴급지원 안내 */}
      {response.status
        === 'urgent_support'
        && (
          <MessageResult
            icon="🛡️"
            title="지금은 안전 확인이 먼저 필요해요."
            message={response.message}
            onEditConditions={
              goBackToInput
            }
          />
        )}


      {/* 알 수 없는 응답 상태 */}
      {![
        'recommendation_completed',
        'policy_lookup_completed',
        'no_policy_found',
        'invalid_input',
        'urgent_support',
      ].includes(response.status) && (
        <MessageResult
          icon="⚠️"
          title="추천 결과를 표시하지 못했어요."
          message={
            '알 수 없는 응답 상태입니다. 조건을 다시 입력해 주세요.'
          }
          onEditConditions={
            goBackToInput
          }
        />
      )}


      {toast.node}
    </div>
  )
}


// =========================================================
// 맞춤 정책 추천 완료
// =========================================================

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
      style={{
        gap: 16,
      }}
    >
      <UnderstoodSituation
        text={
          response.understood_situation
        }
      />

      <div
        className="row"
        style={{
          justifyContent:
            'space-between',

          alignItems:
            'flex-end',

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
            추천 정책{' '}
            {recommendations.length}개
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
            style={{
              fontSize: 13,
            }}
          >
            {formatCreatedAt(
              response.created_at,
            )}
          </div>
        )}
      </div>


      {recommendations.length > 0 ? (
        recommendations.map(
          (policy) => (
            <PolicyCard
              key={
                policy.policy_id
              }
              policy={policy}
              favoriteLoading={
                favoriteLoadingIds.includes(
                  policy.policy_id,
                )
              }
              onFavorite={
                onFavorite
              }
            />
          ),
        )
      ) : (
        <div className="empty">
          추천 결과에 포함된 정책이 없어요.
        </div>
      )}


      <ResultActions
        onEditConditions={
          onEditConditions
        }
      />
    </div>
  )
}


// =========================================================
// 특정 정책명 검색 결과
// =========================================================

function PolicyLookupCompleted({
  response,
  favoriteLoadingIds,
  onFavorite,
  onEditConditions,
}) {
  const policies =
    response.policies || []

  return (
    <div
      className="stack"
      style={{
        gap: 16,
      }}
    >
      <div
        className="card card-pad"
        style={{
          background:
            'var(--teal-50)',

          borderColor:
            'var(--teal-100)',
        }}
      >
        <div
          style={{
            fontSize: 12.5,
            fontWeight: 700,
            color:
              'var(--teal-700)',
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
          {
            response
              .requested_policy_name
            || '정책 검색'
          }
        </div>
      </div>


      <div
        className="muted"
        style={{
          fontSize: 13.5,
        }}
      >
        정책명이 같거나 비슷한 결과를 보여드려요.
        신청 가능 여부는 상세 자격조건을 확인해 주세요.
      </div>


      {policies.length > 0 ? (
        policies.map(
          (policy) => (
            <PolicyCard
              key={
                policy.policy_id
              }
              policy={policy}
              favoriteLoading={
                favoriteLoadingIds.includes(
                  policy.policy_id,
                )
              }
              onFavorite={
                onFavorite
              }
            />
          ),
        )
      ) : (
        <div className="empty">
          검색된 정책이 없어요.
        </div>
      )}


      <ResultActions
        onEditConditions={
          onEditConditions
        }
        editLabel="다른 정책 찾기"
      />
    </div>
  )
}


// =========================================================
// AI가 이해한 현재 상황
// =========================================================

function UnderstoodSituation({
  text,
}) {
  if (!text) {
    return null
  }

  return (
    <section
      className="card card-pad"
      style={{
        background:
          'var(--teal-50)',

        borderColor:
          'var(--teal-100)',
      }}
    >
      <div
        style={{
          fontSize: 12.5,
          fontWeight: 700,
          color:
            'var(--teal-700)',

          marginBottom: 6,
        }}
      >
        AI가 이해한 현재 상황
      </div>

      <div
        style={{
          fontSize: 14.5,
          lineHeight: 1.7,
          whiteSpace:
            'pre-wrap',
        }}
      >
        {text}
      </div>
    </section>
  )
}


// =========================================================
// 추천 정책 카드
// =========================================================

function PolicyCard({
  policy,
  favoriteLoading,
  onFavorite,
}) {
  const categories =
    Array.isArray(policy.category)
      ? policy.category
      : []

  const fitnessLabel =
    FITNESS_LABEL[
      policy.fitness
    ] || '적합도'

  const fitnessValue =
    FITNESS_MAP[
      policy.fitness
    ] || 'ref'

  return (
    <article
      className="card card-pad card-hover"
    >
      <div
        className="row"
        style={{
          justifyContent:
            'space-between',

          alignItems:
            'flex-start',

          gap: 14,
          marginBottom: 10,
        }}
      >
        <div
          style={{
            minWidth: 0,
          }}
        >
          <div
            className="muted"
            style={{
              fontSize: 12.5,
              marginBottom: 4,
            }}
          >
            {
              policy.region
              || '지역 확인 필요'
            }

            {' · '}

            {
              policy.source_name
              || '출처 확인 필요'
            }
          </div>

          <h3
            style={{
              fontSize: 19,
              lineHeight: 1.35,
            }}
          >
            {
              policy.policy_name
            }
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
                fitnessLabel
              }
            >
              <FitBadge
                fit={
                  fitnessValue
                }
              />
            </span>
          )}

          <button
            type="button"
            className="btn btn-plain btn-sm"
            disabled={
              favoriteLoading
            }
            aria-label={
              policy.is_favorite
                ? '즐겨찾기 해제'
                : '즐겨찾기 추가'
            }
            aria-pressed={
              Boolean(
                policy.is_favorite,
              )
            }
            onClick={() => (
              onFavorite(policy)
            )}
            style={{
              minWidth: 38,
              opacity:
                favoriteLoading
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
          {categories.map(
            (category) => (
              <span
                key={category}
                className="chip"
                style={{
                  cursor:
                    'default',

                  fontSize: 12,
                  padding:
                    '5px 9px',
                }}
              >
                {category}
              </span>
            ),
          )}
        </div>
      )}


      {policy.policy_summary && (
        <p
          className="muted"
          style={{
            marginBottom: 12,
            lineHeight: 1.65,
            whiteSpace:
              'pre-wrap',
          }}
        >
          {
            policy.policy_summary
          }
        </p>
      )}


      {policy.recommendation_reason && (
        <div
          style={{
            background:
              'var(--teal-50)',

            border:
              '1px solid var(--teal-100)',

            borderRadius: 10,
            padding: '12px 14px',
            marginBottom: 14,
          }}
        >
          <div
            style={{
              fontSize: 12.5,
              fontWeight: 700,
              color:
                'var(--teal-700)',

              marginBottom: 5,
            }}
          >
            추천 이유
          </div>

          <div
            style={{
              fontSize: 14,
              color:
                'var(--ink-soft)',

              lineHeight: 1.65,
              whiteSpace:
                'pre-wrap',
            }}
          >
            {
              policy
                .recommendation_reason
            }
          </div>
        </div>
      )}


      <div
        className="row"
        style={{
          justifyContent:
            'space-between',

          alignItems:
            'flex-end',

          gap: 14,
          flexWrap: 'wrap',
        }}
      >
        <div
          className="stack"
          style={{
            gap: 4,
          }}
        >
          <div
            className="muted"
            style={{
              fontSize: 13.5,
            }}
          >
            {
              policy.institution_name
              || '담당 기관 확인 필요'
            }
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
                지원 형태:{' '}
                {
                  policy
                    .support_type
                }
              </span>
            )}

            {policy.support_cycle && (
              <span>
                지원 주기:{' '}
                {
                  policy
                    .support_cycle
                }
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
            to={
              `/welfare/policy/${policy.policy_id}`
            }
            state={{
              recommendation:
                policy,
            }}
            className="btn btn-ghost btn-sm"
          >
            상세보기
          </Link>


          {policy.detail_url && (
            <a
              href={
                policy.detail_url
              }
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary btn-sm"
            >
              {
                getPolicySourceButtonLabel(
                  policy.source_name,
                )
              }
            </a>
          )}


          {!policy.detail_url
            && policy.guide_pdf_url
            && (
              <a
                href={
                  policy
                    .guide_pdf_url
                }
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


// =========================================================
// 추천 정책 없음
// =========================================================

function NoPolicyFound({
  response,
  onEditConditions,
  lookupMode = false,
}) {
  const alternativeActions =
    response.alternative_actions
    || []

  return (
    <div
      className="stack"
      style={{
        gap: 16,
      }}
    >
      <UnderstoodSituation
        text={
          response.understood_situation
        }
      />

      <div className="card card-pad">
        <div
          style={{
            fontSize: 18,
            fontWeight: 800,
            marginBottom: 8,
          }}
        >
          {lookupMode
            ? '입력한 이름과 일치하는 정책을 찾지 못했어요.'
            : '현재 조건과 잘 맞는 정책을 찾지 못했어요.'}
        </div>


        <div
          style={{
            background:
              'var(--teal-50)',

            border:
              '1px solid var(--teal-100)',

            borderRadius: 10,
            padding: '12px 14px',
            marginBottom: 16,
          }}
        >
          <div
            style={{
              fontSize: 12.5,
              fontWeight: 700,
              color:
                'var(--teal-700)',

              marginBottom: 5,
            }}
          >
            {lookupMode
              ? '검색 결과'
              : 'AI 분석 결과'}
          </div>

          <div
            style={{
              fontSize: 14,
              lineHeight: 1.65,
              whiteSpace:
                'pre-wrap',
            }}
          >
            {
              response.reason
              || (
                '현재 조건에 맞는 정책을 찾지 못했습니다.'
              )
            }
          </div>
        </div>


        {alternativeActions.length > 0 && (
          <div
            style={{
              marginBottom: 16,
            }}
          >
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
              style={{
                gap: 8,
              }}
            >
              {alternativeActions.map(
                (
                  action,
                  index,
                ) => (
                  <AlternativeAction
                    key={
                      `${action.action_type}-${index}`
                    }
                    action={
                      action
                    }
                  />
                ),
              )}
            </div>
          </div>
        )}


        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={
            onEditConditions
          }
        >
          {lookupMode
            ? '다른 정책 찾기'
            : '조건 다시 입력하기'}
        </button>
      </div>
    </div>
  )
}


// =========================================================
// 정책 없음 대체 안내
// =========================================================

function AlternativeAction({
  action,
}) {
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
          {
            action.description
          }
        </div>
      )}
    </>
  )


// 보건복지상담센터 홈페이지 이동
if (
  action.action_type
    === 'welfare_hotline'
) {
  return (
    <a
      href="https://www.129.go.kr/"
      target="_blank"
      rel="noopener noreferrer"
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


  // 나누다 기관 찾기 이동
  if (
    action.action_type
      === 'institution_search'
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
      style={{
        padding: 13,
      }}
    >
      {content}
    </div>
  )
}


// =========================================================
// 잘못된 입력·긴급지원 공통 화면
// =========================================================

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
      style={{
        textAlign: 'center',
      }}
    >
      <div
        style={{
          fontSize: 32,
        }}
      >
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
        {
          message
          || '입력 내용을 다시 확인해 주세요.'
        }
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
        style={{
          marginTop: 16,
        }}
        onClick={
          onEditConditions
        }
      >
        다시 입력하기
      </button>
    </div>
  )
}


// =========================================================
// 결과 화면 아래 버튼
// =========================================================

function ResultActions({
  onEditConditions,
  editLabel = '입력 내용 수정하기',
}) {
  return (
    <div
      className="row"
      style={{
        gap: 8,
        flexWrap: 'wrap',
        justifyContent:
          'center',

        marginTop: 4,
      }}
    >
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        onClick={
          onEditConditions
        }
      >
        {editLabel}
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