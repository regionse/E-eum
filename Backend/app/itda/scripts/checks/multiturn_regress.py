# -*- coding: utf-8 -*-
"""다중 턴 회귀 — **코드 주석에 기록된 과거 사고**를 그대로 재현한다.

왜 필요한가
  골든셋 34케이스는 «전부 단일 턴»이다. 그런데 이 파일이 기록한 사고 중 상당수가
  «여러 턴에 걸친» 것이다 — 덮어쓰기 · 거부 무시 · 지시대명사 · 칩 선택 소실.
  즉 «고쳤다고 적혀 있지만 지켜주는 테스트가 없는» 것들이다.
  2026-08-06 에 대화 흐름을 여러 곳 건드렸으므로(UTT_KIND · DROP_COND_Q ·
  SLOT_MULTIQ · _landed · ask_reply · is_meta …) 그것들이 살아 있는지 확인한다.

각 케이스의 출처를 주석에 남긴다 — 나중에 실패했을 때 «원래 무슨 사고였는지» 찾으려고.
"""
import asyncio
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.db import async_session                 # noqa: E402
from app.itda.itda_core import ItdaEngine, as_list    # noqa: E402


def _job(out):
    return ((out.get('card') or {}).get('job') or {}).get('name') or ''


def _slots(p, k):
    return [str(x) for x in as_list((p or {}).get(k))]


#  (이름, 출처, 턴 목록, 판정함수(기록들) -> (통과여부, 설명))
CASES = []


def case(name, src, turns):
    def deco(fn):
        CASES.append((name, src, turns, fn))
        return fn
    return deco


@case('① 거부해도 같은 카드가 또 나오나',
      'itda_core.py:328 — 3턴 «근데 계속 그것만 하긴 좀» 에 같은 카드가 또 나갔다',
      ['할머니 간병하면서 학교를 못 다녔어요', '그런 일 계속 해왔어요',
       '근데 계속 그것만 하긴 좀'])
def _c1(rec):
    before = [r['job'] for r in rec[:-1] if r['job']]
    last = rec[-1]['job']
    if not before:
        return None, '앞 턴에 카드가 안 나와 판정 불가'
    if last and last in before:
        return False, f'거부했는데 같은 카드가 또 나옴: {last}'
    return True, f'앞 {before} → 마지막 {last or "카드 없음"}'


@case('② 지시대명사 — 「어르신 쪽이 편해요」',
      'itda_core.py:2054 — 이력 없으면 «어르신» 이 통째로 소실됐다',
      ['어르신 쪽이 편해요'])
def _c2(rec):
    p = rec[-1]['profile']
    got = _slots(p, '세부관심') + _slots(p, '관심분야')
    ok = any('어르신' in x or '노인' in x for x in got)
    return ok, f'세부관심·관심분야 = {got}'


@case('③ 덮어쓰기 — 1턴 돌봄이 3턴 만들기에 지워지나',
      'itda_core.py:1237 — 1턴 돕기·돌봄 → 3턴 만들기 로 «덮여» 돌봄이 사라졌다',
      ['엄마가 아프셔서 제가 계속 챙겨요', '그래서 시간이 없었어요',
       '손으로 만드는 게 편해요'])
def _c3(rec):
    act = _slots(rec[-1]['profile'], '활동유형')
    ok = any('돌봄' in x for x in act) and any('만들' in x for x in act)
    return ok, f'활동유형 = {act}'


@case('④ 방향 전환 — 「아니다 그냥 사무직」',
      'prompts.py:191 — 관심분야=요리가 남아 [사무행정] 카드에 요리가 붙어 있었다',
      ['요리 쪽 관심있어요', '해본 적은 있어요', '아니다 그냥 사무직이 나을까요'])
def _c4(rec):
    iv = _slots(rec[-1]['profile'], '관심분야')
    has_new = any(('사무' in x or '행정' in x or '문서' in x) for x in iv)
    return has_new, f'관심분야 = {iv}  (사무 쪽이 들어와야 한다)'


