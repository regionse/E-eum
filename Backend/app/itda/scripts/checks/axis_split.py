# -*- coding: utf-8 -*-
"""속성 축 분할력 실측 — 「질문을 손으로 쓰지 않고 후보에서 «생성»할 수 있나」.

무엇을 정하려는 건가
  지금 우리는 질문 27개를 손으로 써 두고 순서대로 던진다. 그래서
  ① 반복이 나고(실측: 15턴에 질문 12개 중 6개 재탕)
  ② 질문이 후보와 «무관»하다(「요즘 자주 보는 유튜브 채널이…」).

  CRS 정석은 반대다 — **지금 후보들이 어느 축에서 갈리는지** 보고 그 축을 묻는다.
  그러면 반복이 «구조적으로» 불가능해진다: 한 번 확정된 축은 후보를 좁혔으니
  더 이상 안 갈리고, 따라서 물어볼 대상에서 자동으로 빠진다.

  ⚠ 이 스크립트는 «그 설계가 우리 데이터에서 되는지»만 잰다. 구현이 아니다.

재는 것
  ① 축별 분할력   후보를 그 축의 값으로 묶었을 때의 정규화 엔트로피
                    0 = 전부 같은 값 → 물어도 소용없다
                    1 = 고르게 갈림  → 물으면 최대로 좁혀진다
  ② 깊이          최선 축으로 좁히고 다시 계산 — 몇 턴이면 바닥나나
  ③ 돌봄 계열     act_type '돕기·돌봄' 이 1,064개 중 34개뿐이라 걱정되는 지점
  ④ 축 비교       job_attr(act/obj) vs NCS 계층(대/중분류)

⚠ 점수를 그냥 세지 않는다 — 후보마다 관련도가 다르므로 softmax 로 확률화한 뒤
  축 값별로 합친다(_cluster_buckets 와 같은 순서).
"""
import asyncio
import io
import json
import math
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from sqlalchemy import text                          # noqa: E402

from app.itda.db import async_session                # noqa: E402
import app.itda.match as m                           # noqa: E402
from app.itda.itda_core import ItdaEngine as E       # noqa: E402

CASES = [
    '빵 만드는 일', '용접 일을 하고 싶어요', '자동차 고치고 정비하는 일',
    '머리 만지는 미용 일', '간호조무사가 되고 싶어요', '어르신 요양 돌보는 일',
    '제과제빵 쪽 일',
    '사람에게 도움이 되는 일', '컴퓨터로 하는 일', '손으로 뭔가 만드는 일',
    '몸 안 쓰고 조용히 할 수 있는 일', '자격증 따서 할 수 있는 일',
    '돈 되는 일', '사람 상대하는 일',
    #  ★ 돌봄 계열을 일부러 더 넣는다 — 태그가 34개뿐이라 여기서 무너지면 설계가 안 된다
    '할머니 돌보는 일을 해왔어요', '아이 돌보는 일', '집안일 정리하는 일',
    '병원에서 일하고 싶어요',
]

AXES = [('act_type', '활동유형'), ('obj_type', '다루는대상'),
        ('obj_detail', '누구를'), ('lcls', 'NCS대분류'), ('mcls', 'NCS중분류')]

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_axis_cache.json')


def _softmax(vals, t):
    mx = max(vals)
    ex = [math.exp((v - mx) / max(t, 1e-6)) for v in vals]
    z = sum(ex) or 1.0
    return [e / z for e in ex]


def split_power(cands, key):
    """이 축으로 물으면 후보가 얼마나 갈리나 → (정규화 엔트로피, {값: 질량}).

    엔트로피가 0 이면 전부 같은 값이라 «물어도 아무것도 안 좁혀진다».

    ★★ 2026-08-06 정정 — **미태깅을 한 묶음으로 세면 안 된다.**
      처음엔 `c.get(key) or '(미태깅)'` 로 뭉쳤는데, 그러면 이런 일이 난다:
          「병원에서 일하고 싶어요」  누구를 H=0.59
             (미태깅)(0.62) · 환자·장애인(0.34) · 어르신(0.04)
      여기서 (미태깅) 62% 는 **애초에 사람을 대하는 일이 아닌 직업들**(의료기기관리 등)이다.
      「누구를 대하세요?」로 물어서 갈릴 수 있는 대상이 아니다.
      즉 «물어보면 갈린다»가 아니라 «축이 적용 안 되는 것»인데 갈린 걸로 세고 있었다.
    ⇒ 값이 없는 후보는 **빼고 잰다.** 남은 게 2개 미만이면 0.
      (그래야 「이 축으로 물어봤을 때 실제로 갈리는 정도」가 된다)
    """
    pos = [(c, c['score']) for c in cands
           if c.get('score', 0) > 0 and c.get(key)]
    if len(pos) < 2:
        return 0.0, {}
    ps = _softmax([s for _, s in pos], E.SPREAD_T)
    bk = {}
    for (c, _), p in zip(pos, ps):
        bk[c[key]] = bk.get(c[key], 0.0) + p
    vs = [p for p in bk.values() if p > 0]
    if len(vs) < 2:
        return 0.0, bk
    h = -sum(p * math.log(p) for p in vs)
    return h / math.log(len(vs)), bk


