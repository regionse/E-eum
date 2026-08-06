# -*- coding: utf-8 -*-
"""남용 문턱 — **LLM 0회 · DB 0회 · 0원.**

무엇을 잡으려는 검사인가
  문턱이 턴에 비례하는데(abuse_limits) 분모가 «전체 턴»이었다. 그래서
    ① 6턴에 6번 떠들어도 stop=8 이라 안 잠기고
    ② 잠긴 뒤에도 _turns 가 계속 올라 **3턴마다 차단이 저절로 풀렸다**
  둘 다 골든셋으로는 안 잡힌다 — 골든셋에 트롤 다중턴 시나리오가 없다.

⇒ 분모를 «정상적으로 오간 턴»(_turns − _abuse)으로 바꾸고,
  차단된 턴은 _turns 를 안 올리게 했다. 이 검사가 그 둘을 지킨다.
"""
import sys
import io
import asyncio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.itda_core import abuse_limits, ItdaEngine   # noqa: E402

#  (이름, _turns, _abuse, 잠겨야 하나)
CASES = [
    ('새 대화 · 남용 0',              1,  0, False),
    ('6턴 대화 · 이탈 3회',           6,  3, False),
    ('★ 6턴 대화 · 이탈 6회 (트롤)',   6,  6, True),
    ('★ 8턴 대화 · 이탈 8회 (트롤)',   8,  8, True),
    ('40턴 대화 · 이탈 6회 (대화가 샘)', 40, 6, False),
    #  ⚠ 기대값 정정(2026-08-06) — 처음엔 False 로 적었다가 실측에서 틀린 걸 알았다.
    #    40턴에 15회면 이탈률 37.5% 다. 설계 주석이 「대화가 좀 샜다」의 예로 든 건
    #    15%(6회)지 37.5% 가 아니다. 코드가 맞고 내 기대가 틀렸다.
    ('40턴 대화 · 이탈 15회 (37.5%)', 40, 15, True),
    ('★ 20턴 대화 · 이탈 20회',       20, 20, True),
    ('100턴 대화 · 이탈 19회',        100, 19, False),
    ('★ 100턴 대화 · 이탈 20회 (상한)', 100, 20, True),
]

#  ★ 자동 해제 — **abuse_limits 만 따로 불러서는 못 잰다.**
#    문턱 계산은 _turns 를 받을 뿐이고, 진짜 보호는 «_step 이 차단 턴에 _turns 를
#    안 올리는 것»에서 나온다. 그래서 아래는 실제 step() 을 돌려서 잰다.
#    (처음엔 abuse_limits 만 반복 호출했다가 「여전히 풀린다」는 틀린 결론을 냈다)


async def _release():
    """잠긴 세션에 10턴 더 보낸다. _turns 가 안 움직여야 하고, 계속 blocked 여야 한다.

    ⚠ db=None 으로 부른다 — 차단 경로는 함수 맨 앞에서 return 하므로 DB 를 안 탄다.
      그게 이 게이트의 존재 이유이기도 하다(LLM 0회 · DB 0회 · 비용 0).
    """
    e = ItdaEngine()
    p = {'_turns': 6, '_abuse': 6}
    free = 0
    for i in range(1, 11):
        r = await e.step(None, p, '아 진짜 짜증나 뭐 이런 게 다 있어')
        p = r.get('profile') or p
        blocked = (r.get('kind') == 'blocked')
        if not blocked:
            free += 1
        print(f'     {i:>2}번째 재시도  _turns={p.get("_turns")}  _abuse={p.get("_abuse")}'
              f'  → {"잠김" if blocked else "🔴 풀림"}')
    return free


def main():
    bad = []
    print('■ 문턱 판정 — 분모는 «정상적으로 오간 턴»(_turns − _abuse)')
    print('=' * 84)
    print(f'{"경우":<32}{"턴":>5}{"남용":>6}{"경고":>6}{"종료":>6}{"판정":>8}')
    print('-' * 84)
    for name, t, a, want in CASES:
        w, s = abuse_limits({'_turns': t, '_abuse': a})
        got = a >= s
        okk = (got == want)
        bad.append(name) if not okk else None
        pad = 32 - sum(2 if ord(c) > 0x2E80 else 1 for c in name)
        print(f'{name}{" " * max(1, pad)}{t:>4}{a:>6}{w:>6}{s:>6}'
              f'{("잠김" if got else "통과"):>7}  {"✅" if okk else "🔴 기대=" + str(want)}')

    print('\n■ ★ 자동 해제 — 잠긴 사람이 10턴 더 보내면 «계속» 잠겨 있나 (실제 step 호출)')
    print('=' * 84)
    n_free = asyncio.run(_release())
    if n_free:
        bad.append(f'차단이 {n_free}회 풀림 — _turns 가 오르고 있다')

    print('\n' + '=' * 84)
    print(f'  {"✅ 통과" if not bad else "🔴 실패"}  '
          f'{len(CASES)}건 + 해제 10턴 · LLM 0회 · DB 0회 (0원)')
    for b in bad:
        print(f'    실패: {b}')
    print('=' * 84)
    sys.exit(0 if not bad else 1)


main()
