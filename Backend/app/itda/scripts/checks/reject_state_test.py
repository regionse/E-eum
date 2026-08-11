# -*- coding: utf-8 -*-
r"""거부 상태 전이 — 순수 함수만 (2026-08-10 신설). LLM 0회 · DB 0회 · **0원**

무엇을 지키나
  `rejection_target` → `apply_rejection` → `unexclude_named`/`unexclude_wanted` 가
  프로필을 «어떻게» 바꾸는지를 못 박는다. 실측에서 터진 사슬을 케이스로 만들었다:
    kl_demo01 6턴  대안 거부가 카드를 배제 → 7턴 이름을 불러도 못 꺼냄 → 8턴 엉뚱한 계열
    kl_fix01  9턴  게이트가 「선택」을 「거부」로 오판 → 원하는 것이 배제됨

  ⚠ 이 파일은 «기계»만 잰다. 「거부인가」 판정(게이트)과 검색 결과는 여기서 안 본다.
    그건 talk.py 로 실제 대화를 굴려야 보인다.
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda.itda_core import (                       # noqa: E402
    rejection_target, apply_rejection, unexclude_named, unexclude_wanted,
    shown_targets, drop_questions, _WAIT)

#  ── 픽스처 ──────────────────────────────────────────────────────────
#  ⚠ 처음엔 칩과 대안을 한 프로필에 몰아넣었는데, 그건 «여러 턴의 상태»를 섞은 것이었다.
#    (그 덕에 이름 겹침 결함이 잡히긴 했다 — shown_targets 의 dedup 주석 참고)

#  BASE — kl_demo01 «6턴 직전». 카드가 떠 있고 대안이 셋.
BASE = {
    '_last_job': '12010104', '_last_job_name': '네일미용',
    '_alt_opts': ['아이돌봄', '피부미용', '헤어미용'],
    '_landed': True, '세부관심': '네일미용',
    '_exclude': ['07010202'], '_exclude_names': ['일상생활기능지원'],
}

#  CHIPS — 칩이 떠 있는 상태. 카드는 아직 없다.
CHIPS = {
    '_narrow_opts': ['헤어미용', '네일미용', '피부미용', '이용', '메이크업'],
    '_narrow_codes': ['12010101', '12010104', '12010102', '12010105', '12010103'],
    '_narrowed': True,
}

#  MIXED — 칩과 대안에 «같은 이름»이 겹친 상태. 실측 6턴 뒤 덤프가 정확히 이랬다.
MIXED = dict(BASE, _narrow_opts=['피부미용', '헤어미용', '아이돌봄', '이용', '메이크업'],
             _narrow_codes=['12010102', '12010101', '07030103', '12010105', '12010103'],
             _narrowed=True)

FAIL = []


def check(name, cond, got=None):
    print(f'  {"OK  " if cond else "🔴 "} {name}' + ('' if cond else f'   ← {got}'))
    if not cond:
        FAIL.append(name)


print('=' * 92)
print('  거부 상태 전이 시험 — LLM 0회 · DB 0회 · 0원')
print('=' * 92)

# ── ① 보여준 것 목록 ────────────────────────────────────────────────
print('\n① shown_targets — 화면에 뜬 것을 다 모으나')
sh = shown_targets(BASE)
check('카드 1 + 대안 3 = 4개', len(sh) == 4, len(sh))
check('대안은 코드가 없다(_siblings 가 이름만 준다)',
      all(c is None for k, c, _ in sh if k == 'alt'))
sh = shown_targets(CHIPS)
check('칩은 코드를 갖는다', len(sh) == 5 and all(c for _, c, _ in sh), sh)
#  ★ 이름 겹침 — 처음 짠 코드가 여기서 졌다. 못 박아 둔다.
sh = shown_targets(MIXED)
nms = [nm for _, _, nm in sh]
check('겹친 이름은 «하나»로 합쳐진다', len(nms) == len(set(nms)), nms)
check('겹칠 땐 코드 있는 쪽(칩)이 남는다',
      dict((nm, k) for k, _, nm in sh).get('아이돌봄') == 'chip', sh)

# ── ② 목적어 판정 ───────────────────────────────────────────────────
print('\n② rejection_target — 무엇을 물렸나')
check('대안 이름 → alt',
      rejection_target(BASE, '근데 아이돌봄이 자꾸 뜨는데요')[:1] == ('alt',),
      rejection_target(BASE, '근데 아이돌봄이 자꾸 뜨는데요'))
check('카드 이름 → card',
      rejection_target(BASE, '네일미용은 좀 아닌 것 같아요')[0] == 'card')
check('이름 없음 → card 폴백(예전 동작)',
      rejection_target(BASE, '그거 말고 다른 거 보여주세요')[0] == 'card')
check('이름 둘 → ambiguous',
      rejection_target(BASE, '네일미용 말고 아이돌봄 주세요')[0] == 'ambiguous')
check('겹친 이름은 모호가 «아니다»',
      rejection_target(MIXED, '아이돌봄은 빼주세요')[0] == 'chip',
      rejection_target(MIXED, '아이돌봄은 빼주세요'))

# ── ③ 대안 거부 — 이번 결함의 핵심 ──────────────────────────────────
print('\n③ 대안을 물렸을 때 — 카드가 살아남나 (kl_demo01 6턴)')
tgt = rejection_target(BASE, '근데 아이돌봄이 자꾸 뜨는데요. 돌보는 일은 아니라고요')
p = apply_rejection(BASE, tgt)
check('카드가 _exclude 에 «안» 들어간다', '12010104' not in (p.get('_exclude') or []),
      p.get('_exclude'))
check('_landed 가 살아 있다 → 카드가 안 사라진다', p.get('_landed') is True)
check('세부관심도 살아 있다', p.get('세부관심') == '네일미용')
check('강등도 안 걸린다(대안은 코드가 없다)', not p.get('_demote'), p.get('_demote'))
_m = apply_rejection(MIXED, rejection_target(MIXED, '근데 자꾸 그 얘기가 나오는데요'))
check('(참고) 이름 없는 거부는 여전히 카드로 간다',
      '12010104' in (_m.get('_exclude') or []), _m.get('_exclude'))

# ── ④ 카드 거부 — 예전 동작이 그대로인가 (회귀) ──────────────────────
print('\n④ 카드를 물렸을 때 — 예전 동작 그대로인가 (회귀)')
tgt = rejection_target(MIXED, '네일미용은 좀 아닌 것 같아요')
p = apply_rejection(MIXED, tgt)
check('카드가 _exclude 에 들어간다', '12010104' in (p.get('_exclude') or []))
check('이름도 나란히 남는다', '네일미용' in (p.get('_exclude_names') or []))
check('칩 5개가 전부 강등된다', len(p.get('_demote') or []) == 5, p.get('_demote'))
check('_landed 가 풀린다', p.get('_landed') is None)
check('세부관심이 비워진다', p.get('세부관심') is None)
check('좁히기 목록도 비워진다', p.get('_narrow_opts') is None)

# ── ⑤ target 없이 부르면 (none_of_these 경로) ───────────────────────
print('\n⑤ target 없이 — 「다 아니에요」 경로가 안 깨졌나')
p = apply_rejection(MIXED)
check('예전과 같이 카드를 배제한다', '12010104' in (p.get('_exclude') or []))
check('예전과 같이 칩을 전부 강등한다', len(p.get('_demote') or []) == 5)

# ── ⑥ 칩 하나 거부 ──────────────────────────────────────────────────
print('\n⑥ 칩 하나를 물렸을 때 — 그것만 내려가나')
tgt = rejection_target(CHIPS, '헤어미용 말고요')
p = apply_rejection(CHIPS, tgt)
check('목적어가 chip', tgt[0] == 'chip', tgt)
check('그 칩 코드만 강등', p.get('_demote') == ['12010101'], p.get('_demote'))
check('칩 목록은 남는다(계속 고를 수 있게)', p.get('_narrow_opts') == CHIPS['_narrow_opts'])
tgt = rejection_target(MIXED, '이용은 아니에요')
p = apply_rejection(MIXED, tgt)
check('칩을 물려도 카드는 안 빠진다', '12010104' not in (p.get('_exclude') or []),
      p.get('_exclude'))
check('칩을 물려도 _landed 가 산다', p.get('_landed') is True)

# ── ⑦ 배제 되돌리기 (이름으로 다시 부름) ────────────────────────────
print('\n⑦ unexclude_named — 이름을 다시 부르면 풀리나 (kl_demo01 7턴)')
p = dict(BASE, _exclude=['07010202', '12010104'],
         _exclude_names=['일상생활기능지원', '네일미용'],
         _demote=['12010104', '12010101'])
q, un = unexclude_named(p, '아니 네일미용으로 할게요')
check('풀린 이름을 돌려준다', un == '네일미용', un)
check('_exclude 에서 빠진다', q.get('_exclude') == ['07010202'], q.get('_exclude'))
check('_exclude_names 도 짝이 맞게 빠진다',
      q.get('_exclude_names') == ['일상생활기능지원'], q.get('_exclude_names'))
check('강등도 같이 풀린다', '12010104' not in (q.get('_demote') or []), q.get('_demote'))
q2, un2 = unexclude_named(p, '그냥 아무거나 보여주세요')
check('이름이 없으면 아무것도 안 한다', un2 is None and q2 is p)

# ── ⑦-2 「거부」와 「원함」이 부딪힐 때 ──────────────────────────────
print('\n⑦-2 unexclude_wanted — 게이트 오판을 본문이 되돌리나 (kl_fix01 9턴)')
p = dict(BASE, _exclude=['07010202', '12010104'],
         _exclude_names=['일상생활기능지원', '네일미용'],
         _demote=['12010104'], _gate_reject=True, _rej_target='alt')
q, un = unexclude_wanted(p, {'관심분야': {'네일미용': '원함'}})
check('원함으로 찍힌 이름의 배제가 풀린다', un == '네일미용', un)
check('_exclude 에서 빠진다', q.get('_exclude') == ['07010202'], q.get('_exclude'))
check('강등도 풀린다', '12010104' not in (q.get('_demote') or []))
check('거부 표시도 거둔다', q.get('_gate_reject') is False and not q.get('_rej_target'))
check('해봤음은 안 푼다',
      unexclude_wanted(p, {'관심분야': {'네일미용': '해봤음'}})[1] is None)
check('못함은 안 푼다',
      unexclude_wanted(p, {'관심분야': {'네일미용': '못함'}})[1] is None)
#  ★ 조각 대조는 «절대» 안 한다 — 이 파일이 여러 번 데인 자리다
check('조각(「미용」)으로는 안 풀린다',
      unexclude_wanted(p, {'관심분야': {'미용': '원함'}})[1] is None,
      unexclude_wanted(p, {'관심분야': {'미용': '원함'}})[1])
#  ★ 2차 — 누적 _slot_kind 도 본다. 실측 10턴에서 이번 턴 _kinds 가 비어 있었다.
p2 = dict(p, _slot_kind={'관심분야': {'네일미용': '원함'}})
check('이번 턴 종류가 비어도 누적 _slot_kind 로 푼다',
      unexclude_wanted(p2, {})[1] == '네일미용', unexclude_wanted(p2, {})[1])
#  ★ skip — 무한 고리 방지
check('이번 턴 «카드로» 물린 것은 안 푼다',
      unexclude_wanted(p2, {}, skip='네일미용')[1] is None,
      unexclude_wanted(p2, {}, skip='네일미용')[1])
check('다른 것을 물렸으면 그대로 푼다',
      unexclude_wanted(p2, {}, skip='피부미용')[1] == '네일미용')
check('종류가 아무 데도 없으면 안 한다', unexclude_wanted(p, {})[1] is None)

# ── ⑧ 옛 세션 안전성 ────────────────────────────────────────────────
print('\n⑧ _exclude_names 가 없는 «옛 세션» — 안 터지나')
old = {'_exclude': ['07010202'], '_last_job': '12010104', '_last_job_name': '네일미용'}
q, un = unexclude_named(old, '일상생활기능지원 다시 보여주세요')
check('이름 짝이 없으면 조용히 넘어간다', un is None and q is old)
check('unexclude_wanted 도 마찬가지',
      unexclude_wanted(old, {'관심분야': {'일상생활기능지원': '원함'}})[1] is None)
check('빈 프로필에도 안 터진다', rejection_target({}, '그거 말고')[0] == 'card')
check('apply_rejection 이 빈 프로필을 그대로 돌려준다', apply_rejection({}) == {})

# ── ⑨ 카드 턴의 「기다려 주세요」 ────────────────────────────────────
print('\n⑨ drop_questions — 대기 문장이 카드와 함께 나가지 않나 (kl_fix01 11턴)')
check('물음표 없는 대기 문장도 걸린다', any(w in '잠시만 기다려 주세요.' for w in _WAIT))
check('대기 문장만 있으면 통째로 없어진다',
      drop_questions('잠시만 기다려 주세요.') == '', drop_questions('잠시만 기다려 주세요.'))
check('앞의 공감은 살린다',
      drop_questions('마음이 급하시겠어요. 잠시만 기다려 주세요.') == '마음이 급하시겠어요.',
      drop_questions('마음이 급하시겠어요. 잠시만 기다려 주세요.'))
check('멀쩡한 문장은 안 건드린다',
      drop_questions('네일미용 쪽으로 정리해 드릴게요.') == '네일미용 쪽으로 정리해 드릴게요.')
check('질문은 여전히 떼어낸다',
      drop_questions('좋아요. 어떤 쪽이 편하세요?') == '좋아요.')

print('\n' + '=' * 92)
print(f'  {"전부 통과" if not FAIL else f"🔴 실패 {len(FAIL)}건: " + " · ".join(FAIL)}')
print('=' * 92)
sys.exit(1 if FAIL else 0)
