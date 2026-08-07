# -*- coding: utf-8 -*-
"""ORM 모델이 «아닌» 테이블을 만든다 — 없으면 만들고, 있으면 그대로 둔다.

왜 필요한가 (2026-08-07 사고)
  `job_attr` 과 `itda_session` 은 SQLAlchemy 모델이 아니라 스크립트가 만든 테이블이다.
  그래서 main.py 의 「데이터베이스 초기화」(create_all)가 **이 둘을 안 만든다.**
  DB 를 다시 세우면 조용히 사라지고, 그 사실을 아무도 모른다.

  실제로 그렇게 됐다 —
    job_attr 없음      → 카드 턴이 «전부» 죽었다
                          「지금 추천을 불러오는 데 문제가 있었어요」
                          (job_catalog LEFT JOIN job_attr 에서 1146 Table doesn't exist)
    itda_session 없음  → .env 는 ITDA_SESSION_DB=1 인데 테이블이 없어
                          매번 메모리 전용으로 폴백. 재시작하면 대화가 사라진다.

⚠ 이 스크립트는 **테이블만 만든다. 데이터는 안 채운다.**
  job_attr 의 태그(act_type·obj_type·obj_detail)는 LLM 으로 붙인 것이라
  다시 채우려면 별도 작업이 필요하다. 빈 테이블이어도 LEFT JOIN 이 NULL 을 돌려주므로
  **카드는 정상으로 나간다** — 태그 가중(ATTR_LIFT)만 0 이 될 뿐이다.

쓰는 법:  python -m app.itda.scripts.ensure_tables
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

#  태그 값의 «정본». DB 가 아니라 여기다 — 어느 DB 로 옮겨도 따라간다.
TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'data', 'job_attr.tsv')

DDL = {
    #  검색이 LEFT JOIN 하는 표. 열 이름은 itda_core.search 의 질의와 맞춰야 한다.
    'job_attr': """
        CREATE TABLE IF NOT EXISTS job_attr (
          job_code    VARCHAR(20)  NOT NULL PRIMARY KEY,
          act_type    VARCHAR(30)  NULL,
          obj_type    VARCHAR(30)  NULL,
          obj_detail  VARCHAR(20)  NULL,
          INDEX idx_job_attr_act (act_type),
          INDEX idx_job_attr_obj (obj_type)
        ) DEFAULT CHARSET=utf8mb4
    """,
    #  session.py 도크스트링의 DDL 과 «같은 내용»이다. 한 곳에서만 고치도록 여기로 모은다.
    'itda_session': """
        CREATE TABLE IF NOT EXISTS itda_session (
          session_id  VARCHAR(64) NOT NULL PRIMARY KEY,
          user_id     BIGINT      NULL,
          state_json  JSON        NOT NULL,
          updated_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
          INDEX idx_itda_session_updated (updated_at)
        ) DEFAULT CHARSET=utf8mb4
    """,
}


async def main():
    async with async_session() as db:
        have = {r[0] for r in (await db.execute(text('SHOW TABLES'))).fetchall()}
        for name, ddl in DDL.items():
            if name in have:
                n = (await db.execute(
                    text(f'SELECT COUNT(*) FROM `{name}`'))).scalar()
                print(f'  ✅ {name:<14} 이미 있음 · {n}행')
                continue
            await db.execute(text(ddl))
            await db.commit()
            print(f'  🆕 {name:<14} 만들었습니다 (0행)')

        #  ★★ job_attr 이 «비어 있으면» 레포의 TSV 에서 되돌린다 — LLM 0회 · 0원.
        #    2026-08-07 사고: 태그가 로컬 DB 에만 있어서 RDS 로 옮기자 카드가 전부 죽었고,
        #    태깅 스크립트도 안 남아 있어 복구에 LLM 121회가 들었다.
        #    이제 값이 레포에 있으므로 «어느 DB 에서든» 몇 초면 돌아온다.
        n_attr = (await db.execute(text('SELECT COUNT(*) FROM job_attr'))).scalar()
        if not n_attr and os.path.exists(TSV):
            with io.open(TSV, encoding='utf-8', newline='') as f:
                rows = list(csv.DictReader(f, delimiter='\t'))
            for r in rows:
                await db.execute(text(
                    'INSERT INTO job_attr (job_code, act_type, obj_type, obj_detail) '
                    'VALUES (:c, :a, :o, :d) ON DUPLICATE KEY UPDATE '
                    'act_type=VALUES(act_type), obj_type=VALUES(obj_type), '
                    'obj_detail=VALUES(obj_detail)'),
                    {'c': r['job_code'], 'a': r['act_type'] or None,
                     'o': r['obj_type'] or None, 'd': r['obj_detail'] or None})
            await db.commit()
            print(f'  ♻ job_attr       비어 있어 TSV 에서 되돌림 {len(rows)}행 (LLM 0회)')
        elif not n_attr:
            print(f'  ⚠ job_attr 이 비었고 TSV 도 없습니다 → {TSV}')

        #  결과 확인
        print()
        for name in DDL:
            n = (await db.execute(
                text(f'SELECT COUNT(*) FROM `{name}`'))).scalar()
            print(f'     {name:<14} {n}행')
        n_job = (await db.execute(
            text('SELECT COUNT(*) FROM job_catalog'))).scalar()
        print(f'     {"job_catalog":<14} {n_job}행   ← 태그가 붙어야 할 대상')

asyncio.run(main())
