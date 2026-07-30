import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

import {
  getLatestPolicySyncResult,
  getPolicySyncResult,
  startPolicySync,
} from '../../api/admin.js'

import {
  Empty,
  ErrorBox,
  Loading,
  Modal,
  PageHead,
  useToast,
} from '../../components/ui/index.jsx'


// =========================================================
// 상수
// =========================================================

const POLLING_INTERVAL = 1800

const TERMINAL_STATUSES = new Set([
  'completed',
  'completed_with_failures',
])

const STATUS_INFO = {
  api_syncing: {
    label: 'API 호출 중',
    description:
      '중앙부처 복지정책 데이터를 불러오고 있어요.',
    badgeBackground: 'var(--teal-100)',
    badgeColor: 'var(--teal-700)',
  },

  crawling: {
    label: '정책 크롤링 중',
    description:
      '서울·경기 정책 데이터를 수집하고 있어요.',
    badgeBackground: 'var(--teal-100)',
    badgeColor: 'var(--teal-700)',
  },

  embedding: {
    label: '해시 비교 및 임베딩 중',
    description:
      '변경된 정책을 확인하고 벡터 데이터로 변환하고 있어요.',
    badgeBackground: 'var(--teal-100)',
    badgeColor: 'var(--teal-700)',
  },

  completed: {
    label: '최신화 완료',
    description:
      '정책 데이터 최신화가 정상적으로 완료되었어요.',
    badgeBackground: 'var(--teal-100)',
    badgeColor: 'var(--teal-700)',
  },

  completed_with_failures: {
    label: '일부 실패로 완료',
    description:
      '최신화는 완료되었지만 일부 정책 처리에 실패했어요.',
    badgeBackground: 'var(--warn-bg)',
    badgeColor: '#a9760a',
  },
}

const PIPELINE_STEPS = [
  {
    key: 'api_syncing',
    title: 'API 호출',
    description: '중앙부처 복지정책 동기화',
  },
  {
    key: 'crawling',
    title: '정책 크롤링',
    description: '서울·경기 정책 수집',
  },
  {
    key: 'embedding',
    title: '해시 비교 및 임베딩',
    description: '신규·변경 정책 벡터화',
  },
]


// =========================================================
// 공통 함수
// =========================================================

function isTerminalStatus(status) {
  return TERMINAL_STATUSES.has(status)
}

function formatNumber(value) {
  const numberValue = Number(value)

  if (Number.isNaN(numberValue)) {
    return '0'
  }

  return numberValue.toLocaleString()
}

