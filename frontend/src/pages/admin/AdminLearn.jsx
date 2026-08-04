import { useCallback, useEffect, useRef, useState } from 'react'
import { PageHead, Modal, Loading, useToast } from '../../components/ui/index.jsx'
import { getItdaSyncStatus, getItdaSyncRun, startItdaSync } from '../../api/admin.js'

// 잇다 관리자 · 임베딩 관리 (ADM-ITD-EMB)
//
// ★ 2026-08-02 — 목업(mock/db.js · FAISS)에서 실제 API 연동으로 교체.
//   예전 화면은 존재하지 않는 값을 보여주고 있었다 — FAISS 인덱스, 가짜 카테고리별 집계.
//   실제 구조는 Pinecone 인덱스 1개 + 네임스페이스 3개(cert / course / job)다.
//
// ★ 2026-08-04 ① 화면 모양을 덜다(AdminWelfare)와 통일했다.
//   예전엔 잇다만 KPI 타일 7장 + 실행이력 표로 혼자 다르게 생겼다. 관리자 화면이
//   축마다 다르게 생길 이유가 없다. 「제목+상태배지 → 시각 목록 → 구분선 → 굵은 건수 목록」
//   구조로 맞췄다(SummaryRow 도 같은 모양으로 옮겨왔다).
//
// ★ 2026-08-04 ② 「최신화」 버튼과 진행 모달을 붙였다.
//   그전까지는 서버 터미널에서 배치를 직접 쳐야 했고, 관리자는 결과만 볼 수 있었다.
//   이제 버튼 하나로 적재→임베딩이 백그라운드에서 돌고 진행 상황이 보인다.
//   진행 상황의 출처는 배치가 stdout 에 찍는 «300/613 (48%)» 이다 (Backend/app/itda/sync_runner.py).
//
// 값의 출처 — 화면이 계산하지 않는다.
//   현황(결과)  →  itda_sync_log + content_hash   … GET /admin/itda-sync/latest
//   진행(과정)  →  sync_runner 의 메모리 상태      … GET /admin/itda-sync/run
const fmtNum = (n) => (n ?? 0).toLocaleString()

const POLL_MS = 2000

//  덜다 화면의 같은 이름 컴포넌트와 같은 모양. (공용으로 빼려면 두 화면을 함께 고쳐야 해서
//  지금은 각자 두었다 — 덜다는 팀원이 작업 중인 파일이다.)
function SummaryRow({ label, value, strong = false, danger = false }) {
  return (
    <div
      className="row"
      style={{ justifyContent: 'space-between', alignItems: 'center',
        gap: 20, minHeight: 39, padding: '7px 0' }}
    >
      <span style={{ color: 'var(--ink-soft)', fontSize: 15 }}>{label}</span>
      <span
        style={{
          fontSize: strong ? 17 : 15,
          fontWeight: strong ? 800 : 700,
          color: danger ? 'var(--danger)' : 'var(--ink)',
          textAlign: 'right',
          wordBreak: 'keep-all',
        }}
      >
        {value ?? '-'}
      </span>
    </div>
  )
}

//  진행 모달의 단계 카드 — 지금 도는 단계만 강조하고 나머지는 눌러 둔다.
function StepCard({ step }) {
  const on = step.status === 'running'
  const done = step.status === 'ok'
  const bad = step.status === 'failed'
  const tag = bad ? '실패' : done ? '완료' : on ? `${step.percent}%` : '대기 중'
  return (
    <div
      className="card"
      style={{
        padding: '14px 16px', marginBottom: 10,
        background: on ? 'var(--teal-50)' : '#fff',
        borderColor: on ? 'var(--teal-300)' : bad ? '#f0c9c9' : 'var(--line)',
      }}
    >
      <div className="row" style={{ justifyContent: 'space-between', gap: 12 }}>
        <b style={{ color: bad ? 'var(--danger)' : 'var(--ink)' }}>{step.title}</b>
        <span className="muted" style={{ fontSize: 13, whiteSpace: 'nowrap' }}>{tag}</span>
      </div>
      <p className="muted" style={{ fontSize: 13, margin: '4px 0 0' }}>{step.desc}</p>
      {/* 진행 막대 — 퍼센트가 잡힐 때만 그린다(적재 배치는 퍼센트를 안 찍는다) */}
      {on && step.percent > 0 && (
        <div style={{ height: 4, borderRadius: 999, background: 'var(--teal-100)', marginTop: 8 }}>
          <div style={{ height: '100%', width: `${step.percent}%`, borderRadius: 999,
            background: 'var(--teal-500)', transition: 'width .3s' }} />
        </div>
      )}
      {(on || bad) && step.log && (
        <p className="muted" style={{ fontSize: 12, margin: '6px 0 0', wordBreak: 'break-all' }}>
          {step.log}
        </p>
      )}
    </div>
  )
}

