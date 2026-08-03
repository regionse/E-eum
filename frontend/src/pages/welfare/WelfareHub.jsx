import {
  useCallback,
  useEffect,
  useState,
} from 'react'

import {
  Link,
  useNavigate,
} from 'react-router-dom'

import {
  addPolicyFavorite,
  deletePolicyFavorite,
  getPolicyFavorites,
  getPolicyRecommendationDetail,
  getWelfareMain,
} from '../../api/welfare.js'

import RequireLogin from '../../components/RequireLogin.jsx'

import {
  ErrorBox,
  Loading,
  Modal,
  PageHead,
  useToast,
} from '../../components/ui/index.jsx'

import { useAuth } from '../../store/auth.jsx'


// =========================================================
// 기본값
// =========================================================

const EMPTY_MAIN_DATA = {
  recent_recommendations: [],
  favorite_policies: [],
  popular_policies: [],
}

const CARD_GRID_STYLE = {
  display: 'grid',
  gridTemplateColumns:
    'repeat(auto-fill, minmax(230px, 1fr))',
  gap: 12,
}


// =========================================================
// 공통 함수
// =========================================================

function formatDate(value) {
  if (!value) {
    return ''
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(
    'ko-KR',
    {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    },
  ).format(date)
}


function getErrorMessage(error) {
  return error instanceof Error
    ? error.message
    : '요청 처리 중 오류가 발생했습니다.'
}


// =========================================================
// 덜다 메인 페이지
// =========================================================

export default function WelfareHub() {
  const navigate = useNavigate()
  const toast = useToast()
  const { user } = useAuth()

  const [mainData, setMainData] = useState(
    EMPTY_MAIN_DATA,
  )

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // 즐겨찾기 전체보기 모달
  const [
    favoriteModalOpen,
    setFavoriteModalOpen,
  ] = useState(false)

  const [
    favoriteModalItems,
    setFavoriteModalItems,
  ] = useState([])

  const [
    favoriteModalLoading,
    setFavoriteModalLoading,
  ] = useState(false)

  const [
    favoriteModalError,
    setFavoriteModalError,
  ] = useState(null)

  // 즐겨찾기 처리 중인 정책 ID
  const [
    favoriteLoadingIds,
    setFavoriteLoadingIds,
  ] = useState([])

  // 추천 이력 조회 중인 ID
  const [
    historyLoadingId,
    setHistoryLoadingId,
  ] = useState(null)

  // 즐겨찾기 해제 확인 대상
  const [
    confirmDelete,
    setConfirmDelete,
  ] = useState(null)


  // -------------------------------------------------------
  // 덜다 메인 데이터 조회
  // -------------------------------------------------------

  const loadMain = useCallback(async () => {
    if (!user) {
      setMainData(EMPTY_MAIN_DATA)
      setError(null)
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response =
        await getWelfareMain()

      setMainData({
        recent_recommendations:
          Array.isArray(
            response?.recent_recommendations,
          )
            ? response.recent_recommendations
            : [],

        favorite_policies:
          Array.isArray(
            response?.favorite_policies,
          )
            ? response.favorite_policies
            : [],

        popular_policies:
          Array.isArray(
            response?.popular_policies,
          )
            ? response.popular_policies
            : [],
      })
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError
          : new Error(
            '덜다 정보를 불러오지 못했습니다.',
          ),
      )
    } finally {
      setLoading(false)
    }
  }, [user])


  // -------------------------------------------------------
  // 페이지 진입 시 조회
  //
  // 상세 페이지에서 덜다 홈으로 돌아오면
  // WelfareHub가 다시 열리면서 최신 데이터를 조회한다.
  // -------------------------------------------------------

  useEffect(() => {
    void loadMain()
  }, [loadMain])


  // -------------------------------------------------------
  // 즐겨찾기 전체보기
  // -------------------------------------------------------

  const openFavoriteModal = async () => {
    setFavoriteModalOpen(true)
    setFavoriteModalLoading(true)
    setFavoriteModalError(null)

    try {
      const response =
        await getPolicyFavorites()

      setFavoriteModalItems(
        Array.isArray(response?.favorites)
          ? response.favorites
          : [],
      )
    } catch (requestError) {
      setFavoriteModalError(
        requestError instanceof Error
          ? requestError
          : new Error(
            '즐겨찾기 목록을 불러오지 못했습니다.',
          ),
      )
    } finally {
      setFavoriteModalLoading(false)
    }
  }


  // -------------------------------------------------------
  // 최근 추천 결과 다시 보기
  // -------------------------------------------------------

  const viewRecommendation = async (
    history,
  ) => {
    const recommendationId =
      history.recommendation_id

    if (
      historyLoadingId === recommendationId
    ) {
      return
    }

    setHistoryLoadingId(
      recommendationId,
    )

    try {
      const response =
        await getPolicyRecommendationDetail(
          recommendationId,
        )

      navigate(
        '/welfare/policy/result',
        {
          state: {
            response,
            request: null,
          },
        },
      )
    } catch (requestError) {
      toast.show(
        getErrorMessage(requestError),
      )
    } finally {
      setHistoryLoadingId(null)
    }
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

    const wasFavorite =
      Boolean(policy.is_favorite)

    setFavoriteLoadingIds(
      (previousIds) => [
        ...previousIds,
        policyId,
      ],
    )

    try {
      const result = wasFavorite
        ? await deletePolicyFavorite(
          policyId,
        )
        : await addPolicyFavorite(
          policyId,
        )

      const nextFavorite =
        Boolean(result.is_favorite)

      const updatedPolicy = {
        ...policy,
        is_favorite: nextFavorite,
      }


      // 덜다 메인 화면 상태 변경
      setMainData(
        (previousData) => {
          let nextFavorites =
            previousData.favorite_policies
              .filter(
                (item) => (
                  item.policy_id !== policyId
                ),
              )

          if (nextFavorite) {
            nextFavorites = [
              updatedPolicy,
              ...nextFavorites,
            ].slice(0, 5)
          }

          const nextPopularPolicies =
            previousData.popular_policies
              .map((item) => {
                if (
                  item.policy_id !== policyId
                ) {
                  return item
                }

                const currentCount =
                  Number(
                    item.favorite_count,
                  ) || 0

                return {
                  ...item,

                  is_favorite:
                    nextFavorite,

                  favorite_count:
                    Math.max(
                      0,
                      currentCount
                      + (
                        nextFavorite
                          ? 1
                          : -1
                      ),
                    ),
                }
              })

          return {
            ...previousData,

            favorite_policies:
              nextFavorites,

            popular_policies:
              nextPopularPolicies,
          }
        },
      )


      // 즐겨찾기 전체보기 모달 상태 변경
      setFavoriteModalItems(
        (previousItems) => {
          const nextItems =
            previousItems.filter(
              (item) => (
                item.policy_id !== policyId
              ),
            )

          if (!nextFavorite) {
            return nextItems
          }

          return [
            updatedPolicy,
            ...nextItems,
          ]
        },
      )


      toast.show(
        result.message
        || (
          nextFavorite
            ? '즐겨찾기에 추가했습니다.'
            : '즐겨찾기를 해제했습니다.'
        ),
      )
    } catch (requestError) {
      toast.show(
        getErrorMessage(requestError),
      )
    } finally {
      setFavoriteLoadingIds(
        (previousIds) => (
          previousIds.filter(
            (id) => id !== policyId,
          )
        ),
      )

      setConfirmDelete(null)
    }
  }


  // -------------------------------------------------------
  // 화면 데이터
  // -------------------------------------------------------

  const recentRecommendations =
    mainData.recent_recommendations

  const favoritePolicies =
    mainData.favorite_policies

  const popularPolicies =
    mainData.popular_policies

  const isFirstUse = (
    recentRecommendations.length === 0
    && favoritePolicies.length === 0
  )


  return (
    <div
      className="container page"
      style={{
        maxWidth: 900,
      }}
    >
      <PageHead
        title="💧 덜다 · AI 맞춤 정책 추천"
        sub="조건에 맞는 지원 제도를 찾아, 오늘의 부담을 덜어드려요."
      />


      <RequireLogin axis="덜다">
        {loading ? (
          <Loading
            title="덜다 정보를 불러오고 있어요"
            sub="최근 추천과 즐겨찾기 정책을 확인하고 있어요."
          />
        ) : error ? (
          <ErrorBox
            error={error}
            onRetry={loadMain}
          />
        ) : (
          <div
            className="stack"
            style={{
              gap: 28,
            }}
          >
            <HubHero
              recentCount={
                recentRecommendations.length
              }
              favoriteCount={
                favoritePolicies.length
              }
            />


            {isFirstUse ? (
              <FirstVisitSection />
            ) : (
              <>
                <FavoriteSection
                  policies={
                    favoritePolicies
                  }
                  favoriteLoadingIds={
                    favoriteLoadingIds
                  }
                  onAll={
                    openFavoriteModal
                  }
                  onRemove={
                    setConfirmDelete
                  }
                />

                <RecommendationHistorySection
                  recommendations={
                    recentRecommendations
                  }
                  loadingId={
                    historyLoadingId
                  }
                  onView={
                    viewRecommendation
                  }
                />
              </>
            )}


            <PopularPolicySection
              policies={
                popularPolicies
              }
              favoriteLoadingIds={
                favoriteLoadingIds
              }
              onFavorite={
                toggleFavorite
              }
            />
          </div>
        )}
      </RequireLogin>


      {/* 즐겨찾기 전체보기 */}
      {favoriteModalOpen && (
        <Modal
          title="나의 정책 즐겨찾기"
          modalStyle={{
            width: 'calc(100vw - 48px)',
            maxWidth: 700,
          }}
          onClose={() => {
            setFavoriteModalOpen(false)
            setFavoriteModalError(null)
          }}
        >
          {favoriteModalLoading ? (
            <Loading
              title="즐겨찾기를 불러오고 있어요"
            />
          ) : favoriteModalError ? (
            <ErrorBox
              error={favoriteModalError}
              onRetry={openFavoriteModal}
            />
          ) : favoriteModalItems.length === 0 ? (
            <div className="empty">
              <div className="ic">
                ⭐
              </div>

              <p
                style={{
                  marginTop: 8,
                }}
              >
                즐겨찾기한 정책이 없어요.
              </p>
            </div>
          ) : (
            <div
              className="stack"
              style={{
                gap: 8,
                maxHeight: '55vh',
                overflowY: 'auto',
              }}
            >
              {favoriteModalItems.map(
                (policy) => (
                  <FavoriteModalItem
                    key={
                      policy.policy_id
                    }
                    policy={policy}
                    loading={
                      favoriteLoadingIds
                        .includes(
                          policy.policy_id,
                        )
                    }
                    onDetail={() => {
                      setFavoriteModalOpen(
                        false,
                      )
                    }}
                    onRemove={() => {
                      setFavoriteModalOpen(
                        false,
                      )

                      setConfirmDelete({
                        ...policy,
                        is_favorite: true,
                      })
                    }}
                  />
                ),
              )}
            </div>
          )}
        </Modal>
      )}


      {/* 즐겨찾기 삭제 확인 */}
      {confirmDelete && (
        <Modal
          title="즐겨찾기에서 삭제하시겠습니까?"
          onClose={() => {
            setConfirmDelete(null)
          }}
          actions={(
            <>
              <button
                type="button"
                className="btn btn-plain"
                onClick={() => {
                  setConfirmDelete(null)
                }}
              >
                취소
              </button>

              <button
                type="button"
                className="btn btn-danger"
                disabled={
                  favoriteLoadingIds.includes(
                    confirmDelete.policy_id,
                  )
                }
                onClick={() => {
                  void toggleFavorite({
                    ...confirmDelete,
                    is_favorite: true,
                  })
                }}
              >
                {favoriteLoadingIds.includes(
                  confirmDelete.policy_id,
                )
                  ? '삭제 중...'
                  : '삭제'}
              </button>
            </>
          )}
        >
          <p className="muted">
            {confirmDelete.policy_name}
          </p>
        </Modal>
      )}


      {toast.node}
    </div>
  )
}


