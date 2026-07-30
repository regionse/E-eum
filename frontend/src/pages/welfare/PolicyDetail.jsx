import {
  useEffect,
  useState,
} from 'react'
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom'
import {
  addPolicyFavorite,
  deletePolicyFavorite,
  getPolicyDetail,
} from '../../api/welfare.js'
import {
  Async,
  FitBadge,
  Loading,
  PageHead,
  useAsync,
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

// WEL-104 · 맞춤 지원 정책 상세보기
export default function PolicyDetail() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const toast = useToast()

  // 추천 결과 화면에서 상세 페이지로 이동할 때
  // 전달받은 적합도와 AI 추천 이유입니다.
  // 덜다 메인이나 즐겨찾기에서 바로 들어오면 없을 수 있습니다.
  const recommendation =
    location.state?.recommendation || null

  const state = useAsync(
    () => {
      const policyId = Number(id)

      if (
        !Number.isInteger(policyId)
        || policyId < 1
      ) {
        throw new Error(
          '올바르지 않은 정책 번호입니다.',
        )
      }

      return getPolicyDetail(policyId)
    },
    [id],
  )

  const [favoriteOverride, setFavoriteOverride] =
    useState(null)
  const [favoriteLoading, setFavoriteLoading] =
    useState(false)

  useEffect(() => {
    if (state.data) {
      setFavoriteOverride(
        Boolean(state.data.is_favorite),
      )
    }
  }, [state.data])

  const goBack = () => {
    navigate(-1)
  }

  const toggleFavorite = async (policy) => {
    if (favoriteLoading) {
      return
    }

    const isFavorite =
      favoriteOverride
      ?? Boolean(policy.is_favorite)

    setFavoriteLoading(true)

    try {
      const result = isFavorite
        ? await deletePolicyFavorite(
          policy.policy_id,
        )
        : await addPolicyFavorite(
          policy.policy_id,
        )

      setFavoriteOverride(
        result.is_favorite,
      )

      toast.show(result.message)
    } catch (error) {
      toast.show(
        error instanceof Error
          ? error.message
          : '즐겨찾기 처리에 실패했습니다.',
      )
    } finally {
      setFavoriteLoading(false)
    }
  }

  return (
    <div
      className="container page"
      style={{ maxWidth: 900 }}
    >
      <PageHead
        title="정책 상세"
        sub="지원 대상과 선정 기준, 신청 방법을 확인해 보세요."
        right={(
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={goBack}
          >
            ← 이전 화면
          </button>
        )}
      />

      <Async
        state={state}
        loading={(
          <Loading
            title="정책 정보를 불러오고 있어요"
            sub="지원 대상과 신청 방법을 확인하고 있어요."
          />
        )}
        empty={(
          <div className="empty">
            <div className="ic">🗂️</div>
            <p style={{ marginTop: 8 }}>
              정책을 찾을 수 없어요.
            </p>
            <Link
              to="/welfare"
              className="btn btn-primary btn-sm"
              style={{ marginTop: 12 }}
            >
              덜다 홈으로
            </Link>
          </div>
        )}
      >
        {(policy) => (
          <PolicyDetailContent
            policy={policy}
            recommendation={recommendation}
            isFavorite={
              favoriteOverride
              ?? Boolean(policy.is_favorite)
            }
            favoriteLoading={favoriteLoading}
            onFavorite={() => toggleFavorite(policy)}
          />
        )}
      </Async>

      {toast.node}
    </div>
  )
}

