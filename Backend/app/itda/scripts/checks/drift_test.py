# -*- coding: utf-8 -*-
"""topic drift 측정 — LLM 질의가 «이번 턴»에 쏠려 앞 방향을 버리는가.

Yang 외 (EMNLP 2025, arXiv:2509.19700):
  "not explicitly optimized to track user intent in multi-turn settings,
   often failing under topic drift or contextual ambiguity"

흐름 설계 원칙
  1턴에 «방향»을 분명히 말한다.
  2·3턴에 그 방향과 «무관하지 않지만 부수적인» 말을 한다.
  → LLM 질의가 뒤 턴으로 쏠리면 1턴의 방향이 사라진다. 그게 drift 다.

ITDA_SLOT_MULTIQ=1 이면 누적 슬롯을 «닻»으로 함께 넣는다. 그 효과를 본다.
"""
import asyncio
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.db import async_session          # noqa: E402
import app.itda.match as match_mod             # noqa: E402
from app.itda.itda_core import ItdaEngine, as_list   # noqa: E402

#  ── 검색에 실제로 들어간 질의를 가로챈다 ─────────────────────────
_SEEN_Q = []
_orig_match = match_mod.match_jobs


async def _spy(db, query_text, top_k=6, min_score=0.0):
    qs = query_text if isinstance(query_text, (list, tuple)) else [query_text]
    _SEEN_Q.append(list(qs))
    return await _orig_match(db, query_text, top_k=top_k, min_score=min_score)


match_mod.match_jobs = _spy

#  (이름, 턴들, 1턴이 가리킨 방향을 나타내는 낱말들)
FLOWS = [
    ('① 빵 → 체력',
     ['빵 만드는 게 좋아요', '근데 아침 일찍 일어나는 건 힘들어요', '체력도 약한 편이고요'],
     ('제빵', '제과', '떡', '식품', '조리')),
    ('② 컴퓨터 → 조용함',
     ['컴퓨터로 하는 일이요', '조용한 데가 좋아요', '사람은 별로 안 만나고 싶고요'],
     ('컴퓨터', '데이터', '정보', '전산', '소프트', '웹', '프로그', '사무')),
    ('③ 돌봄 → 만들기',
     ['어르신 돌보는 일 해봤어요', '손으로 뭐 만드는 것도 재밌고', '요즘 그런 게 유행이라던데'],
     ('요양', '돌봄', '간병', '복지', '보건', '아이돌봄', '일상생활')),
    ('④ 정비 → 깔끔함',
     ['자동차 정비 배우고 싶어요', '근데 기름때 묻는 건 좀', '깔끔한 게 좋아서요'],
     ('자동차', '정비', '기계', '차량', '엔진')),
    ('⑤ 돌봄 → 시간제약',
     ['어르신 돌보는 일 해봤어요', '밤에 일하는 건 못 해요', '낮에만 할 수 있어요'],
     ('요양', '돌봄', '간병', '복지', '보건', '아이돌봄', '일상생활')),
    ('⑥ 요리 → 창업·비용',
     ['요리 쪽 관심 있어요', '가게 차리는 것도 생각해봤고', '돈이 얼마나 드는지 궁금해요'],
     ('조리', '요리', '한식', '양식', '외식', '식음료', '제과', '제빵')),
]


async def main():
    eng = ItdaEngine()
    print(f'SLOT_MULTIQ = {eng.SLOT_MULTIQ}')
    drift = 0
    async with async_session() as db:
        for name, turns, want in FLOWS:
            profile = {}
            print('=' * 92)
            print(f'  {name}   (1턴 방향: {"·".join(want[:4])}…)')
            print('=' * 92)
            for i, msg in enumerate(turns, 1):
                _SEEN_Q.clear()
                try:
                    out = await eng.step(db, profile, msg)
                except Exception as e:                    # noqa: BLE001
                    print(f'  [{i}] !! {type(e).__name__}: {str(e)[:60]}')
                    break
                profile = out.get('profile') or profile
                qs = _SEEN_Q[-1] if _SEEN_Q else []
                #  이번 턴 질의들이 1턴 방향을 «하나라도» 담고 있나
                hit = any(any(w in q for w in want) for q in qs)
                print(f'  [{i}] 🧑 {msg}')
                if qs:
                    print(f'      질의 {len(qs)}개  방향유지={"✅" if hit else "🔴 drift"}')
                    for q in qs[:6]:
                        print(f'        · {q[:70]}')
                    if len(qs) > 6:
                        print(f'        · … 외 {len(qs)-6}개')
                    if i == len(turns) and not hit:
                        drift += 1
                card = out.get('card') or {}
                if card.get('job'):
                    nm = card['job'].get('name')
                    ok = any(w in str(nm) for w in want)
                    print(f'      🃏 {nm}   {"✅" if ok else "🔴 방향 이탈"}')
                elif out.get('options'):
                    o = out['options']
                    ok = any(any(w in str(x) for w in want) for x in o)
                    print(f'      [칩] {o}   {"✅" if ok else "🔴 방향 이탈"}')
            print()
    print('=' * 92)
    u = eng.total_usage
    print(f'마지막 턴 기준 drift {drift}/{len(FLOWS)}  ·  LLM {u.get("calls",0)}회 '
          f'· 입력 {u.get("in",0):,}')


asyncio.run(main())
