# -*- coding: utf-8 -*-
"""좁히기 판정 신호 비교 실측 — 어느 신호가 「흩어짐」을 제일 잘 가르나.

무엇을 정하려는 건가
  후보를 받아 놓고 **칩으로 되물을까 / 그냥 착지할까**를 정해야 한다.
  지금은 «벡터 점수 엔트로피» 하나로만 판정한다(SPREAD_MODE='entropy', SPREAD_H=0.70).
  그런데 후보군에는 다른 신호가 여럿 있고, 그중 하나(_cluster_entropy)는
  **구현돼 있는데 [measure] 로그로만 나가고 판정에는 안 쓰인다.**

재는 신호
  V ent    벡터 점수의 정규화 엔트로피          (지금 쓰는 것)
  C ent    NCS 중분류로 묶은 «클러스터» 엔트로피  (미사용 — semantic entropy 축소판)
  R max    리랭커 최고점의 **절대값**            (지금은 저확신 표시에만)
  R ent    리랭커 점수의 정규화 엔트로피
  top1%    softmax 뒤 1위가 차지하는 확률 비중   (= TOP%)
  ncl      묶음(중분류) 개수
  margin   1·2위 차                            (JOB_MARGIN — 기본 설정에선 죽은 경로)

⚠⚠ 정답표를 «신호를 보고» 정하면 시험이 무의미해진다. 그래서 라벨은
  **도메인 상식으로 먼저** 붙였고, 측정 뒤에 고치지 않는다.
    LAND = 방향이 하나로 정해진 질의 (세부 갈래는 남아도 «어느 동네인지»는 정해졌다)
    CHIP = 방향이 여럿인 질의 (서로 다른 동네가 섞인다)

  ★ 주석에 기록된 실측이 이 시험의 출발점이다:
      「고치고 정비하는 일」 ent=0.882 → 칩  [전부 자동차정비 세부 — 한 동네]
      「도움이 되는 일」     ent=0.972 → 칩  [자원봉사·취업알선·요양·진로·전직 — 다른 동네]
    엔트로피는 거의 같은데 «의미»는 완전히 다르다. 그걸 가르는 신호를 찾는 것이다.

비용: 질의당 임베딩 1 + 리랭크 1. LLM 대화 호출은 안 쓴다.
"""
import asyncio
import io
import json
import math
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.db import async_session               # noqa: E402
import app.itda.match as m                          # noqa: E402
from app.itda.itda_core import ItdaEngine as E      # noqa: E402

#  (질의, 정답라벨)  LAND = 착지가 맞다 / CHIP = 되물어야 한다
CASES = [
    #  ── 방향이 하나 (착지) ────────────────────────────────────
    ('빵 만드는 일', 'LAND'),
    ('용접 일을 하고 싶어요', 'LAND'),
    ('자동차 고치고 정비하는 일', 'LAND'),      # ★ 주석의 그 케이스 — 전부 한 동네
    ('머리 만지는 미용 일', 'LAND'),
    ('간호조무사가 되고 싶어요', 'LAND'),
    ('어르신 요양 돌보는 일', 'LAND'),
    ('제과제빵 쪽 일', 'LAND'),
    #  ── 방향이 여럿 (칩) ──────────────────────────────────────
    ('사람에게 도움이 되는 일', 'CHIP'),        # ★ 주석의 그 케이스 — 서로 다른 동네
    ('컴퓨터로 하는 일', 'CHIP'),
    ('손으로 뭔가 만드는 일', 'CHIP'),
    ('몸 안 쓰고 조용히 할 수 있는 일', 'CHIP'),
    ('자격증 따서 할 수 있는 일', 'CHIP'),
    ('돈 되는 일', 'CHIP'),
    ('사람 상대하는 일', 'CHIP'),
]


def _softmax(vals, t):
    mx = max(vals)
    ex = [math.exp((v - mx) / max(t, 1e-6)) for v in vals]
    z = sum(ex) or 1.0
    return [e / z for e in ex]


def _norm_ent(ps):
    if len(ps) < 2:
        return 0.0
    h = -sum(p * math.log(p) for p in ps if p > 0)
    return h / math.log(len(ps))