function PolicyDetailContent({
  policy,
  recommendation,
  isFavorite,
  favoriteLoading,
  onFavorite,
}) {
  const categories = Array.isArray(policy.category)
    ? policy.category
    : []

  const fitness = recommendation?.fitness
  const recommendationReason =
    recommendation?.recommendation_reason

  return (
    <div
      className="stack"
      style={{ gap: 16 }}
    >
      <article className="card card-pad">
        <div
          className="row"
          style={{
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 16,
            marginBottom: 14,
            flexWrap: 'wrap',
          }}
        >
          <div
            className="stack"
            style={{ gap: 8, minWidth: 0 }}
          >
            <div
              className="row"
              style={{
                gap: 7,
                flexWrap: 'wrap',
              }}
            >
              <span className="source-chip">
                {policy.source_name}
              </span>

              <span className="badge badge-gray">
                {policy.region}
              </span>

              {fitness && (
                <span
                  title={
                    FITNESS_LABEL[fitness]
                    || '적합도'
                  }
                >
                  <FitBadge
                    fit={
                      FITNESS_MAP[fitness]
                      || 'ref'
                    }
                  />
                </span>
              )}
            </div>

            <h1
              style={{
                fontSize: 27,
                lineHeight: 1.35,
                letterSpacing: '-0.02em',
              }}
            >
              {policy.policy_name}
            </h1>
          </div>

          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={favoriteLoading}
            aria-pressed={isFavorite}
            onClick={onFavorite}
            style={{ flexShrink: 0 }}
          >
            {favoriteLoading
              ? '처리 중...'
              : isFavorite
                ? '★ 즐겨찾기됨'
                : '☆ 즐겨찾기'}
          </button>
        </div>

        {categories.length > 0 && (
          <div
            className="row"
            style={{
              gap: 7,
              flexWrap: 'wrap',
              marginBottom: 14,
            }}
          >
            {categories.map((category) => (
              <span
                key={category}
                className="chip chip-static"
                style={{
                  fontSize: 12.5,
                  padding: '5px 10px',
                }}
              >
                {category}
              </span>
            ))}
          </div>
        )}

        {policy.policy_summary && (
          <p
            style={{
              color: 'var(--ink-soft)',
              fontSize: 15,
              lineHeight: 1.75,
              whiteSpace: 'pre-wrap',
            }}
          >
            {policy.policy_summary}
          </p>
        )}
      </article>

      {recommendationReason && (
        <section
          className="card card-pad"
          style={{
            background: 'var(--teal-50)',
            borderColor: 'var(--teal-100)',
          }}
        >
          <div
            style={{
              color: 'var(--teal-700)',
              fontSize: 13,
              fontWeight: 800,
              marginBottom: 7,
            }}
          >
            AI 추천 이유
          </div>

          <p
            style={{
              color: 'var(--ink-soft)',
              fontSize: 14.5,
              lineHeight: 1.75,
              whiteSpace: 'pre-wrap',
            }}
          >
            {recommendationReason}
          </p>
        </section>
      )}

      <section className="card card-pad">
        <SectionTitle
          title="기본 정보"
          description="정책을 운영하는 기관과 지원 방식을 확인할 수 있어요."
        />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns:
              'repeat(auto-fit, minmax(170px, 1fr))',
            gap: 12,
            marginTop: 16,
          }}
        >
          <InfoBox
            label="담당 기관"
            value={policy.institution_name}
          />

          <InfoBox
            label="지원 지역"
            value={policy.region}
          />

          <InfoBox
            label="지원 형태"
            value={policy.support_type}
          />

          <InfoBox
            label="지원 주기"
            value={policy.support_cycle}
          />
        </div>
      </section>

      <section className="card card-pad">
        <SectionTitle
          title="지원 대상과 선정 기준"
          description="실제 신청 전 본인의 상황과 세부 조건이 맞는지 확인해 주세요."
        />

        <div
          className="stack"
          style={{ gap: 18, marginTop: 18 }}
        >
          <DetailBlock
            title="지원 대상"
            value={policy.target_detail}
          />

          <DetailBlock
            title="선정 기준"
            value={policy.selection_criteria}
          />
        </div>
      </section>

      <section className="card card-pad">
        <SectionTitle
          title="지원 내용"
          description="제공되는 서비스와 지원 범위를 확인해 보세요."
        />

        <div style={{ marginTop: 18 }}>
          <DetailBlock
            title="지원 내용"
            value={policy.support_content}
            emptyText="등록된 지원 내용이 없어요. 공식 사이트에서 상세 내용을 확인해 주세요."
          />
        </div>
      </section>

      <section className="card card-pad">
        <SectionTitle
          title="신청 방법"
          description="신청 기관과 진행 절차를 확인할 수 있어요."
        />

        <div style={{ marginTop: 18 }}>
          <DetailBlock
            title="신청 절차"
            value={policy.application_method}
            emptyText="등록된 신청 방법이 없어요. 담당 기관이나 공식 사이트에서 확인해 주세요."
          />
        </div>
      </section>

      <div
        className="callout-warn"
        style={{
          fontSize: 13.5,
          lineHeight: 1.7,
        }}
      >
        AI 추천 결과는 정책 탐색을 돕기 위한 안내예요.
        실제 지원 여부와 제출 서류는 담당 기관의 최신 공고와
        심사 결과에 따라 달라질 수 있어요.
      </div>

      <div
        className="card card-pad"
        style={{
          display: 'flex',
          gap: 10,
          justifyContent: 'center',
          flexWrap: 'wrap',
        }}
      >
        {policy.detail_url && (
          <a
            href={policy.detail_url}
            target="_blank"
            rel="noreferrer"
            className="btn btn-primary"
          >
            공식 사이트 보기 ↗
          </a>
        )}

        {policy.guide_pdf_url && (
          <a
            href={policy.guide_pdf_url}
            target="_blank"
            rel="noreferrer"
            className="btn btn-ghost"
          >
            안내문 PDF 보기 ↗
          </a>
        )}

        {!policy.detail_url
          && !policy.guide_pdf_url && (
          <div
            className="muted"
            style={{
              padding: '10px 0',
              fontSize: 14,
            }}
          >
            연결된 공식 사이트나 안내문이 없어요.
          </div>
        )}
      </div>

      <div
        className="row"
        style={{
          justifyContent: 'center',
          gap: 10,
          flexWrap: 'wrap',
        }}
      >
        <Link
          to="/welfare/policy"
          className="btn btn-soft"
        >
          다른 정책 추천받기
        </Link>

        <Link
          to="/welfare"
          className="btn btn-plain"
        >
          덜다 홈으로
        </Link>
      </div>
    </div>
  )
}

