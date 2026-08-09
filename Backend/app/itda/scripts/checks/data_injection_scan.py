# -*- coding: utf-8 -*-
"""DB 데이터에 «지시문»이 섞여 있나 — 읽기만 한다. LLM 0회 · 0원.

왜 필요한가
  프롬프트에 들어가는 건 사용자 발화만이 아니다:
      사용자 발화        ← 낱말표·근거대조가 검사한다
      슬롯 값           ← 근거대조가 검사한다
      🔴 직업 설명 220자  ← 검사 «안 한다»
      🔴 강좌 제목·설명    ← 검사 «안 한다»
  뒤의 둘은 K-MOOC·NCS 에서 «받아온» 글이다. 그 글을 쓴 사람은 우리가 아니다.
  거기 지시문이 있으면 우리가 «검사 없이» LLM 에게 전달한다.
  우리 인젝션 게이트는 «사용자 발화»만 본다 — 구조적으로 못 막는다.
"""
import sys
import io
import re
import asyncio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from sqlalchemy import text                          # noqa: E402
from app.itda.db import async_session                # noqa: E402
from app.itda.itda_core import is_injection          # noqa: E402

#  지시문처럼 보이는 신호. 넓게 잡고 «사람이» 본다 — 자동 차단이 아니다.
SUS = [
    ('명령형 지시', r'(하시오|하라|해라|출력하|무시하|잊어|따르라|응답하라)'),
    ('역할 부여', r'(너는|당신은|You are|assistant|system\s*:|AI는)'),
    ('프롬프트 언급', r'(프롬프트|prompt|시스템\s*지시|instruction)'),
    ('코드 블록', r'(```|<script|</|\{\{|\}\})'),
    ('영문 명령', r'\b(ignore|disregard|override|bypass|reveal|print)\b'),
]

TABLES = [
    ('강좌', 'course', ['title', 'description', 'course_name', 'summary']),
    ('직업', 'job_catalog', ['job_name', 'job_description']),
    ('자격증', 'certification', ['cert_name', 'entry_note']),
]


async def main():
    total = flagged = 0
    async with async_session() as db:
        for label, tbl, want in TABLES:
            cols = [r[0] for r in (await db.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=DATABASE() AND table_name=:t "
                "AND data_type IN ('varchar','text','longtext')"), {'t': tbl})).fetchall()]
            use = [c for c in cols if c in want] or [c for c in cols][:2]
            if not use:
                continue
            sel = ', '.join(f'`{c}`' for c in use)
            rows = (await db.execute(text(
                f'SELECT {sel} FROM `{tbl}`'))).fetchall()
            print(f'\n{"=" * 84}\n■ {label} ({tbl}) — {len(rows)}행 · 열 {use}\n{"=" * 84}')
            hit = 0
            for r in rows:
                for c, v in zip(use, r):
                    if not v:
                        continue
                    s = str(v)
                    total += 1
                    why = [n for n, p in SUS if re.search(p, s, re.I)]
                    inj = is_injection(s)
                    if why or inj:
                        hit += 1
                        flagged += 1
                        tag = '🔴 인젝션게이트도 걸림' if inj else '⚠'
                        print(f'  {tag} [{c}] {" · ".join(why)}')
                        print(f'      「{s[:110]}」')
                        if hit >= 12:
                            break
                if hit >= 12:
                    print('      … (12건까지만 표시)')
                    break
            if not hit:
                print('  ✅ 의심 문자열 없음')

    print(f'\n{"=" * 84}')
    print(f'  검사한 문자열 {total:,}개 · 의심 {flagged}건')
    print(f'  ⚠ 이건 «자동 차단»이 아니다. 사람이 보고 판단하라는 목록이다.')
    print('=' * 84)

asyncio.run(main())