// =========================================================
// 상단 소개 영역
// =========================================================

function HubHero({
  recentCount,
  favoriteCount,
}) {
  return (
    <section
      className="card card-pad"
      style={{
        background:
          'linear-gradient(135deg, var(--teal-50), var(--sand-50))',

        borderColor:
          'var(--teal-100)',

        padding:
          '28px 30px',
      }}
    >
      <div
        className="row"
        style={{
          justifyContent:
            'space-between',

          alignItems:
            'center',

          gap: 24,
          flexWrap: 'wrap',
        }}
      >
        <div
          className="stack"
          style={{
            gap: 8,
            maxWidth: 540,
          }}
        >
          <span className="eyebrow">
            AI POLICY RECOMMENDATION
          </span>

          <h2
            style={{
              fontSize: 26,
              letterSpacing:
                '-0.02em',
            }}
          >
            복잡한 정책 탐색은 덜고,
            <br />
            내게 필요한 지원만 확인해요.
          </h2>

          <p
            className="muted"
            style={{
              fontSize: 14.5,
              lineHeight: 1.7,
            }}
          >
            생활과 돌봄 상황을 입력하면
            실제 정책의 지원 대상과 선정 기준을
            비교해 추천해 드려요.
          </p>

          <div
            style={{
              marginTop: 8,
            }}
          >
            <Link
              to="/welfare/policy"
              className="btn btn-primary"
            >
              맞춤 지원 정책 찾기
            </Link>
          </div>
        </div>

        <div
          className="row"
          style={{
            gap: 10,
          }}
        >
          <SummaryBox
            label="최근 추천"
            value={`${recentCount}건`}
          />

          <SummaryBox
            label="즐겨찾기"
            value={`${favoriteCount}건`}
          />
        </div>
      </div>
    </section>
  )
}


