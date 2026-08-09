# -*- coding: utf-8 -*-
"""job_attr 을 «레포 안 파일»로 내보내고, 거기서 되돌린다 — LLM 0회 · 0원.

왜 이게 필요한가 (2026-08-07 사고)
  태깅은 2026-08-06 에 **로컬 DB** 에서 했고, 공용 RDS 에는 애초에 없었다.
  그래서 서버가 RDS 를 보는 순간 `job_attr` 이 없어 **카드 턴이 전부 죽었다**
  (1146 Table doesn't exist). 그리고 태깅 스크립트도 안 남아 있어서
  복구에 LLM 121회가 들었다.

  ⇒ 태그는 **DB 에만 두면 안 된다.** 값이 1,094줄뿐이고 거의 안 바뀌므로
    레포에 TSV 로 넣어 두면 «어느 DB 에서든 몇 초 만에» 되돌릴 수 있다.

쓰는 법
  python dump_job_attr.py            DB → data/job_attr.tsv  (내보내기)
  python dump_job_attr.py --load     data/job_attr.tsv → DB  (되돌리기 · LLM 0회)

⚠ 되돌리기는 UPSERT 라 기존 행을 덮어쓴다. 지우지는 않는다.
"""
import sys
import io
import os
import csv
import asyncio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from sqlalchemy import text                          # noqa: E402
from app.itda.db import async_session                # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'job_attr.tsv')
LOAD = '--load' in sys.argv
COLS = ('job_code', 'act_type', 'obj_type', 'obj_detail')


async def dump(db):
    rows = (await db.execute(text(
        'SELECT job_code, act_type, obj_type, obj_detail FROM job_attr '
        'ORDER BY job_code'))).fetchall()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n')
        w.writerow(COLS)
        for r in rows:
            w.writerow(['' if x is None else x for x in r])
    print(f'  내보냄 {len(rows)}행 → {OUT}')
    n_d = sum(1 for r in rows if r[3])
    print(f'    act/obj {sum(1 for r in rows if r[1])}행 · obj_detail {n_d}행')


async def load(db):
    if not os.path.exists(OUT):
        print(f'  🔴 파일이 없습니다: {OUT}')
        return
    with io.open(OUT, encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    n = 0
    for r in rows:
        await db.execute(text(
            'INSERT INTO job_attr (job_code, act_type, obj_type, obj_detail) '
            'VALUES (:c, :a, :o, :d) ON DUPLICATE KEY UPDATE '
            'act_type=VALUES(act_type), obj_type=VALUES(obj_type), '
            'obj_detail=VALUES(obj_detail)'),
            {'c': r['job_code'], 'a': r['act_type'] or None,
             'o': r['obj_type'] or None, 'd': r['obj_detail'] or None})
        n += 1
    await db.commit()
    print(f'  되돌림 {n}행  (LLM 0회 · 0원)')


async def main():
    async with async_session() as db:
        have = {x[0] for x in (await db.execute(text('SHOW TABLES'))).fetchall()}
        if 'job_attr' not in have:
            print('  🔴 job_attr 테이블이 없습니다. 먼저 ensure_tables.py 를 돌리세요.')
            return
        await (load(db) if LOAD else dump(db))
        n = (await db.execute(text('SELECT COUNT(*) FROM job_attr'))).scalar()
        print(f'  현재 job_attr: {n}행')

asyncio.run(main())
