# -*- coding: utf-8 -*-
r"""job_attr 태그 가중(ATTR_LIFT)이 «실제로 도움이 되는가» — 정답표 100개로. (2026-08-10)

왜 재나
  사용자 질문: 「태깅 이거 필요 없는 거 아님? 결국 내가 데이터를 만들어낸 거잖아.」
  이미 잰 것 —
    · 태그 신뢰도: 같은 모델 재현 71%, 다른 모델 43% (checks/tag_reliability.py)
    · 골든셋 34/34 는 태그를 «꺼도» 그대로
    · 손으로 고른 4개 질의에서 1위가 같았고, 오히려 「어르신 돌보는 일」에 네일미용이 «들어왔다»
  ⇒ 그런데 4개는 표본이 아니다. **정답표 100개**로 제대로 잰다.

무엇을 재나
  같은 검색 결과에 가중만 0 / 2 / 4 로 바꿔 «정답 직업의 순위»를 본다.
  가중이 값어치가 있으면 Recall@1 이 올라야 한다.

요령 — 검색은 «한 번만» 돈다
  turn() 으로 슬롯을 뽑고, 검색을 한 번 하고, 그 결과에 가중만 바꿔 다시 정렬한다.
  ⇒ 가중값을 몇 개 재든 추가 비용이 0 이다.

비용
  turn() 100회 ≈ 210원 (어블레이션 실측 기준: 입력 735k · 출력 27k)
  + 임베딩/Pinecone 100회. 정렬 비교는 0원.

⚠ 한계
  · 정답표가 합성이다(build_calibration_set). 사람 라벨이 아니다.
  · 1턴차라 슬롯이 얇다. 누적 슬롯이 쌓인 5턴차와 다를 수 있다.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/attr_lift_ablation.py --n 100
"""
import argparse
import asyncio
import io
import json
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda.db import async_session                              # noqa: E402
from app.itda import match                                         # noqa: E402
from app.itda.itda_core import ItdaEngine, verify_slots, wanted_vals  # noqa: E402

SET = Path(__file__).resolve().parents[1] / 'calibration_set.json'
LIFTS = [0, 1, 2, 4, 8]
POOL = 40


def ranked(wide, acts, objs, who, lift):
    """itda_core 의 ATTR_LIFT 블록과 «같은 식»으로 다시 정렬한다."""
    if not lift:
        return wide
    out = sorted(
        ((i - lift * ((1 if j.get('act_type') in acts else 0)
                      + (1 if j.get('obj_type') in objs else 0)
                      + (2 if (who and j.get('obj_detail') == who) else 0)), i, j)
         for i, j in enumerate(wide)), key=lambda t: (t[0], t[1]))
    return [j for _, _, j in out]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=100)
    a = ap.parse_args()

    items = json.loads(SET.read_text(encoding='utf-8'))
    items = (items.get('items') if isinstance(items, dict) else items)[:a.n]

    print('=' * 90)
    print(f'  ATTR_LIFT 어블레이션 — 질의 {len(items)}개 · 검색은 «한 번만» 돈다')
    print('=' * 90)

    eng = ItdaEngine()
    rows, tin, tout, n_tag = [], 0, 0, 0
    async with async_session() as db:
        for i, it in enumerate(items, 1):
            q = it.get('question') or it.get('q')
            code = str(it.get('job_code'))
            try:
                t = await eng.turn({}, q) or {}
                slots, _ = verify_slots(t.get('profile') or {}, q)
            except Exception as e:                                 # noqa: BLE001
                print(f'  [{i}] turn 실패 {type(e).__name__}')
                slots = {}
            u = getattr(eng, 'last_usage', None) or {}
            tin += u.get('in', 0)
            tout += u.get('out', 0)
            acts = {x for x in wanted_vals(slots, '활동유형') if x}
            objs = {x for x in wanted_vals(slots, '다루는대상') if x}
            who = slots.get('대상세부')
            if acts or objs or who:
                n_tag += 1
            try:
                wide = await match.match_jobs(db, q, top_k=POOL)
            except Exception:                                      # noqa: BLE001
                wide = []
            rows.append((wide, acts, objs, who, code))
            if i % 20 == 0:
                print(f'  … {i}/{len(items)}')

    print(f'  슬롯이 하나라도 잡힌 질의 {n_tag}/{len(rows)}  '
          f'(가중이 «걸릴 수 있는» 것만 효과가 있다)')
    print(f'  turn() 토큰 — 입력 {tin:,} · 출력 {tout:,}')
    print()
    print(f'  {"가중":>4s}  {"@1":>5s} {"@3":>5s} {"@5":>5s} {"@10":>5s}   {"MRR":>6s}   변화')
    print('  ' + '-' * 56)
    base = None
    for L in LIFTS:
        rk = []
        for wide, acts, objs, who, code in rows:
            order = ranked(wide, acts, objs, who, L)
            r = next((k for k, j in enumerate(order, 1)
                      if str(j.get('job_code')) == code), None)
            rk.append(r)
        n = len(rk)
        hit = {t: sum(1 for r in rk if r and r <= t) for t in (1, 3, 5, 10)}
        mrr = sum(1 / r for r in rk if r) / max(1, n)
        if base is None:
            base = (hit[1], mrr)
            d = '기준'
        else:
            d = f'@1 {hit[1] - base[0]:+d}  MRR {mrr - base[1]:+.4f}'
        mark = ' ←지금' if L == 2 else ''
        print(f'  {L:4d}  {hit[1]:5d} {hit[3]:5d} {hit[5]:5d} {hit[10]:5d}   {mrr:6.3f}   {d}{mark}')
    print()
    print('  ※ 가중 0 = 태그를 «안 쓰는 것». 지금 값은 2다.')
    print('  ⚠ 정답표가 합성이고 1턴차다. 그 조건에서의 결론이다.')


asyncio.run(main())
