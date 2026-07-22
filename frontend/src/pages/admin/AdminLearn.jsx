import { useState } from 'react'
import { PageHead, Modal, useToast, Loading } from '../../components/ui/index.jsx'
import { learnIndex } from '../../mock/db.js'

// 잇다 관리자 · 임베딩 관리 (ADM-ITD-EMB) — K-MOOC 공개강좌 → FAISS 인덱스 적재·재구축
export default function AdminLearn() {
  const [confirm, setConfirm] = useState(false)
  const [running, setRunning] = useState(false)
  const toast = useToast()
  const d = learnIndex
  const fresh = d.pending === 0

  const rebuild = async () => {
    setConfirm(false); setRunning(true)
    await new Promise((r) => setTimeout(r, 1800)) // 증분 임베딩·인덱스 원자적 교체 흉내
    setRunning(false)
    toast.show('인덱스 재구축 완료 · 상태가 최신으로 갱신되었어요')
  }

  const stats = [
    ['총 공개강좌', d.total.toLocaleString()],
    ['임베딩 완료', d.embedded.toLocaleString()],
    ['미임베딩', d.pending.toLocaleString()],
    ['인덱스 상태', fresh ? '최신 ✓' : '갱신 필요'],
  ]

  return (
    <div>
      <PageHead title="잇다 · 임베딩 관리"
        sub="K-MOOC 공개강좌 임베딩 → FAISS 인덱스 적재·관리 · 잇다 유사도 검색의 근간"
        right={<button className="btn btn-primary btn-sm" onClick={() => setConfirm(true)}>인덱스 재구축</button>} />

      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
        <b>인덱스 상태</b>
        <span className="muted" style={{ fontSize: 13.5 }}>· 마지막 재구축 {d.lastRebuild}</span>
      </div>

      <div className="grid kpi-grid" style={{ marginBottom: 14 }}>
        {stats.map(([l, n]) => (
          <div key={l} className="card kpi"><div className="n" style={{ fontSize: 22 }}>{n}</div><div className="l">{l}</div></div>
        ))}
      </div>

      <p className="muted" style={{ fontSize: 13, marginBottom: 14 }}>
        모델 {d.model} · {d.dim} · 벡터 {d.vector} · 임베딩 텍스트 = 제목＋[대분류·중분류]＋설명
      </p>

      <div className="card" style={{ overflowX: 'auto' }}>
        <table className="tbl">
          <thead><tr><th>대분류</th><th>강좌 수</th><th>임베딩</th><th>상태</th></tr></thead>
          <tbody>
            {d.categories.map((c) => (
              <tr key={c.name}>
                <td style={{ fontWeight: 600 }}>{c.name}</td>
                <td>{c.courses.toLocaleString()}</td>
                <td>{c.embedded.toLocaleString()}</td>
                <td><span className="badge badge-teal">{c.status}</span></td>
              </tr>
            ))}
            <tr>
              <td style={{ fontWeight: 800 }}>합계</td>
              <td style={{ fontWeight: 800 }}>{d.total.toLocaleString()}</td>
              <td style={{ fontWeight: 800 }}>{d.embedded.toLocaleString()}</td>
              <td />
            </tr>
          </tbody>
        </table>
      </div>

      {confirm && (
        <Modal title="인덱스를 재구축할까요?" onClose={() => setConfirm(false)}
          actions={<><button className="btn btn-plain" onClick={() => setConfirm(false)}>취소</button>
            <button className="btn btn-primary" onClick={rebuild}>재구축</button></>}>
          <p className="muted">신규·변경분만 증분 임베딩해 인덱스를 재구축해요. 재구축 중에도 기존 인덱스로 검색은 계속됩니다.</p>
        </Modal>
      )}
      {running && (
        <Modal title="인덱스 재구축 진행 중">
          <Loading title="재구축 중이에요" sub="증분 임베딩 · FAISS 인덱스 원자적 교체" />
        </Modal>
      )}
      {toast.node}
    </div>
  )
}
