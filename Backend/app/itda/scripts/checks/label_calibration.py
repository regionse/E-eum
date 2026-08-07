# -*- coding: utf-8 -*-
"""1단계 — LLM 이 LAND/CHIP 라벨을 «붙일 수 있나»를 먼저 잰다. (2026-08-07)

왜 이걸 «먼저» 하나
  좁히기 신호 비교(spread_signals.py)는 라벨 14케이스로 잰 것이다. 「14개는 적다」는
  지적이 있어 100개로 늘리려는데, **문제는 발화가 아니라 라벨(정답)이다.**
  86개를 사람이 다 판단하면 오래 걸리고, LLM 에게 시키면 믿을 수 있는지 모른다.

  ⇒ **원래 14개는 사람이 붙인 라벨이다. 그걸 채점표로 쓴다.**
     LLM 에게 라벨을 «안 보여주고» 같은 14개를 판정하게 한 뒤, 사람 라벨과 대조한다.
     잘 맞으면 86개를 맡기고, 못 맞으면 여기서 멈추고 사람이 한다.

근거 (2026-08-07 조사 · 원문 확인)
  · Gilardi 외, PNAS 2023 (arXiv 2303.15056) — 트윗 2,382건에서 ChatGPT 의 zero-shot
    정확도가 5개 과제 중 4개에서 크라우드워커를 넘었고, **intercoder agreement 는
    크라우드워커와 훈련된 주석자 둘 다를 넘었다.**
  · Clarke & Dietz (arXiv 2412.17156) — 다만 «검색 적합성 판정»에서는 LLM 이 사람을
    대체 못 한다. **순환성** — LLM 은 사람 글로 배워 사람 판단을 흉내 내므로, 그 사람
    기준으로 채점하면 잘 맞는 것처럼 보이는 «타당성의 착시»가 생긴다.
    ⇒ 그래서 «대체»가 아니라 «먼저 검증»한다. 이 파일이 그 검증이다.
  ⚠ 우리 라벨은 「이 문서가 적합한가」(순환성이 물리는 자리)가 아니라
    「이 질의가 한 방향인가 여러 방향인가」다. 후보 문서를 안 본다. 그래도 잰다.

비용
  발화 14개를 «한 번에» 묶어 보낸다 × 3회 독립 판정 = **LLM 3회.** 대략 2원.

쓰는 법 (Backend/ 에서)
  python -m app.itda.scripts.checks.label_calibration
"""
import asyncio
import io
import os
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda import itda_core as E                                  # noqa: E402

#  ── 사람이 붙인 정답 (spread_signals.py CASES 와 «같은» 목록) ──────────
#     ⚠ 이 라벨은 LLM 에게 안 보여준다. 채점에만 쓴다.
HUMAN = [
    ('빵 만드는 일', 'LAND'),
    ('용접 일을 하고 싶어요', 'LAND'),
    ('자동차 고치고 정비하는 일', 'LAND'),
    ('머리 만지는 미용 일', 'LAND'),
    ('간호조무사가 되고 싶어요', 'LAND'),
    ('어르신 요양 돌보는 일', 'LAND'),
    ('제과제빵 쪽 일', 'LAND'),
    ('사람에게 도움이 되는 일', 'CHIP'),
    ('컴퓨터로 하는 일', 'CHIP'),
    ('손으로 뭔가 만드는 일', 'CHIP'),
    ('몸 안 쓰고 조용히 할 수 있는 일', 'CHIP'),
    ('자격증 따서 할 수 있는 일', 'CHIP'),
    ('돈 되는 일', 'CHIP'),
    ('사람 상대하는 일', 'CHIP'),
]

SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        '판정': {
            'type': 'ARRAY',
            'items': {
                'type': 'OBJECT',
                'properties': {
                    '번호': {'type': 'INTEGER'},
                    '라벨': {'type': 'STRING', 'enum': ['LAND', 'CHIP']},
                    '근거': {'type': 'STRING', 'description': '한 문장'},
                },
                'required': ['번호', '라벨', '근거'],
            },
        }
    },
    'required': ['판정'],
}