// =========================================================
// 요약 카드
// =========================================================

function SummaryBox({
  label,
  value,
}) {
  return (
    <div
      style={{
        minWidth: 104,
        padding: '17px 15px',
        borderRadius: 15,

        background:
          'rgba(255, 255, 255, 0.85)',

        border:
          '1px solid var(--line)',

        textAlign: 'center',

        boxShadow:
          'var(--shadow-sm)',
      }}
    >
      <div
        className="muted"
        style={{
          fontSize: 12.5,
        }}
      >
        {label}
      </div>

      <div
        style={{
          marginTop: 3,
          fontSize: 20,
          fontWeight: 800,

          color:
            'var(--teal-700)',
        }}
      >
        {value}
      </div>
    </div>
  )
}


// =========================================================
// 첫 이용자 안내
// =========================================================

function FirstVisitSection() {
  return (
    <section
      className="card card-pad center"
      style={{
        padding:
          '34px 24px',
      }}
    >
      <div
        style={{
          fontSize: 38,
        }}
      >
        👋
      </div>

      <h3
        style={{
          margin:
            '11px 0 7px',
        }}
      >
        아직 덜다를 이용하지 않으셨어요
      </h3>

      <p
        className="muted"
        style={{
          lineHeight: 1.7,
        }}
      >
        몇 가지 질문에 답하면 현재 상황에 맞는 정책을
        적합도가 높은 순서로 찾아드려요.
      </p>

      <Link
        to="/welfare/policy"
        className="btn btn-primary btn-lg"
        style={{
          marginTop: 18,
        }}
      >
        첫 정책 추천 시작하기
      </Link>
    </section>
  )
}


