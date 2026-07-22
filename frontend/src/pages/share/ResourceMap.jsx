import { useState } from 'react'
import { Link } from 'react-router-dom'
import { listResources } from '../../api/share.js'
import { useAsync, Async, PageHead } from '../../components/ui/index.jsx'

const typeColor = { 보건소: 'var(--teal-500)', 정신건강: '#7c6cf0', 재활: '#e0955b' }

export default function ResourceMap() {
  const state = useAsync(() => listResources(), [])
  const [sel, setSel] = useState(null)

  return (
    <div className="container page">
      <PageHead title="📍 전문가 기관 연결" sub="가까운 전문 기관을 찾아 온라인 상담을 대면으로 이어드려요."
        right={<Link to="/share" className="btn btn-ghost btn-sm">← 나누다</Link>} />
      <Async state={state}>
        {(rows) => (
          <div className="grid" style={{ gridTemplateColumns: '1fr 1.2fr', gap: 'var(--sp-5)', alignItems: 'start' }}>
            {/* 목록 */}
            <div className="stack" style={{ gap: 10 }}>
              {rows.map((r) => (
                <button key={r.id} className="card card-pad" onClick={() => setSel(r)}
                  style={{ textAlign: 'left', border: sel?.id === r.id ? '2px solid var(--teal-400)' : '1px solid var(--line)', cursor: 'pointer' }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span className="row" style={{ gap: 8 }}>
                      <span style={{ width: 10, height: 10, borderRadius: '50%', background: typeColor[r.type] }} />
                      <b>{r.name}</b>
                    </span>
                    <span className="muted" style={{ fontSize: 13 }}>{r.dist}</span>
                  </div>
                  <p className="muted" style={{ fontSize: 13.5, marginTop: 4 }}>{r.desc} · ☎ {r.phone}</p>
                </button>
              ))}
            </div>
            {/* 지도 (mock: 좌표 핀) */}
            <div className="card" style={{ position: 'sticky', top: 'calc(var(--header-h) + 16px)', overflow: 'hidden' }}>
              <div style={{ position: 'relative', aspectRatio: '4/3', background: 'linear-gradient(160deg,#eaf3f1,#dfeeeb)' }}>
                <div style={{ position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px)', backgroundSize: '40px 40px', opacity: .5 }} />
                {rows.map((r) => (
                  <button key={r.id} onClick={() => setSel(r)} title={r.name}
                    style={{ position: 'absolute', left: `${r.x}%`, top: `${r.y}%`, transform: 'translate(-50%,-100%)', background: 'none', border: 'none', cursor: 'pointer', fontSize: sel?.id === r.id ? 34 : 26, filter: `drop-shadow(0 2px 3px rgba(0,0,0,.2))`, transition: 'font-size .1s' }}>
                    <span style={{ color: typeColor[r.type] }}>📌</span>
                  </button>
                ))}
              </div>
              <div className="card-pad">
                {sel ? (
                  <>
                    <b>{sel.name}</b>
                    <p className="muted" style={{ fontSize: 13.5, margin: '4px 0 10px' }}>{sel.dist} · {sel.desc} · ☎ {sel.phone}</p>
                    <a href="#" className="btn btn-primary btn-sm">길찾기 ↗</a>
                  </>
                ) : <p className="muted" style={{ fontSize: 14 }}>기관을 선택하면 위치와 정보를 볼 수 있어요.</p>}
              </div>
            </div>
          </div>
        )}
      </Async>
    </div>
  )
}
