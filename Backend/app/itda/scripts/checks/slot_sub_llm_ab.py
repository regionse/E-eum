# -*- coding: utf-8 -*-
r"""㉮ 지목 제거 — 낱말표 vs 위치규칙 vs **LLM** (2026-08-11)

무엇에 답하려는 건가
  「낱말표 없이 그냥 LLM 에게 시키면 안 되나?」
  추측하지 말고 «같은 채점표»로 나란히 잰다.

세 조건
  ① 낱말표(예전)  `_NEG_MARK` 중 하나라도 발화에 있으면 ㉮ 를 돌린다        8/13
  ② 위치(오늘)    부정어가 값 «뒤»에 있을 때만 ㉮                          12/13
  ③ LLM(이번)     누적된 값과 발화를 주고 「이제 아니라고 한 것」을 고르게 한다

⚠ 프롬프트를 «허수아비»로 만들지 않았다. 오늘 92% 를 낸 `_reject_gate` 와 같은 방식으로
  짰다 — 시스템 프롬프트 없음 · enum 구속 · 「애매하면 빈 목록」 · 「고르는 말은 아니다」.
  LLM 이 지면 그건 프롬프트가 나빠서가 아니라 이 일에 안 맞아서여야 한다.

⚠ 정답표는 `slot_sub_rule_ab.py` 와 «똑같다». 절반이 이 파일에 박힌 실측 사고다.

비용 — 13콜 × 약 0.17원 ≈ **2.2원** (실측값을 마지막에 찍는다)

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/slot_sub_llm_ab.py
"""
import asyncio
import io
import json
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda.itda_core import (                       # noqa: E402
    slot_subtract, _NEG_MARK, _POS_MARK, _PIVOT, _sub_pieces, as_list,
    ItdaEngine as E)


#  ★ 채점표는 slot_sub_rule_ab.py 것을 «그대로» 쓴다 — 둘이 갈라지면 비교가 무의미해진다.
#  ⚠ import 하지 않는다. 그 파일은 모듈 수준에서 표를 찍으므로 import 만으로 통째로 돈다
#    (실측기록 §「ast 로 리터럴만 꺼냈다」와 같은 상황을 여기서 또 만났다).
#    ⇒ ast 로 CASES 리터럴만 꺼낸다. 코드는 한 줄도 실행되지 않는다.
def _load_cases():
    import ast
    src = (Path(__file__).with_name('slot_sub_rule_ab.py')
           .read_text(encoding='utf-8'))
    for node in ast.parse(src).body:
        if (isinstance(node, ast.Assign)
                and any(getattr(t, 'id', '') == 'CASES' for t in node.targets)):
            return ast.literal_eval(node.value)
    raise RuntimeError('slot_sub_rule_ab.py 에서 CASES 를 못 찾았다')


CASES = _load_cases()


#  ── ① 낱말표(예전 동작) 재현 ────────────────────────────────────────
def old_rule(m, x):
    """예전 ㉮ — 값이 발화에 «있기만» 하면 뺀다(부정어 위치는 안 본다)."""
    return any(pc in m for pc in _sub_pieces(x))


#  ── ③ LLM ──────────────────────────────────────────────────────────
async def llm_rule(eng, msg, slots):
    """누적 값 중 「이제 아니다」라고 한 것을 고르게 한다.

    ⚠ 여기서 «묻는 것»이 중요하다. 「부정어가 있나」가 아니라
      **「이 사람이 이걸 이제 원하지 않는다고 말했나」**를 묻는다.
      낱말표가 재던 것은 앞엣것이고, 우리가 알고 싶은 건 뒤엣것이다.
    """
    vals = [v for vs in slots.values() for v in as_list(vs) if v]
    if not vals:
        return []
    schema = {'type': 'OBJECT',
              'properties': {
                  '뺄것': {'type': 'ARRAY',
                          'description': '사용자가 «이제 아니다»라고 한 것. 없으면 빈 목록.',
                          'items': {'type': 'STRING', 'enum': list(vals)}},
                  '근거': {'type': 'STRING', 'description': '사용자 말에서 그대로 인용'}},
              'required': ['뺄것', '근거']}
    prompt = (
        '[지금까지 이 사람에 대해 적어 둔 것] 중에서, [사용자]가 이번 말로\n'
        '«이제 아니다»라고 물린 것을 고르라.\n\n'
        f'[지금까지 적어 둔 것] {" · ".join(vals)}\n'
        f'[사용자] {msg}\n\n'
        '· 그것이 «싫다·힘들다·못 하겠다·안 맞는다»는 뜻이면 고른다.\n'
        '· **하나를 «고르는» 말은 고르지 않는다** — 「그걸로 할게요」·「아니 그거요」처럼\n'
        '  «이걸 달라»는 뜻이면 앞에 부정어가 붙어도 무르는 것이 아니다.\n'
        '· 앞의 «오해를 바로잡는» 말도 고르지 않는다 — 부정어가 가리키는 것이\n'
        '  적어 둔 것이 아니라 「내 말뜻」이면 아니다.\n'
        '· 「A는 좋은데 B는 힘들어요」처럼 조건을 단 것은 «취소가 아니다» — 고르지 않는다.\n'
        '· 형편·제약을 말한 것(「밤엔 못 나가요」)은 그 자체로는 무르는 것이 아니다.\n'
        '· 짐작하지 마라. 애매하면 빈 목록이다. 있던 정보를 지우는 쪽이 더 비싼 실수다.')
    try:
        j = await eng.gemini(prompt, schema, 0.0, think='minimal')
    except Exception as e:                              # noqa: BLE001
        print(f'  (LLM 실패 {type(e).__name__}: {str(e)[:50]})')
        return []
    return [v for v in (j or {}).get('뺄것') or [] if v in vals]


