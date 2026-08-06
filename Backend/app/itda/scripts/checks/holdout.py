# -*- coding: utf-8 -*-
"""홀드아웃 세트 — **골든셋과 출처가 다르다.**

골든셋의 출처   "이 버그가 났다 → 케이스로 만들자"   → 그래서 전부 통과한다
여기의 출처     가족돌봄청년의 실제 상황             → 우리가 한 번도 안 본 것

그래서 「정답」을 미리 못 적는다(적으면 그것도 과적합이다).
대신 **어겨서는 안 되는 원칙**만 자동으로 검사하고, 나머지는 눈으로 본다.
"""
import asyncio
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.db import async_session          # noqa: E402
from app.itda.itda_core import ItdaEngine      # noqa: E402

#  ── 단일 턴 ─────────────────────────────────────────────────────
SINGLE = [
    ('돌봄현실', '엄마 병원 모시고 갔다가 늦었어요'),
    ('돌봄현실', '동생이 아직 어려서 제가 봐야 해요'),
    ('돌봄현실', '할머니가 밤에 자꾸 깨셔서 잠을 못 자요'),
    ('돌봄현실', '낮에는 집을 못 비워요'),
    ('정보부족', '자격증 따면 뭐가 달라져요?'),
    ('정보부족', '저 같은 사람도 취업이 되나요?'),
    ('정보부족', '고졸인데 할 수 있는 게 있어요?'),
    ('정보부족', '뭐부터 해야 하는지도 모르겠어요'),
    ('몸·건강', '전에 하던 일은 몸이 안 따라줘서 그만뒀어요'),
    ('몸·건강', '오래 서 있는 건 힘들어요'),
    ('지침·짜증', '그냥 아무거나 알려주세요'),
    ('지침·짜증', '빨리 좀 알려주세요'),
    ('지침·짜증', '아까 말했잖아요'),
    ('경제', '돈부터 벌어야 해서요'),
    ('경제', '학원비가 없어요'),
    ('4-1 진입', '요양보호사 자격증이요'),
    ('4-1 진입', '사회복지사 되려면 대학 나와야 하나요?'),
    ('혼재', '사람 만나는 건 좋은데 오래는 못 해요'),
]

#  ── 다중 턴 (골든셋이 구조적으로 못 하는 것) ─────────────────────
FLOWS = [
    ('흐름·못정함', ['잘 모르겠어요', '음...', '그냥요', '모르겠다니까요']),
    ('흐름·돌봄→진로', ['할머니 간병하면서 학교를 못 다녔어요', '새벽까지 일해서요',
                    '그만 묻고 그냥 추천해줘']),
    ('흐름·착지후', ['제빵사가 되고 싶어요', '알아들었어?', '시험이 언제예요?']),
]

#  ── 어겨서는 안 되는 것 (자동 검사) ──────────────────────────────
_BAD = [
    (re.compile(r"\['|'\]|\[\]"), '파이썬 리스트 노출'),
    (re.compile(r'다루는대상|활동유형|관심대분류|세부관심|강점성향'), '내부 슬롯명 노출'),
    (re.compile(r'학력부담|체력부담|비용부담|시간부족|대인부담'), '제약 딱지를 되돌려줌'),
    (re.compile(r'\*\*'), '마크다운 별표(프론트에 파서 없음)'),
    (re.compile(r'취미|쉴 때|시간 가는 줄|재밌어 보'), '여유를 전제한 질문'),
    (re.compile(r'어떤 일을 하고 싶|무슨 일을 하고 싶|어떤 직업을'), '프롬프트 최우선 금지 질문'),
]


def check(reply, kind):
    out = []
    for rx, why in _BAD:
        if rx.search(reply or ''):
            out.append(why)
    return out


async def main():
    eng = ItdaEngine()
    bad_total = 0
    async with async_session() as db:
        print('=' * 88)
        print('  단일 턴 18건')
        print('=' * 88)
        for tag, msg in SINGLE:
            try:
                out = await eng.step(db, {}, msg)
            except Exception as e:                        # noqa: BLE001
                print(f'\n[{tag}] 🧑 {msg}\n   !! {type(e).__name__}: {str(e)[:60]}')
                continue
            r = out.get('reply') or ''
            bad = check(r, out.get('kind'))
            bad_total += len(bad)
            print(f'\n[{tag}] 🧑 {msg}')
            print(f'   kind={out.get("kind")}' +
                  (f'  카드={(out.get("card") or {}).get("job",{}).get("name")}'
                   if out.get('card') else ''))
            print('   🤖 ' + r.replace('\n', '\n      ')[:300])
            for b in bad:
                print(f'   🔴 {b}')

        print()
        print('=' * 88)
        print('  다중 턴 3흐름')
        print('=' * 88)
        for tag, turns in FLOWS:
            profile = {}
            seen = []
            print(f'\n■ [{tag}]')
            for i, msg in enumerate(turns, 1):
                try:
                    out = await eng.step(db, profile, msg)
                except Exception as e:                    # noqa: BLE001
                    print(f'  [{i}] !! {type(e).__name__}: {str(e)[:60]}')
                    break
                profile = out.get('profile') or profile
                r = out.get('reply') or ''
                bad = check(r, out.get('kind'))
                #  같은 질문이 두 번 나왔나 (첫 문장 기준)
                head = re.sub(r'\s+', '', r.split('\n')[0])[:40]
                if head and head in seen:
                    bad.append('같은 질문 반복')
                seen.append(head)
                bad_total += len(bad)
                print(f'  [{i}] 🧑 {msg}')
                print(f'      kind={out.get("kind")}')
                print('      🤖 ' + r.replace('\n', '\n         ')[:260])
                for b in bad:
                    print(f'      🔴 {b}')

    u = eng.total_usage
    print()
    print('=' * 88)
    print(f'  원칙 위반 자동검출 {bad_total}건  ·  LLM {u.get("calls",0)}회 '
          f'· 입력 {u.get("in",0):,} · 출력 {u.get("out",0):,}')
    print('=' * 88)


asyncio.run(main())
