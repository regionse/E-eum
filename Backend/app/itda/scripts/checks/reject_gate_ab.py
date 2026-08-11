# -*- coding: utf-8 -*-
r"""「거부」 판정을 안전 게이트에 얹은 채로 둘 것인가, 떼어낼 것인가 (2026-08-11 신설)

무엇에 답하려는 건가
  `_harm_gate` 는 «유해·위기» 판정을 하는 안전 게이트다. 프롬프트가 길다 —
  자해 6기준 · 오탐 방지 3항 · 유해 예외 · 정책질문 예외가 빽빽하다.
  2026-08-10 에 거기에 「거부」 필드를 **얹었다**(6310행께).

  그런데 이 파일 안에 이미 반대 방향의 실측이 있다(_harm_gate 도크스트링 6329행께):
      본문 호출(SYSTEM 12,112자)에 「유해」를 얹으니 **1/4**
      별도 호출로 빼니                              **4/4**
      「너는 진로 동반자다 … 받아주라」가 가득한 맥락에서 판정이 무뎌진다
  「거부」도 같은 처지일 수 있다. **추측하지 말고 잰다.**

무엇을 어떻게 재나 — 같은 발화를 두 갈래로 보낸다
  A. 운영 게이트   `_harm_gate(msg, card)` 를 그대로 부르고 `last_reject` 를 읽는다
  B. 전용 호출     「거부인가」만 묻는 짧은 호출. 시스템 프롬프트 없음
  둘 다 **예/아니오** 이진이다. 목적어는 여기서 안 본다(그건 rejection_target 이 한다).

⚠ 정답표는 손으로 붙였다. 근거를 `왜` 칸에 적었다. 애매한 것은 «애매»라고 적고
  점수에서 뺀다 — 내 판단이 갈리는 것을 정답인 척하지 않는다.
⚠ 케이스 일부는 «실측 대화»에서 그대로 가져왔다(kl_demo01·kl_fix01·kl_fix02).
  내가 지어낸 문장만 쓰면 유리한 쪽으로 기운다.

비용
  케이스당 2호출. A 는 프롬프트가 길다 — 주석의 「0.17원」은 «출력 기준»으로 보이고
  입력을 더하면 더 든다. **이 스크립트가 실측해서 마지막에 찍는다.**

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/reject_gate_ab.py
"""
import asyncio
import io
import json
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda.itda_core import ItdaEngine as E        # noqa: E402