// =========================================================
// 섹션 제목
// =========================================================

function SectionHeader({
  title,
  description,
  action,
}) {
  return (
    <div
      className="row"
      style={{
        justifyContent:
          'space-between',

        alignItems:
          'flex-end',

        gap: 12,
        marginBottom: 10,
        flexWrap: 'wrap',
      }}
    >
      <div>
        <h3
          style={{
            fontSize: 18,
          }}
        >
          {title}
        </h3>

        {description && (
          <p
            className="muted"
            style={{
              marginTop: 3,
              fontSize: 13.5,
            }}
          >
            {description}
          </p>
        )}
      </div>

      {action}
    </div>
  )
}


// =========================================================
// 즐겨찾기 영역
// =========================================================

function FavoriteSection({
  policies,
  favoriteLoadingIds,
  onAll,
  onRemove,
}) {
  return (
    <section>
      <SectionHeader
        title="⭐ 나의 정책 즐겨찾기"
        description="관심 있는 정책을 저장해 두고 다시 확인할 수 있어요."
        action={
          policies.length > 0
            ? (
              <button
                type="button"
                className="btn btn-plain btn-sm"
                onClick={onAll}
              >
                전체보기 ›
              </button>
            )
            : null
        }
      />

      {policies.length === 0 ? (
        <div
          className="card card-pad muted"
        >
          즐겨찾기한 정책이 없어요.
        </div>
      ) : (
        <div
          style={
            CARD_GRID_STYLE
          }
        >
          {policies
            .slice(0, 3)
            .map((policy) => (
              <FavoritePolicyCard
                key={
                  policy.policy_id
                }
                policy={policy}
                loading={
                  favoriteLoadingIds.includes(
                    policy.policy_id,
                  )
                }
                onRemove={() => {
                  onRemove({
                    ...policy,
                    is_favorite: true,
                  })
                }}
              />
            ))}
        </div>
      )}
    </section>
  )
}


