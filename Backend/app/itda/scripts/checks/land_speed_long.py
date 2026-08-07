# -*- coding: utf-8 -*-
"""착지 속도 — **긴 대화(14턴)** 판. `land_speed.py` 의 확장. (2026-08-07)

왜 만들었나
  `land_speed.py` 는 대화가 «4턴»이라 **12턴 완화(LAND_NEED_LATE)를 한 번도 안 건드린다.**
  실측기록 §7 이 요구한 「LAND_WEIGHT 효과 측정」을 4턴으로 하면 절반만 재는 것이다.

    LAND_NEED       2.0    12턴 «전»
    LAND_NEED_LATE  1.5    12턴 «후»   ← 이걸 넘겨야 검증된다
    LAND_RELAX_AFTER 12

  ⇒ 14턴짜리 대화로, **사용자가 1축만 말하고 코드가 1축 채운 상태**(무게 1.5)를
    12턴 너머까지 끌고 가서 「완화가 실제로 착지를 열어 주는가」를 본다.

흐름을 4종으로 줄인 이유
  8종 × 14턴이면 LLM 호출이 두 배가 된다. 12턴 완화를 재는 데 필요한 것만 남겼다.
  ⚠ 「⑧ 한 문장 지목」 대조군은 «반드시» 유지한다 — 명확히 말한 사용자가 느려지지
    않았는지 확인하는 자리다. 4턴 판에서 이게 안 바뀐 게 그 근거였다.

비용
  흐름 4 × 14턴 ≈ 65회 LLM (플래그 하나당). 0/1 둘 다면 약 130회.

쓰는 법 (Backend/ 에서)
  ITDA_LAND_WEIGHT=0 python app/itda/scripts/checks/land_speed_long.py
  ITDA_LAND_WEIGHT=1 python app/itda/scripts/checks/land_speed_long.py
"""
import asyncio
import io
import sys
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda.db import async_session                            # noqa: E402
import app.itda.itda_core as core                                # noqa: E402
from app.itda.itda_core import ItdaEngine, can_land, as_list     # noqa: E402

_CODE_FILLS = []
_orig_fill = core.fill_object_slot


def _spy_fill(p, user_msg):
    p2, got = _orig_fill(p, user_msg)
    if got:
        _CODE_FILLS.append(got)
    return p2, got


core.fill_object_slot = _spy_fill

