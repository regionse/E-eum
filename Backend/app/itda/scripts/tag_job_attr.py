# -*- coding: utf-8 -*-
"""job_attr 을 채운다 — 활동유형(act_type) · 다루는대상(obj_type).

왜 이 스크립트가 «새로» 필요했나 (2026-08-07)
  원래 태깅은 2026-08-06 에 했는데(1,064개), 그때 쓴 스크립트를 레포에 안 남겼다.
  그리고 공용 RDS 에서 `job_attr` 테이블이 통째로 사라지면서 데이터도 함께 없어졌다.
    → 카드 턴이 «전부» 죽었다 (LEFT JOIN 대상이 없어 1146 에러)
  ⇒ 다시는 이런 일이 없도록 **스크립트를 레포에 남긴다.**

무엇이 정본인가
  분류 값은 **prompts.py 의 SYSTEM 슬롯 목록과 «글자까지» 같아야 한다.**
  사용자 슬롯(활동유형=만들기)과 직업 태그(act_type=만들기)를 코드가 그대로 비교하기
  때문이다(ATTR_LIFT). 한쪽만 고치면 가중이 통째로 죽는데 «에러가 안 난다».

⚠ 정의를 반드시 함께 준다 — prompts.py 에 기록된 실측:
    「이름만 준 1차: 빵 → 자연·생물(오답).  정의를 준 2차: 빵 → 창작물(정답)」
  enum 이름만으로는 모델이 우리 뜻을 모른다.

쓰는 법
  python tag_job_attr.py --dry     판정만 하고 저장 안 함(앞 3배치)
  python tag_job_attr.py           전체 실행
  python tag_job_attr.py --redo    이미 채워진 것도 다시
"""
import sys
import io
import asyncio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from sqlalchemy import text                          # noqa: E402
from app.itda.db import async_session                # noqa: E402
from app.itda.itda_core import ItdaEngine            # noqa: E402

BATCH = 10
DRY = '--dry' in sys.argv
REDO = '--redo' in sys.argv

#  ── 분류 체계 (prompts.py SYSTEM 과 «글자까지» 같아야 한다) ────────────
ACT = ['만들기', '고치기·정비', '운전·조작', '돕기·돌봄', '가르치기',
       '분석·연구', '관리·운영', '표현·창작', '판매·설득']
OBJ = ['사람', '기계·설비', '컴퓨터·데이터', '자연·생물', '창작물', '숫자·문서']

PROMPT = """너는 직업 분류기다. 아래 직업들을 두 축으로 분류한다. 설명하지 말고 분류만 해라.

【활동유형】 그 직업이 «주로 하는 행위»
  만들기      물건·음식·작품을 손이나 기계로 만들어 낸다 (제빵·용접·목공·조립)
  고치기·정비  고장난 것을 고치거나 상태를 유지한다 (자동차정비·설비보수·시계수리)
  운전·조작    탈것이나 기계를 몰거나 다룬다 (버스운전·지게차·크레인·중장비)
  돕기·돌봄    사람의 생활·건강·안전을 직접 거든다 (요양보호·간호조무·보육·경호)
  가르치기     지식이나 기술을 다른 사람에게 전한다 (강사·교사·훈련지도)
  분석·연구    조사하고 재고 따져서 결론을 낸다 (연구원·검사·품질분석·회계감사)
  관리·운영    사람·일정·자원을 굴러가게 한다 (매장관리·인사·총무·시설운영)
  표현·창작    디자인·글·영상·공연으로 표현한다 (디자이너·작가·영상편집·연주)
  판매·설득    사고팔거나 상대를 움직인다 (영업·판매·상담판매·중개)

【다루는대상】 그 일의 «주 재료»
  사람          상대가 사람이다. 그 사람의 상태·요구가 일의 대상이다
  기계·설비     장비·차량·설비가 대상이다
  컴퓨터·데이터  소프트웨어·시스템·데이터가 대상이다
  자연·생물     식물·동물·농수산·환경이 대상이다
  창작물        음식·의류·공예품·콘텐츠 등 «만들어 낸 결과물»이 대상이다
                ⚠ 빵·요리·옷·가구는 «자연·생물»이 아니라 여기다
  숫자·문서     장부·서류·계약·통계가 대상이다

★ 각 직업마다 «하나씩»만 고른다. 애매하면 «가장 많은 시간을 쓰는 쪽»으로.
★ 목록에 없는 값을 지어내지 마라.

직업 목록:
{items}"""