function formatDateTime(value) {
  if (!value) {
    return null
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(
    'ko-KR',
    {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    },
  ).format(date)
}

function getMilestoneText({
  value,
  status,
  activeStatus,
}) {
  if (value) {
    return formatDateTime(value)
  }

  if (status === activeStatus) {
    return '진행 중'
  }

  return '대기 중'
}

function getProgressIndex(status) {
  switch (status) {
    case 'api_syncing':
      return 0

    case 'crawling':
      return 1

    case 'embedding':
      return 2

    case 'completed':
    case 'completed_with_failures':
      return PIPELINE_STEPS.length

    default:
      return 0
  }
}


// =========================================================
// 관리자 덜다 정책 임베딩 관리 페이지
// =========================================================

export default function AdminWelfare() {
  const [confirmOpen, setConfirmOpen] =
    useState(false)

  const [pageLoading, setPageLoading] =
    useState(true)

  const [starting, setStarting] =
    useState(false)

  const [running, setRunning] =
    useState(false)

  const [latestResult, setLatestResult] =
    useState(null)

  const [activeResult, setActiveResult] =
    useState(null)

  const [pageError, setPageError] =
    useState(null)

  const [actionError, setActionError] =
    useState(null)

  const pollingTimerRef = useRef(null)

  const activeExecutionIdRef = useRef(null)

  const {
    show: showToast,
    node: toastNode,
  } = useToast()


  // -------------------------------------------------------
  // 상태 조회 반복 중단
  // -------------------------------------------------------

  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      window.clearTimeout(
        pollingTimerRef.current,
      )

      pollingTimerRef.current = null
    }

    activeExecutionIdRef.current = null
  }, [])


  // -------------------------------------------------------
  // 특정 최신화 실행 상태 반복 조회
  // -------------------------------------------------------

  const pollExecution = useCallback(
    async (executionId) => {
      activeExecutionIdRef.current =
        executionId

      try {
        const result =
          await getPolicySyncResult(
            executionId,
          )

        if (
          activeExecutionIdRef.current
          !== executionId
        ) {
          return
        }

        setActiveResult(result)
        setLatestResult(result)

        if (
          isTerminalStatus(result.status)
        ) {
          stopPolling()
          setRunning(false)

          if (
            result.status
            === 'completed_with_failures'
          ) {
            showToast(
              `정책 최신화가 완료되었지만 ${formatNumber(
                result.failed_count,
              )}건이 실패했습니다.`,
            )
          } else {
            showToast(
              '정책 데이터 최신화가 완료되었습니다.',
            )
          }

          return
        }

        pollingTimerRef.current =
          window.setTimeout(
            () => {
              pollExecution(executionId)
            },
            POLLING_INTERVAL,
          )
      } catch (error) {
        if (
          activeExecutionIdRef.current
          !== executionId
        ) {
          return
        }

        stopPolling()
        setRunning(false)

        setActionError(
          error instanceof Error
            ? error
            : new Error(
                '최신화 상태를 확인하지 못했습니다.',
              ),
        )
      }
    },
    [
      showToast,
      stopPolling,
    ],
  )


  // -------------------------------------------------------
  // 최근 최신화 결과 조회
  // -------------------------------------------------------

  const loadLatestResult = useCallback(
    async () => {
      stopPolling()

      setPageLoading(true)
      setPageError(null)
      setActionError(null)

      try {
        const response =
          await getLatestPolicySyncResult()

        const result =
          response?.result ?? null

        setLatestResult(result)
        setActiveResult(result)

        if (
          result
          && !isTerminalStatus(result.status)
        ) {
          setRunning(true)

          void pollExecution(result.id)
        } else {
          setRunning(false)
        }
      } catch (error) {
        setPageError(
          error instanceof Error
            ? error
            : new Error(
                '최근 정책 최신화 결과를 불러오지 못했습니다.',
              ),
        )
      } finally {
        setPageLoading(false)
      }
    },
    [
      pollExecution,
      stopPolling,
    ],
  )


  // -------------------------------------------------------
  // 최초 진입
  // -------------------------------------------------------

  useEffect(() => {
    void loadLatestResult()

    return () => {
      stopPolling()
    }
  }, [
    loadLatestResult,
    stopPolling,
  ])


  // -------------------------------------------------------
  // 정책 최신화 시작
  // -------------------------------------------------------

  const handleStartSync = async () => {
    setConfirmOpen(false)
    setStarting(true)
    setActionError(null)

    try {
      const response =
        await startPolicySync()

      const initialResult = {
        id: response.execution_id,
        status: 'api_syncing',

        api_sync_at: null,
        crawling_at: null,
        embedding_at: null,

        total_policy_count:
          latestResult?.total_policy_count ?? 0,

        new_count: 0,
        updated_count: 0,
        failed_count: 0,
      }

      setLatestResult(initialResult)
      setActiveResult(initialResult)
      setRunning(true)

      showToast(
        response.message
        || '정책 데이터 최신화를 시작했습니다.',
      )

      void pollExecution(
        response.execution_id,
      )
    } catch (error) {
      setRunning(false)

      setActionError(
        error instanceof Error
          ? error
          : new Error(
              '정책 데이터 최신화를 시작하지 못했습니다.',
            ),
      )
    } finally {
      setStarting(false)
    }
  }


  // -------------------------------------------------------
  // 렌더링 값
  // -------------------------------------------------------

  const result = latestResult

  const statusInfo =
    result
      ? STATUS_INFO[result.status]
      : null

  const syncDisabled =
    starting || running


  return (
    <div>
      <PageHead
        title="덜다 · 정책 임베딩 관리"
        sub="복지정책 데이터를 최신화하고 변경된 정책을 벡터 데이터로 관리해요."
        right={
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={syncDisabled}
            onClick={() => {
              setConfirmOpen(true)
            }}
          >
            {starting
              ? '최신화 시작 중'
              : running
                ? '최신화 진행 중'
                : '정책 데이터 최신화'}
          </button>
        }
      />


      {/* 작업 오류 */}
      {actionError && (
        <div
          className="card card-pad"
          style={{
            marginBottom: 'var(--sp-4)',
            borderColor: '#f0c9c9',
            background: '#fffafa',
          }}
        >
          <div
            className="row"
            style={{
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: 16,
            }}
          >
            <div>
              <b
                style={{
                  color: 'var(--danger)',
                }}
              >
                정책 최신화 처리 중 오류가 발생했습니다.
              </b>

              <p
                className="muted"
                style={{
                  marginTop: 6,
                  fontSize: 14,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {actionError.message}
              </p>
            </div>

            <button
              type="button"
              className="btn btn-plain btn-sm"
              onClick={() => {
                setActionError(null)
              }}
            >
              닫기
            </button>
          </div>
        </div>
      )}


      {/* 최초 데이터 로딩 */}
      {pageLoading && (
        <div className="card card-pad">
          <Loading
            title="최근 최신화 결과를 불러오는 중이에요"
            sub="정책 데이터와 임베딩 실행 상태를 확인하고 있어요."
          />
        </div>
      )}


      {/* 페이지 조회 오류 */}
      {!pageLoading && pageError && (
        <div className="card card-pad">
          <ErrorBox
            error={pageError}
            onRetry={loadLatestResult}
          />
        </div>
      )}


      {/* 실행 이력이 없는 경우 */}
      {!pageLoading
        && !pageError
        && !result
        && (
          <div className="card card-pad">
            <Empty icon="🗂️">
              아직 정책 데이터 최신화 실행 이력이 없습니다.
              <br />
              정책 데이터 최신화 버튼을 눌러 첫 작업을 시작해 주세요.
            </Empty>
          </div>
        )}


      {/* 최신화 결과 */}
      {!pageLoading
        && !pageError
        && result
        && (
          <>
            {/* 현재 상태 */}
            <section
              className="card card-pad"
              style={{
                marginBottom: 'var(--sp-4)',
              }}
            >
              <div
                className="row"
                style={{
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: 16,
                  flexWrap: 'wrap',
                }}
              >
                <div>
                  <div
                    className="row"
                    style={{
                      gap: 9,
                      flexWrap: 'wrap',
                    }}
                  >
                    <h3>
                      최근 정책 최신화 결과
                    </h3>

                    {statusInfo && (
                      <span
                        className="badge"
                        style={{
                          background:
                            statusInfo.badgeBackground,
                          color:
                            statusInfo.badgeColor,
                        }}
                      >
                        {statusInfo.label}
                      </span>
                    )}
                  </div>

                  <p
                    className="muted"
                    style={{
                      marginTop: 7,
                      fontSize: 14,
                    }}
                  >
                    {statusInfo?.description}
                  </p>
                </div>

                <div
                  className="muted"
                  style={{
                    fontSize: 13,
                  }}
                >
                  실행 ID · {result.id}
                </div>
              </div>


              {/* 진행 단계 */}
              <div
                style={{
                  marginTop: 24,
                  paddingTop: 22,
                  borderTop:
                    '1px solid var(--line)',
                }}
              >
                <PolicySyncProgress
                  status={result.status}
                />
              </div>
            </section>


            {/* 집계 결과 */}
            <section
              style={{
                marginBottom: 'var(--sp-4)',
              }}
            >
              <div
                className="row"
                style={{
                  justifyContent: 'space-between',
                  marginBottom: 10,
                  gap: 12,
                  flexWrap: 'wrap',
                }}
              >
                <h3>
                  정책 처리 결과
                </h3>

                <span
                  className="muted"
                  style={{
                    fontSize: 13,
                  }}
                >
                  현재 정책 테이블 기준
                </span>
              </div>

              <div
                className="grid kpi-grid"
              >
                <ResultStatCard
                  label="총 정책 수"
                  value={
                    result.total_policy_count
                  }
                />

                <ResultStatCard
                  label="신규 정책"
                  value={result.new_count}
                />

                <ResultStatCard
                  label="변경된 정책"
                  value={result.updated_count}
                />

                <ResultStatCard
                  label="처리 실패"
                  value={result.failed_count}
                  danger={
                    result.failed_count > 0
                  }
                />
              </div>
            </section>


            {/* 단계별 완료 시각 */}
            <section
              className="card card-pad"
            >
              <div
                className="row"
                style={{
                  justifyContent: 'space-between',
                  gap: 12,
                  flexWrap: 'wrap',
                  marginBottom: 18,
                }}
              >
                <div>
                  <h3>
                    단계별 처리 시각
                  </h3>

                  <p
                    className="muted"
                    style={{
                      marginTop: 5,
                      fontSize: 13.5,
                    }}
                  >
                    각 단계가 완료된 시각을 확인할 수 있어요.
                  </p>
                </div>

                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={running}
                  onClick={loadLatestResult}
                >
                  새로고침
                </button>
              </div>

              <div
                className="stack"
                style={{
                  gap: 0,
                }}
              >
                <MilestoneRow
                  label="중앙부처 API 동기화"
                  value={getMilestoneText({
                    value: result.api_sync_at,
                    status: result.status,
                    activeStatus: 'api_syncing',
                  })}
                  active={
                    result.status
                    === 'api_syncing'
                  }
                />

                <MilestoneRow
                  label="서울·경기 정책 크롤링"
                  value={getMilestoneText({
                    value: result.crawling_at,
                    status: result.status,
                    activeStatus: 'crawling',
                  })}
                  active={
                    result.status
                    === 'crawling'
                  }
                />

                <MilestoneRow
                  label="해시 비교 및 임베딩"
                  value={getMilestoneText({
                    value: result.embedding_at,
                    status: result.status,
                    activeStatus: 'embedding',
                  })}
                  active={
                    result.status
                    === 'embedding'
                  }
                  last
                />
              </div>
            </section>


            <p
              className="muted"
              style={{
                marginTop: 12,
                fontSize: 13,
              }}
            >
              정책 최신화는 중앙부처 API 조회,
              서울·경기 정책 크롤링,
              내용 해시 비교,
              신규·변경 정책 임베딩 순서로 진행됩니다.
            </p>
          </>
        )}


      {/* 최신화 확인 팝업 */}
      {confirmOpen && (
        <Modal
          title="정책 데이터를 최신화할까요?"
          onClose={() => {
            if (!starting) {
              setConfirmOpen(false)
            }
          }}
          actions={
            <>
              <button
                type="button"
                className="btn btn-plain"
                disabled={starting}
                onClick={() => {
                  setConfirmOpen(false)
                }}
              >
                취소
              </button>

              <button
                type="button"
                className="btn btn-primary"
                disabled={starting}
                onClick={handleStartSync}
              >
                {starting
                  ? '시작 중'
                  : '최신화 시작'}
              </button>
            </>
          }
        >
          <div
            className="stack"
            style={{
              gap: 14,
            }}
          >
            <p className="muted">
              중앙부처 정책 API와 서울·경기 정책 데이터를
              최신 상태로 수집합니다.
            </p>

            <div
              style={{
                padding: 14,
                borderRadius: 12,
                background: 'var(--teal-50)',
                border:
                  '1px solid var(--teal-100)',
              }}
            >
              <b
                style={{
                  display: 'block',
                  marginBottom: 6,
                  color: 'var(--teal-700)',
                }}
              >
                최신화 처리 방식
              </b>

              <p
                className="muted"
                style={{
                  fontSize: 13.5,
                }}
              >
                전체 정책을 새로 임베딩하지 않고,
                정책 내용의 해시를 비교해 신규 또는 변경된
                정책만 임베딩합니다.
              </p>
            </div>

            <p
              className="muted"
              style={{
                fontSize: 13,
              }}
            >
              작업 시간은 수집되는 정책 수와 외부 사이트
              응답 속도에 따라 달라질 수 있습니다.
            </p>
          </div>
        </Modal>
      )}


      {/* 최신화 진행 팝업 */}
      {running && activeResult && (
        <Modal title="정책 데이터를 최신화하고 있습니다">
          <PolicySyncRunning
            result={activeResult}
          />
        </Modal>
      )}


      {toastNode}
    </div>
  )
}


// =========================================================
// 처리 결과 카드
// =========================================================

function ResultStatCard({
  label,
  value,
  danger = false,
}) {
  return (
    <div className="card kpi">
      <div
        className="n"
        style={{
          fontSize: 26,
          color: danger
            ? 'var(--danger)'
            : 'var(--teal-700)',
        }}
      >
        {formatNumber(value)}
        <span
          style={{
            marginLeft: 4,
            fontSize: 14,
            fontWeight: 700,
          }}
        >
          건
        </span>
      </div>

      <div className="l">
        {label}
      </div>
    </div>
  )
}


// =========================================================
// 단계별 완료 시각 행
// =========================================================

function MilestoneRow({
  label,
  value,
  active = false,
  last = false,
}) {
  return (
    <div
      className="row"
      style={{
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 16,
        padding: '15px 0',
        borderBottom: last
          ? 'none'
          : '1px solid var(--line)',
      }}
    >
      <div
        className="row"
        style={{
          gap: 9,
        }}
      >
        <span
          style={{
            width: 9,
            height: 9,
            flexShrink: 0,
            borderRadius: '50%',
            background: active
              ? 'var(--teal-500)'
              : 'var(--line)',
            boxShadow: active
              ? '0 0 0 4px var(--teal-100)'
              : 'none',
          }}
        />

        <span
          style={{
            fontWeight: 700,
          }}
        >
          {label}
        </span>
      </div>

      <span
        style={{
          color: active
            ? 'var(--teal-700)'
            : 'var(--ink-soft)',
          fontWeight: active
            ? 700
            : 600,
          textAlign: 'right',
        }}
      >
        {value}
      </span>
    </div>
  )
}


// =========================================================
// 진행 단계 표시
// =========================================================

function PolicySyncProgress({
  status,
}) {
  const progressIndex =
    getProgressIndex(status)

  return (
    <div
      className="grid"
      style={{
        gridTemplateColumns:
          'repeat(auto-fit, minmax(180px, 1fr))',
        gap: 12,
      }}
    >
      {PIPELINE_STEPS.map(
        (step, index) => {
          const completed =
            index < progressIndex

          const active =
            index === progressIndex
            && !isTerminalStatus(status)

          return (
            <div
              key={step.key}
              style={{
                padding: 14,
                borderRadius: 12,
                border: active
                  ? '1px solid var(--teal-300)'
                  : '1px solid var(--line)',
                background: active
                  ? 'var(--teal-50)'
                  : completed
                    ? '#f7fbfa'
                    : 'var(--bg)',
              }}
            >
              <div
                className="row"
                style={{
                  gap: 9,
                  alignItems: 'center',
                }}
              >
                <span
                  style={{
                    width: 28,
                    height: 28,
                    flexShrink: 0,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: '50%',
                    background:
                      completed || active
                        ? 'var(--teal-500)'
                        : '#dfe6e4',
                    color: '#fff',
                    fontWeight: 800,
                    fontSize: 13,
                  }}
                >
                  {completed
                    ? '✓'
                    : index + 1}
                </span>

                <b
                  style={{
                    color: active
                      ? 'var(--teal-700)'
                      : undefined,
                  }}
                >
                  {step.title}
                </b>
              </div>

              <p
                className="muted"
                style={{
                  marginTop: 8,
                  fontSize: 13,
                  lineHeight: 1.5,
                }}
              >
                {step.description}
              </p>
            </div>
          )
        },
      )}
    </div>
  )
}


// =========================================================
// 진행 중 모달 내용
// =========================================================

function PolicySyncRunning({
  result,
}) {
  const statusInfo =
    STATUS_INFO[result.status]
    ?? STATUS_INFO.api_syncing

  return (
    <div
      style={{
        minWidth: 320,
      }}
    >
      <div
        className="loading-box"
        style={{
          padding: '12px 0 22px',
          borderBottom:
            '1px solid var(--line)',
        }}
      >
        <div className="spinner" />

        <div>
          <div
            style={{
              fontWeight: 800,
              fontSize: 17,
              color: 'var(--teal-700)',
            }}
          >
            {statusInfo.label}
          </div>

          <div
            className="muted"
            style={{
              marginTop: 4,
              fontSize: 13.5,
            }}
          >
            {statusInfo.description}
          </div>
        </div>
      </div>

      <div
        style={{
          marginTop: 20,
        }}
      >
        <PolicySyncProgress
          status={result.status}
        />
      </div>

      <div
        className="grid"
        style={{
          gridTemplateColumns:
            'repeat(3, minmax(0, 1fr))',
          gap: 8,
          marginTop: 18,
        }}
      >
        <MiniCount
          label="신규"
          value={result.new_count}
        />

        <MiniCount
          label="변경"
          value={result.updated_count}
        />

        <MiniCount
          label="실패"
          value={result.failed_count}
          danger={
            result.failed_count > 0
          }
        />
      </div>

      <p
        className="muted center"
        style={{
          marginTop: 18,
          fontSize: 12.5,
        }}
      >
        서버에서 백그라운드로 처리하고 있습니다.
        완료되면 화면이 자동으로 갱신됩니다.
      </p>
    </div>
  )
}


// =========================================================
// 진행 중 집계 작은 카드
// =========================================================

function MiniCount({
  label,
  value,
  danger = false,
}) {
  return (
    <div
      style={{
        padding: '11px 8px',
        borderRadius: 10,
        background: 'var(--bg)',
        textAlign: 'center',
      }}
    >
      <b
        style={{
          display: 'block',
          fontSize: 18,
          color: danger
            ? 'var(--danger)'
            : 'var(--teal-700)',
        }}
      >
        {formatNumber(value)}
      </b>

      <span
        className="muted"
        style={{
          fontSize: 12.5,
        }}
      >
        {label}
      </span>
    </div>
  )
}