# -*- coding: utf-8 -*-
r"""「왜 굳이 엔트로피까지?」 — RRF만 / +리랭커 / +엔트로피 를 «같은 100건»으로 가른다.
   그리고 같은 데이터로 RRF 의 k 를 쓸어 본다. (2026-08-10 신설)

무엇에 답하려는 건가
  발표에서 나올 두 질문이다.
    ① 「k=60 은 왜죠?」        — 재본 적이 없으면 「표준값이라서」밖에 답이 없다.
    ② 「엔트로피까지 왜 필요해요? 리랭커면 충분하지 않나요?」
  ②가 특히 아프다. 층을 하나 더 얹었으면 «그 층이 무엇을 벌었는지» 숫자로 말해야 한다.

세 조건 — 무엇이 다른가
  A. RRF만          RRF 1위를 그대로 카드로 낸다
  B. +리랭커        리랭커가 다시 줄 세운 1위를 카드로 낸다
  C. +엔트로피      B 에 «답할지 말지»를 하나 더 건다
                    1단 TOP% < 0.90  → 방향 칩(=답 안 함)
                    2단 엔트로피 ≥ 0.70 → 세부 칩(=답 안 함)
                    둘 다 통과해야 카드

★ 세 조건은 «같은 잣대로 못 잰다». A·B 는 항상 답하고 C 는 가려서 답한다.
  그래서 C 는 두 숫자로 본다 —
    답한 비율(coverage)  ·  답했을 때 맞은 비율(precision)
  엔트로피가 값어치가 있으려면 **C 의 precision 이 B 보다 높아야** 한다.
  그리고 «막은 것들이 실제로 틀렸을 것»이어야 한다 — 그것도 같이 센다.

검색은 케이스당 «한 번»만 돈다
  벡터·키워드 순위를 받아 두고 k 만 바꿔 다시 합친다. 리랭커도 한 번만 부른다.
  ⇒ k 를 몇 개 재든, 조건을 몇 개 재든 추가 비용이 0 이다.

비용
  생성 LLM **0회**. 임베딩 n회 + Pinecone n회 + FULLTEXT n회 + 리랭커 n회.
  ⚠ 임베딩 단가는 «확인하지 않았다». 리랭커는 무료 등급(match.py 2026-08-05 확인).

⚠ 한계 — 먼저 적는다
  · 정답표가 합성이다(build_calibration_set). 사람이 라벨링한 게 아니다.
  · 질의를 «원문 하나»만 쓴다. 실사용은 최대 4개(원문·슬롯·LLM변형)를 넣는다.
    다른 변수를 고정해야 k·층의 효과만 보이기 때문이다. 실사용에서 같다는 보장은 없다.
  · C 의 「막은 게 옳았나」는 정답표 기준이다. 실제 사용자가 칩을 보고 좋아했는지는 못 잰다.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/gate_ablation.py [--n 100]
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
from app.itda import match as M                                    # noqa: E402
from app.itda.itda_core import ItdaEngine as E                     # noqa: E402

SET = Path(__file__).resolve().parents[1] / 'calibration_set.json'
KS = [0, 1, 2, 3, 5, 8, 15, 30, 60, 120]   # 0~5 를 촘촘히 — 여기서 갈린다
POOL = 8            # 실사용 JOB_CAND_POOL 과 같은 값으로 자른다
OVER = 40           # 재조합 재료를 넉넉히 받아 둔다


def rrf(*lists, k=60):
    """match._rrf 와 «같은 식». k 만 바꿔 부르려고 여기 둔다."""
    sc = {}
    for lst in lists:
        for i, c in enumerate(lst, 1):
            sc[c] = sc.get(c, 0.0) + 1.0 / (k + i)
    return sorted(sc, key=lambda c: -sc[c])


async def jobs_meta(db, codes):
    """리랭커에 넘길 문서 문자열 — 실사용 `_rr_docs` 와 «같은 모양»으로 만든다.
    (이름 + 중분류 + 설명 120자). 코드만 주면 리랭커가 읽을 게 없다."""
    if not codes:
        return {}
    from sqlalchemy import text as _t
    rs = (await db.execute(
        _t('SELECT job_code, job_name, job_mcls_name, job_description '
           'FROM job_catalog WHERE job_code IN :c').bindparams(
               __import__('sqlalchemy').bindparam('c', expanding=True)),
        {'c': list(codes)})).fetchall()
    return ({str(r[0]): f'{r[1]} {r[2] or ""} {(r[3] or "")[:120]}'.strip() for r in rs},
            {str(r[0]): (r[2] or '') for r in rs})          # 문서, 중분류(묶음 판정용)


async def collect(db, q):
    """한 질의의 «재료»를 모은다 — 벡터 순위 · 키워드 순위 · 직업 문서."""
    vec = await M._search(q, M.NS_JOB, OVER, 0.0)
    kw = await M._keyword_jobs(db, q, OVER)
    v_ids = [c for c, _ in vec]
    k_ids = [c for c, _ in kw]
    meta, grp = await jobs_meta(db, list(dict.fromkeys(v_ids + k_ids))[:60])
    return v_ids, k_ids, dict(vec), dict(kw), meta, grp


def hit(order, ans, n=1):
    return ans in order[:n]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=100)
    a = ap.parse_args()

    items = json.loads(SET.read_text(encoding='utf-8'))
    items = (items.get('items') if isinstance(items, dict) else items)[:a.n]

    print('=' * 96)
    print(f'  게이트 어블레이션 — 질의 {len(items)}개 · 검색은 케이스당 «한 번»')
    print('  생성 LLM 0회. 임베딩·Pinecone·FULLTEXT·리랭커만 돈다.')
    print('=' * 96)

    rows = []
    async with async_session() as db:
        for i, it in enumerate(items, 1):
            q = it.get('question') or it.get('q')
            ans = str(it.get('job_code'))
            try:
                v_ids, k_ids, vs, ks, meta, grp = await collect(db, q)
            except Exception as e:                                 # noqa: BLE001
                print(f'  [{i}] 검색 실패 {type(e).__name__}: {str(e)[:60]}')
                continue
            rows.append({'q': q, 'ans': ans, 'v': v_ids, 'k': k_ids,
                         'vs': vs, 'meta': meta, 'grp': grp})
            if i % 20 == 0:
                print(f'  … 검색 {i}/{len(items)}')

    #  ── ① k 쓸기 (재조합만. 추가 비용 0) ──────────────────────────
    print()
    print(f'  {"k":>4s}  {"@1":>5s} {"@3":>5s} {"@5":>5s} {"@8":>5s}   변화(@1)')
    print('  ' + '-' * 50)
    base = None
    best = None
    for k in KS:
        h = {t: 0 for t in (1, 3, 5, 8)}
        for r in rows:
            o = rrf(r['v'], r['k'], k=k)
            for t in h:
                h[t] += hit(o, r['ans'], t)
        if base is None:
            base = h[1]
            d = '기준'
        else:
            d = f'{h[1] - base:+d}'
        mark = ' ←지금' if k == 60 else ''
        print(f'  {k:4d}  {h[1]:5d} {h[3]:5d} {h[5]:5d} {h[8]:5d}   {d}{mark}')
        if best is None or h[1] > best[1]:
            best = (k, h[1])
    print(f'\n  → @1 이 가장 높은 k = {best[0]} ({best[1]}/{len(rows)})')

    #  ── ② 조건 갈라보기 (리랭커 1회 · 나머지는 계산만) ─────────────
    #    신호 넷을 «각각» 그리고 «겹쳐서» 잰다.
    #      TOP%   _cluster_top   1위 «묶음»(중분류)의 점유율 — 「방향이 정해졌나」
    #      V-ent  _spread_entropy 벡터 점수 분포의 정규화 엔트로피 — 「그 안에서 갈리나」
    #      C-ent  _cluster_entropy 묶음 분포의 엔트로피 — 2026-08-06 에 «기각»했던 신호
    #      RR-min _rr_ok         리랭커 절대점수 문턱(0.05) — 「관련 있다고는 보나」
    print()
    print('  ── 리랭커를 부른다 (케이스당 1회) ──')
    CONDS = ['A. RRF만', 'B. +리랭커', 'C1. +TOP%', 'C2. +V-ent',
             'C3. +C-ent', 'C4. +TOP% & V-ent', 'C5. +TOP% & V-ent & RR-min']
    st = {c: {'ans': 0, 'hit': 0} for c in CONDS}
    blk = {c: {'good': 0, 'bad': 0} for c in CONDS}
    #  ★ 2026-08-10 — 케이스별 «원값»을 남긴다. 표만 남기면 나중에 못 따진다
    #    (오늘만 두 번 겪었다 — 8/8 결과가 낡았는데 그걸 근거로 슬라이드를 고칠 뻔했다).
    dump = []
    for i, r in enumerate(rows, 1):
        order = rrf(r['v'], r['k'], k=60)[:POOL]
        a_ok = hit(order, r['ans'])
        st['A. RRF만']['ans'] += 1; st['A. RRF만']['hit'] += a_ok
        docs = [r['meta'].get(c, c) for c in order]
        try:
            rr = await M.rerank(r['q'], docs, top_n=len(docs))
        except Exception:                                          # noqa: BLE001
            rr = None
        if rr:
            r_order = [order[ix] for ix, _ in rr if 0 <= ix < len(order)]
            r_sc = {order[ix]: sc for ix, sc in rr if 0 <= ix < len(order)}
        else:
            r_order, r_sc = order, {c: 1.0 / (j + 1) for j, c in enumerate(order)}
        b_ok = hit(r_order, r['ans'])
        st['B. +리랭커']['ans'] += 1; st['B. +리랭커']['hit'] += b_ok

        jobs = [{'job_code': c, 'score': r['vs'].get(c, 0.0),
                 'group': r['grp'].get(c, ''), 'rr': r_sc.get(c, 0.0)} for c in order]
        ss = sorted((j['score'] for j in jobs if j['score'] > 0), reverse=True)
        ct, _ = E._cluster_top(jobs)
        ce, _ncl = E._cluster_entropy(jobs)   # (엔트로피, 묶음 수) 를 돌려준다
        g_top = (ct is not None and ct < E.CTOP_H)
        g_vent = (len(ss) >= 2 and E._spread_entropy(ss) >= E.SPREAD_H)
        g_cent = (ce is not None and ce >= E.SPREAD_H)
        g_rr = not any(j['rr'] > E.RR_MIN for j in jobs)
        for name, blocked in (('C1. +TOP%', g_top), ('C2. +V-ent', g_vent),
                              ('C3. +C-ent', g_cent),
                              ('C4. +TOP% & V-ent', g_top or g_vent),
                              ('C5. +TOP% & V-ent & RR-min', g_top or g_vent or g_rr)):
            if blocked:
                blk[name]['good' if not b_ok else 'bad'] += 1
            else:
                st[name]['ans'] += 1; st[name]['hit'] += b_ok
        dump.append({
            '질의': r['q'], '정답코드': r['ans'],
            'RRF1위': order[0] if order else None,
            '리랭커1위': r_order[0] if r_order else None,
            'RRF맞음': bool(a_ok), '리랭커맞음': bool(b_ok),
            'TOP%': None if ct is None else round(ct, 4),
            'V엔트로피': round(E._spread_entropy(ss), 4) if len(ss) >= 2 else None,
            'C엔트로피': None if ce is None else round(ce, 4),
            '리랭커최고점': round(max((j['rr'] for j in jobs), default=0.0), 4),
            '막힘': {'TOP%': bool(g_top), 'V-ent': bool(g_vent),
                    'C-ent': bool(g_cent), 'RR-min': bool(g_rr)},
            '후보8': order,
        })
        if i % 25 == 0:
            print(f'  … 리랭크 {i}/{len(rows)}')

    n = len(rows)
    print()
    print('  ' + '=' * 92)
    print(f'  {"조건":30s} {"답함":>5s} {"맞음":>5s} {"답한율":>7s} {"답했을때 정답률":>14s}  막기적중')
    print('  ' + '-' * 92)
    for c in CONDS:
        d = st[c]; b = blk[c]
        nb = b['good'] + b['bad']
        acc = d['hit'] / max(1, d['ans']) * 100
        bh = f"{b['good']}/{nb} ({b['good'] / nb * 100:.0f}%)" if nb else '—'
        print(f'  {c:30s} {d["ans"]:5d} {d["hit"]:5d} {d["ans"] / n * 100:6.0f}% '
              f'{acc:13.1f}%  {bh}')
    print('  ' + '=' * 92)
    print()
    print('  ※ 「답한율」이 낮을수록 되묻기가 잦다. 「답했을때 정답률」이 높을수록 확신할 때만 답한다.')
    print('  ※ 「막기적중」 = 막은 것 중 «리랭커도 틀렸을» 비율. 높을수록 잘 막은 것이다.')
    print('  ⚠ 정답표가 합성이고 질의가 원문 하나다. 실사용(질의 4개)과 다를 수 있다.')
    print('  ⚠ 되묻기는 «실패가 아니다» — 칩을 고르면 그 턴에 좁혀진다. 이 표는 그 이득을 못 잰다.')

    #  ── 원값 저장 — 표만 남기면 나중에 못 따진다 ──────────────────
    out = Path(__file__).with_name('_gate_ablation.json')
    ks_tbl = {}
    for k in KS:
        h = {t: 0 for t in (1, 3, 5, 8)}
        for r in rows:
            o = rrf(r['v'], r['k'], k=k)
            for t in h:
                h[t] += hit(o, r['ans'], t)
        ks_tbl[str(k)] = h
    out.write_text(json.dumps({
        '잰날': '2026-08-10', '케이스수': n,
        '설정': {'POOL': POOL, 'OVER': OVER, 'CTOP_H': E.CTOP_H,
                'SPREAD_H': E.SPREAD_H, 'SPREAD_T': E.SPREAD_T,
                'SPREAD_K': E.SPREAD_K, 'RR_MIN': E.RR_MIN},
        'k쓸기': ks_tbl,
        '조건별': {c: {**st[c], **{'막음': blk[c]}} for c in CONDS},
        '케이스': dump,
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    print('')
    print(f'  원값 저장: {out.name} (케이스 {len(dump)}건)')


asyncio.run(main())