#  (발화, 방금 준 카드, 정답, 왜)
#    정답 '예'   거부다   ·  '아니오' 거부가 아니다  ·  '애매' 점수에서 뺀다
CASES = [
    # ── 거부가 맞다 ────────────────────────────────────────────────
    ('그거 말고 다른 거 보여주세요', '네일미용', '예', '지시대명사 + 말고'),
    ('네일미용은 좀 아닌 것 같아요', '네일미용', '예', '이름 + 부정'),
    ('이건 어려울 것 같고요', '용접', '예', '낱말표가 못 잡던 꼴(6299행)'),
    ('다른 거 없나요', '헤어미용', '예', '이름 없이 물리는 말'),
    ('근데 아이돌봄이 자꾸 뜨는데요. 돌보는 일은 아니라고 아까 말씀드렸는데',
     '네일미용', '예', '실측 kl_demo01 6턴'),
    ('아이돌봄은 빼주세요', '네일미용', '예', '명시적 제거 요청'),
    ('메이크업 쪽은 아니에요', '네일미용', '예', '이름 + 부정'),
    ('헤어미용 말고요', '피부미용', '예', '이름 + 말고'),
    ('다 아니에요', '네일미용', '예', '목록 전체 거부'),
    ('네일미용 말고 아이돌봄 주세요', '네일미용', '예', 'A 말고 B'),
    ('헤어는 아니라고요. 서서 하는 건 안 된다고 말씀드렸잖아요',
     '헤어미용', '예', '실측 kl_demo01 8턴'),
    ('두 번째 거는 아니에요', '네일미용', '예', '순서 지시'),
    ('집에서 챙기는 게 일이라 밖에서까지 그건 좀', '일상생활기능지원', '예',
     '실측 kl_demo01 2턴 — 사정을 말하며 물린다'),
    ('접수가 3일밖에 안 남았다는 거죠. 그건 너무 촉박한데요. 다른 것도 보여주세요',
     '네일미용', '예', '실측 kl_fix02 8턴'),

    # ── 거부가 아니다 (오탐이 제일 비싼 쪽) ────────────────────────
    ('그거 자격증 뭐예요', '네일미용', '아니오', '추천에 «대해 묻는» 것(6315행)'),
    ('네일미용은 얼마나 걸려요', '네일미용', '아니오', '이름이 나왔지만 질문'),
    ('네일미용으로 할게요', '헤어미용', '아니오', '선택이다'),
    ('아니 네일미용으로 할게요', '헤어미용', '아니오',
     '★실측 kl_fix01 9턴에서 오판. 「아니」가 붙어도 선택이다'),
    ('아니에요 그냥 네일미용으로 할게요', '피부미용', '아니오',
     '★실측 kl_fix02 9턴에서 오판'),
    ('네 좋아요', '네일미용', '아니오', '수락'),
    ('3주에 한 번은 오전에 못 나가요', '네일미용', '아니오', '제약 진술'),
    ('앉아서 하는 거 맞죠', '네일미용', '아니오', '확인 질문'),
    ('요즘 너무 지쳐서 아무것도 못 하겠어요', '네일미용', '아니오', '사정 진술'),
    ('예전에 미용실에서 3년 일했어요. 근데 계속 서 있어야 해서 지금은 좀 그렇고요. '
     '손으로 하는 건 괜찮았던 것 같아요', '일상생활기능지원', '아니오',
     '★실측 kl_fix02 3턴에서 «예» 로 나왔다. 새 정보를 준 턴이다'),
    ('그 자격증 접수가 언제까지예요', '네일미용', '아니오', '일정 질문'),

    # ── 애매 (점수에서 뺀다) ───────────────────────────────────────
    ('아 그런 뜻 아니고요 네일미용 알려주세요', '헤어미용', '애매',
     '실측 오탐 사례(6318행)와 같은 꼴이지만, 카드가 «원하는 것이 아닐 때»는 '
     '카드를 빼도 해가 없다. 내 판단이 갈려서 점수에서 뺀다'),
]

BIN_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        '거부': {'type': 'STRING', 'enum': ['아니오', '예']},
        '근거': {'type': 'STRING', 'description': '사용자 말에서 그대로 인용'}},
    'required': ['거부', '근거']}

#  ★ B 안(전용 호출)의 프롬프트 — 운영 게이트의 「거부」 설명문을 «그대로» 옮기고,
#    안전 프롬프트(자해·유해·정책)는 **한 줄도 넣지 않는다.** 그 차이만 보려는 것이다.
B_PROMPT = (
    '[사용자]가 방금 보여준 추천을 «무르는»(거부하는) 말을 했는가.\n\n'
    '[방금 보여준 추천] {card}\n'
    '[사용자] {msg}\n\n'
    '· 마음에 안 든다·어려울 것 같다·다른 걸 보고 싶다는 뜻이면 「예」다.\n'
    '· 그 추천에 «대해 묻는» 것은 「아니오」다 (「자격증 뭐예요?」·「얼마나 걸려요?」).\n'
    '· 앞의 «오해를 바로잡는» 말도 「아니오」다 — 부정어가 가리키는 것이\n'
    '  추천이 아니라 「내 말뜻」이면 아니오다.\n'
    '· **하나를 «고르는» 말은 「아니오」다** — 「네일미용으로 할게요」·\n'
    '  「아니 그거로 할게요」처럼 «이걸 달라»는 뜻이면 앞에 부정어가 붙어도 아니오다.\n'
    '· 형편·제약을 말하거나(「3주에 한 번 병원에 가야 해서요」),\n'
    '  새 정보를 주는 것(「예전에 미용실에서 일했어요」)은 그 자체로는 「아니오」다.\n'
    '· 짐작하지 마라. 애매하면 「아니오」다 — 원하는 것을 뺏는 쪽이 더 비싼 실수다.')


