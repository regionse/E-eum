# -*- coding: utf-8 -*-
r"""RRF 의 k 를 «재본다». (2026-08-09)

무엇을 정하려는 건가
  match.py `_rrf(*lists, k=60)` 의 주석은 「k=60 은 RRF 표준값」이라고만 적혀 있다.
  즉 **우리가 재보고 고른 값이 아니다.** 발표에서 「k를 재봤다」고 말하면 거짓이 된다.
  ⇒ 실제로 쓸어 보고, 60 이 맞는지 / 다른 값이 나은지 숫자로 답한다.

k 가 무엇인가 (한 줄)
  RRF 점수 = Σ 1/(k + 순위).  k 가 «작을수록» 1등과 2등의 점수 차가 벌어지고,
  «클수록» 평평해져 「몇 개 목록에 나왔나」가 이긴다.
    k=0   → 1등 1.000 · 2등 0.500 · 3등 0.333   (1등이 압도)
    k=60  → 1등 0.0164 · 2등 0.0161 · 3등 0.0159 (거의 같다 → 사실상 «표 세기»)
  Cormack 외 2009 가 처음 제안할 때 쓴 값이 60 이고, 이후 관행이 됐다.

어떻게 재나 — **검색은 «한 번만» 돈다**
  질의마다 벡터 순위·키워드 순위를 한 번 받아 두고, k 만 바꿔 «다시 합친다».
  ⇒ k 를 몇 개 재든 추가 비용이 0 이다. 이게 이 검사의 요점이다.

비용
  생성 LLM **0회**. 임베딩 n회(질의당 약 30토큰) + Pinecone 질의 n회.
  ⚠ 임베딩 단가는 확인하지 않았다. 「작을 것」이라고 «추정»할 뿐 실측이 아니다.

⚠ 한계 — 먼저 적는다
  · 실사용은 질의를 최대 4개(원문·슬롯·LLM변형) 넣는데 여기는 **원문 하나**만 쓴다.
    k 의 효과만 보려고 다른 변수를 고정한 것이다. 질의가 여럿일 때 결론이 같다는 보장은 없다.
  · 정답표는 build_calibration_set 의 합성 질의다(사람 라벨이 아니다).

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/rrf_k_sweep.py [--n 100]
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

from app.itda.db import async_session                                # noqa: E402
from app.itda import match                                          # noqa: E402

SET = Path(__file__).resolve().parents[1] / 'calibration_set.json'
KS = [0, 1, 3, 5, 10, 20, 40, 60, 100, 200, 500, 1000]
OVER = 20


def rrf(lists, k):
    """match._rrf 와 «같은 식». k 만 바깥에서 준다."""
    score = {}
    for ids in lists:
        for rank, cid in enumerate(ids):
            score[cid] = score.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(score, key=score.get, reverse=True)


def rank_of(order, code):
    for i, c in enumerate(order, 1):
        if str(c) == str(code):
            return i
    return None


async def build_queries(eng, q, mode):
    """실사용과 «같은 모양»의 질의 목록을 만든다.

    itda_core.search() 5089행:  qs = [LLM질의] + _slot_queries(profile) + query_alts
    그리고 match_jobs 가 앞에서부터 최대 4개만 쓴다.
    ⚠ --real 은 turn() 을 «부른다». 여기서 비용이 난다.
    """
    if mode == 'raw':
        return [q], 0, 0
    from app.itda.itda_core import verify_slots
    t = await eng.turn({}, q) or {}
    slots, _ = verify_slots(t.get('profile') or {}, q)
    qs = []
    for cand in ([(t.get('query') or '').strip()]
                 + [s.strip() for s in eng._slot_queries(slots)]
                 + [x.strip() for x in (t.get('query_alts') or []) if x]):
        if cand and cand not in qs:
            qs.append(cand)
    if not qs:
        qs = [q]
    u = (getattr(eng, 'last_usage', None) or {})
    return qs[:4], u.get('in', 0), u.get('out', 0)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--real', action='store_true',
                    help='실사용처럼 질의 최대 4개 (turn() 호출 — 비용 발생)')
    a = ap.parse_args()

    items = json.loads(SET.read_text(encoding='utf-8'))
    items = (items.get('items') if isinstance(items, dict) else items)[:a.n]

    print('=' * 88)
    print(f'  RRF k 스윕 — 질의 {len(items)}개 · 검색은 «한 번만» 돈다 · 생성 LLM 0회')
    print('=' * 88)

    mode = 'real' if a.real else 'raw'
    print(f'  조건 : {"실사용 — 질의 최대 4개 (turn 호출)" if a.real else "원문 하나 (LLM 0회)"}')
    eng = None
    if a.real:
        from app.itda.itda_core import ItdaEngine
        eng = ItdaEngine()

    #  ① 검색을 한 번씩만 돌려 순위들을 받아 둔다
    pairs, nq_all, tin, tout = [], [], 0, 0
    async with async_session() as db:
        for i, it in enumerate(items, 1):
            q0 = it.get('question') or it.get('q')
            code = it.get('job_code')
            try:
                qs, ui, uo = await build_queries(eng, q0, mode)
            except Exception as e:                                  # noqa: BLE001
                print(f'  [{i}] turn 실패: {type(e).__name__}: {str(e)[:60]}')
                qs, ui, uo = [q0], 0, 0
            tin += ui
            tout += uo
            nq_all.append(len(qs))
            lists = []
            for q in qs:
                try:
                    vec = await match._search(q, match.NS_JOB, OVER, 0.0)
                except Exception:                                   # noqa: BLE001
                    vec = []
                try:
                    kw = await match._keyword_jobs(db, q, OVER)
                except Exception:                                   # noqa: BLE001
                    kw = []
                lists.append([c for c, _ in vec])
                lists.append([c for c, _ in kw])
            pairs.append((lists, code))
            if i % 20 == 0:
                print(f'  … {i}/{len(items)}')
    if nq_all:
        print(f'  질의 개수 평균 {sum(nq_all) / len(nq_all):.2f}개 '
              f'(1개 {nq_all.count(1)} · 2개 {nq_all.count(2)} · '
              f'3개 {nq_all.count(3)} · 4개 {nq_all.count(4)})')
    if tin or tout:
        print(f'  turn() 토큰 — 입력 {tin:,} · 출력 {tout:,}')

    #  ② k 만 바꿔 다시 합친다 — 여기서부터는 비용 0
    print()
    print(f'  {"k":>5s}  {"@1":>5s} {"@3":>5s} {"@5":>5s} {"@10":>5s} {"@20":>5s}   {"MRR":>6s}  {"못찾음":>6s}')
    print('  ' + '-' * 62)
    best = None
    rows = []
    for k in KS:
        ranks = [rank_of(rrf(lists, k), c) for lists, c in pairs]
        n = len(ranks)
        hit = {t: sum(1 for r in ranks if r and r <= t) for t in (1, 3, 5, 10, 20)}
        mrr = sum(1 / r for r in ranks if r) / max(1, n)
        miss = sum(1 for r in ranks if not r)
        rows.append((k, hit, mrr, miss))
        mark = ' ←지금' if k == 60 else ''
        print(f'  {k:5d}  {hit[1]:5d} {hit[3]:5d} {hit[5]:5d} {hit[10]:5d} {hit[20]:5d}   '
              f'{mrr:6.3f}  {miss:6d}{mark}')
        if best is None or mrr > best[1]:
            best = (k, mrr)

    cur = next(r for r in rows if r[0] == 60)
    print('  ' + '-' * 62)
    print(f'  지금(k=60)  MRR {cur[2]:.3f} · @1 {cur[1][1]}')
    print(f'  최고(k={best[0]})   MRR {best[1]:.3f}')
    d = best[1] - cur[2]
    print(f'  차이        {d:+.4f}  '
          f'{"→ 바꿀 이유가 없다" if abs(d) < 0.01 else "→ 볼 만하다. 다만 합성 질의임을 감안할 것"}')
    print()
    if a.real:
        print('  ⚠ 실사용과 «같은» 질의 조립이다. 다만 1턴차라 슬롯이 얇다 —')
        print('    누적 슬롯이 쌓인 5턴차와는 다를 수 있다.')
    else:
        print('  ⚠ 질의는 «원문 하나»만 썼다. 실사용은 최대 4개를 넣는다 → --real 로 재라.')


asyncio.run(main())
