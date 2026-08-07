# -*- coding: utf-8 -*-
"""실사용에서 난 「추천을 불러오는 데 문제가 있었어요」를 재현한다.

왜 필요한가
  _step() 의 검색 호출이 `except Exception` 으로 감싸여 있어서, 사용자에겐
  「문제가 있었어요」만 나가고 **진짜 예외는 print 한 줄로 흘러간다.**
  서버가 재시작되면 그 줄이 사라져 원인을 못 찾는다.

무엇을 하나
  실사용 로그(2026-08-07)의 발화를 순서대로 넣고, 검색 단계에서 예외가 나면
  **역추적(traceback) 전체**를 찍는다.

비용: LLM 6~8회 (약 5원)
"""
import sys
import io
import asyncio
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.db import async_session                  # noqa: E402
from app.itda.itda_core import ItdaEngine              # noqa: E402

#  실제로 사용자가 친 순서 그대로
TURNS = [
    '사람에게 도움이 되는 일',
    '생각해본적없어',
    '왜 갑자기 그렇게 말해?',
    '몰라 근야 살고 있고',
    '막노동하기싫어',
    '글쎼 딱히 그런건 없었던 것 같기도 하고. 그냥 카페에서 커피 마시면서 있는건 좋아해',
]


async def main():
    e = ItdaEngine()

    #  ★ search() 를 감싸서 «예외를 삼키기 전에» 역추적을 찍는다
    _orig = e.search

    async def _spy(*a, **kw):
        try:
            return await _orig(*a, **kw)
        except Exception:
            print('\n' + '!' * 78)
            print('■ search() 안에서 예외 — 역추적 전체')
            print('!' * 78)
            traceback.print_exc()
            print('!' * 78 + '\n')
            raise
    e.search = _spy

    profile = {}
    async with async_session() as db:
        for i, msg in enumerate(TURNS, 1):
            print(f'\n{"=" * 78}\n[{i}턴] 🧑 {msg}')
            try:
                r = await e.step(db, profile, msg)
            except Exception:
                print('■ step() 밖으로 튀어나온 예외:')
                traceback.print_exc()
                break
            profile = r.get('profile') or profile
            rep = (r.get('reply') or '').replace('\n', ' ')[:110]
            print(f'       🤖 [{r.get("kind")}] {rep}')
            slots = {k: v for k, v in profile.items()
                     if not k.startswith('_') and v}
            print(f'       슬롯 {slots}')

    print(f'\n총 LLM {e.total_usage.get("calls")}회')

asyncio.run(main())
