# -*- coding: utf-8 -*-
r"""거부의 «목적어»를 집어낼 수 있나 — 코드 규칙 vs LLM (2026-08-10 신설)

무엇에 답하려는 건가
  게이트는 「거부했나」에 예/아니오로 답한다(itda_core.py:6310). 그런데
  `apply_rejection`(578행)은 «무엇을» 뺄지를 요구하고, 그 자리를 **항상 `_last_job`**
  으로 메운다. 사용자가 «대안»을 물려도 «카드»가 빠진다.
    실측(kl_demo01 6턴) — 「아이돌봄이 자꾸 뜨는데요」 → _exclude 에 12010104(네일미용)

  고치려면 목적어를 알아야 한다. 두 갈래가 있고, 어느 쪽이 나은지는 재 봐야 안다.
    (가) 코드 규칙   보여준 이름이 발화에 «통째로» 담겼나 — 이 레포가 이미 믿는 방식
                     (7290행 「'정확 포함'만 신뢰… 오탐 0, 20케이스 실측」). LLM 0회·0원.
    (나) LLM 별도호출 `_llm_pick_option`(6436행)과 같은 꼴. enum 구속·시스템프롬프트 없음.

  ⚠ 안전 게이트(_harm_gate)에는 «손대지 않는다». 거기엔 유해·위기 판정이 같이 있고,
    위기는 2층 없이 바로 나간다(6309행). 직업 이름 목록을 얹어 그 판정을 흔들 수 없다.

⚠ 문헌을 그대로 쓰지 않는 이유
  SOM-DST(arXiv:1911.03906)의 「연산 분류기」와 SIMMC 2.0(arXiv:2104.08667)의
  「모호성 검출」은 둘 다 **학습된 전용 모델**이다. 우리는 `gemini-3.1-flash-lite`
  프롬프트 한 방이다. 착상만 빌리고 **성능은 여기서 직접 잰다.**

정답표
  손으로 붙였다. 근거는 각 케이스의 `왜` 칸에 적었다. 합성이 아니다.
  ⚠ 내가 만든 페르소나 발화가 섞여 있다 — 유리하게 고르지 않으려고
    **코드 규칙이 깨질 것이 뻔한 케이스**(이름 둘·부분이름·순서지시)를 일부러 넣었다.

비용
  케이스 N개 × LLM 1회. 입력 ~250 · 출력 ~40 토큰 → **호출당 약 0.17원**
  (gemini-3.1-flash-lite · 입력 $0.25/1M · 출력 $1.50/1M · $1=1,380원)
  `--no-llm` 이면 코드 규칙만 돌고 **0원**이다.

쓰는 법
  python app/itda/scripts/checks/reject_target_probe.py --no-llm     # 공짜
  python app/itda/scripts/checks/reject_target_probe.py              # LLM 포함
"""
import argparse
import asyncio
import io
import json
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda.itda_core import ItdaEngine as E          # noqa: E402