def w(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def pad(s, n):
    return str(s) + ' ' * max(1, n - w(s))


async def main():
    eng = E()
    print('=' * 122)
    print(f'  ㉮ 지목 제거 — 낱말표 vs 위치 vs LLM · 케이스 {len(CASES)}건 · 모델 {eng.model}')
    print('=' * 122)
    print()
    print(f'  {pad("발화", 46)} {pad("빠져야?", 8)} {pad("①낱말표", 10)} '
          f'{pad("②위치", 8)} {pad("③LLM", 8)}')
    print('  ' + '-' * 118)

    n1 = n2 = n3 = 0
    bad = {'①낱말표': [], '②위치': [], '③LLM': []}
    dump = []
    for msg, prof, new, want, src in CASES:
        m = re.sub(r'\s+', '', msg)
        k, x0 = next(iter(prof.items()))
        x = as_list(x0)[0]
        #  ② 위치 — 지금 살아 있는 함수를 그대로 돌린다
        _, sub = slot_subtract(dict(prof), new, msg)
        r2 = bool(sub)
        #  ① 낱말표 — 예전 조건을 재현(제약 슬롯·긍정 가드는 현행과 같다)
        neg = any(n in m for n in _NEG_MARK)
        pos = any(t in m for t in _POS_MARK)
        piv = any(t in m for t in _PIVOT)
        guard = (k != '제약') and not pos and (neg or piv)
        r1 = bool(guard and neg and not pos and old_rule(m, x))
        #  ③ LLM
        got = await llm_rule(eng, msg, prof)
        r3 = (x in got)

        for nm, r in (('①낱말표', r1), ('②위치', r2), ('③LLM', r3)):
            if r != want:
                bad[nm].append(msg[:18])
        n1 += (r1 == want); n2 += (r2 == want); n3 += (r3 == want)
        f = lambda r: ('뺌' if r else '유지') + ('' if r == want else ' ✗')  # noqa: E731
        print(f'  {pad(msg[:44], 46)} {pad("뺌" if want else "유지", 8)} '
              f'{pad(f(r1), 10)} {pad(f(r2), 8)} {pad(f(r3), 8)}')
        dump.append({'발화': msg, '누적': prof, '정답': want, '출처': src,
                     '①낱말표': r1, '②위치': r2, '③LLM': r3, 'LLM고른것': got})

    n = len(CASES)
    print('  ' + '-' * 118)
    for nm, sc in (('① 낱말표', n1), ('② 위치  ', n2), ('③ LLM   ', n3)):
        key = nm.replace(' ', '')
        print(f'  {nm} {sc}/{n}   틀린 것: '
              f'{" · ".join(bad.get(key) or bad.get(nm.strip()) or []) or "없음"}')
    u = eng.total_usage
    won = ((u.get('in', 0) - u.get('cached', 0)) * 0.25
           + u.get('cached', 0) * 0.025 + u.get('out', 0) * 1.50) / 1e6 * 1380
    print()
    print(f'  LLM 실측 — 호출 {u.get("calls",0)} · 입력 {u.get("in",0):,} · 출력 {u.get("out",0):,} '
          f'· **{won:.2f}원** (호출당 {won/max(1,u.get("calls",1)):.3f}원)')
    print('=' * 122)
    print('  ※ 「유지」 오답이 훨씬 비싸다 — 사용자가 방금 «고른 것»이 사라지는 쪽이다.')
    print('  ⚠ 13건은 통계가 아니라 «경계 확인»이다.')

    out = Path(__file__).with_name('_slot_sub_llm_ab.json')
    out.write_text(json.dumps({'잰날': '2026-08-11', '모델': eng.model,
                               '①낱말표': n1, '②위치': n2, '③LLM': n3,
                               '사용량': dict(u), '원': round(won, 2),
                               '케이스': dump}, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    print(f'  원값 저장: {out.name}')


asyncio.run(main())
