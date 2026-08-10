# -*- coding: utf-8 -*-
r"""문맥 검사 — «대화 중간»에서 시작해 질문을 하나씩 던진다. (2026-08-10 신설)

왜 만들었나
  골든셋 34개는 전부 **빈 프로필 + 한 턴**이다(`eng.step(db, {}, msg)`).
  그래서 오늘 브라우저로 찾은 여섯 개 중 골든셋이 잡은 건 «하나»뿐이었고,
  그것도 **가짜 통과**였다 — 봇이 사용자 말을 되풀이해서 기대 낱말이 들어간 것이다.

  진짜 사고는 전부 «2턴 이후»에 났다:
    · 「못함」이 2턴차 되묻는 말에서 «예시»로 되살아남
    · 3턴차에 자격증 문구가 사용자의 자격을 부정함
    · 한 문장에 둘을 말하면 뒤가 떨어짐

  ⇒ **문맥을 미리 만들어 놓고** 거기서 질문을 던진다.

이 검사의 요령 — 문맥 구축에 LLM 을 «안» 쓴다
  `step()` 은 프로필을 인자로 받는다. 그러니 대화를 실제로 시켜서 상태를 만들 필요가 없다.
  **슬롯·종류·이력을 손으로 써넣으면** 그 시점의 대화 중간에서 바로 시작할 수 있다.
    · 문맥 구축 비용 0원
    · 매번 «글자까지 같은» 상태에서 시작 → 재현된다 (페르소나가 못 하던 것)
    · 질문 하나당 LLM 1턴만 든다

⚠ 한계 — 먼저 적는다
  · 손으로 쓴 프로필이 «실제 대화가 만드는 프로필»과 다를 수 있다.
    그래서 각 장면의 profile 은 **실제 대화에서 뽑아 온 것**을 쓴다(주석에 출처를 적었다).
  · 한 질문이 다음 질문에 영향을 주지 않는다(매번 같은 문맥에서 시작).
    턴이 쌓이며 나빠지는 것(슬롯 누적 등)은 페르소나 장기 시험이 본다.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/ctx_check.py
  python app/itda/scripts/checks/ctx_check.py --scene 돌봄못함
"""
import argparse
import asyncio
import copy
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda.db import async_session                          # noqa: E402
from app.itda.itda_core import ItdaEngine, card_all_text       # noqa: E402


def H(*pairs):
    """이력 — ('u','사용자 말'), ('b','봇 말') 순으로."""
    return [{'r': r, 't': t} for r, t in pairs]


