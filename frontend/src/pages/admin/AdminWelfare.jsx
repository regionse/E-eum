import { useState } from 'react'
import { PageHead, Modal, useToast, Loading } from '../../components/ui/index.jsx'
import { policyEmbed } from '../../mock/db.js'

// 덜다 관리자 · 정책 임베딩 관리 (ADDUL-001) — 정책 데이터 최신화 → 임베딩
export default function AdminWelfare() {
  const [confirm, setConfirm] = useState(false)
  const [running, setRunning] = useState(false)
  const toast = useToast()
  const d = policyEmbed

  const run = async () => {
    setConfirm(false); setRunning(true)
    await new Promise((r) => setTimeout(r, 1800)) // API 조회·크롤링·해시 비교·임베딩 흉내
    setRunning(false)
    toast.show('임베딩이 완료되었습니다.')
  }

  const times = [['마지막 API 동기화', d.lastApiSync], ['마지막 크롤링', d.lastCrawl], ['마지막 임베딩', d.lastEmbed]]
  const counts = [
    ['총 정책', d.total], ['API 정책', d.api], ['서울 정책', d.seoul],
    ['신규 정책', d.added], ['변경된 정책', d.changed], ['임베딩 완료', d.embedded],
  ]

  return (
    <div>
      <PageHead title="덜다 · 정책 임베딩 관리" sub="복지 정책 데이터를 최신화해 벡터스토어에 임베딩·관리해요."
        right={<button className="btn btn-primary btn-sm" onClick={() => setConfirm(true)}>정책 데이터 최신화</button>} />

      <div className="card card-pad" style={{ maxWidth: 640 }}>
        <h3 style={{ marginBottom: 16 }}>정책 데이터 관리</h3>
        <div className="stack" style={{ gap: 10 }}>
          {times.map(([k, v]) => (
            <div key={k} className="row" style={{ justifyContent: 'space-between' }}>
              <span className="muted">{k}</span><b>{v}</b>
            </div>
          ))}
        </div>
        <div style={{ borderTop: '1px solid var(--line)', margin: '16px 0' }} />
        <div className="stack" style={{ gap: 10 }}>
          {counts.map(([k, v]) => (
            <div key={k} className="row" style={{ justifyContent: 'space-between' }}>
              <span className="muted">{k}</span><b>{v.toLocaleString()} 건</b>
            </div>
          ))}
        </div>
      </div>

      {confirm && (
        <Modal title="정책 데이터 최신화를 시작하시겠습니까?" onClose={() => setConfirm(false)}
          actions={<><button className="btn btn-plain" onClick={() => setConfirm(false)}>취소</button>
            <button className="btn btn-primary" onClick={run}>확인</button></>}>
          <p className="muted">API 조회 · 크롤링 · 해시 비교 후 신규·변경 정책만 다시 임베딩해요.</p>
        </Modal>
      )}
      {running && (
        <Modal title="정책 데이터를 확인하고 있습니다.">
          <Loading title="최신화 중이에요" sub="API 조회 · 크롤링 · 임베딩" />
        </Modal>
      )}
      {toast.node}
    </div>
  )
}
