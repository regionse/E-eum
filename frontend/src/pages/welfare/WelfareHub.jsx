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

const EMPTY_MAIN_DATA = {
  recent_recommendations: [],
  favorite_policies: [],
  popular_policies: [],
}

const CARD_GRID_STYLE = {
  display: 'grid',
  gridTemplateColumns:
    'repeat(auto-fill, minmax(240px, 1fr))',
  gap: 14,
}

function formatDate(value) {
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

function normalizeMainData(data) {
  return {
    recent_recommendations:
      data?.recent_recommendations || [],
    favorite_policies:
      data?.favorite_policies || [],
    popular_policies:
      data?.popular_policies || [],
  }
}

// WEL-101 · 덜다 메인
export default function WelfareHub() {
  const navigate = useNavigate()
  const toast = useToast()
  const { user } = useAuth()

  const [mainData, setMainData] = useState(
    EMPTY_MAIN_DATA,
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [favoriteModalOpen, setFavoriteModalOpen] =
    useState(false)
  const [favoriteModalItems, setFavoriteModalItems] =
    useState([])
  const [favoriteModalLoading, setFavoriteModalLoading] =
    useState(false)
  const [favoriteModalError, setFavoriteModalError] =
    useState(null)

  const [favoriteLoadingIds, setFavoriteLoadingIds] =
    useState([])
  const [historyLoadingId, setHistoryLoadingId] =
    useState(null)
  const [confirmDelete, setConfirmDelete] =
    useState(null)

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
      const response = await getWelfareMain()
      setMainData(normalizeMainData(response))
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => {
    loadMain()
  }, [loadMain])

  const openFavoriteModal = async () => {
    setFavoriteModalOpen(true)
    setFavoriteModalLoading(true)
    setFavoriteModalError(null)

    try {
      const response = await getPolicyFavorites()
      setFavoriteModalItems(
        response?.favorites || [],
      )
    } catch (requestError) {
      setFavoriteModalError(requestError)
    } finally {
      setFavoriteModalLoading(false)
    }
  }

  const viewRecommendation = async (history) => {
    if (
      historyLoadingId
      === history.recommendation_id
    ) {
      return
    }

    setHistoryLoadingId(
      history.recommendation_id,
    )

    try {
      const response =
        await getPolicyRecommendationDetail(
          history.recommendation_id,
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

  const toggleFavorite = async (policy) => {
    const policyId = policy.policy_id

    if (
      favoriteLoadingIds.includes(policyId)
    ) {
      return
    }

    const wasFavorite = Boolean(
      policy.is_favorite,
    )

    setFavoriteLoadingIds((previousIds) => [
      ...previousIds,
      policyId,
    ])

    try {
      const result = wasFavorite
        ? await deletePolicyFavorite(policyId)
        : await addPolicyFavorite(policyId)

      setMainData((previousData) => {
        const updatedPolicy = {
          ...policy,
          is_favorite: result.is_favorite,
        }

        let nextFavorites =
          previousData.favorite_policies.filter(
            (item) => (
              item.policy_id !== policyId
            ),
          )

        if (result.is_favorite) {
          nextFavorites = [
            updatedPolicy,
            ...nextFavorites,
          ].slice(0, 5)
        }

        const nextPopular =
          previousData.popular_policies.map(
            (item) => {
              if (item.policy_id !== policyId) {
                return item
              }

              const countChange =
                result.is_favorite
                  ? 1
                  : -1

              return {
                ...item,
                is_favorite:
                  result.is_favorite,
                favorite_count: Math.max(
                  0,
                  (item.favorite_count || 0)
                    + countChange,
                ),
              }
            },
          )

        return {
          ...previousData,
          favorite_policies: nextFavorites,
          popular_policies: nextPopular,
        }
      })

      setFavoriteModalItems((previousItems) => {
        const withoutPolicy =
          previousItems.filter(
            (item) => (
              item.policy_id !== policyId
            ),
          )

        if (!result.is_favorite) {
          return withoutPolicy
        }

        return [
          {
            ...policy,
            is_favorite: true,
          },
          ...withoutPolicy,
        ]
      })

      toast.show(result.message)
    } catch (requestError) {
      toast.show(
        getErrorMessage(requestError),
      )
    } finally {
      setFavoriteLoadingIds((previousIds) => (
        previousIds.filter(
          (id) => id !== policyId,
        )
      ))

      setConfirmDelete(null)
    }
  }

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
      style={{ maxWidth: 940 }}
    >
      <PageHead
        title="💧 덜다 · AI 맞춤 정책 추천"
        sub="내 상황에 맞는 지원 정책을 찾고, 필요한 정보를 한곳에서 확인해 보세요."
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
            style={{ gap: 30 }}
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
                  policies={favoritePolicies}
                  favoriteLoadingIds={
                    favoriteLoadingIds
                  }
                  onAll={openFavoriteModal}
                  onRemove={setConfirmDelete}
                />

                <RecommendationHistorySection
                  recommendations={
                    recentRecommendations
                  }
                  loadingId={historyLoadingId}
                  onView={viewRecommendation}
                />
              </>
            )}

            <PopularPolicySection
              policies={popularPolicies}
              favoriteLoadingIds={
                favoriteLoadingIds
              }
              onFavorite={toggleFavorite}
            />
          </div>
        )}
      </RequireLogin>

      {favoriteModalOpen && (
        <Modal
          title="나의 정책 즐겨찾기"
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
              <div className="ic">⭐</div>
              <p style={{ marginTop: 8 }}>
                즐겨찾기한 정책이 없어요.
              </p>
            </div>
          ) : (
            <div
              className="stack"
              style={{
                gap: 8,
                maxHeight: '58vh',
                overflowY: 'auto',
              }}
            >
              {favoriteModalItems.map(
                (policy) => (
                  <div
                    key={policy.policy_id}
                    className="card card-pad"
                    style={{ padding: 14 }}
                  >
                    <div
                      style={{
                        fontWeight: 750,
                        marginBottom: 4,
                      }}
                    >
                      {policy.policy_name}
                    </div>

                    <div
                      className="muted"
                      style={{
                        fontSize: 12.5,
                        marginBottom: 10,
                      }}
                    >
                      {policy.institution_name
                        || policy.source_name}
                    </div>

                    <div
                      className="row"
                      style={{ gap: 8 }}
                    >
                      <Link
                        to={`/welfare/policy/${policy.policy_id}`}
                        className="btn btn-ghost btn-sm"
                        onClick={() => (
                          setFavoriteModalOpen(false)
                        )}
                      >
                        상세보기
                      </Link>

                      <button
                        type="button"
                        className="btn btn-plain btn-sm"
                        disabled={
                          favoriteLoadingIds.includes(
                            policy.policy_id,
                          )
                        }
                        onClick={() => {
                          setFavoriteModalOpen(false)
                          setConfirmDelete(policy)
                        }}
                      >
                        즐겨찾기 해제
                      </button>
                    </div>
                  </div>
                ),
              )}
            </div>
          )}
        </Modal>
      )}

      {confirmDelete && (
        <Modal
          title="즐겨찾기에서 삭제할까요?"
          onClose={() => setConfirmDelete(null)}
          actions={(
            <>
              <button
                type="button"
                className="btn btn-plain"
                onClick={() => setConfirmDelete(null)}
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
                onClick={() => (
                  toggleFavorite(confirmDelete)
                )}
              >
                삭제
              </button>
            </>
          )}
        >
          <p>{confirmDelete.policy_name}</p>
        </Modal>
      )}

      {toast.node}
    </div>
  )
}

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
        borderColor: 'var(--teal-100)',
        padding: '30px 32px',
      }}
    >
      <div
        className="row"
        style={{
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 24,
          flexWrap: 'wrap',
        }}
      >
        <div
          className="stack"
          style={{ gap: 8, maxWidth: 570 }}
        >
          <span className="eyebrow">
            AI POLICY RECOMMENDATION
          </span>

          <h2
            style={{
              fontSize: 27,
              letterSpacing: '-0.02em',
            }}
          >
            복잡한 정책 탐색은 덜고,
            <br />
            내게 필요한 지원만 확인해요.
          </h2>

          <p
            className="muted"
            style={{ fontSize: 15 }}
          >
            생활과 돌봄 상황을 입력하면 AI가 실제 정책의
            지원 대상과 선정 기준을 비교해 추천해 드려요.
          </p>

          <div style={{ marginTop: 8 }}>
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
          style={{ gap: 12 }}
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

