# -*- coding: utf-8 -*-
"""홀드아웃 2차 — **1차와 겹치지 않는 각도.**

1차가 본 것   돌봄현실 · 정보부족 · 몸건강 · 지침짜증 · 경제 · 진입점 · 흐름3
2차가 볼 것   오타/구어체 · 긴 발화 · 모순 · 되돌리기 · 다중요구 · 부정형 ·
              질문폭탄 · 종료 · 극단짧음 · 흐름(반복거부·주제전환)

1차 세트는 이제 «회귀»다(우리가 그걸로 고쳤으니까). 여기가 진짜 검증이다.
"""
import asyncio
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.db import async_session          # noqa: E402
from app.itda.itda_core import ItdaEngine      # noqa: E402

SINGLE = [
    ('오타·구어체', '제빵사되고싶어여'),
    ('오타·구어체', '자겨증 뭐가조아요'),
    ('오타·구어체', 'ㅇㅇ 근데 그거 오래걸려요?'),
    ('긴 발화', '엄마가 치매라서 3년째 돌보는데 제가 고졸이고 시간도 없어서 뭘 할 수 있을지 모르겠어요'),
    ('긴 발화', '예전에 편의점이랑 카페 알바 해봤고 지금은 할머니 때문에 집에 있는데 자격증 하나라도 따두면 좋을까요'),
    ('부정형만', '몸 쓰는 건 싫어요'),
    ('부정형만', '사무직은 아니에요'),
    ('부정형만', '사람 많은 데는 좀'),
    ('다중요구', '제빵이랑 요양보호사 둘 다 궁금해요'),
    ('다중요구', '자격증도 알려주고 강좌도 알려주세요'),
    ('질문폭탄', '자격증 몇 개예요? 얼마나 걸려요? 돈은요?'),
    ('질문폭탄', '이거 하면 취업 되나요? 월급은 얼마예요?'),
    ('종료', '고마워요 이제 됐어요'),
    ('종료', '나중에 다시 올게요'),
    ('극단짧음', '응'),
    ('극단짧음', '네'),
    ('극단짧음', '그래서요'),
    ('메타·불신', '너 그거 진짜야?'),
    ('메타·불신', '아무거나 막 던지는 거 아니에요?'),
]

FLOWS = [
    ('흐름·모순', ['사람 만나는 거 좋아해요', '근데 사람 상대하는 건 힘들어요',
                '어떤 게 맞을까요']),
    ('흐름·되돌리기', ['제빵사가 되고 싶어요', '아니 그거 말고', '다른 거 없어요?']),
    ('흐름·주제전환', ['컴퓨터 하는 일이요', '아 근데 지금 당장 돈이 급해서요',
                  '그냥 빨리 되는 걸로 알려주세요']),
]

_BAD = [
    (re.compile(r"\['|'\]|\[\]"), '파이썬 리스트 노출'),
    (re.compile(r'다루는대상|활동유형|관심대분류|세부관심|강점성향'), '내부 슬롯명 노출'),
    (re.compile(r'학력부담|체력부담|비용부담|시간부족|대인부담'), '제약 딱지를 되돌려줌'),
    (re.compile(r'\*\*'), '마크다운 별표'),
    (re.compile(r'취미|쉴 때|시간 가는 줄|재밌어 보'), '여유를 전제한 질문'),
    (re.compile(r'어떤 일을 하고 싶|무슨 일을 하고 싶|어떤 직업을'), '프롬프트 최우선 금지 질문'),
    (re.compile(r'기다려|잠시만 기다|곧 알려'), '기다리라고 함(카드 턴이면 거짓)'),
]


async def main():
    eng = ItdaEngine()
    bad = 0
    async with async_session() as db:
        print('=' * 88)
        print('  단일 턴 19건')
        print('=' * 88)
        for tag, msg in SINGLE:
            try:
                out = await eng.step(db, {}, msg)
            except Exception as e:                    # noqa: BLE001
                print(f'\n[{tag}] 🧑 {msg}\n   !! {type(e).__name__}: {str(e)[:60]}')
                continue
            r = out.get('reply') or ''
            hits = [w for rx, w in _BAD if rx.search(r)]
            #  기다림 문구는 카드 턴에서만 문제다
            if out.get('kind') != 'card':
                hits = [h for h in hits if '기다리라고' not in h]
            bad += len(hits)
            print(f'\n[{tag}] 🧑 {msg}')
            print(f'   kind={out.get("kind")}' +
                  (f'  카드={(out.get("card") or {}).get("job",{}).get("name")}'
                   if out.get('card') else ''))
            print('   🤖 ' + r.replace('\n', '\n      ')[:280])
            for h in hits:
                print(f'   🔴 {h}')

        print()
        print('=' * 88)
        print('  다중 턴 3흐름')
        print('=' * 88)
        for tag, turns in FLOWS:
            profile, seen = {}, []
            print(f'\n■ [{tag}]')
            for i, msg in enumerate(turns, 1):
                try:
                    out = await eng.step(db, profile, msg)
                except Exception as e:                # noqa: BLE001
                    print(f'  [{i}] !! {type(e).__name__}: {str(e)[:60]}')
                    break
                profile = out.get('profile') or profile
                r = out.get('reply') or ''
                hits = [w for rx, w in _BAD if rx.search(r)]
                if out.get('kind') != 'card':
                    hits = [h for h in hits if '기다리라고' not in h]
                head = re.sub(r'\s+', '', r.split('\n')[0])[:40]
                if head and head in seen:
                    hits.append('같은 질문 반복')
                seen.append(head)
                bad += len(hits)
                print(f'  [{i}] 🧑 {msg}')
                print(f'      kind={out.get("kind")}' +
                      (f'  카드={(out.get("card") or {}).get("job",{}).get("name")}'
                       if out.get('card') else ''))
                print('      🤖 ' + r.replace('\n', '\n         ')[:240])
                for h in hits:
                    print(f'      🔴 {h}')

    u = eng.total_usage
    print()
    print('=' * 88)
    print(f'  원칙 위반 {bad}건  ·  LLM {u.get("calls",0)}회 · 입력 {u.get("in",0):,}')
    print('=' * 88)


asyncio.run(main())
