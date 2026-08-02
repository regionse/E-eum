import { useState } from 'react'

import {
  getDashboard,
} from '../../api/admin.js'

import {
  Async,
  PageHead,
  useAsync,
} from '../../components/ui/index.jsx'


const PERIODS = [
  {
    label: '최근 7일',
    value: '7d',
  },
  {
    label: '최근 30일',
    value: '30d',
  },
  {
    label: '최근 3개월',
    value: '3m',
  },
  {
    label: '1년',
    value: '1y',
  },
]


// =========================================================
// AI 기반 서비스 이용 추이
// =========================================================

function LineChart({
  data,
}) {
  if (!data?.length) {
    return (
      <p
        className="muted center"
        style={{
          padding: 30,
        }}
      >
        아직 이용 데이터가 없습니다.
      </p>
    )
  }

  const width = 900
  const height = 320

  const padding = {
    top: 24,
    right: 28,
    bottom: 50,
    left: 64,
  }

  const chartWidth = (
    width
    - padding.left
    - padding.right
  )

  const chartHeight = (
    height
    - padding.top
    - padding.bottom
  )

  const maxValue = Math.max(
    ...data.map(
      (item) => Number(item.count) || 0,
    ),
    0,
  )

  // 세로축을 5칸으로 나눔
  const tickCount = 5

  // 최대값에 맞춰 정수 단위 눈금 계산
  const tickStep = Math.max(
    1,
    Math.ceil(
      maxValue / tickCount,
    ),
  )

  const yMax = (
    tickStep * tickCount
  )

  const yTicks = Array.from(
    {
      length: tickCount + 1,
    },
    (_, index) =>
      index * tickStep,
  )

  const denominator = Math.max(
    data.length - 1,
    1,
  )

  const points = data.map(
    (item, index) => {
      const x = (
        padding.left
        + (
          index
          * chartWidth
        )
        / denominator
      )

      const y = (
        padding.top
        + chartHeight
        - (
          (
            Number(item.count) || 0
          )
          / yMax
        )
        * chartHeight
      )

      return [
        x,
        y,
      ]
    },
  )

  const path = points
    .map(
      (point, index) =>
        `${
          index === 0
            ? 'M'
            : 'L'
        } ${point[0]} ${point[1]}`,
    )
    .join(' ')

  const area = (
    `${path} `
    + `L${
      points[
        points.length - 1
      ][0]
    } ${
      padding.top
      + chartHeight
    } `
    + `L${points[0][0]} ${
      padding.top
      + chartHeight
    } Z`
  )

  // 데이터가 많으면 날짜 라벨 일부만 표시
  const labelStep = (
    data.length > 15
      ? Math.ceil(
        data.length / 7,
      )
      : 1
  )

  return (
    <svg
      viewBox={
        `0 0 ${width} ${height}`
      }
      style={{
        width: '100%',
        minHeight: 300,
        display: 'block',
      }}
    >
      <defs>
        <linearGradient
          id="dashboardTrendGradient"
          x1="0"
          y1="0"
          x2="0"
          y2="1"
        >
          <stop
            offset="0%"
            stopColor="var(--teal-300)"
            stopOpacity=".4"
          />

          <stop
            offset="100%"
            stopColor="var(--teal-300)"
            stopOpacity="0"
          />
        </linearGradient>
      </defs>


      {/* 세로축 단위 */}
      <text
        x={padding.left}
        y={16}
        fontSize="18"
        fontWeight="700"
        fill="var(--muted)"
      >
        건
      </text>


      {/* 가로 눈금선과 세로축 숫자 */}
      {yTicks.map((value) => {
        const y = (
          padding.top
          + chartHeight
          - (
            value / yMax
          )
          * chartHeight
        )

        return (
          <g key={value}>
            <line
              x1={padding.left}
              y1={y}
              x2={
                width
                - padding.right
              }
              y2={y}
              stroke="var(--line)"
              strokeWidth="1"
              strokeDasharray={
                value === 0
                  ? undefined
                  : '4 4'
              }
            />

            <text
              x={padding.left - 14}
              y={y + 5}
              textAnchor="end"
              fontSize="18"
              fontWeight="600"
              fill="var(--muted)"
            >
              {value.toLocaleString()}
            </text>
          </g>
        )
      })}


      {/* 세로축 */}
      <line
        x1={padding.left}
        y1={padding.top}
        x2={padding.left}
        y2={
          padding.top
          + chartHeight
        }
        stroke="var(--line)"
        strokeWidth="1"
      />


      {/* 영역 채우기 */}
      <path
        d={area}
        fill={
          'url(#dashboardTrendGradient)'
        }
      />


      {/* 꺾은선 */}
      <path
        d={path}
        fill="none"
        stroke="var(--teal-500)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />


      {/* 데이터 점과 날짜 눈금 */}
      {points.map(
        (point, index) => {
          const showLabel = (
            index % labelStep === 0
            || index
            === points.length - 1
          )

          return (
            <g key={data[index].label}>
              <circle
                cx={point[0]}
                cy={point[1]}
                r="4.5"
                fill="#fff"
                stroke="var(--teal-500)"
                strokeWidth="2.5"
              />

              {showLabel && (
                <>
                  {/* 가로축 작은 눈금 */}
                  <line
                    x1={point[0]}
                    y1={
                      padding.top
                      + chartHeight
                    }
                    x2={point[0]}
                    y2={
                      padding.top
                      + chartHeight
                      + 6
                    }
                    stroke="var(--line)"
                    strokeWidth="1"
                  />

                  {/* 날짜 */}
                  <text
                    x={point[0]}
                    y={
                      padding.top
                      + chartHeight
                      + 28
                    }
                    textAnchor="middle"
                    fontSize="18"
                    fontWeight="600"
                    fill="var(--muted)"
                  >
                    {data[index].label}
                  </text>
                </>
              )}
            </g>
          )
        },
      )}
    </svg>
  )
}


