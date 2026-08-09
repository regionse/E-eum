# -*- coding: utf-8 -*-
r"""job_attr 태깅이 «얼마나 믿을 만한가» — 재현성과 모델 간 일치도를 잰다. (2026-08-09)

왜 재나
  사용자 질문: 「태깅 이거 신뢰도가 어느 정도됨? 우리가 어디를 보고 한 게 아니잖아.
              그냥 제미나이한테 물어보고 답 가져온 거랑 뭐가 다름?」
  **맞는 지적이다.** tag_job_attr.py 는 직업 이름과 NCS 분류만 열 개씩 묶어
  Gemini 에 던지고, 아홉 개 낱말 중 하나를 고르게 해서 그 답을 그대로 저장한다.
  사람 검수도, 대조할 정답표도 없다. 그런데 **신뢰도를 «한 번도 안 쟀다».**

무엇을 재나 — 정답표가 없으므로 «일치도»로 대신한다
  ① 재현성(test-retest)  같은 모델·같은 프롬프트·온도 0 으로 다시 태깅 → 저장값과 비교
     낮으면 그 태그는 «그날의 운»이다. 정답 여부 이전의 문제다.
  ② 모델 간 일치도       다른 모델(Solar)로 같은 일 → Gemini 답과 비교
     낮으면 「모델의 상식」이 아니라 「그 모델의 버릇」을 저장한 것이다.

⚠ 이 검사가 «못» 말하는 것
  일치도가 높다고 «맞다»는 뜻이 아니다. 두 모델이 같이 틀릴 수 있다.
  일치도는 **신뢰도의 상한**일 뿐이다 — 재현조차 안 되면 정확할 수가 없다.

비용
  표본 80개 · 배치 10 → 모델당 8콜.
  Gemini 약 12원 · Solar 약 5원 (Pro3 $0.15/$0.60 기준). 합계 약 20원.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/tag_reliability.py --n 80
"""
import argparse
import asyncio
import collections
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from sqlalchemy import text                                     # noqa: E402
from app.itda.db import async_session                           # noqa: E402
from app.itda.itda_core import ItdaEngine                       # noqa: E402

HERE = Path(__file__).resolve().parent
ENV = HERE.parents[2] / '.env'
UP_URL = 'https://api.upstage.ai/v1/chat/completions'


def _pull(name):
    """tag_job_attr.py 를 «실행하지 않고» 리터럴만 꺼낸다 (그 파일은 import 하면 돈다)."""
    import ast
    src = (HERE.parent / 'tag_job_attr.py').read_text(encoding='utf-8')
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    raise SystemExit(f'{name} 을 못 찾았다')


PROMPT = _pull('PROMPT')
ACT = _pull('ACT')
OBJ = _pull('OBJ')
BATCH = 10

#  ⚠ SCHEMA 는 «못» 꺼낸다 — 그 리터럴 안에 ACT·OBJ 변수가 들어 있어서
#    ast.literal_eval 이 거부한다. 그래서 여기서 «같은 모양»으로 다시 짠다.
#    ⇒ tag_job_attr.py 의 SCHEMA 를 고치면 이쪽도 같이 고쳐야 한다.
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
    }}},
    'required': ['결과'],
}


def env():
    d = {}
    for ln in ENV.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if ln and not ln.startswith('#') and '=' in ln:
            k, v = ln.split('=', 1)
            d[k.strip()] = v.strip()
    return d