def _buckets(jobs, key='group'):
    """후보를 계층(중분류)으로 묶고 묶음별 «확률 질량»을 낸다 → {묶음: p}.

    ⚠ 점수를 그냥 더하지 않는다 — 코사인은 확률이 아니라 합이 스케일을 깨뜨린다.
      ① 확률화(softmax) → ② 묶음별 합. (_cluster_entropy 와 같은 순서)
    """
    pos = [((j.get(key) or j.get('job_name') or '?'), (j.get('score') or 0))
           for j in jobs if (j.get('score') or 0) > 0]
    pos = sorted(pos, key=lambda x: -x[1])[:E.SPREAD_K]
    if not pos:
        return {}
    ps = _softmax([s for _, s in pos], E.SPREAD_T)
    out = {}
    for (g, _), p in zip(pos, ps):
        out[g] = out.get(g, 0.0) + p
    return out


def signals(jobs, rr):
    """후보 목록에서 신호를 전부 뽑는다."""
    sc = sorted((j.get('score') or 0 for j in jobs if (j.get('score') or 0) > 0),
                reverse=True)[:E.SPREAD_K]
    out = {}
    if len(sc) >= 2:
        ps = _softmax(sc, E.SPREAD_T)
        out['V'] = _norm_ent(ps)
        out['Vtop'] = ps[0]          # 항목 기준 TOP% — 1위 «직업»의 확률
        out['mg'] = sc[0] - sc[1]
    ce, ncl = E._cluster_entropy(jobs)
    out['C'] = ce
    out['ncl'] = ncl
    #  ★ 묶음 기준 TOP% — 최대 «묶음»의 확률 질량.
    #    항목 기준과 결정적으로 다르다: 「CO₂용접·로봇용접·피복아크용접」은
    #    항목으로 재면 서로 갉아먹어 1위가 0.31 밖에 안 되지만,
    #    묶음으로 재면 «금속재료» 하나가 1.00 을 갖는다.
    bk = _buckets(jobs)
    if bk:
        out['Ctop'] = max(bk.values())
        out['nb'] = len(bk)
    if rr:
        rv = sorted(rr, reverse=True)[:E.SPREAD_K]
        out['Rmax'] = rv[0]
        if len(rv) >= 2:
            rps = _softmax(rv, E.SPREAD_T)
            out['R'] = _norm_ent(rps)
            out['Rtop'] = rps[0]     # 리랭커 기준 TOP%
    return out


def sweep(rows, key, higher_means_chip):
    """이 신호 하나로 가를 때 **가장 잘 가르는 임계값**과 그때의 정확도."""
    vals = sorted({r['sig'][key] for r in rows if r['sig'].get(key) is not None})
    if len(vals) < 2:
        return None, 0, 0
    best = (None, -1, 0)
    cands = [(a + b) / 2 for a, b in zip(vals, vals[1:])] + [vals[0] - 1e-6, vals[-1] + 1e-6]
    for th in cands:
        ok = 0
        for r in rows:
            v = r['sig'].get(key)
            if v is None:
                continue
            pred = 'CHIP' if ((v > th) == higher_means_chip) else 'LAND'
            ok += (pred == r['want'])
        if ok > best[1]:
            best = (th, ok, len(rows))
    return best


#  ★ 측정 결과를 캐시한다 — 분석(임계값 스윕·조합 비교)은 **0원으로 몇 번이든** 돌리게.
#    검색·리랭크는 돈이 드는데 그 결과를 매번 다시 뽑을 이유가 없다.
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_spread_cache.json')


async def collect():
    rows = []
    async with async_session() as db:
        for q, want in CASES:
            try:
                jobs = await m.match_jobs(db, q, top_k=E.JOB_CAND_POOL)
            except Exception as e:                       # noqa: BLE001
                print(f'  !! {q}: {type(e).__name__}: {str(e)[:50]}')
                continue
            rr = []
            if jobs:
                try:
                    rr = [s for _, s in await m.rerank(q, E._rr_docs(jobs))]
                except Exception as e:                   # noqa: BLE001
                    print(f'  (리랭크 생략 {q}: {type(e).__name__})')
            rows.append({'q': q, 'want': want, 'sig': signals(jobs, rr),
                         'top': [j['job_name'] for j in jobs[:4]],
                         'grp': sorted({(j.get('group') or '?') for j in jobs[:E.SPREAD_K]})})
    with io.open(CACHE, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f'(측정 결과를 캐시했다 → {os.path.basename(CACHE)})\n')
    return rows


