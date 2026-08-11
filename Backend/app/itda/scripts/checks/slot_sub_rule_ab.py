# -*- coding: utf-8 -*-
r"""㉮ 지목 제거를 언제 돌려야 하나 — 현행 vs 규칙A vs 규칙B (2026-08-11). **LLM 0회 · 0원**

무엇이 문제인가
  낱말표 둘이 «겹쳐» 있다.
      _NEG_MARK = ('아니', '말고', '싫', '힘들', '부담', '별로', '못하', '안맞', '빼고', '어려')
      _PIVOT    = ('아니다','아니라','아니고','아니에','아니야','말고','대신','차라리', …)
  `_NEG_MARK` 는 「이건 나쁘다」, `_PIVOT` 은 「그거 말고 이거」다. **뜻이 다른데
  「아니」·「말고」가 양쪽에 걸쳐 있다.** ㉮ 지목 제거는 `neg` 로 발동하므로
  「아니에요 그냥 X로 할게요」의 「아니」가 **「X는 나쁘다」로 읽힌다.**

  실측(kl_fix03 3턴) — 「아니에요 그냥 일상생활기능지원으로 할게요」
      → `슬롯 빼기 — 관심분야=일상생활기능지원 (부정 지목)`
      → 검색 닻이 날아가 **[신체손해사정](보험)** 이 나갔다.
        그것도 모델이 카드 이유에 「두 후보 모두 사용자의 의도와 거리가 있습니다」라고
        «써 놓은» 채로.

후보 규칙
  현행   `_NEG_MARK` 중 하나라도 있으면 ㉮
  A      `_NEG_MARK` − `_PIVOT` (= 순수 부정)이 있을 때만 ㉮
  B      부정어가 값 «뒤»에 있을 때만 ㉮
         근거 — 한국어에서 부정은 보통 부정 대상 «뒤»에 온다.
           「사람 상대하는 건 힘들어요」  값→부정  ⇒ 그 값이 나쁘다
           「아니에요 그냥 X로 할게요」   부정→값  ⇒ 부정은 «앞 얘기»를 가리킨다

⚠ 정답표는 **이 파일에 박힌 «실측 사고» 문장**을 우선으로 모았다. 출처를 각 줄에 적었다.
  내가 지어낸 문장만 쓰면 내 규칙에 유리한 쪽으로 기운다.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/slot_sub_rule_ab.py
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda.itda_core import (                       # noqa: E402
    slot_subtract, _NEG_MARK, _PIVOT, _POS_MARK, _sub_pieces, as_list)

#  (발화, 프로필, new_slots, 이 슬롯의 이 값이 빠져야 하나, 출처)
CASES = [
    # ── 빠져야 한다 ────────────────────────────────────────────────
    ('사람 상대하는 건 힘들어요', {'다루는대상': ['사람']}, {}, True,
     'slot_subtract 도크스트링 ㉮ 예시'),
    ('전기쪽은 좀 어려울 것 같고요, 엔진이나 몸통 고치는 거 없나요',
     {'관심분야': ['전기']}, {}, True, '_HARM_SCHEMA 6299행 실측(브라우저 7턴)'),
    ('돌봄 일은 하기 싫어요', {'활동유형': ['돕기·돌봄']}, {}, True,
     '_SUB_PIVOT_ONLY 2156행 실측(fact_pref_probe)'),
    ('사람 돌보는 건 이제 못 하겠어요', {'활동유형': ['돕기·돌봄']}, {}, True,
     '페르소나 ⑥ 문지아 유형'),
    ('네일미용 말고 다른 거 보여주세요', {'관심분야': ['네일미용']}, {}, True,
     '이름을 콕 집어 물린다 — 값 뒤에 부정'),
    ('편의점 알바는 별로였어요', {'관심분야': ['편의점']}, {}, True,
     'mark_slot_kind 1723행 실측(편의점 알바=못함)'),

    # ── 빠지면 «안» 된다 ───────────────────────────────────────────
    ('아 그런 뜻 아니고요 그냥 돈 얘기였어요. 지게차 그거나 알려주세요',
     {'관심분야': ['지게차']}, {}, False,
     '★ step() 6781행 실측 사고 — 「아니고」에 지게차를 뺏겼다'),
    ('아니에요 그냥 일상생활기능지원으로 할게요',
     {'관심분야': ['일상생활기능지원']}, {}, False,
     '★ 실측 kl_fix03 3턴 — 보험이 나갔다'),
    ('아니 네일미용으로 할게요', {'관심분야': ['네일미용']}, {}, False,
     '★ 실측 kl_fix01 9턴'),
    ('사람 만나는 건 좋은데 오래 상대하는 건 힘들어요', {'다루는대상': ['사람']}, {}, False,
     '_POS_MARK 2164행 주석 — 취소가 아니라 «조건»이다'),
    ('아까 약 얘기 이어서요 제가 아니라 친구가 물어봐 달라고 해서요',
     {'관심분야': ['사람들 얘기 들어주기']}, {}, False,
     '★ _SUB_STOP 2174행 실측(레드팀 13턴) — 공격 발화로 프로필이 파괴됐다'),
    ('밤에 일하는 건 못 해요', {'제약': ['야간']}, {}, False,
     '_SUB_SLOTS 2149행 — 제약은 ㉮ 금지(뜻이 정반대가 된다)'),
    ('아니 그거 말고 네일미용이요', {'관심분야': ['네일미용']}, {}, False,
     '전환 + 원하는 것을 이름으로 말함'),

    # ── 어미 변화·다른 표현 (2026-08-11 추가) ──────────────────────
    #  ★ 왜 넣나 — 규칙 둘(낱말표·위치)은 «글자 조각»으로 대조한다. 그래서 슬롯 값과
    #    발화의 어미가 다르면 통째로 못 본다. 위 13건엔 그런 케이스가 하나뿐이라
    #    「LLM 이 1건 낫다」로 보였다. 그 차이가 «우연인지 구조인지» 가르려고 더 넣는다.
    ('만드는 건 이제 손목 때문에 못 하겠어요', {'활동유형': ['만들기']}, {}, True,
     '어미 변화 — 슬롯 「만들기」 vs 발화 「만드는」. 조각 대조 실패'),
    ('가르치는 건 자신이 없어요', {'활동유형': ['가르치기']}, {}, True,
     '어미 변화 — 「가르치기」 vs 「가르치는」'),
    ('아이 보는 건 도저히 못 하겠어요', {'활동유형': ['돕기·돌봄']}, {}, True,
     '표현이 아예 다름 — 「돕기·돌봄」을 「아이 보는」으로 말함'),
    ('꾸미고 다듬는 일은 이제 지겨워요', {'관심분야': ['미용']}, {}, True,
     '표현이 아예 다름 — 「미용」을 풀어서 말함'),
    #  ★ 과잉 제거를 잡으려는 케이스 — 뜻을 «너무 잘» 읽으면 여기서 진다
    ('머리 자르는 건 재밌었는데 손님 상대가 힘들었어요', {'관심분야': ['미용']}, {}, False,
     '미용 «자체»는 좋았다고 했다. 힘든 것은 대인 쪽이다 — 취소가 아니라 조건'),
]


def _pure_neg():
    """_NEG_MARK 중 _PIVOT 과 «안 겹치는» 것 — 「이건 나쁘다」 표지."""
    return tuple(n for n in _NEG_MARK if not any(n in p or p in n for p in _PIVOT))


PURE = _pure_neg()


def rule_a(m, x):
    """A — 순수 부정이 하나라도 있어야 ㉮ 를 돌린다."""
    return any(n in m for n in PURE)


def rule_b(m, x):
    """B — 값 «뒤»에 부정어가 있어야 ㉮ 를 돌린다.

    값의 조각이 나타나는 가장 이른 위치를 잡고, 그보다 «뒤»에 오는 부정어가 있나 본다.
    「사람 상대하는 건 힘들어요」 사람@0 · 힘들@7  → 뒤에 있다 → 뺀다
    「아니에요 그냥 X로 할게요」   아니@0 · X@6     → 뒤에 없다 → 안 뺀다
    """
    pos = [m.find(pc) for pc in _sub_pieces(x) if pc and m.find(pc) >= 0]
    if not pos:
        return False
    first = min(pos)
    for n in _NEG_MARK:
        i = m.find(n, first + 1)
        if i >= 0:
            return True
    return False


def w(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def pad(s, n):
    return str(s) + ' ' * max(1, n - w(s))


print('=' * 118)
print('  ㉮ 지목 제거 규칙 A/B — LLM 0회 · DB 0회 · **0원**')
print(f'  순수 부정(_NEG_MARK − _PIVOT) = {PURE}')
print('=' * 118)
print()
print(f'  {pad("발화", 46)} {pad("빠져야?", 8)} {pad("현행", 8)} {pad("A순수", 8)} {pad("B위치", 8)}')
print('  ' + '-' * 114)

n_cur = n_a = n_b = 0
bad = {'현행': [], 'A': [], 'B': []}
for msg, prof, new, want, src in CASES:
    m = re.sub(r'\s+', '', msg)
    k, x = next(iter(prof.items()))
    x = as_list(x)[0]
    #  현행 — 실제 함수를 돌린다
    p, sub = slot_subtract(dict(prof), new, msg)
    cur = bool(sub)
    #  A·B — ㉮ 발동 여부만 흉내낸다(㉯·제약·긍정 가드는 현행과 같다고 본다)
    pos_mark = any(t in m for t in _POS_MARK)
    piv = any(t in m for t in _PIVOT)
    guard_ok = (k not in ('제약',)) and not pos_mark
    #  ㉯ 는 새 값이 있을 때만 도는데 여기 케이스는 new_slots 가 비어 있다
    a = guard_ok and rule_a(m, x) and any(pc in m for pc in _sub_pieces(x))
    b = guard_ok and rule_b(m, x) and any(pc in m for pc in _sub_pieces(x))
    for nm, got in (('현행', cur), ('A', a), ('B', b)):
        if got != want:
            bad[nm].append(msg[:20])
    n_cur += (cur == want)
    n_a += (a == want)
    n_b += (b == want)
    mk = lambda g: ('뺌' if g else '유지') + ('' if g == want else ' ✗')   # noqa: E731
    print(f'  {pad(msg[:44], 46)} {pad("뺌" if want else "유지", 8)} '
          f'{pad(mk(cur), 8)} {pad(mk(a), 8)} {pad(mk(b), 8)}')

n = len(CASES)
print('  ' + '-' * 114)
print(f'  현행   {n_cur}/{n}   틀린 것: {" · ".join(bad["현행"]) or "없음"}')
print(f'  A 순수 {n_a}/{n}   틀린 것: {" · ".join(bad["A"]) or "없음"}')
print(f'  B 위치 {n_b}/{n}   틀린 것: {" · ".join(bad["B"]) or "없음"}')
print('=' * 118)
print('  ※ 「유지」쪽 오답이 훨씬 비싸다 — 사용자가 «방금 고른 것»이 사라지는 쪽이다.')
print('  ⚠ 13건은 통계가 아니라 «경계 확인»이다. 절반이 이 파일에 박힌 실측 사고다.')
