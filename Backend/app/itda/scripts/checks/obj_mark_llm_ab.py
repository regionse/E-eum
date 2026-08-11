# -*- coding: utf-8 -*-
r"""「다루는대상」·「누구를」을 낱말표로 채우는 게 맞나 — 낱말표 vs LLM (2026-08-11)

무엇이 문제인가
  `_OBJ_MARK`(58) + `_OBJ_DETAIL_MARK`(56) = **낱말 114개**로 슬롯을 «채운다».
      「할머니」 → 다루는대상=사람 · 대상세부=어르신
      「치매」   → 〃
  이건 «사람이 말하는 방식»(열린 집합)에 목록을 들이대는 것이다. 셀 수 없다.

  그리고 실측 사고가 있다(kl_demo01 1턴) —
      🧑「3주에 한 번은 병원에 같이 가야 해서요. 그런 것도 되는 일이 있을까요」
      [itda] 종류 — {"활동유형": {"돕기·돌봄": "못함"}}      ← 돌봄은 «못함»으로 잘 잡았다
      [itda] 다루는대상 코드보완: 사람                        ← 그런데 낱말표가 이걸 채웠고
      [itda] 누구를 코드보완: 환자·장애인                     ← 이것도 채웠다
      🤖 [카드 «일상생활기능지원»]                            ← 결국 돌봄 직무가 나갔다
    딱지는 «채우기 뒤»에 붙으므로 이 두 칸은 구조적으로 딱지를 못 받는다.
    즉 앞문은 막혔는데 **뒷문으로 돌봄이 들어왔다.**

무엇을 재나
  ① 낱말표  현행 `fill_object_slot` / `fill_obj_detail` 을 그대로 부른다
  ② LLM     같은 발화를 주고 「이 사람이 «상대하고 싶은» 대상」을 고르게 한다
            ⚠ 「말에 나온 대상」이 아니라 «원하는» 대상을 묻는다 — 그게 슬롯의 뜻이다

⚠ 정답표는 손으로 붙였다. 절반은 실측 대화(kl_*)와 personas.md 에서 가져왔다.

비용 — 케이스당 1콜 × 약 0.17원. 실측을 마지막에 찍는다.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/obj_mark_llm_ab.py
"""
import asyncio
import io
import json
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda.itda_core import (                       # noqa: E402
    fill_object_slot, fill_obj_detail, ItdaEngine as E)

OBJ = ['사람', '기계·설비', '컴퓨터·데이터', '자연·생물', '숫자·문서']

