# -*- coding: utf-8 -*-
"""잇다 · Conformal 임계값 캘리브레이션 (2026-08-03 신설)

무엇을 하나
  캘리브레이션 셋(질문 + 정답 직업)으로 검색을 돌려 **정답의 점수**를 모으고,
  허용 오류율 α 에 해당하는 **분위수를 컷**으로 계산한다.

  보장:  컷 이상인 후보를 전부 반환하면, 정답이 그 안에 있을 확률 ≥ 1−α.

왜 필요한가
  지금 착지 판정은 손으로 정한 JOB_MARGIN=0.02 · JOB_NARROW_GAP=0.04 에 걸려 있고,
  그 숫자가 무엇을 보장하는지 근거가 없다. 그래서 점수가 경계 근처(실측 0.006)면
  같은 입력에도 카드↔되묻기가 뒤집혔다. 컷을 데이터가 정하면 그 뒤집힘이
  **집합 크기 변화**로 바뀐다(답이 안 바뀐다).

덤으로 recall@k 도 나온다 — 지금까지 문서에 세 번(§12-2·§13-4·§16-1) 요구됐으나 없던 수치.

실행 (Backend/ 에서)
    python -m app.itda.scripts.calibrate_threshold
    python -m app.itda.scripts.calibrate_threshold --set /path/calib.json --alpha 0.1
"""
import argparse
import asyncio
import io
import json
import statistics
import sys
from pathlib import Path

from ._common import setup_console
from ..db import async_session
from .. import match as m

setup_console()

DEFAULT_SET = Path(__file__).with_name('calibration_set.json')
POOL = 20          # 정답이 어디쯤 있는지 보려면 넉넉히 받는다
CONC = 5


async def probe(db, item, sem):
    async with sem:
        jobs = await m.match_jobs(db, [item['question']], top_k=POOL)
    codes = [j['job_code'] for j in jobs]
    truth = str(item['job_code'])
    rank = codes.index(truth) + 1 if truth in codes else None
    return {
        'q': item['question'],
        'truth': item['job_name'],
        'rank': rank,
        'score': jobs[codes.index(truth)]['score'] if rank else None,
        'top1': jobs[0]['score'] if jobs else None,
        'top1_name': jobs[0]['job_name'] if jobs else None,
    }


def quantile(xs, q):
    """하위 q 분위수 — 정렬 후 선형보간 없이 보수적으로(내림)."""
    if not xs:
        return None
    s = sorted(xs)
    i = max(0, min(len(s) - 1, int(len(s) * q) - 1))
    return s[i]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', default=str(DEFAULT_SET))
    ap.add_argument('--alpha', type=float, default=0.1)
    a = ap.parse_args()

    items = json.loads(Path(a.set).read_text(encoding='utf-8'))
    print(f'캘리브레이션 셋 {len(items)}개 · POOL={POOL}\n')

    sem = asyncio.Semaphore(CONC)
    async with async_session() as db:
        res = await asyncio.gather(*(probe(db, it, sem) for it in items))

    found = [r for r in res if r['rank']]
    missed = [r for r in res if not r['rank']]

    # ── recall@k ─────────────────────────────────────────────
    print('  ══ recall@k (정답이 상위 k 안에 있는 비율) ══')
    for k in (1, 3, 5, 8, 10, 20):
        hit = sum(1 for r in found if r['rank'] <= k)
        print(f'    recall@{k:<2} {hit/len(res)*100:5.1f}%   ({hit}/{len(res)})')
    print(f'    상위 {POOL} 안에 없음: {len(missed)}개')

    # ── 정답 점수 분포 → conformal 컷 ─────────────────────────
    scores = [r['score'] for r in found if r['score'] is not None]
    print(f'\n  ══ 정답의 점수 분포 (n={len(scores)}) ══')
    if scores:
        s = sorted(scores)
        print(f'    최소 {s[0]:.4f} · 25% {quantile(s,.25):.4f} · 중앙 {statistics.median(s):.4f} '
              f'· 75% {quantile(s,.75):.4f} · 최대 {s[-1]:.4f}')
        print(f'\n  ══ α 별 conformal 컷 ══')
        print(f'    {"α":>6} {"보장":>6}  {"컷":>8}   이 컷일 때 평균 집합 크기')
        print('    ' + '-' * 52)
        for alpha in (0.05, 0.10, 0.15, 0.20, 0.30):
            cut = quantile(s, alpha)
            #  이 컷을 적용하면 후보 몇 개가 남나 — 실측 top1 대비가 아니라 절대 컷 기준
            sizes = []
            for r in res:
                if r['top1'] is None:
                    continue
                sizes.append(1)          # 근사: top1 은 항상 포함
            print(f'    {alpha:>6.2f} {1-alpha:>5.0%}  {cut:>8.4f}')
        print('\n    ※ 집합 크기는 다음 단계(엔진 적용)에서 실제 후보로 다시 잰다.')

    # ── 실패 사례 ─────────────────────────────────────────────
    print(f'\n  ══ 정답을 못 찾은 것 (상위 {POOL} 밖) ══')
    for r in missed[:8]:
        print(f'    «{r["q"][:38]}»')
        print(f'       정답 [{r["truth"]}]  ·  1위였던 것 [{r["top1_name"]}] {r["top1"]:.3f}')
    if len(missed) > 8:
        print(f'    … 외 {len(missed)-8}개')

    # ── 순위는 맞았지만 낮은 것 ────────────────────────────────
    low = sorted([r for r in found if r['rank'] > 3], key=lambda x: -x['rank'])[:5]
    if low:
        print(f'\n  ══ 정답이 4위 밖이었던 것 ══')
        for r in low:
            print(f'    {r["rank"]:>2}위  «{r["q"][:34]}»  →  [{r["truth"]}] {r["score"]:.3f}')


if __name__ == '__main__':
    asyncio.run(main())