function SectionTitle({
  title,
  description,
}) {
  return (
    <div>
      <h2
        style={{
          fontSize: 19,
          marginBottom: 5,
        }}
      >
        {title}
      </h2>

      {description && (
        <p
          className="muted"
          style={{ fontSize: 13.5 }}
        >
          {description}
        </p>
      )}
    </div>
  )
}

function InfoBox({ label, value }) {
  return (
    <div
      style={{
        padding: '14px 15px',
        borderRadius: 12,
        border: '1px solid var(--line)',
        background: 'var(--bg)',
      }}
    >
      <div
        className="muted"
        style={{
          fontSize: 12.5,
          marginBottom: 4,
        }}
      >
        {label}
      </div>

      <div
        style={{
          fontSize: 14.5,
          fontWeight: 700,
          lineHeight: 1.5,
        }}
      >
        {value || '확인 필요'}
      </div>
    </div>
  )
}

function DetailBlock({
  title,
  value,
  emptyText = '등록된 내용이 없어요.',
}) {
  return (
    <div>
      <h3
        style={{
          fontSize: 15,
          marginBottom: 7,
        }}
      >
        {title}
      </h3>

      <div
        style={{
          padding: '15px 16px',
          borderRadius: 12,
          border: '1px solid var(--line)',
          background: 'var(--bg)',
          color: value
            ? 'var(--ink-soft)'
            : 'var(--muted)',
          fontSize: 14,
          lineHeight: 1.8,
          whiteSpace: 'pre-wrap',
          overflowWrap: 'anywhere',
        }}
      >
        {value || emptyText}
      </div>
    </div>
  )
}