@case('⑤ 한 문장에 다 차면 카드를 미루나',
      'itda_core.py:1139 — 「빵 만드는 거 좋아해요」 한 마디에 [제빵] 카드가 나갔다',
      ['빵 만드는 거 좋아해요'])
def _c5(rec):
    return rec[0]['kind'] != 'card', f"1턴 kind = {rec[0]['kind']}"


@case('⑥ 되묻는 턴을 카드로 확정하나',
      'itda_core.py:4689 — 「가구제작은 무슨 소리야?」 에 [가구제작] 카드가 확정됐다',
      ['손으로 만드는 일이 좋아요', '가구제작은 무슨 소리야?'])
def _c6(rec):
    return rec[-1]['kind'] != 'card', f"kind = {rec[-1]['kind']}"


@case('⑦ 돌봄 발화를 통조림 질문으로 덮나',
      'itda_core.py:618 — 공감 답변이 「주로 무엇을 다루는…」 으로 갈아치워졌다',
      ['그냥 모르겠어 크게 생각해본 적 없는데. 어머니가 아프셔서 돌봐드리느라 그럴 겨를이 없었어요'])
def _c7(rec):
    r = rec[-1]['reply']
    bad = ('주로 무엇을 다루는' in r) or ('일의 주 재료' in r)
    return not bad, f'답변 앞부분: {r[:50]}'


@case('⑧ 「알아들었어?」 에 내부 구조가 새나',
      'itda_core.py:4576 — 관심분야 [\'용접\'] · 제약 [\'학력부담\'] 이 화면에 나갔다',
      ['제빵사가 되고 싶어요', '알아들었어?'])
def _c8(rec):
    r = rec[-1]['reply']
    bad = [t for t in ("['", "']", '제약', '관심대분류', '다루는대상') if t in r]
    return not bad, (f'노출: {bad}' if bad else '내부 구조 노출 없음')


async def main():
    eng = ItdaEngine()
    print(f'UTT_KIND={eng.UTT_KIND} · SLOT_MULTIQ={eng.SLOT_MULTIQ} '
          f'· DROP_COND_Q={eng.DROP_COND_Q}\n')
    fails = []
    async with async_session() as db:
        for name, src, turns, judge in CASES:
            profile, rec = {}, []
            print('=' * 92)
            print(f'  {name}')
            print(f'  출처: {src}')
            print('=' * 92)
            for i, msg in enumerate(turns, 1):
                try:
                    out = await eng.step(db, profile, msg)
                except Exception as e:                    # noqa: BLE001
                    print(f'  [{i}] !! {type(e).__name__}: {str(e)[:60]}')
                    rec = []
                    break
                profile = out.get('profile') or profile
                rec.append({'kind': out.get('kind'), 'job': _job(out),
                            'reply': out.get('reply') or '', 'profile': dict(profile)})
                print(f'  [{i}] 🧑 {msg}')
                print(f'      kind={out.get("kind")}' +
                      (f'  🃏 {_job(out)}' if _job(out) else '') +
                      (f'  [칩] {out["options"]}' if out.get('options') else ''))
            if not rec:
                fails.append((name, '실행 실패'))
                print()
                continue
            ok, why = judge(rec)
            if ok is None:
                print(f'  ⚪ 판정 불가 — {why}')
            elif ok:
                print(f'  ✅ {why}')
            else:
                fails.append((name, why))
                print(f'  🔴 실패 — {why}')
            print()

    print('=' * 92)
    print(f'  통과 {len(CASES)-len(fails)} / {len(CASES)}')
    for n, w in fails:
        print(f'    🔴 {n} — {w}')
    u = eng.total_usage
    print(f'  LLM {u.get("calls",0)}회 · 입력 {u.get("in",0):,}')
    print('=' * 92)


asyncio.run(main())