// =========================================================
// 서비스별 AI 활용 건수
// =========================================================

function DonutChart({
  data,
}) {
  const safeData = (
    data ?? []
  ).map((item) => ({
    ...item,
    count: Number(item.count) || 0,
  }))

  const total = safeData.reduce(
    (sum, item) =>
      sum + item.count,
    0,
  )

  const size = 280
  const center = size / 2
  const radius = 92
  const strokeWidth = 34

  const circumference = (
    2 * Math.PI * radius
  )

  const colors = [
    'var(--teal-600)',
    'var(--teal-400)',
    'var(--teal-200)',
  ]

  let accumulatedLength = 0

  return (
    <div
      className="grid"
      style={{
        gridTemplateColumns:
          'minmax(260px, 340px) minmax(260px, 1fr)',
        alignItems: 'center',
        gap: 38,
      }}
    >
      {/* 도넛 그래프 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        <svg
          viewBox={`0 0 ${size} ${size}`}
          style={{
            width: '100%',
            maxWidth: 320,
            display: 'block',
          }}
          role="img"
          aria-label="서비스별 AI 활용 건수"
        >
          {/* 배경 원 */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="var(--teal-50)"
            strokeWidth={strokeWidth}
          />

          {total > 0 && safeData.map(
            (item, index) => {
              const segmentLength = (
                item.count
                / total
                * circumference
              )

              const dashOffset = (
                -accumulatedLength
              )

              accumulatedLength +=
                segmentLength

              return (
                <circle
                  key={item.service_name}
                  cx={center}
                  cy={center}
                  r={radius}
                  fill="none"
                  stroke={
                    colors[
                      index % colors.length
                    ]
                  }
                  strokeWidth={strokeWidth}
                  strokeDasharray={
                    `${segmentLength} ${
                      circumference
                      - segmentLength
                    }`
                  }
                  strokeDashoffset={
                    dashOffset
                  }
                  strokeLinecap="butt"
                  transform={
                    `rotate(-90 ${center} ${center})`
                  }
                />
              )
            },
          )}

          {/* 중앙 전체 건수 */}
          <text
            x={center}
            y={center - 8}
            textAnchor="middle"
            fontSize="34"
            fontWeight="800"
            fill="var(--ink)"
          >
            {total.toLocaleString()}
          </text>

          <text
            x={center}
            y={center + 25}
            textAnchor="middle"
            fontSize="15"
            fontWeight="600"
            fill="var(--muted)"
          >
            전체 이용 건수
          </text>
        </svg>
      </div>

      {/* 서비스별 범례 */}
      <div
        className="stack"
        style={{
          gap: 16,
        }}
      >
        {safeData.map(
          (item, index) => {
            const percentage = (
              total > 0
                ? (
                  item.count
                  / total
                  * 100
                )
                : 0
            )

            return (
              <div
                key={item.service_name}
                style={{
                  display: 'grid',
                  gridTemplateColumns:
                    'auto 1fr auto',
                  alignItems: 'center',
                  gap: 12,
                  padding: '14px 16px',
                  border:
                    '1px solid var(--line)',
                  borderRadius: 12,
                }}
              >
                <span
                  style={{
                    width: 13,
                    height: 13,
                    borderRadius: '50%',
                    background:
                      colors[
                        index % colors.length
                      ],
                  }}
                />

                <div>
                  <b
                    style={{
                      display: 'block',
                      fontSize: 15,
                    }}
                  >
                    {item.service_name}
                  </b>

                  <span
                    className="muted"
                    style={{
                      fontSize: 13,
                    }}
                  >
                    {percentage.toFixed(1)}%
                  </span>
                </div>

                <b
                  style={{
                    fontSize: 18,
                    color:
                      'var(--teal-700)',
                  }}
                >
                  {item.count.toLocaleString()}
                  <span
                    style={{
                      marginLeft: 3,
                      fontSize: 13,
                    }}
                  >
                    건
                  </span>
                </b>
              </div>
            )
          },
        )}
      </div>
    </div>
  )
}


function formatDateTime(
  value,
) {
  if (!value) {
    return '-'
  }

  return String(value)
    .replace('T', ' ')
    .slice(0, 16)
}


export default function Dashboard() {
  const [period, setPeriod] =
    useState('7d')

  const state = useAsync(
    () => getDashboard(period),
    [period],
  )

  const currentPeriodLabel = (
    PERIODS.find(
      (item) =>
        item.value === period,
    )?.label
    || '최근 7일'
  )

  return (
    <div>
      <PageHead
        title="대시보드"
        sub="서비스 지표 한눈에 보기"
        right={
          <select
            className="select"
            style={{
              width: 'auto',
            }}
            value={period}
            onChange={(event) => {
              setPeriod(
                event.target.value,
              )
            }}
          >
            {PERIODS.map((item) => (
              <option
                key={item.value}
                value={item.value}
              >
                기간 · {item.label}
              </option>
            ))}
          </select>
        }
      />

      <Async state={state}>
        {(dashboard) => (
          <>
            <div
              className="grid kpi-grid"
              style={{
                marginBottom:
                  'var(--sp-5)',
              }}
            >
              {[
                [
                  '총 사용자 수',
                  dashboard
                    .kpis
                    .total_users,
                ],
                [
                  '오늘 로그인한 회원 수',
                  dashboard
                    .kpis
                    .today_logins,
                ],
                [
                  '최근 정책 최신화 실패 수',
                  dashboard
                    .kpis
                    .latest_sync_failures,
                ],
                [
                  '오늘 AI 서비스 이용 건수',
                  dashboard
                    .kpis
                    .today_ai_usage,
                ],
              ].map(
                ([
                  label,
                  value,
                ]) => (
                  <div
                    key={label}
                    className="card kpi"
                  >
                    <div className="n">
                      {(
                        value ?? 0
                      ).toLocaleString()}
                    </div>

                    <div className="l">
                      {label}
                    </div>
                  </div>
                ),
              )}
            </div>

            <div
              className="grid"
              style={{
                gridTemplateColumns: '1fr',
                gap: 'var(--sp-5)',
              }}
            >
              <div className="card card-pad">
                <b
                  style={{
                    display: 'block',
                    marginBottom: 12,
                  }}
                >
                  AI 기반 서비스 이용 추이
                </b>

                <LineChart
                  data={
                    dashboard
                      .ai_service_trend
                  }
                />
              </div>

              <div className="card card-pad">
                <b
                  style={{
                    display: 'block',
                    marginBottom: 12,
                  }}
                >
                  서비스별 AI 활용 건수
                </b>

                <DonutChart
                  data={
                    dashboard
                      .service_ai_usage
                  }
                />
              </div>
            </div>

            <p
              className="muted"
              style={{
                fontSize: 13,
                marginTop: 12,
              }}
            >
              조회 시간 ·{' '}
              {formatDateTime(
                dashboard.queried_at,
              )}
              {' '}
              (기간: {
                currentPeriodLabel
              })
            </p>
          </>
        )}
      </Async>
    </div>
  )
}