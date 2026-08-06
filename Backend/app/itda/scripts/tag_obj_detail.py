# -*- coding: utf-8 -*-
"""job_attr 에 `obj_detail`(누구를 대하는가) 축을 붙인다 — obj_type='사람' 인 109개만.

왜 필요한가 (2026-08-06 실측)
  속성 축으로 질문을 «생성»할 수 있는지 재 봤더니(checks/axis_split.py)
  18케이스 중 6건이 act_type·obj_type 으로 전혀 안 갈렸다. 그 6건을 뜯어보니 둘로 나뉜다.

    부류 A (4건) — 물을 필요가 없다. 이미 한 동네다.
        「빵 만드는 일」 TOP%=0.996  [제빵·제과·떡제조·한과제조]
        「손으로 만드는 일」 TOP%=0.910 [목공예·가구제작·섬유공예·금속공예]
      ⇒ 2단 판정(TOP%≥0.90 → 세부 칩)이 이미 처리한다. 새 축이 필요 없다.

    부류 B (2건) — **진짜로 못 가른다.** 그리고 하필 우리 사용자군의 핵심이다.
        「어르신 요양 돌보는 일」 [요양지원·아이돌봄·병원안내·산후육아지원]
        「할머니 돌보는 일을 해왔어요」 [아이돌봄·산후육아지원·가사지원·요양지원]
      후보가 전부 `돕기·돌봄 + 사람` 이라 우리 축으로는 동일하다.
      **「어르신 돌봄」과 「아이 돌봄」이 구별이 안 된다.**
      NCS 중분류로는 갈리지만(보건/보육/청소) 그건 사용자가 답할 수 없는 말이다 —
      「사회복지 / 경비·청소 / 보건 중 어디요?」라고 물을 수는 없다.

  ⇒ 축 하나만 더 있으면 풀린다: **누구를 대하는가.**
    그리고 이 질문은 `_ASK_Q2` 에 이미 있다 —
      「사람을 상대한다면 어떤 분들이 그나마 편하세요? 어르신, 아이, 또래 중에요.」
    **질문은 있는데 답을 담을 축이 없어서** 슬롯에도 검색에도 안 쓰이고 있었다.

어휘 (6종, 단일값 — act_type·obj_type 과 일관되게)
  어르신 / 아동·청소년 / 환자·장애인 / 고객·손님 / 학습자 / 직원·동료

  ⚠ 겹치는 경우의 우선순위 — 「요양지원」은 어르신이자 환자다.
    **「어르신」을 우선한다.** 사용자는 「어르신 돌보는 일」로 찾지
    「환자 돌보는 일」로는 잘 안 찾고, 우리 사용자군의 실제 경험이 그쪽이다.

⚠ obj_type='사람' 이 아닌 직업은 건드리지 않는다(NULL 로 둔다). 985개는 이 축이 무의미하다.

쓰는 법:  python app/itda/scripts/tag_obj_detail.py [--dry]
"""
import asyncio
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from sqlalchemy import text                          # noqa: E402

from app.itda.db import async_session                # noqa: E402
from app.itda.itda_core import ItdaEngine            # noqa: E402

DRY = '--dry' in sys.argv
BATCH = 10

VALUES = ['어르신', '아동·청소년', '환자·장애인', '고객·손님', '학습자', '직원·동료']

SCHEMA = {'type': 'OBJECT',
          'properties': {'결과': {'type': 'ARRAY', 'items': {
              'type': 'OBJECT',
              'properties': {'직업명': {'type': 'STRING'},
                             '대상': {'type': 'STRING', 'enum': VALUES}},
              'required': ['직업명', '대상']}}},
          'required': ['결과']}

PROMPT = """아래 직업들이 **누구를 주로 대하는 일인지** 하나씩 고른다.

고를 수 있는 값 (이 여섯 개 중 하나만):
  어르신        노인 요양·돌봄이 주 대상
  아동·청소년   영유아·아동·청소년이 주 대상
  환자·장애인   의료·재활·장애 지원이 주 대상
  고객·손님     물건이나 서비스를 사는 사람이 주 대상 (판매·접객·여행·미용 등)
  학습자        배우는 사람이 주 대상 (교육·훈련·지도)
  직원·동료     조직 내부 구성원이 주 대상 (인사·노무·사내교육)

★ 겹칠 때의 우선순위 — **어르신 > 아동·청소년 > 환자·장애인 > 학습자 > 직원·동료 > 고객·손님**
  예) 「요양지원」은 어르신이자 환자지만 → **어르신**
      「보육」은 아동이자 학습자지만 → **아동·청소년**
  ⚠ 대상이 특정되지 않는 일반 서비스업은 「고객·손님」이다.

직업 목록:
{items}"""


