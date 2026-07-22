import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { PageHead, Empty } from '../../components/ui/index.jsx'

// 자료실 = 이음이 다루는 제도·강좌·자격을 한눈에 (추천 아닌 '직접 찾아보기' 보조 서랍)
// mock 데이터. 실제로는 공공데이터(복지로·K-MOOC·Q-Net) 기반으로 채워짐.
const ITEMS = [
  { id: 1, type: '제도', title: '가족돌봄청년 자기돌봄비', org: '보건복지부', tag: '경제지원', to: '/welfare' },
  { id: 2, type: '제도', title: '청년 월세 특별지원', org: '국토교통부', tag: '주거', to: '/welfare' },
  { id: 3, type: '제도', title: '재난적 의료비 지원', org: '국민건강보험공단', tag: '의료비', to: '/welfare' },
  { id: 4, type: '제도', title: '청년내일저축계좌', org: '보건복지부', tag: '자산형성', to: '/welfare' },
  { id: 5, type: '제도', title: '긴급복지 생계지원', org: '보건복지부', tag: '긴급지원', to: '/welfare' },
  { id: 6, type: '강좌', title: '사회복지실천론', org: 'K-MOOC', tag: '복지', to: '/learn' },
  { id: 7, type: '강좌', title: '노인심리상담 기초', org: 'K-MOOC', tag: '상담', to: '/learn' },
  { id: 8, type: '강좌', title: '요양보호 실무의 이해', org: 'K-MOOC', tag: '돌봄', to: '/learn' },
  { id: 9, type: '강좌', title: '초보자를 위한 정보처리 입문', org: 'K-MOOC', tag: 'IT', to: '/learn' },
  { id: 10, type: '자격', title: '사회복지사 2급', org: '한국사회복지사협회', tag: '복지', to: '/learn' },
  { id: 11, type: '자격', title: '요양보호사', org: '국시원', tag: '돌봄', to: '/learn' },
  { id: 12, type: '자격', title: '정보처리기사', org: '한국산업인력공단', tag: 'IT', to: '/learn' },
]
const TYPES = ['전체', '제도', '강좌', '자격']

export default function Library() {
  const [q, setQ] = useState('')
  const [type, setType] = useState('전체')

  const list = useMemo(() => {
    const kw = q.trim().toLowerCase()
    return ITEMS.filter((it) =>
      (type === '전체' || it.type === type) &&
      (kw === '' || (it.title + it.org + it.tag).toLowerCase().includes(kw))
    )
  }, [q, type])

  return (
    <div className="container page">
      <PageHead title="🗂️ 자료실" sub="이음이 다루는 제도·강좌·자격을 한눈에. 추천 말고 직접 찾아보고 싶을 때." />

      {/* 검색 + 유형 필터 */}
      <div className="card card-pad" style={{ marginBottom: 'var(--sp-5)' }}>
        <input
          className="input"
          placeholder="검색 (예: 월세, 복지, 요양, 정보처리)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="row" style={{ gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          {TYPES.map((t) => (
            <button key={t} className={`chip ${type === t ? 'on' : ''}`} onClick={() => setType(t)}>{t}</button>
          ))}
        </div>
      </div>

      <p className="muted" style={{ fontSize: 13.5, marginBottom: 10 }}>총 {list.length}건</p>

      {/* 결과 */}
      {list.length === 0 ? (
        <Empty icon="🔍">검색 결과가 없어요. 다른 말로 찾아보실래요?</Empty>
      ) : (
        <div className="card">
          {list.map((it) => (
            <Link key={it.id} to={it.to} className="list-row">
              <div className="row" style={{ gap: 12 }}>
                <span className="badge badge-teal">{it.type}</span>
                <div>
                  <div style={{ fontWeight: 700 }}>{it.title}</div>
                  <div className="muted" style={{ fontSize: 13 }}>{it.org} · {it.tag}</div>
                </div>
              </div>
              <span className="muted" aria-hidden>→</span>
            </Link>
          ))}
        </div>
      )}

      <p className="muted center" style={{ marginTop: 'var(--sp-5)', fontSize: 13 }}>
        * 목업 데이터입니다. 실제 서비스에선 공공데이터(복지로 · K-MOOC · Q-Net) 기반으로 채워져요.
      </p>
    </div>
  )
}