#  ── 케이스 ────────────────────────────────────────────────────────────
#  (발화, 카드이름, 대안들, 칩들, 정답, 왜)
#    정답 '카드'   = 카드를 물렸다 → _exclude 에 _last_job
#    정답 '<이름>' = 그 대안/칩을 물렸다 → 카드는 «건드리면 안 된다»
#    정답 '없음'   = 거부가 아니거나 대상을 모른다 → «아무것도 안 한다»
CASES = [
    # ── ① 카드 거부 (지금 동작이 맞는 자리 — 회귀로 지킨다) ──────────
    ('그거 말고 다른 거 보여주세요', '네일미용', ['아이돌봄', '메이크업'], [], '카드',
     '지시대명사가 방금 준 카드를 가리킨다'),
    ('네일미용은 좀 아닌 것 같아요', '네일미용', ['아이돌봄', '메이크업'], [], '카드',
     '카드 이름을 콕 집어 물렸다'),
    ('이건 어려울 것 같고요', '용접', ['배관', '판금'], [], '카드',
     '낱말표가 못 잡던 꼴(6299행). 대상은 카드다'),
    ('다른 거 없나요', '헤어미용', ['네일미용'], [], '카드',
     '이름이 없지만 방금 준 것을 물린 것이다'),

    # ── ② 대안 거부 (오늘 터진 자리) ────────────────────────────────
    ('근데 아이돌봄이 자꾸 뜨는데요. 돌보는 일은 아니라고 아까 말씀드렸는데',
     '네일미용', ['아이돌봄', '피부미용', '헤어미용'], [], '아이돌봄',
     '실측 kl_demo01 6턴. 카드가 아니라 대안을 가리켰다'),
    ('아이돌봄은 빼주세요', '네일미용', ['아이돌봄', '메이크업'], [], '아이돌봄',
     '대안 이름을 콕 집었다'),
    ('메이크업 쪽은 아니에요', '네일미용', ['아이돌봄', '메이크업'], [], '메이크업',
     '대안 이름 + 부정'),

    # ── ③ 칩 거부 ────────────────────────────────────────────────────
    ('헤어미용 말고요', '', [], ['피부미용', '헤어미용', '아이돌봄', '이용'], '헤어미용',
     '칩 하나를 지목했다'),
    ('다 아니에요', '', [], ['피부미용', '헤어미용', '아이돌봄'], '없음',
     '목록 «전체» 거부는 none_of_these 가 따로 처리한다. 여기선 하나를 고르면 안 된다'),

    # ── ④ 코드 규칙이 깨질 자리 (일부러 넣는다) ──────────────────────
    ('네일미용 말고 아이돌봄 주세요', '네일미용', ['아이돌봄', '메이크업'], [], '카드',
     '★이름이 둘. 물린 것은 카드, 원하는 것이 대안이다. 코드 규칙은 여기서 진다'),
    ('아이돌봄 말고 네일미용요', '아이돌봄', ['네일미용', '메이크업'], [], '카드',
     '★위와 어순만 바꿨다. 여전히 카드가 물린 것이다'),
    ('헤어는 아니라고요. 서서 하는 건 안 된다고 말씀드렸잖아요',
     '헤어미용', ['네일미용', '메이크업'], [], '카드',
     '★부분 이름(헤어 ⊂ 헤어미용). 통째 포함이 아니라 코드 규칙이 놓친다'),
    ('두 번째 거는 아니에요', '', [], ['피부미용', '헤어미용', '아이돌봄'], '헤어미용',
     '★순서 지시. 코드 규칙에 순서 처리가 없다'),

    # ── ⑤ 거부가 «아닌» 것 (오탐 방지 — 여기가 제일 중요하다) ────────
    ('그거 자격증 뭐예요', '네일미용', ['아이돌봄'], [], '없음',
     '추천에 «대해 묻는» 것이다(6315행)'),
    ('네일미용은 얼마나 걸려요', '네일미용', ['아이돌봄'], [], '없음',
     '이름이 나왔지만 질문이다'),
    ('아 그런 뜻 아니고요 네일미용 알려주세요', '헤어미용', ['네일미용'], [], '없음',
     '실측 오탐 사례(6318행). 부정어가 «내 말뜻»을 가리킨다. 무엇도 빼면 안 된다'),
    ('네일미용으로 할게요', '헤어미용', ['네일미용'], [], '없음',
     '★실측 kl_demo01 7턴. 이건 «선택»이지 거부가 아니다'),
    ('아니 네일미용으로 할게요', '헤어미용', ['네일미용'], [], '없음',
     '★「아니」가 앞에 붙어도 선택이다. 낱말표가 지던 자리'),
    ('네 좋아요', '네일미용', ['아이돌봄'], [], '없음',
     '수락이다'),
    ('3주에 한 번은 오전에 못 나가요', '네일미용', ['아이돌봄'], [], '없음',
     '제약을 말한 것이지 거부가 아니다'),
    ('앉아서 하는 거 맞죠', '네일미용', ['아이돌봄'], [], '없음',
     '확인 질문이다'),

    # ── ⑥ 사정·위기 인접 (안전 경로를 안 건드리는지) ─────────────────
    ('집에서 챙기는 게 일이라 밖에서까지 그건 좀', '일상생활기능지원', ['아이돌봄'], [], '카드',
     '실측 kl_demo01 2턴. 사정을 말하며 카드를 물렸다'),
    ('요즘 너무 지쳐서 아무것도 못 하겠어요', '네일미용', ['아이돌봄'], [], '없음',
     '사정이다. 거부가 아니다'),
]


