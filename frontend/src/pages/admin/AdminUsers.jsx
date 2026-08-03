import {
  useEffect,
  useState,
} from 'react'

import {
  listAdminUsers,
  updateAdminUserStatus,
} from '../../api/admin.js'

import {
  Async,
  PageHead,
  useAsync,
  useToast,
} from '../../components/ui/index.jsx'


const CHANGEABLE_STATUSES = [
  '정상',
  '휴면',
  '정지',
]

const STATUS_BADGE = {
  정상: 'badge-teal',
  휴면: 'badge-gray',
  정지: 'badge-amber',
  탈퇴: 'badge-gray',
}

function calculateAge(birthdate) {
  if (!birthdate) {
    return '-'
  }

  const parts = birthdate
    .split('-')
    .map(Number)

  if (
    parts.length !== 3
    || parts.some(Number.isNaN)
  ) {
    return '-'
  }

  const [
    birthYear,
    birthMonth,
    birthDay,
  ] = parts

  const today = new Date()

  let age = (
    today.getFullYear()
    - birthYear
  )

  const birthdayPassed = (
    today.getMonth() + 1
    > birthMonth
    || (
      today.getMonth() + 1
      === birthMonth
      && today.getDate()
      >= birthDay
    )
  )

  if (!birthdayPassed) {
    age -= 1
  }

  return `만 ${age}세`
}


function formatDate(value) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return '-'
  }

  return new Intl.DateTimeFormat(
    'ko-KR',
    {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    },
  ).format(date)
}


function getErrorMessage(error) {
  return (
    error instanceof Error
      ? error.message
      : '회원 상태를 변경하지 못했습니다.'
  )
}


function StatusActions({
  current,
  loading,
  onSet,
}) {
  if (current === '탈퇴') {
    return (
      <span className="muted">
        변경 불가
      </span>
    )
  }

  const labels = {
    정상: '활성',
    휴면: '휴면',
    정지: '정지',
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        flexWrap: 'nowrap',
        minWidth: 128,
      }}
    >
      {CHANGEABLE_STATUSES.map(
        (status) => {
          const isCurrent = (
            status === current
          )

          return (
            <button
              key={status}
              type="button"
              disabled={loading}
              aria-pressed={isCurrent}
              onClick={
                () => {
                  if (!isCurrent) {
                    onSet(status)
                  }
                }
              }
              style={{
                display: 'inline-flex',
                visibility: 'visible',
                alignItems: 'center',
                justifyContent: 'center',
                width: 40,
                minWidth: 40,
                height: 28,
                margin: 0,
                padding: 0,
                border: (
                  status === '정지'
                    ? '1px solid #f1bcbc'
                    : isCurrent
                      ? '1px solid #148779'
                      : '1px solid #d9e0e2'
                ),
                borderRadius: 8,
                backgroundColor: (
                  isCurrent
                    ? (
                      status === '정지'
                        ? '#fff1f1'
                        : status === '휴면'
                          ? '#eef1f2'
                          : '#148779'
                    )
                    : '#fff'
                ),
                color: (
                  status === '정지'
                    ? '#dc3f3f'
                    : (
                      isCurrent
                      && status === '정상'
                        ? '#fff'
                        : '#677579'
                    )
                ),
                fontFamily: 'inherit',
                fontSize: 13,
                fontWeight: (
                  isCurrent ? 700 : 500
                ),
                lineHeight: 1,
                cursor: (
                  isCurrent
                    ? 'default'
                    : 'pointer'
                ),
                opacity: loading ? 0.6 : 1,
              }}
            >
              {labels[status]}
            </button>
          )
        },
      )}
    </div>
  )
}