#  ⚠ 어느 흐름도 「추천해줘」라고 하지 않는다. 자연스러운 대화만.
#    12턴을 넘겨야 하므로, 사람이 실제로 할 법한 말로 «길게» 이어 붙였다.
FLOWS = [
    #  ★ 핵심 — 사용자는 «돌봄 사정»만 말한다. 진로 축은 스스로 안 댄다.
    #    코드가 「다루는대상=사람」을 채워 무게 0.5 를 만든다.
    #    12턴을 넘으면 문턱이 1.5 로 내려가는데, 그때 착지가 열리는가?
    ('① 돌봄 이야기만 14턴', [
        '요즘 할머니 돌보느라 정신이 없어요',
        '그냥 하루가 다 가요',
        '밤에도 몇 번씩 깨야 해서요',
        '언제까지 이럴지 모르겠어요',
        '주말에도 똑같아요',
        '병원 가는 날이면 하루가 통째로 없어져요',
        '엄마는 일 나가시고 저만 집에 있어요',
        '친구들은 다 학교 다니는데',
        '가끔은 좀 답답하긴 해요',
        '그래도 할머니가 저를 알아보실 때가 좋아요',
        '요양보호사분이 오시면 좀 나아요',
        '그분들 보면 대단하다 싶어요',        # 12턴 — 여기부터 완화 구간
        '저는 그냥 하루하루 버티는 거죠',
        '앞으로 어떻게 될지 모르겠네요',
    ]),
    #  막연함만 반복 — 완화가 «이것까지» 열어 주면 그건 위험 신호다
    ('② 막연함만 14턴', [
        '잘 모르겠어요',
        '생각해본 적이 없어서',
        '그냥요',
        '음...',
        '딱히 없는데',
        '몰라요 진짜',
        '뭘 좋아하는지도 모르겠고',
        '남들은 어떻게 정하는 거예요',
        '그런 거 생각할 여유가 없었어요',
        '해본 게 없어서요',
        '아무거나 상관없어요',
        '그냥 아무거나요',                    # 12턴
        '모르겠다니까요',
        '음 글쎄요',
    ]),
    #  점진적으로 정보를 흘리는 «정상 경로»
    ('③ 천천히 정보 제공 14턴', [
        '요즘 할머니 돌보고 있어요',
        '학교는 그만뒀고요',
        '집에만 있으니까 답답해요',
        '예전에 편의점 알바는 해봤어요',
        '손님 응대는 그럭저럭 했어요',
        '근데 오래 서 있는 건 힘들더라고요',
        '집에서 할머니 식사 챙기는 건 익숙해요',
        '음식 만드는 건 좀 재밌기도 하고',
        '빵 같은 것도 만들어 봤어요',
        '유튜브 보고 따라 했는데 잘 되더라고요',
        '그런 쪽도 일이 될까요',
        '자격증 같은 게 있으면 좋을 텐데',      # 12턴
        '시간을 많이 뺏기진 않았으면 해요',
        '할머니 봐야 해서요',
    ]),
    #  ★ 대조군 — 명확히 말한 사용자. «느려지면 안 된다»
    ('④ 한 문장 지목 (대조군)', [
        '빵 만드는 일 하고 싶어요',
        '빵 만드는 게 재밌더라고요',
        '제과제빵 쪽으로 알아보고 있어요',
        '자격증도 따려고요',
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


def weight_of(p):
    """지금 무게가 얼마인가 — can_land 의 내부를 그대로 다시 센다(설명용)."""
    src = p.get('_slot_src') or {}
    axes = [k for k in AXES if p.get(k)]
    return sum(core.LAND_W_CODE if src.get(k) == 'code' else core.LAND_W_USER
               for k in axes)


async def main():
    eng = ItdaEngine()
    flag = os.environ.get('ITDA_LAND_WEIGHT', '(미설정)')
    print('=' * 100)
    print(f'  긴 대화 착지 측정  ·  ITDA_LAND_WEIGHT={flag}  →  LAND_WEIGHT={core.LAND_WEIGHT}')
    print(f'  문턱  12턴 전 {core.LAND_NEED} / 12턴 후 {core.LAND_NEED_LATE}')
    print('=' * 100)
    summary = []
    async with async_session() as db:
        for name, turns in FLOWS:
            profile, card_turn, land_turn = {}, None, None
            n_code = 0
            print(f'\n{"=" * 100}\n  {name}\n{"=" * 100}')
            for i, msg in enumerate(turns, 1):
                _CODE_FILLS.clear()
                try:
                    out = await eng.step(db, profile, msg)
                except Exception as e:                            # noqa: BLE001
                    print(f'  [{i}] !! {type(e).__name__}: {str(e)[:70]}')
                    break
                profile = out.get('profile') or profile
                n_code += len(_CODE_FILLS)
                kind = out.get('kind')
                landed = can_land(profile)
                if landed and land_turn is None:
                    land_turn = i
                if kind == 'card' and card_turn is None:
                    card_turn = i
                mark = f'   ★코드: {"·".join(_CODE_FILLS)}' if _CODE_FILLS else ''
                late = ' (완화구간)' if i >= core.LAND_RELAX_AFTER else ''
                print(f'  [{i:>2}]{late} 🧑 {msg}')
                print(f'       kind={kind:<9} can_land={"✅" if landed else "—"} '
                      f'무게={weight_of(profile):.1f}{mark}')
                print(f'       슬롯: {slot_str(profile)}')
                if out.get('card'):
                    print(f'       🃏 카드 = {(out["card"].get("job") or {}).get("name")}')
                if out.get('options'):
                    print(f'       [칩] {out["options"]}')
            summary.append((name, land_turn, card_turn, n_code, len(turns)))

    print('\n' + '=' * 100)
    print(f'{"흐름":<30} {"착지가능":<10} {"카드":<9} {"코드가 채운 슬롯"}')
    print('-' * 100)
    for name, lt, ct, nc, tot in summary:
        pad = 30 - sum(2 if ord(c) > 0x2E80 else 1 for c in name)
        print(f'{name}{" " * max(1, pad)} '
              f'{(str(lt) + "턴") if lt else "안 됨":<10} '
              f'{(str(ct) + "턴") if ct else "안 나옴":<9} {nc}개')
    u = eng.total_usage
    print('=' * 100)
    print(f'LLM {u.get("calls", 0)}회 · 입력 {u.get("in", 0):,} · 출력 {u.get("out", 0):,}')


asyncio.run(main())