export default function AdminLearn() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [run, setRun] = useState(null)          // 최신화 진행 현황
  const [confirm, setConfirm] = useState(false)
  const [starting, setStarting] = useState(false)
  const [actionError, setActionError] = useState('')
  const toast = useToast()
  const timer = useRef(null)

  const loadStatus = useCallback(async () => {
    try { setData(await getItdaSyncStatus()) }
    catch (e) { setErr(e?.message || '현황을 불러오지 못했어요.') }
  }, [])

  //  첫 진입 — 현황과 진행 상황을 함께 본다.
  //  진행 상황까지 보는 이유: 최신화 도중에 새로고침하거나 다른 화면을 다녀와도
  //  다시 진행 모달에 붙어야 한다. 안 그러면 "돌고는 있는데 화면엔 안 보이는" 상태가 된다.
  useEffect(() => {
    let alive = true
    ;(async () => {
      await loadStatus()
      try {
        const r = await getItdaSyncRun()
        if (alive && r && r.status !== 'idle') setRun(r)
      } catch { /* 진행 현황은 못 받아도 화면은 뜬다 */ }
    })()
    return () => { alive = false }
  }, [loadStatus])

  //  폴링 — 도는 동안만. 끝나면 현황을 다시 읽어 값이 갱신되게 한다.
  useEffect(() => {
    if (!run || run.status !== 'running') return undefined
    timer.current = setInterval(async () => {
      try {
        const r = await getItdaSyncRun()
        setRun(r)
        if (r.status !== 'running') {
          clearInterval(timer.current)
          await loadStatus()
          toast.show(r.status === 'done'
            ? '최신화가 끝났어요.'
            : '최신화가 끝났지만 일부 단계가 실패했어요.')
        }
      } catch { /* 한 번 실패해도 다음 폴링에서 다시 시도한다 */ }
    }, POLL_MS)
    return () => clearInterval(timer.current)
  }, [run, loadStatus, toast])

  const start = async () => {
    setConfirm(false); setStarting(true); setActionError('')
    try {
      setRun(await startItdaSync())
    } catch (e) {
      setActionError(e?.message || '최신화를 시작하지 못했어요.')
    } finally { setStarting(false) }
  }

  const running = run?.status === 'running'

  const head = (
    <PageHead
      title="잇다 · 임베딩 관리"
      sub="자격증·직업·강좌 데이터를 벡터로 만들어 Pinecone 에 저장·관리해요."
      right={(
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={starting || running}
          onClick={() => setConfirm(true)}
        >
          {starting ? '최신화 시작 중' : running ? '최신화 진행 중' : '진로 데이터 최신화'}
        </button>
      )}
    />
  )

  if (err) {
    return (
      <div>
        {head}
        <div className="card card-pad" style={{ maxWidth: 780 }}>
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
        {head}
        <div className="card card-pad" style={{ maxWidth: 780 }}>
          <Loading title="현황을 불러오는 중이에요"
            sub="배치 실행 기록과 임베딩 상태를 확인하고 있어요." />
        </div>
      </div>
    )
  }

  const runs = data.runs || []
  //  '신규 · 변경'은 대상별 최근 실행을 합친 값이다.
  //  각 배치가 content_hash 를 비교해 넣은 숫자라 화면이 다시 세지 않는다.
  const sum = (k) => runs.reduce((a, r) => a + (r[k] || 0), 0)
  const failed = Number(data.failed_recent || 0)

  //  배경은 .badge 가 아니라 색상 클래스(.badge-teal 등)가 준다 — 클래스를 써야 알약 모양이 된다.
  const status = running
    ? { label: '최신화 중', cls: 'badge-teal' }
    : runs.length === 0
      ? { label: '실행 기록 없음', cls: 'badge-gray' }
      : failed > 0
        ? { label: '일부 실패', cls: 'badge-amber' }
        : { label: '정상', cls: 'badge-teal' }

  return (
    <div>
      {head}

      {actionError && (
        <div className="card card-pad"
          style={{ marginBottom: 14, borderColor: '#f0c9c9', background: '#fffafa', maxWidth: 780 }}>
          <div className="row" style={{ justifyContent: 'space-between', gap: 16 }}>
            <b style={{ color: 'var(--danger)' }}>{actionError}</b>
            <button type="button" className="btn btn-plain btn-sm"
              onClick={() => setActionError('')}>닫기</button>
          </div>
        </div>
      )}

      <div
        className="card card-pad"
        style={{ width: '100%', maxWidth: 780, boxSizing: 'border-box',
          borderRadius: 18, padding: 28 }}
      >
        {/* 카드 제목과 상태 */}
        <div
          className="row"
          style={{ justifyContent: 'space-between', alignItems: 'center',
            gap: 16, flexWrap: 'wrap', marginBottom: 18 }}
        >
          <h3 style={{ margin: 0, fontSize: 22 }}>진로 데이터 관리</h3>
          <span className={`badge ${status.cls}`} style={{ gap: 7, padding: '7px 12px' }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%',
              background: 'currentColor' }} />
            {status.label}
          </span>
        </div>

        {/* 처리 단계와 시각 */}
        <div>
          <SummaryRow label="마지막 데이터 적재" value={data.last_api_sync || '기록 없음'} />
          <SummaryRow label="마지막 임베딩" value={data.last_embedding || '기록 없음'} />
        </div>

        {/* 처리 결과 구분선 */}
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--line)' }}>
          <SummaryRow label="전체 자격증" value={`${fmtNum(data.cert_total)} 건`} strong />
          <SummaryRow label="전체 직업" value={`${fmtNum(data.job_total)} 건`} strong />
          <SummaryRow label="전체 강좌" value={`${fmtNum(data.course_total)} 건`} strong />
          <SummaryRow
            label="임베딩 완료"
            value={`${fmtNum((data.cert_embedded || 0) + (data.course_embedded || 0))} 건`}
            strong
          />
          <SummaryRow label="신규" value={`${fmtNum(sum('inserted'))} 건`} strong />
          <SummaryRow label="변경" value={`${fmtNum(sum('updated'))} 건`} strong />
          <SummaryRow label="실패 · 최근 7일" value={`${fmtNum(failed)} 건`}
            strong danger={failed > 0} />
        </div>

        <p className="muted" style={{ fontSize: 13.5, marginTop: 16, lineHeight: 1.7 }}>
          인덱스 1개(<code>eum-itda</code>) · 네임스페이스 3개(cert · course · job) · 3072차원 cosine
          <br />
          「신규 · 변경」은 <code>content_hash</code> 비교 결과예요 — 내용이 바뀐 것만 다시 임베딩해요.
        </p>
      </div>

      {/* 시작 전 확인 */}
      {confirm && (
        <Modal title="진로 데이터 최신화를 시작하시겠습니까?" onClose={() => setConfirm(false)}
          actions={(
            <>
              <button className="btn btn-plain" onClick={() => setConfirm(false)}>취소</button>
              <button className="btn btn-primary" onClick={start}>확인</button>
            </>
          )}>
          <p className="muted">
            자격증·강좌를 다시 불러온 뒤 <b>내용이 바뀐 것만</b> 임베딩해요.
            <br />
            서버에서 백그라운드로 처리하고, 바뀐 게 많으면 10분 이상 걸릴 수 있어요.
          </p>
        </Modal>
      )}

      {/* 진행 상황 — 도는 동안, 그리고 끝난 직후 결과를 확인할 때까지 띄운다 */}
      {run && run.status !== 'idle' && (
        <Modal
          title={running ? '진로 데이터를 최신화하고 있습니다' : '최신화가 끝났습니다'}
          onClose={running ? undefined : () => setRun(null)}
          actions={running ? undefined : (
            <button className="btn btn-primary btn-block" onClick={() => setRun(null)}>확인</button>
          )}
        >
          {running && (
            <Loading
              title={(run.steps || []).find((s) => s.status === 'running')?.title || '준비 중'}
              sub={(run.steps || []).find((s) => s.status === 'running')?.desc || ''}
            />
          )}

          <div style={{ marginTop: running ? 14 : 0 }}>
            {(run.steps || []).map((s) => <StepCard key={s.key} step={s} />)}
          </div>

          <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
            {running
              ? '서버에서 백그라운드로 처리하고 있어요. 이 창을 닫아도 계속 진행돼요.'
              : run.message}
          </p>
        </Modal>
      )}

      {toast.node}
    </div>
  )
}
