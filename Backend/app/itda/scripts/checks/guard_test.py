# -*- coding: utf-8 -*-
"""출력가드 검사 — **LLM 안 부른다(0원).**

왜 있나 (2026-08-06)
  페르소나 시험에서 가드가 «자기 편 문장»을 죽이는 게 잡혔다:
      [itda] 출력가드: 1문장 제거 — 응시요건 단정:
             자격증의 응시 자격은 제가 단정해서 말씀드릴 수 없어요.
  `_ENTRY_CLAIM` 의 '응시자격은' 이 면책 문장에 부분일치했다. 그 결과 답변은
  유보 이유조차 없이 회피적으로 남았고, 사용자는 스스로 포기 선언을 했다.

  이 문장 형식이 왜 중요한가 — 우리 DB 에는 응시요건 원문이 없고(오염도 확인),
  근거 없이 「정정」을 밀면 멀쩡한 전제까지 반박한다(Cancer-Myth 41% · Wagner 2026 57%).
  남는 건 «인식적 유보»뿐이고, 그 형식의 효과는 실측돼 있다 —
  Kim 외 (FAccT 2024, arXiv:2405.00623, N=404):
    "First-person expressions (e.g., 'I'm not sure, but...') decrease participants'
     confidence in the system and tendency to agree with the system's answers,
     while **increasing participants' accuracy**."

⚠ 이 검사의 절반은 «지워져야 하는» 쪽이다. 그쪽이 진짜 시험이다 —
  「부정문이면 살린다」로 잘못 고치면 「학력 제한이 **없**어요」(부정형 사실 단정)가
  같이 살아난다. 구별점은 부정 여부가 아니라 **무엇을 부정하는가**다.
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.itda_core import scrub_output          # noqa: E402

#  ── 살아야 하는 것: 화자 «자신의 앎»을 부정하는 문장 ───────────────
KEEP = [
    ('실측 사고 문장', '자격증의 응시 자격은 제가 단정해서 말씀드릴 수 없어요.'),
    #  ⚠ ㅂ불규칙 — '어렵'으로 패턴을 쓰면 '어려워요'가 안 걸린다(실제로 이 검사가 잡았다)
    ('ㅂ불규칙 어려워요', '응시요건은 제가 확인해 드리기 어려워요.'),
    ('ㅂ불규칙 어렵습니다', '응시자격은 제가 단정하기 어렵습니다.'),
    ('ㅂ불규칙 어려운', '응시조건은 제가 확인해 드리기 어려운 부분이에요.'),
    ('저는 알 수 없', '학력 제한이 있는지는 저는 알 수 없어요.'),
    ('확실하지 않', '자격조건은 자격증마다 달라서 확실하지 않아요.'),
    ('확인처 이관', '응시요건은 큐넷에서 확인해 보셔야 해요.'),
    ('무관한 일반 문장', '빵 만드는 일에 관심이 있으시군요.'),
]

#  ── 지워져야 하는 것: «세상의 사실»을 주장하는 문장 ─────────────────
DROP = [
    #  ↓ 부정형인데도 «사실 단정»이다. 「부정문 예외」로 고치면 이게 살아난다
    ('부정형 사실단정', '이건 학력 제한 없이 누구나 응시할 수 있는 자격증이에요.'),
    ('긍정형 사실단정', '응시자격은 고졸 이상이에요.'),
    ('유보 + 단정 혼합', '제가 단정할 수 없지만 제한없이 누구나 응시 가능해요.'),
    ('나이 단정', '나이 제한은 만 18세 이상이에요.'),
    ('학력 단정', '학력 제한은 없습니다.'),
    ('자격증 속성을 직업에', '그중에 지금 바로 시작할 수 있는 게 건설기계정비예요.'),
]

bad = []
for label, cases, want_keep in (('■ 살아야 하는 문장 (1인칭 인식 유보)', KEEP, True),
                                ('■ 지워져야 하는 문장 (사실 단정)', DROP, False)):
    print(label)
    for name, s in cases:
        out, dropped = scrub_output(s, '')
        ok = (s.strip() in out) if want_keep else bool(dropped)
        print(f'  {"✅" if ok else "🔴"}  [{name}] {s[:48]}')
        if not ok:
            bad.append(name)
            print(f'        → {out[:60]!r}  dropped={dropped}')
    print()

tot = len(KEEP) + len(DROP)
print('=' * 84)
print(f'  통과 {tot - len(bad)} / {tot}   ·  LLM 0회 (0원)')
for n in bad:
    print(f'    🔴 {n}')
print('=' * 84)
