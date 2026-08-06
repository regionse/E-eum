# -*- coding: utf-8 -*-
"""착지 속도 측정 — **몇 턴 만에 카드가 나오나. 슬롯은 누가 채웠나.**

걱정의 형태:
  「슬롯이 너무 쉽게 채워져서, 충분한 정보 없이 3~5턴 안에 직업이 나오는 것 아닌가」

그래서 여기서는 **카드를 달라고 하지 않는다.** 그냥 자연스럽게 이야기만 한다.
그런데도 카드가 나오면, 그게 답이다.

측정하는 것
  · 턴마다 슬롯이 몇 개 · 무엇이 찼나
  · 그중 **코드가 자동으로 넣은 것**(fill_object_slot)이 몇 개인가
  · can_land 가 언제 True 가 되나
  · 카드가 몇 턴째에 나오나
"""
import asyncio
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.db import async_session                       # noqa: E402
import app.itda.itda_core as core                           # noqa: E402
from app.itda.itda_core import ItdaEngine, can_land, as_list  # noqa: E402

#  ── 코드가 슬롯을 채운 횟수를 센다 ────────────────────────────────
_CODE_FILLS = []
_orig_fill = core.fill_object_slot


def _spy_fill(p, user_msg):
    p2, got = _orig_fill(p, user_msg)
    if got:
        _CODE_FILLS.append(got)
    return p2, got


core.fill_object_slot = _spy_fill

#  ⚠ 어느 흐름도 「추천해줘」라고 하지 않는다. 자연스러운 대화만.
FLOWS = [
    ('① 돌봄만 말함', [
        '요즘 할머니 돌보느라 정신이 없어요',
        '그냥 하루가 다 가요',
        '밤에도 몇 번씩 깨야 해서요',
        '언제까지 이럴지 모르겠어요',
    ]),
    ('② 경험만 나열', [
        '예전에 편의점에서 일했어요',
        '카페에서도 좀 했고요',
        '지금은 쉬고 있어요',
        '그때가 그래도 나았던 것 같아요',
    ]),
    ('③ 싫은 것만 말함', [
        '몸 쓰는 건 좀 힘들어요',
        '사람 많은 데도 별로고요',
        '앉아서만 하는 것도 답답하고',
        '잘 모르겠네요',
    ]),
    ('④ 모순', [
        '사람 만나는 건 좋아해요',
        '근데 오래 상대하는 건 힘들어요',
        '조용한 것도 좋고요',
        '음...',
    ]),
    ('⑤ 막연함만 반복', [
        '잘 모르겠어요',
        '생각해본 적이 없어서',
        '그냥요',
        '음...',
    ]),
    ('⑥ 감정만 말함', [
        '요즘 너무 지쳐요',
        '뭘 해도 힘이 안 나요',
        '이러다 아무것도 못 할 것 같아요',
        '어떻게 해야 할지 모르겠어요',
    ]),
    ('⑦ 점진적으로 정보 제공', [
        '집에서 할머니 챙기고 있어요',
        '약 챙겨드리고 병원도 같이 가요',
        '그런 건 이제 익숙해졌어요',
        '이런 걸로 뭐 할 수 있는 게 있을까요',
    ]),
    ('⑧ 한 문장 지목 (대조군)', [
        '제빵사가 되고 싶어요',
        '빵 만드는 게 재밌더라고요',
    ]),
]

AXES = ('관심분야', '활동유형', '다루는대상')


def slot_str(p):
    out = []
    for k in AXES:
        v = as_list(p.get(k))
        if v:
            out.append(f'{k[:2]}={"·".join(str(x) for x in v)}')
    extra = [f'{k[:2]}={"·".join(str(x) for x in as_list(p.get(k)))}'
             for k in ('세부관심', '강점성향', '제약') if p.get(k)]
    return ' | '.join(out + extra) or '(빈 슬롯)'


async def main():
    eng = ItdaEngine()
    summary = []
    async with async_session() as db:
        for name, turns in FLOWS:
            profile, card_turn, land_turn = {}, None, None
            n_code = 0
            print('=' * 96)
            print(f'  {name}')
            print('=' * 96)
            for i, msg in enumerate(turns, 1):
                _CODE_FILLS.clear()
                try:
                    out = await eng.step(db, profile, msg)
                except Exception as e:                       # noqa: BLE001
                    print(f'  [{i}] !! {type(e).__name__}: {str(e)[:60]}')
                    break
                profile = out.get('profile') or profile
                n_code += len(_CODE_FILLS)
                kind = out.get('kind')
                landed = can_land(profile)
                if landed and land_turn is None:
                    land_turn = i
                if kind == 'card' and card_turn is None:
                    card_turn = i
                mark = ''
                if _CODE_FILLS:
                    mark = f'   ★코드가 채움: {"·".join(_CODE_FILLS)}'
                print(f'  [{i}] 🧑 {msg}')
                print(f'      kind={kind:<9} can_land={"✅" if landed else "—"}'
                      f'{mark}')
                print(f'      슬롯: {slot_str(profile)}')
                if out.get('card'):
                    j = (out['card'].get('job') or {}).get('name')
                    print(f'      🃏 카드 = {j}')
                if out.get('options'):
                    print(f'      [칩] {out["options"]}')
            summary.append((name, land_turn, card_turn, n_code, len(turns)))
            print()

    print('=' * 96)
    print(f'{"흐름":<26} {"착지가능":<9} {"카드":<8} {"코드가 채운 슬롯":<14}')
    print('-' * 96)
    for name, lt, ct, nc, tot in summary:
        pad = 26 - sum(2 if ord(c) > 0x2E80 else 1 for c in name)
        print(f'{name}{" " * max(1, pad)} '
              f'{(str(lt) + "턴") if lt else "안 됨":<9} '
              f'{(str(ct) + "턴") if ct else "안 나옴":<8} '
              f'{nc}개')
    u = eng.total_usage
    print('=' * 96)
    print(f'LLM {u.get("calls",0)}회 · 입력 {u.get("in",0):,} · 출력 {u.get("out",0):,}')


asyncio.run(main())