def solar_tag(key, items, model='solar-pro3'):
    """같은 프롬프트를 Solar 에. 스키마는 json_schema 로 «같은 급»을 준다."""
    sch = {'type': 'object', 'properties': {'결과': {'type': 'array', 'items': {
        'type': 'object',
        'properties': {'직업명': {'type': 'string'},
                       '활동유형': {'type': 'string', 'enum': ACT},
                       '다루는대상': {'type': 'string', 'enum': OBJ}},
        'required': ['직업명', '활동유형', '다루는대상']}}}, 'required': ['결과']}
    body = json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': PROMPT.format(items=items)}],
        'temperature': 0.0,
        'response_format': {'type': 'json_schema',
                            'json_schema': {'name': 'tags', 'strict': True, 'schema': sch}},
    }).encode()
    req = urllib.request.Request(UP_URL, data=body, headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    r = json.loads(urllib.request.urlopen(req, timeout=90).read())
    t = r['choices'][0]['message']['content'].strip()
    if t.startswith('```'):
        t = t.split('\n', 1)[1].rsplit('```', 1)[0]
    return json.loads(t)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=80)
    a = ap.parse_args()
    e = env()
    skey = e.get('SOLAR_KEY') or ''

    eng = ItdaEngine()
    async with async_session() as db:
        #  ⚠ 표본을 «고르게» 뽑는다 — job_code 순으로 등간격. 특정 분야에 몰리면
        #    그 분야의 난이도가 전체 수치로 둔갑한다.
        rows = (await db.execute(text(
            "SELECT jc.job_code, jc.job_name, jc.job_lcls_name, jc.job_mcls_name, "
            "       ja.act_type, ja.obj_type "
            "FROM job_catalog jc JOIN job_attr ja ON ja.job_code = jc.job_code "
            "WHERE ja.act_type IS NOT NULL ORDER BY jc.job_code"))).fetchall()
        step = max(1, len(rows) // a.n)
        sample = rows[::step][:a.n]

    print('=' * 92)
    print(f'  job_attr 태깅 신뢰도 — 표본 {len(sample)}개 (전체 {len(rows)}개에서 등간격)')
    print('  ⚠ 정답표가 없다. «일치도»는 신뢰도의 «상한»일 뿐 정확도가 아니다.')
    print('=' * 92)

    gem, sol = {}, {}
    for i in range(0, len(sample), BATCH):
        chunk = sample[i:i + BATCH]
        items = '\n'.join(f'- {r[1]} (분류: {r[2]} / {r[3]})' for r in chunk)
        try:
            r = await eng.gemini(PROMPT.format(items=items), SCHEMA, 0.0)
            for x in (r or {}).get('결과', []):
                gem[x.get('직업명')] = (x.get('활동유형'), x.get('다루는대상'))
        except Exception as ex:                                  # noqa: BLE001
            print(f'    Gemini 배치 {i // BATCH + 1} 실패: {type(ex).__name__}')
        if skey:
            try:
                r2 = solar_tag(skey, items)
                for x in (r2 or {}).get('결과', []):
                    sol[x.get('직업명')] = (x.get('활동유형'), x.get('다루는대상'))
            except Exception as ex:                              # noqa: BLE001
                print(f'    Solar 배치 {i // BATCH + 1} 실패: {type(ex).__name__}: {str(ex)[:60]}')
        print(f'    … {min(i + BATCH, len(sample))}/{len(sample)}')

    def score(pred, label):
        na = nb = n = 0
        diff = []
        for code, name, _l, _m, act, obj in sample:
            p = pred.get(name)
            if not p:
                continue
            n += 1
            na += (p[0] == act)
            nb += (p[1] == obj)
            if p[0] != act:
                diff.append((name, act, p[0]))
        return n, na, nb, diff

    print()
    for pred, label in ((gem, '같은 모델 재현 (Gemini)'), (sol, '다른 모델 (Solar Pro3)')):
        if not pred:
            continue
        n, na, nb, diff = score(pred, label)
        if not n:
            continue
        print(f'  ■ {label}   비교 {n}개')
        print(f'      활동유형 일치 {na}/{n} = {na / n * 100:.0f}%   '
              f'다루는대상 일치 {nb}/{n} = {nb / n * 100:.0f}%')
        print(f'      둘 다 일치 {sum(1 for c, nm, _l, _m, ac, ob in sample if pred.get(nm) == (ac, ob))}/{n}')
        if diff:
            print(f'      활동유형이 달라진 것 {len(diff)}개 중 앞 8:')
            for nm, was, now in diff[:8]:
                print(f'        {nm:22s} 저장 {was:8s} → 이번 {now}')
        print()

    if gem and sol:
        both = [nm for _c, nm, _l, _m, _a, _o in sample if nm in gem and nm in sol]
        agree = sum(1 for nm in both if gem[nm][0] == sol[nm][0])
        print(f'  ■ 두 모델끼리 활동유형 일치 {agree}/{len(both)} = {agree / max(1, len(both)) * 100:.0f}%')
    print()
    print('  ※ 이 숫자가 낮으면 「맞다/틀리다」 이전에 «그날의 운»이라는 뜻이다.')


asyncio.run(main())