#  ⚠ 판정 기준은 spread_signals.py 의 라벨 정의를 «그대로» 옮겼다. 새로 쓰지 않았다.
#    (사람이 그 기준으로 붙였으므로, LLM 에게도 같은 기준을 줘야 공정하다)
PROMPT_HEAD = """진로 상담 챗봇이 사용자 발화를 받았다. 각 발화에 대해
**바로 직업을 추천해도 되는지(LAND)** / **어느 쪽인지 되물어야 하는지(CHIP)** 만 판정해라.

  LAND  방향이 «하나»로 정해진 발화.
        세부 갈래는 남아 있어도 「어느 동네인지」는 정해졌다.
  CHIP  방향이 «여럿»인 발화. 서로 다른 직업 동네가 섞인다.

★ 한국 NCS 직업 분류(1,094개)를 검색해 추천하는 상황이다.
★ 확실하지 않으면 억지로 정하지 말고, 더 그럴듯한 쪽을 고르되 근거를 짧게 남겨라.
★ 근거는 한 문장으로.

[발화 목록]
"""


async def one_round(eng, n):
    body = '\n'.join(f'{i+1}. {q}' for i, (q, _) in enumerate(HUMAN))
    r = await eng.gemini(PROMPT_HEAD + body, SCHEMA, 0.0 if n == 0 else 0.6)
    out = {}
    for it in (r or {}).get('판정') or []:
        try:
            out[int(it['번호'])] = (it['라벨'], it.get('근거', ''))
        except (KeyError, TypeError, ValueError):
            continue
    return out


async def main():
    eng = E.ItdaEngine()
    print('=' * 78)
    print('  LLM 라벨 검증 — 사람이 붙인 14개를 «라벨 없이» 다시 판정하게 한다')
    print(f'  LLM 3회 (발화 14개를 한 번에 묶어 보냄) · 대략 2원')
    print('=' * 78)

    rounds = []
    for n in range(3):
        try:
            rounds.append(await one_round(eng, n))
            print(f'  {n+1}회차 완료 ({len(rounds[-1])}건 응답)')
        except Exception as ex:                                   # noqa: BLE001
            print(f'  🔴 {n+1}회차 실패: {type(ex).__name__}: {str(ex)[:100]}')
            rounds.append({})

    print()
    print(f"{'':3} {'발화':<26} {'사람':<6} {'1':<6}{'2':<6}{'3':<6} {'다수결':<7} 결과")
    print('-' * 78)
    agree_major = 0
    unanimous = 0
    per_round = [0, 0, 0]
    disagreed = []
    for i, (q, human) in enumerate(HUMAN):
        got = [rounds[k].get(i + 1, ('?', ''))[0] for k in range(3)]
        for k in range(3):
            if got[k] == human:
                per_round[k] += 1
        cnt = Counter(g for g in got if g in ('LAND', 'CHIP'))
        major = cnt.most_common(1)[0][0] if cnt else '?'
        uni = len(set(got)) == 1 and got[0] in ('LAND', 'CHIP')
        unanimous += uni
        ok = (major == human)
        agree_major += ok
        if not ok or not uni:
            disagreed.append((q, human, got))
        print(f'{i+1:>3} {q[:24]:<26} {human:<6} '
              + ''.join(f'{g:<6}' for g in got)
              + f' {major:<7} {"✅" if ok else "🔴"}{"" if uni else "  (갈림)"}')

    print('-' * 78)
    n = len(HUMAN)
    print(f'  회차별 일치     {per_round[0]}/{n} · {per_round[1]}/{n} · {per_round[2]}/{n}')
    print(f'  다수결 일치     {agree_major}/{n}')
    print(f'  3회 만장일치    {unanimous}/{n}   ← LLM 끼리의 일관성')
    print()
    if agree_major >= 13:
        print('  ✅ 통과 — 86개를 LLM 에게 맡겨도 된다. 갈린 것만 사람이 본다.')
    elif agree_major >= 11:
        print('  ⚠ 애매 — 맡기되 «갈린 것 + 경계 사례»를 사람이 더 넓게 봐야 한다.')
    else:
        print('  🔴 부족 — 여기서 멈춘다. 라벨은 사람이 붙여야 한다.')
    if disagreed:
        print()
        print('  사람과 다르거나 LLM 끼리 갈린 것:')
        for q, h, got in disagreed:
            print(f'    · {q}   사람={h}  LLM={got}')


asyncio.run(main())