#  ── (가) 코드 규칙 — 보여준 이름이 발화에 «통째로» 담겼나 ──────────
def code_rule(msg, card, alts, chips):
    """LLM 0회. 반환 ('카드'|'<이름>'|'없음', 이유)

    규칙 — 이 레포가 이미 믿는 「정확 포함」(7290행)만 쓴다.
      · 보여준 이름 중 발화에 통째로 든 것을 모은다(공백 제거 후 대조)
      · 정확히 하나면 그것. 카드면 '카드'
      · 둘 이상이면 «모호» → 없음 (「애매하면 안 뺀다」 — 1993행 원칙)
      · 하나도 없으면 카드 (지금 동작 유지 — 이름 없는 「그거 말고」가 여기 온다)
    ⚠ 이 규칙엔 «거부인지 아닌지» 판단이 없다. 그건 게이트가 이미 했다는 전제다.
    """
    m = re.sub(r'\s+', '', msg or '')
    shown = ([(card, '카드')] if card else []) + \
            [(a, a) for a in (alts or [])] + [(c, c) for c in (chips or [])]
    hit = [(nm, tag) for nm, tag in shown if nm and re.sub(r'\s+', '', nm) in m]
    if len(hit) == 1:
        return hit[0][1], f'통째 포함 1개: {hit[0][0]}'
    if len(hit) > 1:
        return '없음', f'이름 {len(hit)}개 겹침({[h[0] for h in hit]}) → 모호'
    return '카드', '통째 포함 0개 → 카드로 폴백(지금 동작)'


#  ── (나) LLM — `_llm_pick_option`(6436행)과 «같은 꼴» ──────────────
REJ_SCHEMA_DESC = (
    '[사용자]가 «물린»(거부한) 것을 [보기]에서 고르라.\n\n'
    '· [보기]에는 방금 보여준 추천 하나와, 함께 내놓은 다른 후보들이 들어 있다.\n'
    '· 거부가 «아니면» 빈 목록이다 — 추천에 대해 «묻는» 것, 하나를 «고르는» 것,\n'
    '  형편·제약을 말하는 것, 수락하는 것은 모두 거부가 아니다.\n'
    '· 앞의 «오해를 바로잡는» 말도 거부가 아니다 —\n'
    '  「그런 뜻 아니고요, 그거 알려주세요」는 «그것을 달라»는 뜻이다.\n'
    '· 「A 말고 B」처럼 둘이 나오면 «물린 것은 A»다. B 는 원하는 것이다.\n'
    '· 순서로 가리켜도 좋다 — 「두 번째 거」는 보기의 두 번째다.\n'
    '· 보기 전체를 아니라고 하면 **전부** 고르라.\n'
    '· 짐작하지 마라. 애매하면 빈 목록이다. 하나를 억지로 고르는 것이 가장 나쁘다.')


async def llm_rule(eng, msg, card, alts, chips):
    opts = ([card] if card else []) + list(alts or []) + list(chips or [])
    opts = [o for o in dict.fromkeys(opts) if o]
    if not opts:
        return '없음', '보기 없음'
    schema = {'type': 'OBJECT',
              'properties': {
                  '물린것': {'type': 'ARRAY',
                            'description': '사용자가 거부한 보기. 거부가 아니면 빈 목록.',
                            'items': {'type': 'STRING', 'enum': list(opts)}},
                  '근거': {'type': 'STRING', 'description': '사용자 말에서 그대로 인용'}},
              'required': ['물린것', '근거']}
    prompt = (REJ_SCHEMA_DESC + '\n\n'
              f'[보기] {" · ".join(opts)}\n'
              f'[사용자] {msg}')
    try:
        j = await eng.gemini(prompt, schema, 0.0, think='minimal')
    except Exception as e:                                  # noqa: BLE001
        return '없음', f'실패 {type(e).__name__}: {str(e)[:50]}'
    got = [o for o in (j or {}).get('물린것') or [] if o in opts]
    why = str((j or {}).get('근거') or '')[:40]
    if not got:
        return '없음', why
    if len(got) > 1:
        return '없음', f'{got} 다중 → 없음 취급 ({why})'
    return ('카드' if got[0] == card else got[0]), why


