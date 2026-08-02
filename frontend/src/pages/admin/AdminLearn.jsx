import { useEffect, useState } from 'react'
import { PageHead, Loading } from '../../components/ui/index.jsx'
import { getItdaSyncStatus } from '../../api/admin.js'

// 잇다 관리자 · 임베딩 관리 (ADM-ITD-EMB)
//
// ★ 2026-08-02 — 목업(mock/db.js · FAISS)에서 실제 API 연동으로 교체.
//   예전 화면은 존재하지 않는 값을 보여주고 있었다 — FAISS 인덱스, 가짜 카테고리별 집계.
//   실제 구조는 Pinecone 인덱스 1개 + 네임스페이스 3개(cert / course / job)다.
//
// 값의 출처 — 화면이 계산하지 않는다. 배치가 돌 때 기록한 '사실'을 그대로 보여준다.
//   시각 · 신규 · 변경 · 임베딩  →  itda_sync_log   (배치 실행 기록)
//   총계                        →  각 테이블 COUNT
//   임베딩 완료                 →  content_hash 가 채워진 행 수
const fmtNum = (n) => (n ?? 0).toLocaleString()

export default function AdminLearn() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    let alive = true
    getItdaSyncStatus()
      .then((d) => { if (alive) setData(d) })
      .catch((e) => { if (alive) setErr(e?.message || '현황을 불러오지 못했어요.') })
    return () => { alive = false }   // 언마운트 후 setState 방지
  }, [])

  if (err) {
    return (
      <div>
        <PageHead title="잇다 · 임베딩 관리" sub="자격증 · 직업 · 강좌 벡터 인덱스 현황" />
        <div className="card" style={{ padding: 20 }}>
          <p style={{ margin: 0 }}>{err}</p>
          <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>
            관리자 계정으로 로그인했는지 확인해 주세요.
          </p>
        </div>
      </div>
    )
  }
  if (!data) {
    return (
      <div>
        <PageHead title="잇다 · 임베딩 관리" sub="자격증 · 직업 · 강좌 벡터 인덱스 현황" />
        <Loading title="현황을 불러오는 중이에요" />
      </div>
    )
  }

  const runs = data.runs || []
  //  '신규 · 변경'은 대상별 최근 실행을 합친 값이다.
  //  각 배치가 content_hash 를 비교해 넣은 숫자라 화면이 다시 세지 않는다.
  const sum = (k) => runs.reduce((a, r) => a + (r[k] || 0), 0)

  const totals = [
    ['총 자격증', fmtNum(data.cert_total)],
    ['총 직업', fmtNum(data.job_total)],
    ['총 강좌', fmtNum(data.course_total)],
    ['임베딩 완료', fmtNum((data.cert_embedded || 0) + (data.course_embedded || 0))],
  ]

  return (
    <div>
      <PageHead
        title="잇다 · 임베딩 관리"
        sub="자격증 · 직업 · 강좌를 벡터로 만들어 Pinecone 에 저장 — 잇다 검색의 근간"
      />

      {/* ── 마지막 실행 시각 ── */}
      <div className="card" style={{ padding: 16, marginBottom: 14 }}>
        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <span className="muted">마지막 API 동기화</span>
          <b>{data.last_api_sync || '기록 없음'}</b>
        </div>
        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
          <span className="muted">마지막 임베딩</span>
          <b>{data.last_embedding || '기록 없음'}</b>
        </div>
      </div>

      {/* ── 총계 ── */}
      <div className="grid kpi-grid" style={{ marginBottom: 14 }}>
        {totals.map(([l, n]) => (
          <div key={l} className="card kpi">
            <div className="n" style={{ fontSize: 22 }}>{n}</div>
            <div className="l">{l}</div>
          </div>
        ))}
      </div>

      {/* ── 최근 실행 합계 ── */}
      <div className="grid kpi-grid" style={{ marginBottom: 14 }}>
        <div className="card kpi">
          <div className="n" style={{ fontSize: 22 }}>{fmtNum(sum('inserted'))}</div>
          <div className="l">신규</div>
        </div>
        <div className="card kpi">
          <div className="n" style={{ fontSize: 22 }}>{fmtNum(sum('updated'))}</div>
          <div className="l">변경됨</div>
        </div>
        <div className="card kpi">
          <div className="n" style={{ fontSize: 22 }}>{fmtNum(data.failed_recent)}</div>
          <div className="l">실패 · 최근 7일</div>
        </div>
      </div>

      <p className="muted" style={{ fontSize: 13, marginBottom: 14, lineHeight: 1.7 }}>
        인덱스 1개(<code>eum-itda</code>) · 네임스페이스 3개(cert · course · job) · 3072차원 cosine
        <br />
        「신규 · 변경됨」은 <code>content_hash</code> 비교 결과예요 — 내용이 바뀐 것만 다시 임베딩해요.
        <br />
        직업은 해시를 쓰지 않아 「임베딩 완료」에서 빠져 있어요 (NCS 원본이라 거의 바뀌지 않아요).
      </p>

      {/* ── 실행 이력 ── */}
      <div className="card" style={{ overflowX: 'auto' }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>배치</th><th>완료</th><th>읽음</th><th>신규</th><th>변경</th><th>임베딩</th><th>상태</th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 && (
              <tr>
                <td colSpan={7} className="muted" style={{ textAlign: 'center', padding: 20 }}>
                  아직 실행 기록이 없어요.
                </td>
              </tr>
            )}
            {runs.map((r) => (
              <tr key={r.target}>
                <td style={{ fontWeight: 600 }}>{r.target}</td>
                <td className="muted">{r.finished_at}</td>
                <td>{fmtNum(r.fetched)}</td>
                <td>{fmtNum(r.inserted)}</td>
                <td>{fmtNum(r.updated)}</td>
                <td>{fmtNum(r.embedded)}</td>
                <td>
                  <span className={`badge ${r.status === 'ok' ? 'badge-teal' : 'badge-amber'}`}>
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/*  TODO — 「최신화」 버튼(POST /admin/itda-sync)은 아직 없다.
           배치가 '파일 실행형'이라 함수로 감싸야 하고, 강좌 8,273개 재임베딩은 10분이 넘어
           HTTP 요청이 기다릴 수 없다(BackgroundTasks + 진행상황 폴링이 필요 — 덜다가 그렇게 했다).
           지금은 서버 터미널에서 돌린다:  python -m app.itda.scripts.embed_cert          */}
      <p className="muted" style={{ fontSize: 13, marginTop: 14 }}>
        최신화는 현재 서버에서 배치로 실행해요 — 실행 결과가 위 표에 자동으로 쌓입니다.
      </p>
    </div>
  )
}