async def main():
    eng = ItdaEngine()
    async with async_session() as db:
        #  ── 칼럼이 없으면 만든다 (기존 칼럼은 안 건드린다) ──
        cols = [r[0] for r in (await db.execute(text('SHOW COLUMNS FROM job_attr'))).fetchall()]
        if 'obj_detail' not in cols:
            if DRY:
                print('[dry] ALTER TABLE job_attr ADD obj_detail VARCHAR(20) NULL')
            else:
                await db.execute(text(
                    'ALTER TABLE job_attr ADD COLUMN obj_detail VARCHAR(20) NULL'))
                await db.commit()
                print('✅ 칼럼 추가: job_attr.obj_detail')
        else:
            print('(obj_detail 칼럼 이미 있음)')

        rows = (await db.execute(text(
            "SELECT jc.job_code, jc.job_name, jc.job_lcls_name, ja.act_type, "
            "       LEFT(COALESCE(jc.job_description,''), 120) "
            "FROM job_attr ja JOIN job_catalog jc ON jc.job_code = ja.job_code "
            "WHERE ja.obj_type = '사람' ORDER BY jc.job_code"))).fetchall()
        print(f'대상: {len(rows)}개  ·  배치 {BATCH}개씩 → LLM {-(-len(rows)//BATCH)}콜\n')

        got, fail = {}, []
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            items = '\n'.join(
                f'- {nm}  [{lcls} / {act}]  {(desc or "").strip()[:110]}'
                for _, nm, lcls, act, desc in chunk)
            try:
                r = await eng.gemini(PROMPT.format(items=items), SCHEMA, 0.0)
            except Exception as e:                        # noqa: BLE001
                print(f'  !! 배치 {i//BATCH+1} 실패: {type(e).__name__}: {str(e)[:60]}')
                fail += [nm for _, nm, *_ in chunk]
                continue
            by_name = {x['직업명']: x['대상'] for x in (r or {}).get('결과', [])}
            for code, nm, *_ in chunk:
                v = by_name.get(nm)
                if v in VALUES:
                    got[code] = v
                else:
                    fail.append(nm)
            print(f'  배치 {i//BATCH+1:>2}: {len(by_name)}개 판정')

        print(f'\n판정 {len(got)} / {len(rows)}' + (f'  · 실패 {len(fail)}: {fail[:6]}' if fail else ''))

        #  분포
        dist = {}
        for v in got.values():
            dist[v] = dist.get(v, 0) + 1
        print('\n분포')
        for k, v in sorted(dist.items(), key=lambda x: -x[1]):
            print(f'  {k:<12} {v:>3}')

        #  ★ 눈으로 확인해야 하는 것 — 돌봄 계열이 제대로 갈렸나
        CHECK = ('요양지원', '아이돌봄', '보육', '산후육아지원', '가사지원',
                 '일상생활기능지원', '병원안내', '청소년상담복지', '심리상담',
                 '골프캐디', '항공객실서비스', '경호')
        print('\n★ 눈으로 확인 (돌봄 계열 + 경계 케이스)')
        for code, nm, lcls, act, _ in rows:
            if nm in CHECK:
                print(f'  {nm:<16} → {got.get(code, "(실패)")}')

        if DRY:
            print('\n[dry] 저장 안 함')
            return
        for code, v in got.items():
            await db.execute(text('UPDATE job_attr SET obj_detail = :v WHERE job_code = :c'),
                             {'v': v, 'c': code})
        await db.commit()
        print(f'\n✅ 저장 완료 {len(got)}건')
        u = eng.total_usage
        print(f'LLM {u.get("calls", 0)}회 · 입력 {u.get("in", 0):,} · 출력 {u.get("out", 0):,}')


asyncio.run(main())