def w(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def pad(s, n):
    return str(s) + ' ' * max(1, n - w(s))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-llm', action='store_true', help='코드 규칙만 (0원)')
    a = ap.parse_args()

    print('=' * 116)
    print(f'  거부 목적어 프로브 — 케이스 {len(CASES)}건')
    print(f'  (가) 코드 규칙: LLM 0회 · 0원   |   (나) LLM: '
          f'{"건너뜀" if a.no_llm else f"{len(CASES)}회 · 약 {len(CASES) * 0.17:.1f}원"}')
    print('=' * 116)

    eng = None
    if not a.no_llm:
        eng = E()
        print(f'  모델 = {eng.model}')
    print()
    print(f'  {pad("발화", 46)} {pad("정답", 12)} {pad("코드", 12)} {pad("LLM", 12)}')
    print('  ' + '-' * 112)

    n = len(CASES)
    ok_c = ok_l = 0
    dump = []
    for msg, card, alts, chips, want, why in CASES:
        gc, wc = code_rule(msg, card, alts, chips)
        if a.no_llm:
            gl, wl = '—', ''
        else:
            gl, wl = await llm_rule(eng, msg, card, alts, chips)
        c_ok = (gc == want)
        l_ok = (gl == want)
        ok_c += c_ok
        ok_l += l_ok
        print(f'  {pad(msg[:44], 46)} {pad(want, 12)} '
              f'{pad(gc + ("" if c_ok else " ✗"), 12)} '
              f'{pad(gl + ("" if (l_ok or a.no_llm) else " ✗"), 12)}')
        dump.append({'발화': msg, '카드': card, '대안': alts, '칩': chips,
                     '정답': want, '왜': why,
                     '코드규칙': {'답': gc, '맞음': bool(c_ok), '이유': wc},
                     'LLM': {'답': gl, '맞음': bool(l_ok), '근거': wl}})

    print('  ' + '-' * 112)
    print(f'  코드 규칙  {ok_c}/{n} ({ok_c / n * 100:.0f}%)'
          + ('' if a.no_llm else f'      LLM  {ok_l}/{n} ({ok_l / n * 100:.0f}%)'))
    if eng is not None:
        u = eng.total_usage
        won = ((u.get('in', 0) - u.get('cached', 0)) * 0.25
               + u.get('cached', 0) * 0.025 + u.get('out', 0) * 1.50) / 1e6 * 1380
        print(f'  실측 사용량 — 호출 {u.get("calls", 0)} · 입력 {u.get("in", 0):,} '
              f'· 캐시 {u.get("cached", 0):,} · 출력 {u.get("out", 0):,} · **{won:.2f}원**')
    print('=' * 116)
    print('  ※ 「없음」이 정답인 케이스가 9건이다 — 오탐(안 물렸는데 뺌)이 제일 비싼 실수라서다.')
    print('  ⚠ 정답표는 손으로 붙였다. 케이스 23건은 통계가 아니라 «경계 확인»이다.')

    out = Path(__file__).with_name('_reject_target_probe.json')
    res = {'잰날': '2026-08-10', '케이스수': n,
           '코드규칙정답': ok_c, 'LLM정답': (None if a.no_llm else ok_l),
           '모델': (None if eng is None else eng.model),
           '사용량': (None if eng is None else dict(eng.total_usage)),
           '케이스': dump}
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'  원값 저장: {out.name}')


asyncio.run(main())