#  (발화, 새슬롯(LLM이 이번 턴에 담은 것), 정답 다루는대상 또는 None, 왜)
CASES = [
    # ── 채우면 «안» 되는 것 — 돌봄은 «상대하고 싶은 대상»이 아니다 ──
    ('3주에 한 번은 병원에 같이 가야 해서요. 그런 것도 되는 일이 있을까요',
     {'활동유형': ['돕기·돌봄']}, None,
     '★실측 kl_demo01 1턴 — 낱말표가 「사람」을 채워 돌봄 직무가 나갔다'),
    ('할머니가 치매신데 제가 봐요', {'활동유형': ['돕기·돌봄']}, None,
     '돌봄은 «의무»다. 상대하고 싶은 대상이 아니다'),
    ('돌봄 때문에 학원을 그만뒀어요', {}, None,
     '★ _llm_said_nothing 2261행 실측 — 낱말표가 「사람」을 채워 되돌렸다'),
    ('아빠 간병하느라 아무것도 못 했어요', {}, None, '위와 같은 꼴'),
    ('사람 상대하는 건 힘들어요', {'다루는대상': []}, None, '명시적 거부'),
    ('버스에서 학생들이랑 놀러다녔어', {}, None,
     '★ 2263행 실측 — 일상 발화인데 「학생」을 보고 사람을 채웠다'),
    ('엄마가 식당에서 밤늦게까지 일하세요', {}, None,
     '«남»의 이야기다. 이 사람이 상대할 대상이 아니다'),

    # ── 채워야 하는 것 ────────────────────────────────────────────
    ('어르신들이랑 얘기하는 건 편했어요', {'활동유형': ['돕기·돌봄']}, '사람',
     '실제로 «좋았다»고 했다'),
    ('아이들 가르치는 일 해보고 싶어요', {'활동유형': ['가르치기']}, '사람',
     '원한다고 말함'),
    ('기계 만지는 게 재밌어요', {'활동유형': ['조작']}, '기계·설비', '원함'),
    ('컴퓨터로 뭐 만드는 거 좋아해요', {'활동유형': ['만들기']}, '컴퓨터·데이터', '원함'),
    ('식물 키우는 거 좋아해요', {'관심분야': ['원예']}, '자연·생물', '원함'),
    ('엑셀 만지는 건 자신 있어요', {'관심분야': ['사무']}, '숫자·문서', '원함'),
    ('손님 응대하는 건 해봤어요', {'관심분야': ['판매']}, '사람',
     '해봤다 — 싫다고는 안 했다'),

    # ── 애매한 경계 ────────────────────────────────────────────────
    ('네일아트 배우고 싶어요', {'관심분야': ['네일미용']}, '사람',
     '네일은 손님을 상대하는 일이다 — 다만 발화에 「사람」이 없다'),
    ('용접 배워보려고요', {'관심분야': ['용접']}, '기계·설비',
     '발화에 「기계」가 없다 — 낱말표는 「용접」을 갖고 있다'),
    ('배달 4년 했어요', {'관심분야': ['배달']}, None,
     '대상이 분명하지 않다. 짐작하면 안 된다'),
    ('그냥 조용히 혼자 하는 일이면 좋겠어요', {}, None,
     '★ 실측(정지훈 9턴) — 이건 «방식»이지 대상이 아니다'),
    ('뭐라도 해야 되는데 뭘 해야 될지 모르겠어요', {}, None,
     'personas.md ① 첫 마디 — 아무 정보가 없다'),
    ('남편이 위암 수술하고 아직 회복 중이에요', {}, None,
     '★ 차은결 배경 — 사정 진술이지 진로 선호가 아니다'),
]


