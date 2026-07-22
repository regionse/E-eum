import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHead, Modal } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'

// 위치정보 동의(SHA-100) — 전문가·기관 연결(동네 자원 지도)은 위치 동의가 필요.
const LOC_KEY = 'eum_loc_consent'
const hasLocConsent = () => { try { return localStorage.getItem(LOC_KEY) === '1' } catch { return false } }

export default function ShareHub() {
  const nav = useNavigate()
  const [locAsk, setLocAsk] = useState(false)

  // 지도 카드 클릭 — 위치 동의 없으면 SHA-100 팝업으로 가로챈다.
  const guardMap = (e) => {
    if (!hasLocConsent()) { e.preventDefault(); setLocAsk(true) }
  }
  const consentAndGo = () => {
    try { localStorage.setItem(LOC_KEY, '1') } catch { /* noop */ }
    setLocAsk(false); nav('/share/map')
  }

  return (
    <div className="container page">
      <PageHead title="🤝 나누다" sub="혼자 감당하지 않도록, 전문가와 가족을 이어드려요." />
      <RequireLogin axis="나누다">
        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-5)' }}>
          <Link to="/share/map" onClick={guardMap} className="card card-hover axis-card">
            <div className="ic">📍</div>
            <h3>전문가 기관 연결</h3>
            <p className="muted">내 상황에 맞는 동네 전문 기관을 지도로 찾아드려요.</p>
            <span className="go">바로가기 →</span>
          </Link>
          <Link to="/family" className="card card-hover axis-card">
            <div className="ic">💌</div>
            <h3>가족편지</h3>
            <p className="muted">가족과 함께 오늘의 돌봄을 기록하고, 돌봄일지로 쌓아 봐요.</p>
            <span className="go">바로가기 →</span>
          </Link>
        </div>
        <p className="hint" style={{ marginTop: 14 }}>💌 <b>가족편지</b>에 남긴 돌봄 기록은 그대로 <b>돌봄일지</b>로 쌓여요. 연결된 가족만 볼 수 있어요.</p>
      </RequireLogin>

      {/* SHA-100 · 위치정보 동의 */}
      {locAsk && (
        <Modal title="위치정보 동의가 필요해요" onClose={() => setLocAsk(false)}
          actions={<>
            <button className="btn btn-plain" onClick={() => setLocAsk(false)}>취소</button>
            <button className="btn btn-primary" onClick={consentAndGo}>동의하고 계속</button>
          </>}>
          <p className="muted" style={{ lineHeight: 1.7 }}>
            전문가·기관을 내 주변에서 찾으려면 위치정보 동의가 필요해요. 동의하면 동네 자원 지도로 이동해요.
            <br />(동의 내역은 마이페이지 &gt; 동의 관리에서 언제든 바꿀 수 있어요.)
          </p>
        </Modal>
      )}
    </div>
  )
}
