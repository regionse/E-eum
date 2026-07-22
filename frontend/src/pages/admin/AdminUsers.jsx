import { useState, useEffect } from 'react'
import { listAdminUsers } from '../../api/admin.js'
import { useAsync, Async, PageHead, useToast } from '../../components/ui/index.jsx'

const STATUSES = ['활성', '휴면', '정지']
const statusBadge = { 활성: 'badge-teal', 휴면: 'badge-gray', 정지: 'badge-amber' }
const statusTint = { 활성: 'var(--teal-600)', 휴면: 'var(--muted)', 정지: 'var(--danger)' }

// 액션 = 활성/휴면/정지 즉시 전환 (팝업 없이 · 현재 상태는 강조). 스토리보드 a06/a29
function StatusActions({ current, onSet }) {
  return (
    <div className="row" style={{ gap: 4 }}>
      {STATUSES.map((s) => {
        const on = s === current
        return (
          <button key={s} onClick={() => !on && onSet(s)} disabled={on}
            style={{
              padding: '3px 10px', fontSize: 12.5, fontWeight: on ? 800 : 600, borderRadius: 6,
              color: on ? '#fff' : statusTint[s],
              background: on ? statusTint[s] : 'transparent',
              border: `1px solid ${on ? statusTint[s] : 'var(--line)'}`,
              cursor: on ? 'default' : 'pointer',
            }}>{s}</button>
        )
      })}
    </div>
  )
}

const ROLES = ['전체', '뷰어']

export default function AdminUsers() {
  const state = useAsync(() => listAdminUsers(), [])
  const [rows, setRows] = useState([])
  useEffect(() => { if (state.data) setRows(state.data.map((u) => ({ ...u }))) }, [state.data])
  const [q, setQ] = useState('')
  const [roleF, setRoleF] = useState('전체')
  const [statusF, setStatusF] = useState('전체')
  const toast = useToast()

  const setStatus = (id, s) => {
    setRows((prev) => prev.map((u) => (u.id === id ? { ...u, status: s } : u)))
    toast.show(`${id} 상태를 '${s}'로 변경했어요`)
  }
  const list = rows.filter((u) =>
    u.id.includes(q.trim()) &&
    (roleF === '전체' || u.role === roleF) &&
    (statusF === '전체' || u.status === statusF)
  )

  return (
    <div>
      <PageHead title="회원 관리" sub="가입 회원을 조회하고 상태를 관리해요." />
      <div className="row" style={{ gap: 8, marginBottom: 'var(--sp-4)', flexWrap: 'wrap' }}>
        <input className="input" style={{ maxWidth: 220 }} placeholder="ID 검색" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="select" style={{ width: 'auto' }} value={roleF} onChange={(e) => setRoleF(e.target.value)}>
          {ROLES.map((r) => <option key={r} value={r}>권한 · {r}</option>)}
        </select>
        <select className="select" style={{ width: 'auto' }} value={statusF} onChange={(e) => setStatusF(e.target.value)}>
          {['전체', ...STATUSES].map((s) => <option key={s} value={s}>상태 · {s}</option>)}
        </select>
      </div>
      <div className="card" style={{ overflowX: 'auto' }}>
        <Async state={state}>
          {() => (
            <table className="tbl">
              <thead><tr><th>ID</th><th>나이</th><th>가입일</th><th>상태</th><th>역할</th><th>액션</th></tr></thead>
              <tbody>
                {list.length === 0 ? (
                  <tr><td colSpan={6} className="muted center" style={{ padding: 20 }}>조건에 맞는 회원이 없어요.</td></tr>
                ) : list.map((u) => (
                  <tr key={u.id}>
                    <td style={{ fontWeight: 600 }}>{u.id}</td>
                    <td>{u.age}</td>
                    <td className="muted">{u.joined}</td>
                    <td><span className={`badge ${statusBadge[u.status]}`}>{u.status}</span></td>
                    <td className="muted">{u.role}</td>
                    <td><StatusActions current={u.status} onSet={(s) => setStatus(u.id, s)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Async>
      </div>
      {toast.node}
    </div>
  )
}