async def main():
    print(f'SPREAD_K={E.SPREAD_K} · SPREAD_T={E.SPREAD_T} · '
          f'현재 판정: V ent > SPREAD_H({E.SPREAD_H})\n')
    #  --fresh 를 주면 다시 측정한다. 없으면 캐시를 쓴다(0원).
    if '--fresh' not in sys.argv and os.path.exists(CACHE):
        with io.open(CACHE, encoding='utf-8') as f:
            rows = json.load(f)
        print(f'(캐시 사용 — 다시 재려면 --fresh · LLM/검색 0회)\n')
    else:
        rows = await collect()

    def f(v, p=3):
        return '  -  ' if v is None else format(v, f'.{p}f')

    print(f'{"질의":<24}{"정답":<6}{"V ent":>7}{"C ent":>7}{"Vtop%":>7}'
          f'{"Ctop%":>7}{"Rtop%":>7}{"Rmax":>8}{"ncl":>5}')
    print('-' * 96)
    for r in rows:
        s = r['sig']
        pad = 24 - sum(2 if ord(c) > 0x2E80 else 1 for c in r['q'])
        print(f'{r["q"]}{" " * max(1, pad)}{r["want"]:<6}'
              f'{f(s.get("V")):>7}{f(s.get("C")):>7}{f(s.get("Vtop")):>7}'
              f'{f(s.get("Ctop")):>7}{f(s.get("Rtop")):>7}{f(s.get("Rmax"),4):>8}'
              f'{s.get("ncl", 0):>5}')
        print(f'{"":26}묶음{len(r["grp"])}: {"·".join(r["grp"])[:66]}')

    print('\n' + '=' * 96)
    print('■ 신호 하나로 가를 때 — 가장 잘 가르는 임계값과 정확도')
    print('=' * 96)
    #  (신호, 값이 크면 CHIP 인가)
    for key, hi in (('C', True), ('Ctop', False), ('V', True), ('Vtop', False),
                    ('Rmax', False), ('Rtop', False), ('R', True),
                    ('ncl', True), ('mg', False)):
        th, ok, n = sweep(rows, key, hi)
        if th is None:
            print(f'  {key:<6} 측정 불가')
            continue
        bar = '█' * int(ok / max(n, 1) * 30)
        print(f'  {key:<6} 임계 {th:>8.4f}  →  {ok}/{n}  {bar}')

    print('\n' + '=' * 96)
    print('■ 두 신호를 «같이» 쓸 때 (AND: 둘 다 흩어졌다고 해야 칩)')
    print('=' * 96)
    pairs = [('C', True, 'Ctop', False), ('V', True, 'C', True), ('V', True, 'Ctop', False),
             ('V', True, 'Rmax', False), ('C', True, 'Rmax', False),
             ('Ctop', False, 'Rmax', False), ('V', True, 'Vtop', False)]
    for k1, h1, k2, h2 in pairs:
        t1, _, _ = sweep(rows, k1, h1)
        t2, _, _ = sweep(rows, k2, h2)
        if t1 is None or t2 is None:
            continue
        ok = 0
        for r in rows:
            v1, v2 = r['sig'].get(k1), r['sig'].get(k2)
            if v1 is None or v2 is None:
                continue
            c1 = (v1 > t1) == h1
            c2 = (v2 > t2) == h2
            ok += (('CHIP' if (c1 and c2) else 'LAND') == r['want'])
        print(f'  {k1}&{k2:<8} 임계 {t1:.4f} / {t2:.4f}  →  {ok}/{len(rows)}')

    #  ── 3중 조합 ────────────────────────────────────────────────
    print('\n' + '=' * 96)
    print('■ 신호 3개를 같이 쓸 때')
    print('=' * 96)

    def _spread_by(r, key, th, hi):
        v = r['sig'].get(key)
        if v is None:
            return None
        return (v > th) == hi

    TRIPLES = [
        ('V&C&Ctop  (AND — 셋 다 흩어져야 칩)', 'AND',
         [('V', 0.70, True), ('C', 0.30, True), ('Ctop', 0.7225, False)]),
        ('V&C&Ctop  (다수결 — 2/3)', 'VOTE',
         [('V', 0.70, True), ('C', 0.30, True), ('Ctop', 0.7225, False)]),
        ('V&C&Rmax  (AND)', 'AND',
         [('V', 0.70, True), ('C', 0.30, True), ('Rmax', 0.1269, False)]),
        ('V&C&Rmax  (다수결)', 'VOTE',
         [('V', 0.70, True), ('C', 0.30, True), ('Rmax', 0.1269, False)]),
        ('C&Ctop&Rmax (다수결 — 전부 묶음/절대값 축)', 'VOTE',
         [('C', 0.30, True), ('Ctop', 0.7225, False), ('Rmax', 0.1269, False)]),
    ]
    for name, mode, specs in TRIPLES:
        ok, miss = 0, []
        for r in rows:
            votes = [_spread_by(r, k, t, h) for k, t, h in specs]
            votes = [v for v in votes if v is not None]
            if not votes:
                continue
            chip = all(votes) if mode == 'AND' else (sum(votes) * 2 > len(votes))
            pred = 'CHIP' if chip else 'LAND'
            if pred == r['want']:
                ok += 1
            else:
                miss.append(f'{r["q"]}({r["want"]}→{pred})')
        print(f'  {name:<40} {ok}/{len(rows)}')
        for x in miss:
            print(f'      🔴 {x}')

    #  ── ★ 임계값 안전 마진 ──────────────────────────────────────
    #  「몇 개 맞았나」보다 중요한 것: **임계값을 어디에 둬도 되는 구간이 얼마나 넓나.**
    #  구간이 좁으면 케이스가 하나만 늘어도 뒤집힌다.
    print('\n' + '=' * 96)
    print('■ ★ 임계값 안전 마진 — V AND C 에서 C 를 어디에 둘 수 있나')
    print('=' * 96)
    gated = [r for r in rows if (r['sig'].get('V') or 0) > E.SPREAD_H]
    land_c = sorted(r['sig'].get('C') for r in gated
                    if r['want'] == 'LAND' and r['sig'].get('C') is not None)
    chip_c = sorted(r['sig'].get('C') for r in gated
                    if r['want'] == 'CHIP' and r['sig'].get('C') is not None)
    print(f'  V > {E.SPREAD_H} 로 걸러진 것: {len(gated)}건 '
          f'(LAND {len(land_c)} · CHIP {len(chip_c)})')
    if land_c and chip_c:
        lo, hi = max(land_c), min(chip_c)
        print(f'  LAND 쪽 C 최대 = {lo:.3f}   ({[r["q"] for r in gated if r["want"]=="LAND"]})')
        print(f'  CHIP 쪽 C 최소 = {hi:.3f}   '
              f'({[r["q"] for r in gated if r["want"]=="CHIP" and abs((r["sig"].get("C") or 0)-hi)<1e-9]})')
        print(f'  ⇒ **임계값을 {lo:.3f} ~ {hi:.3f} 사이 어디에 둬도 같은 결과** '
              f'(폭 {hi-lo:.3f})')
        print(f'     지금 값 CLUSTER_H={E.CLUSTER_H} — 이 구간 안이면 안전.')
        print(f'     ⚠ 낮게 둘수록 «착지에 보수적»이다: 정말 한 동네일 때만 착지한다.')
    print('\n  (참고) 게이트 없이 C 단독으로 볼 때의 마진:')
    a = sorted(r['sig'].get('C') for r in rows if r['want'] == 'LAND' and r['sig'].get('C') is not None)
    b = sorted(r['sig'].get('C') for r in rows if r['want'] == 'CHIP' and r['sig'].get('C') is not None)
    if a and b:
        print(f'     LAND 최대 {max(a):.3f} / CHIP 최소 {min(b):.3f} → 폭 {min(b)-max(a):.3f}')
    a2 = sorted(r['sig'].get('Ctop') for r in rows if r['want'] == 'LAND' and r['sig'].get('Ctop') is not None)
    b2 = sorted(r['sig'].get('Ctop') for r in rows if r['want'] == 'CHIP' and r['sig'].get('Ctop') is not None)
    if a2 and b2:
        print(f'     Ctop: LAND 최소 {min(a2):.3f} / CHIP 최대 {max(b2):.3f} → '
              f'폭 {min(a2)-max(b2):+.3f}  (음수면 «겹친다» = 단독으로 못 가름)')

    print('\n' + '=' * 96)
    print('■ 오분류 (현재 방식: V ent > SPREAD_H)')
    print('=' * 96)
    for r in rows:
        v = r['sig'].get('V')
        if v is None:
            continue
        pred = 'CHIP' if v > E.SPREAD_H else 'LAND'
        if pred != r['want']:
            print(f'  🔴 {r["q"]}  정답={r["want"]} 예측={pred} '
                  f'(V={v:.3f} C={f(r["sig"].get("C"))} ncl={r["sig"].get("ncl")})')
            print(f'      상위: {r["top"]}')


asyncio.run(main())
