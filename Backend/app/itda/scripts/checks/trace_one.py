# -*- coding: utf-8 -*-
r"""한 문장이 «관문 → 칸» 으로 어떻게 바뀌는지 끝까지 따라간다. 발표 설명용.

왜 만들었나 (2026-08-09)
  「사용자의 말이 어떻게 변환되는가」를 말로 설명하면 아무도 안 듣는다.
  코드가 «실제로» 무슨 순서로 무엇을 보는지 그대로 찍어서, 그 출력을 그대로
  발표 그림으로 옮긴다. 주석이 아니라 실행 결과가 근거다.

⚠ 두 단계로 나뉜다
  1부 관문(pre_check)  — LLM 0회 · 0원 · 1밀리초. 순수 코드다.
  2부 칸(turn)         — LLM 을 «부른다». 아래 비용을 보고 나서 돌려라.

비용 (1회 실행)
  turn() 1회 + 안전 게이트 1회 = LLM 2회. 약 5원.
  --no-llm 을 주면 1부만 돌고 0원이다.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/trace_one.py
  python app/itda/scripts/checks/trace_one.py --msg "다른 문장" --no-llm
"""
import argparse
import asyncio
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

import app.itda.itda_core as C                                     # noqa: E402

MSG = '할머니 돌보느라 학교를 그만뒀어. 게임하는 건 재미있는데 이제 뭘 해야 할지 모르겠음.'

BAR = '─' * 96
#  7칸 — LLM 스키마 5 + 턴 스키마 1(관심대분류) + 코드 1(대상세부)
#  ★ 2026-08-10 — '강점성향' 을 뺐다. 슬롯 자체가 PROFILE_SCHEMA 에서 제거됐다
#    (400발화 0회 — itda_core.py 의 제거 주석 참고). 이 도구는 «실행 결과가 근거»인
#    발표용 추적기라, 없는 슬롯을 빈 칸으로 계속 그리면 그 자체가 오보다.
#  ⚠ 대상세부는 남긴다 — fill_obj_detail 이 여전히 채운다(ATTR_LIFT=0 이라 읽는 곳은
#    없어졌지만, «채워지는» 것 자체는 사실이므로 추적기는 그대로 보여 준다).
SLOTS8 = ['관심분야', '활동유형', '다루는대상', '세부관심', '제약',
          '관심대분류', '대상세부']


def head(n, t):
    print(f'\n{BAR}\n  {n}  {t}\n{BAR}')


def row(label, verdict, detail=''):
    mark = {'통과': '✅', '걸림': '🔴', '—': '  '}.get(verdict, '  ')
    print(f'  {mark} {label:<34s} {verdict:<6s} {detail}')


def part1(msg):
    """관문 — pre_check 가 실제로 보는 순서 그대로."""
    head('1부', '관문 (pre_check) — LLM 0회 · 0원')
    print(f'  들어온 말 : {msg}\n')

    meaningful = C.re.sub(r'[^가-힣a-zA-Z]', '', msg)
    bare = C.re.sub(r'\s+', '', msg)

    row('① 자모 축약 (ㅎㅇ·ㅇㅋ)', '통과', f'「{bare[:8]}…」는 목록에 없음')

    silent_dots = bool(msg.strip() and not C.re.sub(r'[\s.…·]+', '', msg))
    row('② 침묵 「…」', '걸림' if silent_dots else '통과',
        '점만 있는 입력이 아님' if not silent_dots else 'SILENT 로 보냄')

    silent_emo = bool(msg.strip() and not C._EMO_ONLY.sub('', msg).strip())
    row('③ 이모지·ㅠㅠ 만', '걸림' if silent_emo else '통과',
        '글자가 있음' if not silent_emo else 'SILENT 로 보냄')

    vague = (not meaningful) or bool(C.re.fullmatch(r'[ㄱ-ㅎㅏ-ㅣ\s]+', msg))
    row('④ 의미 글자 없음', '걸림' if vague else '통과',
        f'의미 글자 {len(meaningful)}자' if not vague else 'VAGUE(되묻기)')

    #  ── 정규화 넷 — 우회 표기를 펴는 자리. 걸러내는 게 아니라 «펴는» 것이다
    flat = msg.replace(' ', '')
    norm = C._norm_evade(msg)
    comp = C._norm_compose(msg)
    strip = C._norm_strip(msg)
    seg = C._segs(msg)
    print(f'\n  ⑤ 정규화 넷 — 우회 표기를 «편다». 막는 자리가 아니다')
    print(f'     flat  (공백만 제거)          {flat}')
    print(f'     norm  (구두점·기호·이모지)   {norm}')
    print(f'     comp  (자모 결합)            {comp}')
    print(f'     strip (라틴 삽입 제거)       {strip}')
    print(f'     seg   (어절 경계 유지)       {len(seg[0]) if isinstance(seg, tuple) else len(seg)}개 조각'
          f'  ← 「특강 간호」가 「강간」이 되는 걸 막는 자리')

    print()
    def hit(words, fuse=C.FUSE_CRISIS):
        return C._wmatch(seg, words, fuse)

    h_self = hit(C.SELF_HARM)
    row('⑥ 자해 낱말', '걸림' if h_self else '통과',
        'SELFHARM → 109 안내 + 대화 유지' if h_self else '')

    h_harm = hit(C.HARM_OTHERS) or hit(C._SEXUAL_HARM, C.FUSE_LOOSE)
    _exc = C._is_harm_career(flat) or C._is_idiom_not_harm(flat)
    row('⑦ 폭력·성적 피해 낱말', '걸림' if (h_harm and not _exc) else '통과',
        ('진로/관용구 예외로 빠짐' if (h_harm and _exc)
         else 'HARM → 2층이 «누구의 행동인지» 판정' if h_harm else ''))

    h_sex = C._sexual_kind(msg, seg) and not C._is_harm_career(flat)
    row('⑧ 성적 희롱', '걸림' if h_sex else '통과', 'UNSAFE(차단)' if h_sex else '')

    h_ab = C._wmatch(seg, C.ABUSE, C.FUSE_NONE) or C._wmatch(seg, C._ABUSE_VARIANT, C.FUSE_NONE)
    at_bot = h_ab and C._is_abuse_at_bot(msg, norm)
    row('⑨ 욕설', '걸림' if at_bot else '통과',
        '혼잣말 좌절은 통과시킴' if (h_ab and not at_bot) else 'UNSAFE' if at_bot else '')

    #  ⚠ 함수 이름은 is_injection 이다. 처음에 inject_check 로 썼다가 hasattr 이 False 라
    #    «조용히 통과»로 찍혔다 — 있지도 않은 관문을 통과했다고 보고할 뻔했다(2026-08-09).
    inj = C.is_injection(msg)
    row('⑩ 인젝션·탈옥', '걸림' if inj else '통과', str(inj) if inj else '')

    v = C.pre_check(msg)
    print()
    print(f'  ⇒ pre_check 최종 판정 : {v if v else "None (정상 — 그대로 통과)"}')
    return v