async def fetch(db, q):
    jobs = await m.match_jobs(db, q, top_k=E.JOB_CAND_POOL)
    if not jobs:
        return []
    codes = [j['job_code'] for j in jobs]
    rows = (await db.execute(text(
        "SELECT jc.job_code, ja.act_type, ja.obj_type, ja.obj_detail, "
        "       jc.job_lcls_name, jc.job_mcls_name "
        "FROM job_catalog jc LEFT JOIN job_attr ja ON ja.job_code = jc.job_code "
        "WHERE jc.job_code IN :codes"), {'codes': tuple(codes)})).fetchall()
    meta = {r[0]: {'act_type': r[1], 'obj_type': r[2], 'obj_detail': r[3],
                   'lcls': r[4], 'mcls': r[5]}
            for r in rows}
    out = []
    for j in jobs:
        d = dict(j)
        d.update(meta.get(j['job_code'], {}))
        out.append(d)
    return out


def depth_sim(cands, max_turns=6):
    """최선 축으로 좁히고 다시 계산 — 몇 턴이면 «더 물을 게 없어지나».

    사용자가 «가장 큰 묶음»을 고른다고 가정한다(가장 보수적 — 덜 좁혀진다).
    """
    live, used, trace = list(cands), set(), []
    for t in range(1, max_turns + 1):
        best = None
        for key, label in AXES:
            if key in used:
                continue
            h, bk = split_power(live, key)
            if best is None or h > best[0]:
                best = (h, key, label, bk)
        if best is None or best[0] < 0.05:
            trace.append((t, None, None, len(live), '더 물을 축이 없음'))
            break
        h, key, label, bk = best
        used.add(key)
        top = max(bk.items(), key=lambda x: x[1])[0]
        live = [c for c in live if (c.get(key) or '(미태깅)') == top]
        trace.append((t, label, h, len(live), f'{top} 선택'))
        if len(live) <= 2:
            break
    return trace


async def main():
    if '--fresh' not in sys.argv and os.path.exists(CACHE):
        rows = json.load(io.open(CACHE, encoding='utf-8'))
        print('(캐시 사용 — 다시 재려면 --fresh)\n')
    else:
        rows = []
        async with async_session() as db:
            for q in CASES:
                try:
                    rows.append({'q': q, 'c': await fetch(db, q)})
                except Exception as e:                    # noqa: BLE001
                    print(f'  !! {q}: {type(e).__name__}: {str(e)[:50]}')
        json.dump(rows, io.open(CACHE, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'(캐시 저장 → {os.path.basename(CACHE)})\n')

    print('=' * 100)
    print('■ ① 축별 분할력 — 0.00 이면 «물어도 아무것도 안 좁혀진다»')
    print('=' * 100)
    print(f'{"질의":<26}' + ''.join(f'{lab:>10}' for _, lab in AXES) + '   최선')
    print('-' * 100)
    tot = {k: [] for k, _ in AXES}
    for r in rows:
        vals, best = [], (None, -1)
        for key, label in AXES:
            h, _ = split_power(r['c'], key)
            vals.append(h)
            tot[key].append(h)
            if h > best[1]:
                best = (label, h)
        pad = 26 - sum(2 if ord(c) > 0x2E80 else 1 for c in r['q'])
        print(f'{r["q"]}{" " * max(1, pad)}'
              + ''.join(f'{v:>10.2f}' for v in vals)
              + f'   {best[0]}({best[1]:.2f})')
    print('-' * 100)
    print(f'{"평균":<24}' + ''.join(
        f'{sum(tot[k])/max(len(tot[k]),1):>10.2f}' for k, _ in AXES))

    print('\n' + '=' * 100)
    print('■ ② 깊이 — 최선 축으로 좁히고 다시 계산. 몇 턴이면 바닥나나')
    print('=' * 100)
    depths = []
    for r in rows:
        tr = depth_sim(r['c'])
        depths.append(len([x for x in tr if x[1]]))
        print(f'  {r["q"]}')
        for t, label, h, n, note in tr:
            if label:
                print(f'     {t}턴  {label}(H={h:.2f}) → 후보 {n}개   [{note}]')
            else:
                print(f'     {t}턴  — {note} (후보 {n}개)')
    print(f'\n  평균 깊이: {sum(depths)/max(len(depths),1):.1f}턴')

    print('\n' + '=' * 100)
    print('■ ③ 돌봄 계열에서도 되나 (태그가 34개뿐인 축)')
    print('=' * 100)
    for r in rows:
        if not any(w in r['q'] for w in ('돌보', '요양', '집안일', '병원', '도움')):
            continue
        print(f'  {r["q"]}')
        for key, label in AXES:
            h, bk = split_power(r['c'], key)
            top = sorted(bk.items(), key=lambda x: -x[1])[:4]
            print(f'     {label:<10} H={h:.2f}  ' +
                  ' · '.join(f'{k}({v:.2f})' for k, v in top))

    print('\n' + '=' * 100)
    print('■ ④ 미태깅 비율')
    print('=' * 100)
    n_all = sum(len(r['c']) for r in rows)
    for key, label in AXES:
        miss = sum(1 for r in rows for c in r['c'] if not c.get(key))
        print(f'  {label:<10} {miss}/{n_all}  ({miss/max(n_all,1)*100:.1f}%)')


asyncio.run(main())
