import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHead, useToast } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'
import { popularCourses } from '../../mock/db.js'
import { getResume } from '../../api/learn.js'
import { getFavs, getRecent, hasUsed, toggleFav, isFav } from '../../store/history.js'

function CourseRow({ c, onFav, favActive }) {
  const name = c.name || c.title
  return (
    <div className="list-row">
      <div className="row" style={{ gap: 12, minWidth: 0 }}>
        <span className="badge badge-teal">강좌</span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700 }}>{name}</div>
          <div className="muted" style={{ fontSize: 13 }}>
            {c.provider}{c.favCount ? ` · ⭐ ${c.favCount.toLocaleString()}` : ''}
          </div>
        </div>
      </div>
      <div className="row" style={{ gap: 2 }}>
        {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="btn btn-plain btn-sm" aria-label="강좌 이동">↗</a>}
        <button className="btn btn-plain btn-sm" onClick={() => onFav(c)} aria-label="즐겨찾기">{favActive ? '★' : '☆'}</button>
      </div>
    </div>
  )
}

function Section({ title, desc, children }) {
  return (
    <div style={{ marginBottom: 'var(--sp-6)' }}>
      <h3 style={{ fontSize: 17, marginBottom: 2 }}>{title}</h3>
      {desc && <p className="muted" style={{ fontSize: 13.5, marginBottom: 10 }}>{desc}</p>}
      {children}
    </div>
  )
}

// 내 미래설계지도 — 저장된 지도. 헤더를 누르면 강좌 목록 + 지금 듣는 강좌가 펼쳐진다.
// (잇다의 모든 학습이 '하나의 미래설계지도' 안에 담겨 있다는 걸 보여주는 중심 카드)
function MyMap({ resume }) {
  const [open, setOpen] = useState(true)
  const courses = resume.courses || []
  const current = courses[0]
  return (
    <div className="card" style={{ marginBottom: 'var(--sp-6)', overflow: 'hidden' }}>
      <div role="button" tabIndex={0} onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setOpen((o) => !o)}
        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, padding: '16px 18px', background: 'var(--teal-50)' }}>
        <div style={{ minWidth: 0 }}>
          <b style={{ fontSize: 16 }}>🗺️ {resume.goal} · 미래설계지도</b>
          <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
            지금 듣고 있는: <b style={{ color: 'var(--teal-700)' }}>{current?.title || '—'}</b> · {resume.weeksText}
          </div>
        </div>
        <span style={{ fontSize: 18, color: 'var(--teal-600)', flexShrink: 0 }}>{open ? '▾' : '▸'}</span>
      </div>
      {open && (
        <div style={{ padding: '10px 18px 18px' }}>
          {courses.map((c, i) => (
            <div key={c.id} className="list-row">
              <div className="row" style={{ gap: 12, minWidth: 0 }}>
                <span style={{ width: 24, height: 24, borderRadius: '50%', flexShrink: 0, fontWeight: 800, fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', background: i === 0 ? 'var(--teal-500)' : 'var(--teal-100)', color: i === 0 ? '#fff' : 'var(--teal-700)' }}>{i + 1}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 700 }}>{c.title}</div>
                  <div className="muted" style={{ fontSize: 12.5 }}>{c.provider} · {c.hours}시간 · 무료</div>
                </div>
              </div>
              <div className="row" style={{ gap: 6, flexShrink: 0 }}>
                <span className="badge" style={{ fontSize: 11, background: i === 0 ? 'var(--teal-100)' : 'transparent', color: i === 0 ? 'var(--teal-700)' : 'var(--muted, #888)' }}>{i === 0 ? '듣는 중' : '예정'}</span>
                {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="btn btn-plain btn-sm" aria-label="강좌 이동">↗</a>}
              </div>
            </div>
          ))}
          <div className="row" style={{ gap: 8, marginTop: 8, paddingTop: 10, borderTop: '1px dashed var(--teal-100)' }}>
            <span style={{ width: 24, height: 24, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--teal-700)', color: '#fff', fontSize: 13 }}>◎</span>
            <b style={{ color: 'var(--teal-700)' }}>{resume.goal}</b>
            <span className="muted" style={{ fontSize: 12.5 }}>도착점</span>
          </div>
          <Link to="/learn/chat" className="btn btn-primary btn-sm" style={{ marginTop: 14 }}>대화로 이어가기 →</Link>
        </div>
      )}
    </div>
  )
}

export default function LearnHub() {
  const nav = useNavigate()
  const toast = useToast()
  const [, force] = useState(0)

  const resume = getResume()
  const used = hasUsed('learn')
  const favs = getFavs('learn')
  const recent = getRecent('learn', 5)

  const onFav = (c) => {
    const added = toggleFav('learn', { id: c.id, name: c.name || c.title, provider: c.provider, url: c.url })
    toast.show(added ? '즐겨찾기에 담았어요' : '즐겨찾기에서 뺐어요')
    force((n) => n + 1)
  }
  const rows = (list) => (
    <div className="card">
      {list.map((c) => <CourseRow key={c.id} c={c} onFav={onFav} favActive={isFav('learn', c.id)} />)}
    </div>
  )

  return (
    <div className="container page" style={{ maxWidth: 860 }}>
      <PageHead title="🌱 잇다" sub="되고 싶은 모습을 말하면, 지금 위치부터 목표까지 무료 강좌로 지도를 그려드려요."
        right={<Link to="/learn/chat" className="btn btn-primary btn-sm">＋ 새 목표 시작</Link>} />

      <RequireLogin axis="잇다">
        {resume ? (
          <MyMap resume={resume} />
        ) : !used ? (
          <>
            {/* 신규(빈 상태) 온보딩 — ITD-100E */}
            <div className="card card-pad center" style={{ background: 'var(--teal-50)', borderColor: 'var(--teal-100)', marginBottom: 'var(--sp-6)' }}>
              <div style={{ fontSize: 34 }}>🌱</div>
              <h3 style={{ margin: '10px 0 6px' }}>아직 그려둔 지도가 없어요</h3>
              <p className="muted">되고 싶은 모습을 말하면, 지금 위치부터 목표까지 무료 강좌로 첫 배움 지도를 그려드릴게요.</p>
              <button className="btn btn-primary btn-lg" style={{ marginTop: 16 }} onClick={() => nav('/learn/chat')}>첫 지도 그리기 →</button>
            </div>
            <p className="muted" style={{ fontSize: 13.5, marginBottom: 'var(--sp-6)' }}>⭐ 아직 즐겨찾은 강좌가 없어요. 마음에 드는 강좌에 ☆를 눌러보세요.</p>
          </>
        ) : null}

        {favs.length > 0 && <Section title="⭐ 즐겨찾기" desc="찜해둔 강좌예요.">{rows(favs)}</Section>}
        {recent.length > 0 && <Section title="🕘 최근 본 강좌" desc="최근 잇다에서 추천받은 강좌예요.">{rows(recent)}</Section>}
        <Section title="🔥 지금 인기 있는 무료 강좌" desc="즐겨찾기를 많이 받은 순이에요.">{rows(popularCourses)}</Section>
      </RequireLogin>
      {toast.node}
    </div>
  )
}