SCHEMA = {
    'type': 'OBJECT',
    'properties': {'결과': {'type': 'ARRAY', 'items': {
        'type': 'OBJECT',
        'properties': {
            '직업명': {'type': 'STRING'},
            '활동유형': {'type': 'STRING', 'enum': ACT},
            '다루는대상': {'type': 'STRING', 'enum': OBJ},
        },
        'required': ['직업명', '활동유형', '다루는대상'],
        'propertyOrdering': ['직업명', '활동유형', '다루는대상'],
    }}},
    'required': ['결과'],
}


async def main():
    eng = ItdaEngine()
    async with async_session() as db:
        #  대상 고르기 — 이미 채워진 건 건너뛴다(--redo 면 전부)
        where = '' if REDO else \
            'WHERE ja.job_code IS NULL OR ja.act_type IS NULL'
        rows = (await db.execute(text(
            "SELECT jc.job_code, jc.job_name, jc.job_lcls_name, jc.job_mcls_name "
            "FROM job_catalog jc LEFT JOIN job_attr ja ON ja.job_code = jc.job_code "
            f"{where} ORDER BY jc.job_code"))).fetchall()

        n_call = -(-len(rows) // BATCH)
        print(f'대상 {len(rows)}개 · 배치 {BATCH}개씩 → LLM {n_call}콜')
        print(f'{"[DRY] 저장 안 함 · 앞 3배치만" if DRY else "저장한다"}\n')
        if DRY:
            rows = rows[:BATCH * 3]

        ok = 0
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            items = '\n'.join(
                f'- {r[1]} (분류: {r[2]} / {r[3]})' for r in chunk)
            try:
                r = await eng.gemini(PROMPT.format(items=items), SCHEMA, 0.0)
            except Exception as e:                               # noqa: BLE001
                print(f'  !! 배치 {i // BATCH + 1} 실패: {type(e).__name__}: {str(e)[:70]}')
                continue
            by_name = {x.get('직업명'): x for x in (r or {}).get('결과', [])}

            for code, name, _l, _m in chunk:
                got = by_name.get(name)
                if not got:
                    print(f'     ? {name} — 판정 없음')
                    continue
                a, o = got.get('활동유형'), got.get('다루는대상')
                if a not in ACT or o not in OBJ:
                    print(f'     ? {name} — 목록 밖 값 ({a}/{o})')
                    continue
                if DRY:
                    print(f'     {name:<22} {a:<10} {o}')
                    continue
                await db.execute(text(
                    "INSERT INTO job_attr (job_code, act_type, obj_type) "
                    "VALUES (:c, :a, :o) "
                    "ON DUPLICATE KEY UPDATE act_type=VALUES(act_type), "
                    "obj_type=VALUES(obj_type)"), {'c': code, 'a': a, 'o': o})
                ok += 1
            if not DRY:
                await db.commit()
            print(f'  배치 {i // BATCH + 1:>3}/{n_call}: 누적 {ok}개')

        if not DRY:
            n = (await db.execute(text(
                'SELECT COUNT(*) FROM job_attr WHERE act_type IS NOT NULL'))).scalar()
            print(f'\n  job_attr 채워진 행: {n}')
            dist = (await db.execute(text(
                'SELECT act_type, COUNT(*) FROM job_attr GROUP BY act_type '
                'ORDER BY 2 DESC'))).fetchall()
            print('  활동유형 분포:', ' · '.join(f'{a}={c}' for a, c in dist))

    u = eng.total_usage
    print(f'\n  LLM {u.get("calls", 0)}회 · 입력 {u.get("in", 0):,} · 출력 {u.get("out", 0):,}')

asyncio.run(main())
