# -*- coding: utf-8 -*-
"""AWS RDS 상태 점검 — 「넣었는데 앱에 안 나온다」를 진단한다.

    python -m tools.db_status              전체 테이블 현황
    python -m tools.db_status 표이름 …      그 테이블의 최근 5행까지

왜 필요한가 — RDS 에 직접 INSERT 했는데 화면에 안 나오는 경우, 원인은 보통 셋이다.
  ① 앱이 보는 DB 와 다른 곳에 넣었다            → 아래 「앱이 보는 DB」로 확인
  ② 넣긴 넣었는데 **조회 조건에 걸러진다**       → 최근 행의 값(날짜·소속 id·상태)을 눈으로 본다
     실제 사례(2026-08-05): care_group_letters 는 편지 목록엔 조건이 없지만
     주간분석은 `created_at >= 이번주시작 AND < 이번주끝` 으로 거른다.
     과거 날짜로 넣으면 목록엔 보이는데 주간분석에선 통째로 안 보인다.
  ③ 벡터 검색이 옛 문장을 본다                  → MySQL 을 고쳐도 Pinecone 은 안 바뀐다.
     검색 결과가 안 변하면 재임베딩이 필요하다(app.itda.scripts.embed_*).

※ 읽기 전용이다. 아무것도 쓰지 않는다.
"""
import asyncio
import sys

sys.path.insert(0, __file__.rsplit('tools', 1)[0])

from app.database import SessionLocal          # noqa: E402
from sqlalchemy import text                    # noqa: E402

#  각 축의 핵심 테이블 — 「최신화가 됐나」를 볼 때 제일 먼저 보는 것들
AXES = {
    '잇다(진로)': ['certification', 'exam_schedule', 'cert_job', 'job_catalog',
                'course', 'itda_map', 'itda_sync_log'],
    '나누다(돌봄)': ['care_groups', 'care_group_letters', 'weekly_analysis_letters',
                 'invite_codes'],
    '덜다(정책)': ['policy', 'policies'],
    '공통': ['user', 'notice', 'inquiry'],
}


async def overview(db):
    dbname = (await db.execute(text('SELECT DATABASE()'))).scalar()
    print(f'\n  앱이 보는 DB : {dbname}')
    print(f'  서버 시각     : {(await db.execute(text("SELECT NOW()"))).scalar()}')

    have = {r[0] for r in (await db.execute(text(
        'SELECT table_name FROM information_schema.tables '
        'WHERE table_schema = DATABASE()'))).fetchall()}

    for axis, tables in AXES.items():
        shown = [t for t in tables if t in have]
        if not shown:
            continue
        print(f'\n  ── {axis} ' + '─' * (46 - len(axis)))
        for t in shown:
            cnt = (await db.execute(text(f'SELECT COUNT(*) FROM `{t}`'))).scalar()
            #  시간 컬럼이 있으면 「가장 최근 행이 언제 들어왔나」를 같이 본다.
            #  이게 「최신화가 됐나」의 가장 직접적인 답이다.
            tcol = (await db.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = :t "
                "  AND data_type IN ('datetime','timestamp','date') "
                "ORDER BY FIELD(column_name,'updated_at','created_at') DESC, column_name "
                "LIMIT 1"), {'t': t})).scalar()
            last = ''
            if tcol and cnt:
                v = (await db.execute(text(f'SELECT MAX(`{tcol}`) FROM `{t}`'))).scalar()
                last = f'   최근 {tcol} = {v}'
            print(f'    {t:26} {cnt:>7,} 행{last}')

    extra = sorted(have - {t for ts in AXES.values() for t in ts})
    if extra:
        print(f'\n  ── 그 밖의 테이블 ({len(extra)}개) ' + '─' * 20)
        print('    ' + ' · '.join(extra))


async def detail(db, tables):
    for t in tables:
        print(f'\n  ══ {t} ' + '═' * (52 - len(t)))
        try:
            cols = [r[0] for r in (await db.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = :t "
                "ORDER BY ordinal_position"), {'t': t})).fetchall()]
            if not cols:
                print('    (그런 테이블이 없다)')
                continue
            pk = (await db.execute(text(
                "SELECT column_name FROM information_schema.key_column_usage "
                "WHERE table_schema = DATABASE() AND table_name = :t "
                "  AND constraint_name = 'PRIMARY' LIMIT 1"), {'t': t})).scalar() or cols[0]
            rows = (await db.execute(text(
                f'SELECT * FROM `{t}` ORDER BY `{pk}` DESC LIMIT 5'))).fetchall()
            print('    ' + ' | '.join(cols))
            for r in rows:
                #  긴 본문은 잘라서 한 줄로 — 여기서 보려는 건 내용이 아니라 **값의 모양**이다
                #  (날짜가 언제인지, 소속 id 가 맞는지, 상태 컬럼이 뭔지)
                print('    ' + ' | '.join(str(v)[:24].replace('\n', ' ') for v in r))
            if not rows:
                print('    (행이 없다 — INSERT 가 안 들어갔거나 다른 곳에 들어갔다)')
        except Exception as e:                                  # noqa: BLE001
            print(f'    조회 실패: {type(e).__name__}: {str(e)[:80]}')


async def main():
    async with SessionLocal() as db:
        if len(sys.argv) > 1:
            await detail(db, sys.argv[1:])
        else:
            await overview(db)
            print('\n  특정 테이블의 최근 행을 보려면:')
            print('    python -m tools.db_status care_group_letters')


if __name__ == '__main__':
    asyncio.run(main())
