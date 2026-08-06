# -*- coding: utf-8 -*-
"""LLM 이 죽었을 때 대화가 살아남나 — **LLM 을 안 부른다. 0원.**

왜 이 검사가 필요한가
  gemini_util.call 은 실패하면 **None 이 아니라 RuntimeError 를 던진다.**
  그런데 utt_kind·_on_topic·turn 의 도크스트링은 「실패(None)하면 …」이라고 적혀 있었고
  구현이 그걸 안 따라갔다. 즉 **Gemini 가 한 번 흔들리면 1턴차가 error 화면**이었다.
  골든셋으로는 절대 안 잡힌다 — 골든셋은 Gemini 가 살아 있을 때만 돈다.

무엇을 확인하나
  ① utt_kind   → None    (부르는 쪽이 낱말표로 판단하게)
  ② _on_topic  → True    (fail-open. 주제 게이트지 접근 제어가 아니다)
  ③ turn       → None + last_block='CALL_FAILED'
  ④ _step 전체 → 예외 없이 응답. 그리고 **안전차단 문구가 아니어야 한다**
  ⑤ ★ 낡은 last_block 오염 — 직전 호출이 'SAFETY' 를 남긴 채 네트워크가 죽으면?
       고치기 전이면 「희롱을 막았다」 문구가 나갔다. 정반대 응답이다.

⚠ 안전층(pre_check·is_injection)은 순수 코드라 LLM 과 무관하다.
  그래서 fail-open 해도 안 뚫린다 — 그걸 ⑥에서 같이 확인한다.
"""
import sys
import io
import asyncio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

import app.itda.gemini_util as gutil                    # noqa: E402
from app.itda.itda_core import ItdaEngine, pre_check    # noqa: E402
from app.itda.itda_core import SAFETY_BLOCK_REPLY       # noqa: E402


async def _dead(make_request, env, **kw):
    """Gemini 가 죽은 척한다 — 실제 실패와 «같은» 예외를 던진다."""
    raise RuntimeError('Gemini 호출 실패 — TimeoutError: timed out')


async def main():
    gutil.call = _dead                       # 전 노선 차단
    e = ItdaEngine()
    ok = 0
    bad = []

    def chk(name, cond, got):
        nonlocal ok
        if cond:
            ok += 1
            print(f'  ✅ {name:<44} {got}')
        else:
            bad.append(name)
            print(f'  🔴 {name:<44} {got}')

    print('■ LLM 이 완전히 죽은 상태에서\n')

    try:
        r = await e.utt_kind('빵 만드는 일 하고 싶어요')
        chk('① utt_kind → None (예외 안 남)', r is None, f'→ {r}')
    except Exception as ex:                              # noqa: BLE001
        chk('① utt_kind → None (예외 안 남)', False, f'💥 {type(ex).__name__}')

    try:
        r = await e._on_topic('빵 만드는 일 하고 싶어요')
        chk('② _on_topic → True (fail-open)', r is True, f'→ {r}')
    except Exception as ex:                              # noqa: BLE001
        chk('② _on_topic → True (fail-open)', False, f'💥 {type(ex).__name__}')

    try:
        e.last_block = None
        r = await e.turn({}, '빵 만드는 일 하고 싶어요')
        chk('③ turn → None + last_block=CALL_FAILED',
            r is None and e.last_block == 'CALL_FAILED', f'→ {r} / {e.last_block}')
    except Exception as ex:                              # noqa: BLE001
        chk('③ turn → None + last_block=CALL_FAILED', False, f'💥 {type(ex).__name__}')

    try:
        e.last_block = None
        st = await e.step(None, {}, '빵 만드는 일 하고 싶어요')
        rep = (st or {}).get('reply') or ''
        chk('④ step 전체 → 예외 없이 응답', bool(rep), f'kind={st.get("kind")}')
        chk('④-b 안전차단 문구가 «아니어야» 한다',
            rep[:20] != SAFETY_BLOCK_REPLY[:20], f'{rep[:36]}…')
    except Exception as ex:                              # noqa: BLE001
        chk('④ step 전체 → 예외 없이 응답', False, f'💥 {type(ex).__name__}: {str(ex)[:50]}')

    #  ⑤ 낡은 last_block 오염 — 이게 이번에 같이 고친 것이다
    try:
        e.last_block = 'SAFETY'              # 직전 호출(또는 배경 요약)이 남긴 값
        st = await e.step(None, {}, '용접 배우고 싶어요')
        rep = (st or {}).get('reply') or ''
        chk('⑤ ★ 낡은 last_block=SAFETY 오염 방어',
            rep[:20] != SAFETY_BLOCK_REPLY[:20], f'{rep[:36]}…')
    except Exception as ex:                              # noqa: BLE001
        chk('⑤ ★ 낡은 last_block=SAFETY 오염 방어', False, f'💥 {type(ex).__name__}')

    #  ⑥ LLM 이 죽어도 안전층은 그대로여야 한다 (순수 코드니까)
    print()
    for msg, want in (('죽고 싶어요', 'SELFHARM'), ('아빠가 엄마를 때려요', 'HARM'),
                      ('너 병신이냐', 'UNSAFE'), ('빵 만드는 일', None),
                      ('장애인 활동지원사 알려주세요', None)):
        got = pre_check(msg)
        chk(f'⑥ 안전층 «{msg}»', got == want, f'→ {got}')

    print(f'\n{"=" * 76}\n  {"✅ 통과" if not bad else "🔴 실패"}  '
          f'{ok}건 통과 · LLM 0회 (0원)')
    if bad:
        for b in bad:
            print(f'    실패: {b}')
    print('=' * 76)
    sys.exit(0 if not bad else 1)

asyncio.run(main())