// =========================================================
// 즐겨찾기 정책 카드
// =========================================================

function FavoritePolicyCard({
  policy,
  loading,
  onRemove,
}) {
  const categories =
    Array.isArray(policy.category)
      ? policy.category
      : []

  return (
    <article
      className="card card-pad card-hover"
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: 215,
      }}
    >
      <div
        className="row"
        style={{
          justifyContent:
            'space-between',

          alignItems:
            'flex-start',

          gap: 10,
        }}
      >
        <span className="source-chip">
          {policy.region || '전국'}
        </span>

        <button
          type="button"
          className="btn btn-plain btn-sm"
          aria-label="즐겨찾기 해제"
          disabled={loading}
          onClick={onRemove}
          style={{
            fontSize: 20,
            padding: '2px 6px',
          }}
        >
          {loading ? '…' : '★'}
        </button>
      </div>

      <h4
        style={{
          marginTop: 12,
          fontSize: 17,
          lineHeight: 1.5,
        }}
      >
        {policy.policy_name}
      </h4>

      <div
        className="muted"
        style={{
          marginTop: 5,
          fontSize: 12.5,
        }}
      >
        {policy.institution_name
          || policy.source_name
          || '담당 기관 확인 필요'}
      </div>

      {categories.length > 0 && (
        <div
          className="row"
          style={{
            gap: 6,
            flexWrap: 'wrap',
            marginTop: 11,
          }}
        >
          {categories
            .slice(0, 2)
            .map((category) => (
              <span
                key={category}
                className="badge badge-gray"
              >
                {category}
              </span>
            ))}
        </div>
      )}

      <div
        style={{
          marginTop: 'auto',
          paddingTop: 16,
        }}
      >
        <Link
          to={
            `/welfare/policy/${policy.policy_id}`
          }
          className="btn btn-ghost btn-sm"
        >
          상세보기
        </Link>
      </div>
    </article>
  )
}


// =========================================================
// 최근 추천 이력
// =========================================================

function RecommendationHistorySection({
  recommendations,
  loadingId,
  onView,
}) {
  return (
    <section>
      <SectionHeader
        title="🕘 최근 정책 추천 이력"
        description="최근 추천 결과를 최대 3건까지 다시 확인할 수 있어요."
      />

      {recommendations.length === 0 ? (
        <div
          className="card card-pad muted"
        >
          아직 추천받은 이력이 없어요.
        </div>
      ) : (
        <div
          style={
            CARD_GRID_STYLE
          }
        >
          {recommendations.map(
            (history) => (
              <article
                key={
                  history.recommendation_id
                }
                className="card card-pad"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  minHeight: 190,
                }}
              >
                <div
                  className="muted"
                  style={{
                    fontSize: 12.5,
                  }}
                >
                  {formatDate(
                    history.created_at,
                  )}
                </div>

                <div
                  style={{
                    marginTop: 8,
                    fontSize: 17,
                    fontWeight: 800,
                  }}
                >
                  추천 정책{' '}
                  {history.result_count ?? 0}건
                </div>

                {history.understood_situation && (
                  <p
                    className="muted"
                    style={{
                      marginTop: 8,
                      fontSize: 13,
                      lineHeight: 1.6,

                      display:
                        '-webkit-box',

                      WebkitLineClamp: 2,

                      WebkitBoxOrient:
                        'vertical',

                      overflow:
                        'hidden',
                    }}
                  >
                    {history.understood_situation}
                  </p>
                )}

                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{
                    marginTop: 'auto',
                    alignSelf: 'flex-start',
                  }}
                  disabled={
                    loadingId
                    === history.recommendation_id
                  }
                  onClick={() => {
                    void onView(history)
                  }}
                >
                  {loadingId
                    === history.recommendation_id
                    ? '불러오는 중...'
                    : '결과보기'}
                </button>
              </article>
            ),
          )}
        </div>
      )}
    </section>
  )
}