def w(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def pad(s, n):
    return str(s) + ' ' * max(1, n - w(s))


async def llm_obj(eng, msg):
    schema = {'type': 'OBJECT',
              'properties': {
                  '대상': {'type': 'STRING', 'enum': OBJ + ['없음'],
                          'description': '이 사람이 «일에서 상대하고 싶은» 대상. 모르면 없음.'},
                  '근거': {'type': 'STRING', 'description': '사용자 말에서 그대로 인용'}},
              'required': ['대상', '근거']}
    prompt = (
        '[사용자]가 «일에서 상대하고 싶은 대상»을 고르라.\n\n'
        f'[보기] {" · ".join(OBJ)}\n'
        f'[사용자] {msg}\n\n'
        '· 「좋다·하고 싶다·편했다·자신 있다」처럼 그 대상을 **원한다**고 했을 때만 고른다.\n'
        '· **돌봄·간병은 대개 «의무»다** — 「할머니를 돌봐요」·「병원에 같이 가요」는\n'
        '  그 사람이 «사람을 상대하고 싶다»는 뜻이 아니다. 없음이다.\n'
        '· 남의 이야기(「엄마가 식당에서 일해요」)·일상 이야기도 없음이다.\n'
        '· 일하는 «방식»(「조용히 혼자」)은 대상이 아니다. 없음이다.\n'
        '· 직업 이름만 말했으면 그 일이 «주로 상대하는» 것을 골라도 된다\n'
        '  (네일미용→사람, 용접→기계·설비).\n'
        '· 짐작하지 마라. 애매하면 없음이다. 없는 선호를 만들어 내는 쪽이 더 비싼 실수다.')
    try:
        j = await eng.gemini(prompt, schema, 0.0, think='minimal')
    except Exception as e:                              # noqa: BLE001
        return None, f'실패 {type(e).__name__}'
    v = ((j or {}).get('대상') or '없음').strip()
    return (None if v == '없음' else v), str((j or {}).get('근거') or '')[:26]


async def main():
    eng = E()
    print('=' * 124)
    print(f'  「다루는대상」 채우기 — 낱말표(114낱말) vs LLM · {len(CASES)}건 · {eng.model}')
    print('=' * 124)
    print()
    print(f'  {pad("발화", 44)} {pad("정답", 12)} {pad("①낱말표", 14)} {pad("②LLM", 12)}')
    print('  ' + '-' * 120)
    n1 = n2 = 0
    b1, b2 = [], []
    dump = []
    for msg, new, want, why in CASES:
        #  ★★ 2026-08-11 정정 — 처음엔 빈 프로필을 넘겼는데 그건 «실제와 다르다».
        #    fill_object_slot 에는 「활동유형에서 유도」 경로가 있어서(_ACT_OBJ),
        #    프로필에 활동유형이 있으면 결과가 달라진다. 실측 로그가 그 증거다 —
        #      [itda] 다루는대상 코드보완: 사람   ← 빈 프로필로는 재현이 안 됐다
        #    그리고 «대상세부»를 채점에서 빼고 있었다. 오늘 사고를 낸 칸이 그건데.
        _base = {k: v for k, v in new.items() if k == '활동유형' and v}
        _, got1 = fill_object_slot(dict(_base), msg, new)
        _, det = fill_obj_detail(dict(_base), msg, new)
        #  ★★ 2026-08-11 — **진짜 게이트를 부른다.** 처음엔 이 파일이 프롬프트 «사본»을
        #    갖고 있었다. 그러면 본체를 고쳐도 여기선 안 잡힌다 — 오늘 「못거르는조건」
        #    필드를 얹으면서 그걸 깨달았다. 사본을 재는 시험은 시험이 아니다.
        _r = await eng._obj_gate(msg, {})
        got2, ev = ((_r[0], '') if _r else (None, '호출실패'))
        #  정답이 「없음」인데 **둘 중 하나라도** 채웠으면 틀린 것이다
        #  — 없는 선호를 만들어 내는 쪽이 이 시험에서 제일 비싼 실수다.
        ok1 = (got1 == want) and not (want is None and det)
        ok2 = (got2 == want)
        n1 += ok1
        n2 += ok2
        if not ok1:
            b1.append(msg[:16])
        if not ok2:
            b2.append(msg[:16])
        s1 = (got1 or '없음') + (f'/{det}' if det else '')
        print(f'  {pad(msg[:42], 44)} {pad(want or "없음", 12)} '
              f'{pad(s1 + ("" if ok1 else " ✗"), 14)} '
              f'{pad((got2 or "없음") + ("" if ok2 else " ✗"), 12)}')
        dump.append({'발화': msg, '정답': want, '낱말표': got1, '대상세부': det,
                     'LLM': got2, 'LLM근거': ev, '왜': why})
    n = len(CASES)
    print('  ' + '-' * 120)
    print(f'  ① 낱말표 {n1}/{n}   틀린 것: {" · ".join(b1) or "없음"}')
    print(f'  ② LLM    {n2}/{n}   틀린 것: {" · ".join(b2) or "없음"}')
    u = eng.total_usage
    won = ((u.get('in', 0) - u.get('cached', 0)) * 0.25
           + u.get('cached', 0) * 0.025 + u.get('out', 0) * 1.50) / 1e6 * 1380
    print(f'\n  LLM 실측 — 호출 {u.get("calls",0)} · 입력 {u.get("in",0):,} '
          f'· 출력 {u.get("out",0):,} · **{won:.2f}원** '
          f'(호출당 {won/max(1,u.get("calls",1)):.3f}원)')
    print('=' * 124)
    print('  ※ 「없음」이 정답인 케이스가 절반이다 — «없는 선호를 만들어 내는» 쪽이 더 비싸다.')
    print('  ⚠ 20건은 통계가 아니라 «경계 확인»이다.')
    Path(__file__).with_name('_obj_mark_llm_ab.json').write_text(
        json.dumps({'잰날': '2026-08-11', '모델': eng.model, '낱말표': n1, 'LLM': n2,
                    '사용량': dict(u), '원': round(won, 2), '케이스': dump},
                   ensure_ascii=False, indent=1), encoding='utf-8')
    print('  원값 저장: _obj_mark_llm_ab.json')


asyncio.run(main())