export default function AdminUsers() {
  const state = useAsync(
    () => listAdminUsers(),
    [],
  )

  const toast = useToast()

  const [rows, setRows] = useState([])
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = (
    useState('전체')
  )
  const [loadingUserIds, setLoadingUserIds] = (
    useState([])
  )


  useEffect(() => {
    if (Array.isArray(state.data)) {
      setRows(
        state.data.map(
          (user) => ({ ...user }),
        ),
      )
    }
  }, [state.data])


  const setStatus = async (
    user,
    nextStatus,
  ) => {
    if (
      loadingUserIds.includes(
        user.user_id,
      )
    ) {
      return
    }

    setLoadingUserIds(
      (previousIds) => [
        ...previousIds,
        user.user_id,
      ],
    )

    try {
      const updatedUser = (
        await updateAdminUserStatus(
          user.user_id,
          nextStatus,
        )
      )

      setRows(
        (previousRows) => (
          previousRows.map(
            (item) => (
              item.user_id
              === updatedUser.user_id
                ? updatedUser
                : item
            ),
          )
        ),
      )

      toast.show(
        `${updatedUser.username} 회원을 `
        + `'${updatedUser.status}' 상태로 변경했어요.`,
      )
    } catch (requestError) {
      toast.show(
        getErrorMessage(requestError),
      )
    } finally {
      setLoadingUserIds(
        (previousIds) => (
          previousIds.filter(
            (id) => id !== user.user_id,
          )
        ),
      )
    }
  }


  const normalizedQuery = (
    query.trim().toLowerCase()
  )

  const filteredRows = rows.filter(
    (user) => {
      const matchesQuery = (
        !normalizedQuery
        || user.username
          .toLowerCase()
          .includes(normalizedQuery)
        || String(user.user_id)
          .includes(normalizedQuery)
      )

      const matchesStatus = (
        statusFilter === '전체'
        || user.status === statusFilter
      )

      return (
        matchesQuery
        && matchesStatus
      )
    },
  )


  return (
    <div
      style={{
        width: '100%',
        minWidth: 0,
      }}
    >
      <style>
        {`
          .admin-user-table {
            width: 100% !important;
            min-width: 0 !important;
          }

          .admin-user-table th,
          .admin-user-table td {
            padding-left: 10px !important;
            padding-right: 10px !important;
          }
        `}
      </style>

      <PageHead
        title="회원 관리"
        sub="가입 회원을 조회하고 상태를 관리해요."
      />

      <div
        className="row"
        style={{
          gap: 8,
          marginBottom: 'var(--sp-4)',
          flexWrap: 'wrap',
        }}
      >
        <input
          className="input"
          style={{
            maxWidth: 240,
          }}
          placeholder="회원 번호 또는 아이디 검색"
          value={query}
          onChange={
            (event) => (
              setQuery(event.target.value)
            )
          }
        />

        <select
          className="select"
          style={{
            width: 'auto',
          }}
          value={statusFilter}
          onChange={
            (event) => (
              setStatusFilter(
                event.target.value,
              )
            )
          }
        >
          {[
            '전체',
            ...CHANGEABLE_STATUSES,
            '탈퇴',
          ].map(
            (status) => (
              <option
                key={status}
                value={status}
              >
                상태 · {
                  status === '정상'
                    ? '활성'
                    : status
                }
              </option>
            ),
          )}
        </select>
      </div>

      <div
        className="card"
        style={{
          width: '100%',
          maxWidth: '100%',
          minWidth: 0,
          overflowX: 'hidden',
        }}
      >
        <Async state={state}>
          {() => (
            <table
              className="tbl admin-user-table"
              style={{
                width: '100%',
                maxWidth: '100%',
                minWidth: 0,
                tableLayout: 'fixed',
                whiteSpace: 'nowrap',
              }}
            >
              <colgroup>
                <col style={{ width: '6%' }} />
                <col style={{ width: '17%' }} />
                <col style={{ width: '8%' }} />
                <col style={{ width: '11%' }} />
                <col style={{ width: '12%' }} />
                <col style={{ width: '12%' }} />
                <col style={{ width: '10%' }} />
                <col style={{ width: '24%' }} />
              </colgroup>

              <thead>
                <tr>
                  <th>번호</th>
                  <th>아이디</th>
                  <th>나이</th>
                  <th>지역</th>
                  <th>가입일</th>
                  <th>최근 로그인</th>
                  <th>상태</th>
                  <th>액션</th>
                </tr>
              </thead>

              <tbody>
                {filteredRows.length === 0
                  ? (
                    <tr>
                      <td
                        colSpan={8}
                        className="muted center"
                        style={{
                          padding: 20,
                        }}
                      >
                        조건에 맞는 회원이 없어요.
                      </td>
                    </tr>
                  )
                  : filteredRows.map(
                    (user) => (
                      <tr key={user.user_id}>
                        <td className="muted">
                          {user.user_id}
                        </td>

                        <td
                          title={user.username}
                          style={{
                            fontWeight: 600,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {user.username}
                        </td>

                        <td>
                          {calculateAge(
                            user.birthdate,
                          )}
                        </td>

                        <td>
                          {user.region_sido || '-'}
                        </td>

                        <td className="muted">
                          {formatDate(
                            user.created_at,
                          )}
                        </td>

                        <td className="muted">
                          {formatDate(
                            user.last_login_at,
                          )}
                        </td>

                        <td>
                          <span
                            className={
                              `badge ${
                                STATUS_BADGE[
                                  user.status
                                ]
                                || 'badge-gray'
                              }`
                            }
                          >
                            {
                              user.status === '정상'
                                ? '활성'
                                : user.status
                            }
                          </span>
                        </td>

                        <td>
                          <StatusActions
                            current={user.status}
                            loading={
                              loadingUserIds.includes(
                                user.user_id,
                              )
                            }
                            onSet={
                              (nextStatus) => (
                                setStatus(
                                  user,
                                  nextStatus,
                                )
                              )
                            }
                          />
                        </td>
                      </tr>
                    ),
                  )}
              </tbody>
            </table>
          )}
        </Async>
      </div>

      {toast.node}
    </div>
  )
}