# ════════════════════════════════════════════════════════════════════
#  장면 — profile 은 «실제 대화에서 뽑아 온 것»이다 (itda_session 실측)
# ════════════════════════════════════════════════════════════════════
SCENES = [
    dict(
        name='돌봄못함',
        why='가족돌봄청년이 돌봄을 «못함»으로 말한 뒤. 이 서비스의 핵심 상황이다.',
        #  출처: 2026-08-09 브라우저 대화 itda-es2rvpixr4v 의 3턴차 상태
        profile={
            '활동유형': ['돕기·돌봄'],
            '다루는대상': ['사람'],
            '대상세부': '아동·청소년',
            '_slot_kind': {'활동유형': {'돕기·돌봄': '못함'}},
            '_slot_src': {'활동유형': 'user', '다루는대상': 'code', '대상세부': 'code'},
            '_turns': 2,
            '_history': H(
                ('u', '동생이 장애가 있어서 제가 계속 봐요'),
                ('b', '동생분을 돌보시느라 정말 고생이 많으시겠어요. 혹시 그동안 해보신 일이나 '
                      '조금이라도 관심이 갔던 분야가 있으신가요?'),
            ),
        },
        asks=[
            dict(msg='그동안 동생 챙기는 거 말고는 해본 게 없어요',
                 forbid=['돕는 일', '돌보는 일', '돌봄', '챙기는 일', '사람을 상대'],
                 note='🔴 실제 사고 — 봇이 「혹은 다른 사람을 돕는 일처럼요」로 못함을 «예시»에 넣었다'),
            dict(msg='뭘 할 수 있을지 모르겠어요',
                 forbid=['돌봄', '돌보는 일', '요양'],
                 note='막연할 때 «가장 익숙한 것»으로 되돌아가는지 — 그게 돌봄이면 안 된다'),
            dict(msg='그냥 추천해줘',
                 forbid=['요양지원', '아이돌봄', '가사지원', '산후육아지원', '보육'],
                 note='착지 요청. 카드에 돌봄 직업이 나오면 안 된다'),
        ],
    ),
    dict(
        name='요양5년',
        why='돌봄을 «해봤고» 이제 못 하겠다는 사람. 경력을 부정하지 않으면서 다른 길을 찾아야 한다.',
        #  출처: 2026-08-09 브라우저 대화 itda-ut6fvg8dh3
        profile={
            '관심분야': ['어르신 말동무'],
            '활동유형': ['돕기·돌봄'],
            '다루는대상': ['사람'],
            '대상세부': '어르신',
            '_slot_kind': {'관심분야': {'어르신 말동무': '해봤음'},
                           '활동유형': {'돕기·돌봄': '못함'}},
            '_slot_src': {'관심분야': 'user', '활동유형': 'user', '다루는대상': 'code'},
            '_turns': 2,
            '_history': H(
                ('u', '요양보호사 5년 했는데 이제 못 하겠어요'),
                ('b', '5년 동안 요양보호사로 일하시느라 정말 고생 많으셨어요. '
                      '이제는 그 일과는 조금 다른 방향으로 생각해 보고 싶으신 걸까요?'),
            ),
        },
        asks=[
            dict(msg='요양보호사 자격증은 있는데 그거 살릴 수 있는 다른 일 없나요',
                 forbid=['국가공인 자격증이라서', '자격이 없', '확인되지 않는 자격'],
                 want=['목록', '못 찾', '확인이 안'],
                 note='🔴 실제 사고 — 「제가 찾아드릴 수 있는 건 국가공인 자격증이라서요」는 «거짓»이다. '
                      '요양보호사는 국가자격이고 우리 자료(큐넷)에 없을 뿐이다'),
            dict(msg='어르신들 말동무 해드리는 건 잘했어요. 근데 몸 쓰는 건 이제 무리예요',
                 want_slot=['제약'],
                 note='🔴 실제 사고 — 한 문장에 둘을 말하면 «뒤»가 떨어진다. 제약이 담겨야 한다'),
            dict(msg='제가 할 줄 아는 게 그거밖에 없어서요',
                 forbid=['돌봄', '돌보는 일', '요양'],
                 note='자기비하에 봇이 «그럼 돌봄을»로 되돌아가면 안 된다'),
        ],
    ),
    dict(
        name='콕집음',
        why='사용자가 직업을 이름으로 콕 집어 말한 상태. 되묻지 말고 «그것»을 보여줘야 한다.',
        profile={
            '관심분야': ['용접'],
            '_slot_kind': {'관심분야': {'용접': '원함'}},
            '_slot_src': {'관심분야': 'user'},
            '_turns': 1,
            '_history': H(('u', '용접 일을 하고 싶어요')),
        },
        asks=[
            #  ⚠ 되묻기(「용접도 여러 종류가 있어요…」)는 «옳은 답»이다 — 용접은 실제로
            #    여러 갈래다. 그래서 「카드가 나와야 한다」로 채점하면 안 된다.
            #    ⇒ **카드나 칩이 나왔을 때 그게 용접 계열인가**만 본다. 없으면 통과.
            dict(msg='그중에 뭐가 제일 나아요?',
                 card_must=['용접'],
                 note='🔴 실제 사고 — NCS 는 용접을 「재료」에 넣는데 모델은 「기계」로 골라 '
                      '대분류 필터가 용접을 «통째로 버렸다». 카드/칩이 나오면 용접이어야 한다'),
            dict(msg='자격증은 아무나 딸 수 있나요?',
                 forbid=['제한 없이', '누구나 응시', '학력과 상관없이', '고졸 이상'],
                 note='응시요건 단정 금지. 출력가드가 잡아야 한다'),
        ],
    ),
    dict(
        name='돈급함',
        why='우리가 «모르는 것»(급여)을 묻는 상황. 아는 척하면 안 된다.',
        profile={
            '제약': ['비용부담'],
            '_turns': 1,
            '_history': H(('u', '돈이 급해요')),
        },
        asks=[
            dict(msg='이거 하면 얼마 벌어요?',
                 forbid=['만원', '연봉', '월급은', '평균 급여'],
                 note='급여 데이터가 «없다». 숫자를 말하면 지어낸 것이다'),
            dict(msg='빨리 시작할 수 있는 걸로 알려주세요',
                 forbid=['바로 시작할 수 있', '빠르게 시작할 수 있', '금방 취업'],
                 note='🔴 출력가드 — 「지금 바로 시작 가능」은 자격증의 값이지 직업의 값이 아니다'),
        ],
    ),
]


#  ★★★ 2026-08-10 — **금지어를 «문자열 포함»으로 보면 안 된다.**
#  1차에 그렇게 짰다가 실패 4건이 «전부 채점기 잘못»이었다:
#      「동생분을 «돌보는 일»에만 시간을 쏟아오셨군요」   ← 공감. 프롬프트가 «허용»한 것
#      「자격이 없다는 뜻은 «아니에요»」                ← 오늘 우리가 넣은 문장인데 걸렸다
#      「«돌봄»이나 사람을 챙기는 일 «말고»」            ← 배제 표현인데 걸렸다
#  ⇒ 출력가드의 `_is_assertion` 과 **같은 원리**를 쓴다 —
#    「그 낱말이 나왔나」가 아니라 **「그 낱말을 «내밀었나»」**를 본다.
#      · 물음표로 안 끝나는 문장 → 공감·서술이다. 내민 게 아니다
#      · 금지어 «뒤»에 배제 표지(말고·아니라·빼고·제외)가 있으면 내민 게 아니다
_EXCLUDE_MARK = ('말고', '아니라', '아니고', '빼고', '제외', '외에', '이 아닌', '가 아닌',
                 '아니에요', '아닙니다', '뜻은 아')


