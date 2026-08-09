"""job_attr.obj_detail 재태깅 (2026-08-09).

왜 — 실측으로 **1,094개 중 992개(91%)가 비어 있고, 「어르신」이 단 1개**다.
  ```
  obj_detail   None 992 · 고객·손님 64 · 직원·동료 13 · 환자·장애인 11
               학습자 7 · 아동·청소년 6 · 어르신 1
  ```
  가족돌봄청년 서비스에서 「어르신」은 대상세부로 가장 흔하게 들어오는 값인데,
  그걸로 순위를 당길 직업이 하나뿐이다. **ATTR_LIFT 가 사실상 작동하지 않는 축이다.**

⚠ 이 스크립트는 **읽기만 하고 --write 없이는 DB를 안 고친다.** 먼저 그냥 돌려 보고
  결과 JSON 을 눈으로 확인한 다음 --write 를 붙여라.

비용 (돌리기 전에 읽을 것)
  · 대상 992개 · 한 번에 20개씩 → **약 50회 호출**
  · 호출당 입력 ~1,500 · 출력 ~400 토큰
  · gemini-3.1-flash-lite $0.25/1M(입력) · $1.50/1M(출력)
    50 × (1500×0.25 + 400×1.50) / 1e6 = **$0.049 ≈ 68원**
  · 소요 ~5분
  ⚠ 이 값은 «계산»이다. 실제 청구는 --write 없이 3배치(60개)만 돌려서 확인하라
    (--limit 60). 그게 실측이다.

쓰는 법
  python -m app.itda.scripts.retag_obj_detail                # 미리보기 (DB 안 건드림)
  python -m app.itda.scripts.retag_obj_detail --limit 60     # 3배치만 (비용 실측용)
  python -m app.itda.scripts.retag_obj_detail --write        # 실제 반영
"""
import sys, os, json, asyncio, argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from sqlalchemy import text                                   # noqa: E402
from app.itda import itda_core as C                           # noqa: E402
from app.itda.db import async_session                         # noqa: E402

#  ⚠ 이 목록은 job_attr.obj_detail 의 기존 값에서 뽑은 것이다. 새로 지어내지 않는다.
#    (기존 분포: 고객·손님 · 직원·동료 · 환자·장애인 · 학습자 · 아동·청소년 · 어르신)
DETAIL = ['어르신', '아동·청소년', '환자·장애인', '학습자', '고객·손님', '직원·동료', '해당없음']

SCHEMA = {'type': 'ARRAY', 'items': {'type': 'OBJECT', 'properties': {
    'job_code': {'type': 'STRING'},
    'obj_detail': {'type': 'STRING', 'enum': DETAIL},
    '근거': {'type': 'STRING', 'description': '직업 설명에서 그대로 인용'}},
    'required': ['job_code', 'obj_detail', '근거']}}

PROMPT = (
    '아래 직업들이 «주로 어떤 사람»을 상대하는지 하나씩 고르라.\n\n'
    '· 사람을 직접 상대하지 않는 일(기계·서류·데이터가 대상)은 「해당없음」이다.\n'
    '· 여럿에 걸치면 **가장 자주 마주하는 쪽** 하나만 고른다.\n'
    '· 근거는 직업 설명에 실제로 있는 말을 그대로 인용하라. 없으면 「해당없음」이다.\n'
    '  ⚠ 짐작해서 채우지 마라. 비어 있는 편이 틀린 것보다 낫다.\n\n'
    '[보기]\n'
    '  어르신     노인 요양·돌봄·복지\n'
    '  아동·청소년 보육·아동복지·청소년지도\n'
    '  환자·장애인 의료·간호·재활·장애인복지\n'
    '  학습자     교육·훈련·강의\n'
    '  고객·손님   판매·서비스·상담 응대\n'
    '  직원·동료   인사·노무·조직 관리\n'
    '  해당없음    사람이 주 대상이 아니다\n\n'
    '[직업 목록]\n{jobs}')


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='DB 에 실제로 쓴다')
    ap.add_argument('--limit', type=int, default=0, help='앞에서 N개만 (비용 실측용)')
    ap.add_argument('--batch', type=int, default=20)
    a = ap.parse_args()

    eng = C.ItdaEngine()
    async with async_session() as db:
        rows = (await db.execute(text(
            "SELECT jc.job_code, jc.job_name, LEFT(COALESCE(jc.job_description,''), 200) d "
            "FROM job_catalog jc LEFT JOIN job_attr ja ON ja.job_code = jc.job_code "
            "WHERE ja.obj_detail IS NULL OR ja.obj_detail = '' "
            "ORDER BY jc.job_code"))).fetchall()
        if a.limit:
            rows = rows[:a.limit]
        print(f'■ 대상 {len(rows)}개 · 배치 {a.batch} → 호출 {(len(rows)+a.batch-1)//a.batch}회')
        if not a.write:
            print('■ 미리보기 모드 — DB 를 고치지 않는다 (--write 로 반영)')

        out, calls = [], 0
        for i in range(0, len(rows), a.batch):
            chunk = rows[i:i + a.batch]
            jobs = '\n'.join(f'{c[0]} | {c[1]} | {(c[2] or "")[:120]}' for c in chunk)
            try:
                j = await eng.gemini(PROMPT.format(jobs=jobs), SCHEMA, 0.0, think='minimal')
            except Exception as e:                              # noqa: BLE001
                print(f'  🔴 배치 {i//a.batch+1} 실패(건너뜀): {type(e).__name__}: {e}')
                continue
            calls += 1
            got = [x for x in (j or []) if isinstance(x, dict)]
            out.extend(got)
            print(f'  배치 {i//a.batch+1}: {len(got)}개  '
                  f'(해당없음 {sum(1 for x in got if x.get("obj_detail")=="해당없음")})')

        #  분포를 먼저 보여준다 — 눈으로 확인하고 나서 쓰라는 뜻이다.
        dist = {}
        for x in out:
            dist[x.get('obj_detail')] = dist.get(x.get('obj_detail'), 0) + 1
        print('\n■ 새 분포')
        for k, v in sorted(dist.items(), key=lambda t: -t[1]):
            print(f'   {str(k):12} {v:5}')

        p = os.path.join(os.path.dirname(__file__), 'checks', '_retag_obj_detail.json')
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f'\n■ 결과 저장 {p}  (호출 {calls}회)')

        if not a.write:
            print('■ DB 는 그대로다. 확인 후 --write 로 다시 돌려라.')
            return

        #  ⚠ 「해당없음」은 NULL 로 되돌린다 — 없는 것을 있는 것처럼 채우지 않는다.
        n = 0
        for x in out:
            v = x.get('obj_detail')
            if v == '해당없음':
                continue
            await db.execute(text(
                "UPDATE job_attr SET obj_detail = :v WHERE job_code = :c"),
                {'v': v, 'c': x.get('job_code')})
            n += 1
        await db.commit()
        print(f'■ DB 반영 {n}개 (해당없음은 건드리지 않음)')


if __name__ == '__main__':
    asyncio.run(main())
