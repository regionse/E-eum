import {
  useEffect,
  useState,
} from 'react'

import {
  listAdminAccounts,
  updateAdminAccountStatus,
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
      : '관리자 상태를 변경하지 못했습니다.'
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
          const isCurrent = status === current

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
                fontFamily: 'inherit',
                fontSize: 13,
                fontWeight: isCurrent ? 700 : 500,
                lineHeight: 1,
                cursor: (
                  isCurrent
                    ? 'default'
                    : 'pointer'
                ),
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
                    : isCurrent && status === '정상'
                      ? '#fff'
                      : '#677579'
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


export default function AdminAccounts() {
  const state = useAsync(
    () => listAdminAccounts(),
    [],
  )

  const toast = useToast()

  const [rows, setRows] = useState([])
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = (
    useState('전체')
  )
  const [roleFilter, setRoleFilter] = (
    useState('전체')
  )
  const [loadingUserIds, setLoadingUserIds] = (
    useState([])
  )


  useEffect(() => {
    if (Array.isArray(state.data)) {
      setRows(
        state.data.map(
          (account) => ({ ...account }),
        ),
      )
    }
  }, [state.data])


  const setStatus = async (
    account,
    nextStatus,
  ) => {
    if (
      loadingUserIds.includes(
        account.user_id,
      )
    ) {
      return
    }

    setLoadingUserIds(
      (previousIds) => [
        ...previousIds,
        account.user_id,
      ],
    )

    try {
      const updatedAccount = (
        await updateAdminAccountStatus(
          account.user_id,
          nextStatus,
        )
      )

      setRows(
        (previousRows) => (
          previousRows.map(
            (item) => (
              item.user_id
              === updatedAccount.user_id
                ? updatedAccount
                : item
            ),
          )
        ),
      )

      toast.show(
        `${updatedAccount.username} 관리자를 `
        + `'${updatedAccount.status}' 상태로 변경했어요.`,
      )
    } catch (requestError) {
      toast.show(
        getErrorMessage(requestError),
      )
    } finally {
      setLoadingUserIds(
        (previousIds) => (
          previousIds.filter(
            (id) => id !== account.user_id,
          )
        ),
      )
    }
  }


  const normalizedQuery = (
    query.trim().toLowerCase()
  )

  const filteredRows = rows.filter(
    (account) => {
      const matchesQuery = (
        !normalizedQuery
        || account.username
          .toLowerCase()
          .includes(normalizedQuery)
        || String(account.user_id)
          .includes(normalizedQuery)
      )

      const matchesStatus = (
        statusFilter === '전체'
        || account.status === statusFilter
      )

      const matchesRole = (
        roleFilter === '전체'
        || roleFilter === '관리자'
      )

      return (
        matchesQuery
        && matchesStatus
        && matchesRole
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
          .admin-account-table {
            width: 100% !important;
            min-width: 0 !important;
          }

          .admin-account-table th,
          .admin-account-table td {
            padding-left: 12px !important;
            padding-right: 12px !important;
          }
        `}
      </style>

      <PageHead
        title="관리자 계정 관리"
        sub="관리자·상담사 계정과 권한을 관리해요. (관리자 전용)"
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
            maxWidth: 248,
          }}
          placeholder="ID 검색"
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
            width: 156,
          }}
          value={roleFilter}
          onChange={
            (event) => (
              setRoleFilter(
                event.target.value,
              )
            )
          }
        >
          <option value="전체">
            권한 · 전체
          </option>
          <option value="관리자">
            권한 · 관리자
          </option>
        </select>

        <select
          className="select"
          style={{
            width: 140,
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
              className="tbl admin-account-table"
              style={{
                width: '100%',
                maxWidth: '100%',
                minWidth: 0,
                tableLayout: 'fixed',
                whiteSpace: 'nowrap',
              }}
            >
              <colgroup>
                <col style={{ width: '14%' }} />
                <col style={{ width: '17%' }} />
                <col style={{ width: '11%' }} />
                <col style={{ width: '12%' }} />
                <col style={{ width: '24%' }} />
                <col style={{ width: '22%' }} />
              </colgroup>

              <thead>
                <tr>
                  <th>ID</th>
                  <th>가입일</th>
                  <th>상태</th>
                  <th>권한</th>
                  <th>기능</th>
                  <th>액션</th>
                </tr>
              </thead>

              <tbody>
                {filteredRows.length === 0
                  ? (
                    <tr>
                      <td
                        colSpan={6}
                        className="muted center"
                        style={{
                          padding: 20,
                        }}
                      >
                        조건에 맞는 관리자 계정이 없어요.
                      </td>
                    </tr>
                  )
                  : filteredRows.map(
                    (account) => (
                      <tr key={account.user_id}>
                        <td
                          title={account.username}
                          style={{
                            fontWeight: 600,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {account.username}
                        </td>

                        <td className="muted">
                          {formatDate(
                            account.created_at,
                          )}
                        </td>

                        <td>
                          <span
                            className={
                              `badge ${
                                STATUS_BADGE[
                                  account.status
                                ]
                                || 'badge-gray'
                              }`
                            }
                          >
                            {
                              account.status === '정상'
                                ? '활성'
                                : account.status
                            }
                          </span>
                        </td>

                        <td>
                          <span className="badge badge-teal">
                            관리자
                          </span>
                        </td>

                        <td
                          className="muted"
                          title="열람·수정·작성·삭제"
                          style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          열람·수정·작성·삭제
                        </td>

                        <td>
                          <StatusActions
                            current={account.status}
                            loading={
                              loadingUserIds.includes(
                                account.user_id,
                              )
                            }
                            onSet={
                              (nextStatus) => (
                                setStatus(
                                  account,
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