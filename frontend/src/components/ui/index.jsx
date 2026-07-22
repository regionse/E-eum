import { useState, useEffect, useCallback } from 'react'

// ---------- 비동기 로딩 훅 : mock/real 공통으로 로딩·에러·데이터 상태 관리 ----------
// 진짜 API를 붙여도 이 훅은 그대로 쓴다 (Promise만 반환하면 됨).
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ loading: true, error: null, data: null })
  const run = useCallback(() => {
    let alive = true
    setState({ loading: true, error: null, data: null })
    Promise.resolve(fn())
      .then((data) => alive && setState({ loading: false, error: null, data }))
      .catch((error) => alive && setState({ loading: false, error, data: null }))
    return () => { alive = false }
  }, deps) // eslint-disable-line
  useEffect(run, [run])
  return { ...state, reload: run }
}

// ---------- 로딩 ----------
export function Loading({ title = '불러오는 중이에요', sub, steps }) {
  return (
    <div className="loading-box">
      <div className="spinner" />
      <div>
        <div style={{ fontWeight: 700, fontSize: 17 }}>{title}</div>
        {sub && <div className="muted" style={{ marginTop: 4 }}>{sub}</div>}
      </div>
      {steps && (
        <div className="steps" style={{ marginTop: 4 }}>
          {steps.map((s, i) => (
            <span key={s}>
              {i > 0 && <span className="sep"> · </span>}
              <span className="step">{s}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------- 에러 ----------
export function ErrorBox({ error, onRetry }) {
  return (
    <div className="empty">
      <div className="ic">⚠️</div>
      <p style={{ marginTop: 8 }}>{error?.message || '문제가 발생했어요.'}</p>
      {onRetry && <button className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={onRetry}>다시 시도</button>}
    </div>
  )
}

// ---------- 빈 상태 ----------
export function Empty({ icon = '🗂️', children }) {
  return (
    <div className="empty">
      <div className="ic">{icon}</div>
      <p style={{ marginTop: 8 }}>{children}</p>
    </div>
  )
}

// ---------- 비동기 영역 래퍼 : 로딩/에러/성공을 한 번에 ----------
export function Async({ state, children, loading, empty }) {
  if (state.loading) return loading || <Loading />
  if (state.error) return <ErrorBox error={state.error} onRetry={state.reload} />
  const data = state.data
  const isEmpty = data == null || (Array.isArray(data) && data.length === 0)
  if (isEmpty && empty) return empty
  return children(data)
}

// ---------- 모달 ----------
export function Modal({ title, children, onClose, actions }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="dim" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        {title && <h3>{title}</h3>}
        {children}
        {actions && <div className="modal-actions">{actions}</div>}
      </div>
    </div>
  )
}

// ---------- 간단 토스트 ----------
export function useToast() {
  const [msg, setMsg] = useState(null)
  const show = useCallback((m) => {
    setMsg(m)
    setTimeout(() => setMsg(null), 2200)
  }, [])
  const node = msg ? (
    <div style={{
      position: 'fixed', bottom: 28, left: '50%', transform: 'translateX(-50%)',
      background: 'var(--ink)', color: '#fff', padding: '12px 20px', borderRadius: 999,
      fontWeight: 600, fontSize: 14.5, zIndex: 80, boxShadow: 'var(--shadow-lg)',
    }}>{msg}</div>
  ) : null
  return { show, node }
}

// ---------- 적합도 뱃지 ----------
export function FitBadge({ fit }) {
  const map = { best: ['fit-best', '매우 적합'], good: ['fit-good', '적합'], rec: ['fit-rec', '추천'], ref: ['fit-ref', '참고'] }
  const [cls, label] = map[fit] || map.ref
  return <span className={`fit ${cls}`}>{label}</span>
}

// ---------- 페이지 헤더 ----------
export function PageHead({ title, sub, right }) {
  return (
    <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 'var(--sp-5)', gap: 12, flexWrap: 'wrap' }}>
      <div>
        <h1 className="section-title">{title}</h1>
        {sub && <p className="section-sub" style={{ marginBottom: 0 }}>{sub}</p>}
      </div>
      {right}
    </div>
  )
}
