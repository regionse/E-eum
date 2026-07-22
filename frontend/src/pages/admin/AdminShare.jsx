import { useState } from 'react'
import { PageHead, Modal, useToast, Loading } from '../../components/ui/index.jsx'
import { shareEmbed } from '../../mock/db.js'

// 나누다 관리자 · 임베딩 관리 (ADSHA-001) — 지원서비스/기관 데이터 최신화 → 임베딩
// (스토리보드는 덜다 화면을 복제해 "정책"으로 표기돼 있으나, 나누다는 지원서비스 데이터라 라벨을 바로잡음)
export default function AdminShare() {
  const [confirm, setConfirm] = useState(false)
  const [running, setRunning] = useState(false)
  const toast = useToast()
  const d = shareEmbed

  const run = async () => {
    setConfirm(false); setRunning(true)
    await new Promise((r) => setTimeout(r, 1800))
    setRunning(false)
    toast.show('임베딩이 완료되었습니다.')
  }

  const times = [['마지막 API 동기화', d.lastApiSync], ['마지막 임베딩', d.lastEmbed]]
  const counts = [['지원서비스', d.api], ['신규', d.added], ['변경', d.changed], ['임베딩 완료', d.embedded]]

  return (
    <div>
      <PageHead title="나누다 · 임베딩 관리" sub="지원 서비스·기관 데이터를 최신화해 벡터스토어에 임베딩·관리해요."
        right={<button className="btn btn-primary btn-sm" onClick={() => setConfirm(true)}>지원서비스 데이터 최신화</button>} />

      <div className="card card-pad" style={{ maxWidth: 640 }}>
        <h3 style={{ marginBottom: 16 }}>지원 서비스 데이터 관리</h3>
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
        <Modal title="지원서비스 데이터 최신화를 시작하시겠습니까?" onClose={() => setConfirm(false)}
          actions={<><button className="btn btn-plain" onClick={() => setConfirm(false)}>취소</button>
            <button className="btn btn-primary" onClick={run}>확인</button></>}>
          <p className="muted">API 조회 · 해시 비교 후 신규·변경 지원서비스만 다시 임베딩해요.</p>
        </Modal>
      )}
      {running && (
        <Modal title="지원서비스 데이터를 확인하고 있습니다.">
          <Loading title="최신화 중이에요" sub="API 조회 · 임베딩" />
        </Modal>
      )}
      {toast.node}
    </div>
  )
}