def w(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def pad(s, n):
    return str(s) + ' ' * max(1, n - w(s))


def won(u):
    return ((u.get('in', 0) - u.get('cached', 0)) * 0.25
            + u.get('cached', 0) * 0.025 + u.get('out', 0) * 1.50) / 1e6 * 1380


async def main():
    engA = E()
    engB = E()
    print('=' * 118)
    print(f'  「거부」 판정 A/B — 케이스 {len(CASES)}건 · 모델 {engA.model}')
    print('  A = 운영 게이트(_harm_gate 에 얹힌 필드)   |   B = 전용 호출(안전 프롬프트 없음)')
    print('=' * 118)
    print()
    print(f'  {pad("발화", 50)} {pad("정답", 8)} {pad("A(운영)", 10)} {pad("B(전용)", 10)}')
    print('  ' + '-' * 114)

    nA = nB = tot = 0
    fpA = fnA = fpB = fnB = 0
    dump = []
    for msg, card, want, why in CASES:
        #  A — 운영 게이트를 그대로 부른다. 반환값이 아니라 last_reject 를 읽는다.
        try:
            await engA._harm_gate(msg, card)
            a = '예' if getattr(engA, 'last_reject', False) else '아니오'
            if not getattr(engA, 'last_reject_seen', False):
                a = '판정못함'
        except Exception as e:                              # noqa: BLE001
            a = f'실패({type(e).__name__})'
        #  B — 전용 호출
        try:
            j = await engB.gemini(B_PROMPT.format(card=card, msg=msg),
                                  BIN_SCHEMA, 0.0, think='minimal')
            b = ((j or {}).get('거부') or '아니오').strip()
        except Exception as e:                              # noqa: BLE001
            b = f'실패({type(e).__name__})'

        if want == '애매':
            mk = '(뺌)'
            okA = okB = None
        else:
            tot += 1
            okA, okB = (a == want), (b == want)
            nA += okA
            nB += okB
            if not okA:
                fpA += (want == '아니오')
                fnA += (want == '예')
            if not okB:
                fpB += (want == '아니오')
                fnB += (want == '예')
            mk = ''
        print(f'  {pad(msg[:48], 50)} {pad(want, 8)} '
              f'{pad(a + ("" if okA is None or okA else " ✗"), 10)} '
              f'{pad(b + ("" if okB is None or okB else " ✗"), 10)} {mk}')
        dump.append({'발화': msg, '카드': card, '정답': want, '왜': why,
                     'A운영': a, 'B전용': b,
                     'A맞음': okA, 'B맞음': okB})

    print('  ' + '-' * 114)
    print(f'  A 운영 게이트  {nA}/{tot} ({nA / tot * 100:.0f}%)   '
          f'오탐(거부 아닌데 예) {fpA} · 놓침(거부인데 아니오) {fnA}')
    print(f'  B 전용 호출    {nB}/{tot} ({nB / tot * 100:.0f}%)   '
          f'오탐 {fpB} · 놓침 {fnB}')
    print()
    uA, uB = engA.total_usage, engB.total_usage
    print(f'  A 사용량 — 호출 {uA.get("calls", 0)} · 입력 {uA.get("in", 0):,} '
          f'· 캐시 {uA.get("cached", 0):,} · 출력 {uA.get("out", 0):,} · **{won(uA):.2f}원** '
          f'(호출당 {won(uA) / max(1, uA.get("calls", 1)):.3f}원)')
    print(f'  B 사용량 — 호출 {uB.get("calls", 0)} · 입력 {uB.get("in", 0):,} '
          f'· 캐시 {uB.get("cached", 0):,} · 출력 {uB.get("out", 0):,} · **{won(uB):.2f}원** '
          f'(호출당 {won(uB) / max(1, uB.get("calls", 1)):.3f}원)')
    print('=' * 118)
    print('  ※ 오탐(거부 아닌데 「예」)이 놓침보다 비싸다 — 원하는 것을 뺏는 쪽이다.')
    print('  ⚠ 정답표는 손으로 붙였고 25건은 통계가 아니라 «경계 확인»이다.')

    out = Path(__file__).with_name('_reject_gate_ab.json')
    out.write_text(json.dumps({
        '잰날': '2026-08-11', '모델': engA.model, '채점케이스': tot,
        'A운영': {'정답': nA, '오탐': fpA, '놓침': fnA, '사용량': dict(uA),
                 '원': round(won(uA), 2)},
        'B전용': {'정답': nB, '오탐': fpB, '놓침': fnB, '사용량': dict(uB),
                 '원': round(won(uB), 2)},
        '케이스': dump}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'  원값 저장: {out.name}')


asyncio.run(main())
