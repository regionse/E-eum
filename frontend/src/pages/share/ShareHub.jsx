import { Link } from 'react-router-dom'
import { PageHead } from '../../components/ui/index.jsx'
import RequireLogin from '../../components/RequireLogin.jsx'

export default function ShareHub() {
  return (
    <div className="container page">
      <PageHead
        title="🤝 나누다"
        sub="혼자 감당하지 않도록, 전문가와 가족을 이어드려요."
      />

      <RequireLogin axis="나누다">
        <div
          className="grid"
          style={{
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 'var(--sp-5)',
          }}
        >
          <Link
            to="/share/map"
            className="card card-hover axis-card"
          >
            <div className="ic">🗺️</div>
            <h3>전문가 기관 추천</h3>
            <p className="muted">
              현재 위치 주변의 복지시설을 지도에서 검색해요.
            </p>
            <span className="go">바로가기 →</span>
          </Link>

          <Link
            to="/family"
            className="card card-hover axis-card"
          >
            <div className="ic">💌</div>
            <h3>가족편지</h3>
            <p className="muted">
              가족과 함께 오늘의 돌봄을 기록하고, 돌봄일지로 쌓아 봐요.
            </p>
            <span className="go">바로가기 →</span>
          </Link>
        </div>

        <p className="hint" style={{ marginTop: 14 }}>
          💌 <b>가족편지</b>에 남긴 돌봄 기록은 그대로{' '}
          <b>돌봄일지</b>로 쌓여요. 연결된 가족만 볼 수 있어요.
        </p>
      </RequireLogin>
    </div>
  )
}