function SummaryBox({ label, value }) {
  return (
    <div
      style={{
        minWidth: 108,
        padding: '18px 16px',
        borderRadius: 16,
        background: 'rgba(255,255,255,.82)',
        border: '1px solid var(--line)',
        textAlign: 'center',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      <div
        className="muted"
        style={{ fontSize: 12.5 }}
      >
        {label}
      </div>
      <div
        style={{
          marginTop: 3,
          fontSize: 21,
          fontWeight: 800,
          color: 'var(--teal-700)',
        }}
      >
        {value}
      </div>
    </div>
  )
}

function FirstVisitSection() {
  return (
    <section
      className="card card-pad center"
      style={{ padding: '36px 24px' }}
    >
      <div style={{ fontSize: 40 }}>👋</div>

      <h3 style={{ margin: '12px 0 7px' }}>
        아직 맞춤 정책 추천 이력이 없어요
      </h3>

      <p className="muted">
        몇 가지 질문에 답하면 현재 상황에 맞는 정책을
        적합도가 높은 순서로 찾아드려요.
      </p>

      <Link
        to="/welfare/policy"
        className="btn btn-primary btn-lg"
        style={{ marginTop: 20 }}
      >
        첫 정책 추천 시작하기
      </Link>
    </section>
  )
}

function SectionHeader({
  title,
  description,
  action,
}) {
  return (
    <div
      className="row"
      style={{
        justifyContent: 'space-between',
        alignItems: 'flex-end',
        gap: 12,
        marginBottom: 12,
        flexWrap: 'wrap',
      }}
    >
      <div>
        <h3 style={{ fontSize: 19 }}>
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
        action={policies.length > 0 ? (
          <button
            type="button"
            className="btn btn-plain btn-sm"
            onClick={onAll}
          >
            전체보기 ›
          </button>
        ) : null}
      />

      {policies.length === 0 ? (
        <div className="card card-pad muted">
          아직 즐겨찾기한 정책이 없어요. 추천 결과나 인기
          정책에서 별표를 눌러 저장해 보세요.
        </div>
      ) : (
        <div style={CARD_GRID_STYLE}>
          {policies.slice(0, 3).map(
            (policy) => (
              <FavoritePolicyCard
                key={policy.policy_id}
                policy={policy}
                loading={
                  favoriteLoadingIds.includes(
                    policy.policy_id,
                  )
                }
                onRemove={() => onRemove(policy)}
              />
            ),
          )}
        </div>
      )}
    </section>
  )
}

function FavoritePolicyCard({
  policy,
  loading,
  onRemove,
}) {
  const categories = Array.isArray(
    policy.category,
  )
    ? policy.category
    : []

  return (
    <article
      className="card card-pad card-hover"
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: 220,
      }}
    >
      <div
        className="row"
        style={{
          justifyContent: 'space-between',
          alignItems: 'flex-start',
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
          style={{ fontSize: 20, padding: '2px 6px' }}
        >
          ★
        </button>
      </div>

      <h4
        style={{
          marginTop: 12,
          fontSize: 17,
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
          || policy.source_name}
      </div>

      {categories.length > 0 && (
        <div
          className="row"
          style={{
            gap: 6,
            flexWrap: 'wrap',
            marginTop: 12,
          }}
        >
          {categories.slice(0, 2).map(
            (category) => (
              <span
                key={category}
                className="badge badge-gray"
              >
                {category}
              </span>
            ),
          )}
        </div>
      )}

      <div
        className="row"
        style={{
          gap: 8,
          marginTop: 'auto',
          paddingTop: 18,
        }}
      >
        <Link
          to={`/welfare/policy/${policy.policy_id}`}
          className="btn btn-ghost btn-sm"
        >
          상세보기
        </Link>
      </div>
    </article>
  )
}

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
        <div className="card card-pad muted">
          아직 추천받은 이력이 없어요.
        </div>
      ) : (
        <div style={CARD_GRID_STYLE}>
          {recommendations.map((history) => (
            <article
              key={history.recommendation_id}
              className="card card-pad"
              style={{
                display: 'flex',
                flexDirection: 'column',
                minHeight: 210,
              }}
            >
              <div
                className="muted"
                style={{ fontSize: 12.5 }}
              >
                {formatDate(history.created_at)}
              </div>

              <div
                style={{
                  marginTop: 8,
                  fontSize: 18,
                  fontWeight: 800,
                }}
              >
                추천 정책 {history.result_count}건
              </div>

              {history.understood_situation && (
                <p
                  className="muted"
                  style={{
                    marginTop: 9,
                    fontSize: 13.5,
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
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
                onClick={() => onView(history)}
              >
                {loadingId
                  === history.recommendation_id
                  ? '불러오는 중...'
                  : '결과보기'}
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function PopularPolicySection({
  policies,
  favoriteLoadingIds,
  onFavorite,
}) {
  return (
    <section>
      <SectionHeader
        title="🔥 많은 사용자가 저장한 정책 TOP 5"
        description="다른 사용자들이 관심 있게 살펴본 정책이에요."
      />

      {policies.length === 0 ? (
        <div className="card card-pad muted">
          아직 인기 정책 집계가 없어요.
        </div>
      ) : (
        <div className="card">
          {policies.map((policy, index) => (
            <PopularPolicyRow
              key={policy.policy_id}
              rank={index + 1}
              policy={policy}
              loading={
                favoriteLoadingIds.includes(
                  policy.policy_id,
                )
              }
              onFavorite={() => (
                onFavorite(policy)
              )}
            />
          ))}
        </div>
      )}
    </section>
  )
}

function PopularPolicyRow({
  rank,
  policy,
  loading,
  onFavorite,
}) {
  return (
    <div className="list-row">
      <Link
        to={`/welfare/policy/${policy.policy_id}`}
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
            color: 'var(--teal-700)',
            fontSize: 13,
            fontWeight: 800,
          }}
        >
          {rank}
        </span>

        <div style={{ minWidth: 0 }}>
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
              || policy.source_name}
            {' · '}
            {policy.region}
            {' · '}
            ⭐ {(policy.favorite_count || 0)
              .toLocaleString()}
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
        disabled={loading}
        onClick={onFavorite}
        style={{
          fontSize: 21,
          padding: '4px 7px',
          color: policy.is_favorite
            ? 'var(--amber-500)'
            : 'var(--muted)',
        }}
      >
        {policy.is_favorite ? '★' : '☆'}
      </button>
    </div>
  )
}