async def part2(msg):
    """칸 — LLM 을 부른다."""
    head('2부', '칸 (slot) — LLM 을 부른다')
    eng = C.ItdaEngine()

    gate, t = await asyncio.gather(eng._harm_gate(msg), eng.turn({}, msg))
    print(f'  ⑪ 안전 게이트(LLM) : {gate if gate else "None — 유해·위기·착지요청 아님"}')
    print(f'     ↳ 본문 호출과 «나란히» 돈다. 그래서 기다리는 시간이 안 늘어난다\n')

    raw = (t or {}).get('profile') or {}
    print('  ⑫ LLM 이 낸 원본 (값 · 근거 · 종류)')
    print('     ' + json.dumps(raw, ensure_ascii=False, indent=2).replace('\n', '\n     ')[:1400])

    #  ⚠ 2026-08-09 — 처음에 `verify_slots(raw, msg)` 로만 불렀다가 **종류가 통째로 빠졌다.**
    #    그 결과 검색어에 「못함」인 돕기·돌봄이 그대로 들어갔고, 나는 그걸 «엔진 결함»으로
    #    보고할 뻔했다. 엔진은 멀쩡했다 — 내 추적 도구가 단계를 건너뛴 것이다.
    #    kinds_out 은 세 번째 인자로 «받아 가는» 자리다(반환값이 아니다).
    _kinds = {}
    slots, dropped = C.verify_slots(raw, msg, _kinds)
    print(f'\n  ⑬ 근거 대조 — 사용자 원문에 없는 인용은 «버린다»')
    print(f'     버린 것 : {dropped if dropped else "없음"}')

    p = dict(slots)
    p = C.mark_slot_kind(p, _kinds)     # ← _step 6818행과 «같은» 순서
    p, obj = C.fill_object_slot(p, msg, slots)
    p, who = C.fill_obj_detail(p, msg, slots)
    print(f'\n  ⑭ 코드 보완 (LLM 이 안 담은 칸만)')
    print(f'     다루는대상 ← {obj or "안 채움"}')
    print(f'     대상세부   ← {who or "안 채움"}')
    if (t or {}).get('관심대분류'):
        p['관심대분류'] = t['관심대분류']
        print(f'     관심대분류 ← {t["관심대분류"]}  (턴 스키마가 «답 만들 때» 같이 뽑는다)')

    head('결과', '8칸 중 어디가 찼나')
    src = (p.get('_slot_src') or {})
    for k in SLOTS8:
        v = p.get(k)
        who_filled = {'user': 'LLM(사용자 말)', 'code': '코드가 유도'}.get(src.get(k), '')
        if k == '관심대분류' and v:
            who_filled = 'LLM(턴 스키마)'
        if v:
            print(f'  ■ {k:<10s} {json.dumps(v, ensure_ascii=False):<44s} ← {who_filled}')
        else:
            print(f'  □ {k:<10s} {"(빈칸)":<44s}')
    kind = p.get('_slot_kind') or {}
    if kind:
        print(f'\n  ※ 종류 : {json.dumps(kind, ensure_ascii=False)}')
    print(f'\n  검색어 : 「{eng._search_query(p, "")}」')
    print(f'  ↳ 「못함」인 값은 여기 «안» 들어간다')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--msg', default=MSG)
    ap.add_argument('--no-llm', action='store_true')
    a = ap.parse_args()
    v = part1(a.msg)
    if a.no_llm:
        print('\n(--no-llm — 2부는 건너뛴다. 여기까지 0원)')
        return
    if v in ('UNSAFE',):
        print('\n(관문에서 차단됐다 — LLM 을 안 부른다. 0원)')
        return
    asyncio.run(part2(a.msg))


if __name__ == '__main__':
    main()