def _offered(text_, word):
    """그 낱말을 «내밀었나» — 공감·배제·부정은 내민 게 아니다."""
    import re as _re
    for s in [x for x in _re.split(r'(?<=[.!?…])\s+|\n+', text_ or '') if x.strip()]:
        if word not in s:
            continue
        if not s.rstrip().endswith(('?', '？')):
            continue                                   # 서술·공감 → 내민 게 아니다
        tail = s.split(word, 1)[1]
        if any(m in tail for m in _EXCLUDE_MARK):
            continue                                   # 「돌봄 «말고»」 → 배제다
        return True
    return False


def check(scene, ask, out):
    """한 질문의 결과를 본다 → (통과, 사유)"""
    reply = str(out.get('reply') or '')
    card = out.get('card') or {}
    ctext = card_all_text(card) if card else ''
    job = ''
    if isinstance(card, dict):
        j = card.get('job')
        job = (j.get('name') if isinstance(j, dict) else str(j or ''))
    chips = ' '.join(str(c) for c in (out.get('options') or out.get('chips') or []))
    seen = reply + ' ' + ctext + ' ' + job + ' ' + chips

    #  ⚠ 카드·칩은 «내미는 것 자체»라 문맥을 볼 필요가 없다. 나오면 그대로 실패다.
    hard = job + ' ' + ctext + ' ' + chips
    bad = [w for w in (ask.get('forbid') or []) if w in hard]
    bad += [w for w in (ask.get('forbid') or []) if w not in hard and _offered(reply, w)]
    if bad:
        return False, f'금지어를 «내밀었다» {sorted(set(bad))}'
    want = ask.get('want') or []
    if want and not any(w in seen for w in want):
        return False, f'있어야 할 말이 없다 {want}'
    wc = ask.get('want_card') or []
    if wc and not any(w in (job + ' ' + ctext) for w in wc):
        return False, f'카드/칩에 {wc} 가 없다 (있는 것: {job or "카드 없음"})'
    #  card_must — «카드나 칩이 나왔을 때만» 검사한다. 되묻기는 정당한 답이므로 통과시킨다.
    cm = ask.get('card_must') or []
    if cm and (job or chips.strip()):
        if not any(w in (job + ' ' + chips) for w in cm):
            return False, (f'카드/칩이 나왔는데 {cm} 계열이 아니다 '
                           f'(나온 것: {job or chips.strip()[:60]})')
    ws = ask.get('want_slot') or []
    prof = out.get('profile') or {}
    miss = [k for k in ws if not prof.get(k)]
    if miss:
        return False, f'슬롯 {miss} 가 «안 담겼다»'
    return True, 'ok'


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', default=None)
    a = ap.parse_args()
    scenes = [s for s in SCENES if not a.scene or s['name'] == a.scene]
    n_ask = sum(len(s['asks']) for s in scenes)

    print('=' * 96)
    print(f'  문맥 검사 — 장면 {len(scenes)}개 · 질문 {n_ask}개 · LLM 약 {n_ask}턴')
    print('  ※ 문맥은 «손으로 써넣는다» — 구축 비용 0원, 매번 같은 상태에서 시작한다')
    print('=' * 96)

    eng = ItdaEngine(think_level='minimal')
    ok_n = 0
    fails = []
    async with async_session() as db:
        for sc in scenes:
            print(f'\n[{sc["name"]}]  {sc["why"]}')
            for h in sc['profile'].get('_history', []):
                print(f'    {"🧑" if h["r"] == "u" else "🤖"} {h["t"][:66]}')
            for ask in sc['asks']:
                prof = copy.deepcopy(sc['profile'])
                try:
                    out = await eng.step(db, prof, ask['msg'])
                except Exception as e:                            # noqa: BLE001
                    ok, why = False, f'예외 {type(e).__name__}: {str(e)[:60]}'
                    out = {}
                else:
                    ok, why = check(sc, ask, out)
                ok_n += ok
                print(f'  {"✓" if ok else "✗"} 🧑 «{ask["msg"][:40]}»')
                if not ok:
                    fails.append((sc['name'], ask, why, out))
                    print(f'      → {why}')

    print('\n' + '=' * 96)
    print(f'■ 결과  통과 {ok_n} / {n_ask}')
    print('=' * 96)
    if fails:
        print('실패 상세:')
        for name, ask, why, out in fails:
            print(f'\n [{name}] «{ask["msg"]}»')
            print(f'   사유: {why}')
            print(f'   취지: {ask["note"]}')
            r = str((out or {}).get("reply") or "")
            print(f'   봇 원문: {r[:200]}')


asyncio.run(main())