// =========================================================
// 인기 정책 영역
// =========================================================

function PopularPolicySection({
  policies,
  favoriteLoadingIds,
  onFavorite,
}) {
  return (
    <section>
      <SectionHeader
        title="🔥 많은 사용자가 즐겨찾기한 정책 TOP 5"
        description="다른 사용자들이 관심 있게 살펴본 정책이에요."
      />

      {policies.length === 0 ? (
        <div
          className="card card-pad muted"
        >
          아직 인기 정책 집계가 없어요.
        </div>
      ) : (
        <div className="card">
          {policies.map(
            (policy, index) => (
              <PopularPolicyRow
                key={
                  policy.policy_id
                }
                rank={index + 1}
                policy={policy}
                loading={
                  favoriteLoadingIds.includes(
                    policy.policy_id,
                  )
                }
                onFavorite={() => {
                  void onFavorite(policy)
                }}
              />
            ),
          )}
        </div>
      )}
    </section>
  )
}


// =========================================================
// 인기 정책 한 줄
// =========================================================

function PopularPolicyRow({
  rank,
  policy,
  loading,
  onFavorite,
}) {
  const favoriteCount =
    Number(policy.favorite_count) || 0

  return (
    <div className="list-row">
      <Link
        to={
          `/welfare/policy/${policy.policy_id}`
        }
        className="row"
        style={{
          gap: 12,
          minWidth: 0,
          flex: 1,
        }}
      >
        <span
          style={{
            width: 30,
            height: 30,
            borderRadius: '50%',

            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',

            flexShrink: 0,

            background:
              rank <= 3
                ? 'var(--teal-100)'
                : 'var(--bg)',

            color:
              'var(--teal-700)',

            fontSize: 13,
            fontWeight: 800,
          }}
        >
          {rank}
        </span>

        <div
          style={{
            minWidth: 0,
          }}
        >
          <div
            style={{
              fontWeight: 750,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {policy.policy_name}
          </div>

          <div
            className="muted"
            style={{
              marginTop: 2,
              fontSize: 12.5,
            }}
          >
            {policy.institution_name
              || policy.source_name
              || '담당 기관 확인 필요'}

            {' · '}

            {policy.region || '전국'}

            {' · '}

            ⭐ {favoriteCount.toLocaleString()}
          </div>
        </div>
      </Link>

      <button
        type="button"
        className="btn btn-plain btn-sm"
        aria-label={
          policy.is_favorite
            ? '즐겨찾기 해제'
            : '즐겨찾기 추가'
        }
        aria-pressed={
          Boolean(policy.is_favorite)
        }
        disabled={loading}
        onClick={onFavorite}
        style={{
          fontSize: 21,
          padding: '4px 7px',

          color:
            policy.is_favorite
              ? '#f59e0b'
              : 'var(--muted)',
        }}
      >
        {loading
          ? '…'
          : policy.is_favorite
            ? '★'
            : '☆'}
      </button>
    </div>
  )
}


// =========================================================
// 즐겨찾기 전체보기 항목
// =========================================================

function FavoriteModalItem({
  policy,
  loading,
  onDetail,
  onRemove,
}) {
  return (
    <div
      className="list-row"
    >
      <div
        style={{
          minWidth: 0,
        }}
      >
        <div
          style={{
            fontWeight: 700,
          }}
        >
          {policy.policy_name}
        </div>

        <div
          className="muted"
          style={{
            marginTop: 3,
            fontSize: 12.5,
          }}
        >
          {policy.institution_name
            || policy.source_name
            || '담당 기관 확인 필요'}
        </div>
      </div>

      <div
        className="row"
        style={{
          gap: 8,
          flexShrink: 0,
        }}
      >
        <Link
          to={
            `/welfare/policy/${policy.policy_id}`
          }
          className="btn btn-ghost btn-sm"
          onClick={onDetail}
        >
          상세보기
        </Link>

        <button
          type="button"
          className="btn btn-plain btn-sm"
          disabled={loading}
          onClick={onRemove}
        >
          {loading
            ? '처리 중...'
            : '즐겨찾기 해제'}
        </button>
      </div>
    </div>
  )
}