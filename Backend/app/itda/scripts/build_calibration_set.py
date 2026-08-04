# -*- coding: utf-8 -*-
"""잇다 · 캘리브레이션 셋 생성 (2026-08-03 신설)

무엇을 위한 것인가
  지금 착지 판정(카드를 줄지 / 되물을지)이 **손으로 정한 임계값**에 걸려 있다.
      JOB_MARGIN = 0.02 · JOB_NARROW_GAP = 0.04
  이 숫자가 무엇을 보장하는지 아무도 모른다. 원시 코사인 점수는 **확률이 아니다**.
  그래서 점수가 임계값 근처(실측 0.006 차)면 같은 입력에도 판정이 뒤집혔다
      「자동차 고치는 일이 좋아요」 → 30회 중 카드 6 · 되묻기 24

  정식 해법은 **Conformal Prediction** 이다(CONFLARE, arXiv 2404.04287).
      ① 캘리브레이션 셋(질문 + 정답)을 만든다          ← 이 파일
      ② 각 질문에서 '정답의 점수'를 기록한다
      ③ 허용 오류율 α 의 분위수를 컷으로 삼는다
      ④ 컷 이상인 후보 전부를 '예측 집합'으로 반환한다
  보장: 정답이 집합 안에 있을 확률 ≥ 1−α.
  그러면 점수가 흔들려도 **집합 크기가 4↔5로 변할 뿐 답이 뒤집히지 않는다.**

어떻게 만드나 — 합성 질의(synthetic query)
  직업의 NCS 설명을 LLM 에 주고 "그 직업을 원하는 사람이 상담에서 할 법한 말"을 짓게 한다.
  **정답은 원본 직업으로 자동 확정**되므로 사람이 라벨을 달 필요가 없다.
  ★ 직업명을 그대로 쓰면 검색이 아니라 '이름 찾기'가 되므로 금지하고, 사후에도 검사한다.

실행 (Backend/ 에서)
    python -m app.itda.scripts.build_calibration_set --n 150
    python -m app.itda.scripts.build_calibration_set --n 20 --out /tmp/mini.json
"""
import argparse
import asyncio
import io
import json
import math
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

from ._common import setup_console, ENV, db_conn
from .. import gemini_util as _gutil

setup_console()

MODEL = ENV.get('COURSE_LLM_MODEL') or 'gemini-3.1-flash-lite'
CHUNK = 8          # LLM 한 번에 만들 질문 수
OUT_DEFAULT = Path(__file__).with_name('calibration_set.json')

_SCHEMA = {
    'type': 'object',
    'properties': {
        'items': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'code': {'type': 'string'},
                    'question': {'type': 'string'},
                },
                'required': ['code', 'question'],
            },
        },
    },
    'required': ['items'],
}

PROMPT = """너는 진로상담 데이터를 만드는 사람이다.
아래 각 직업에 대해, **그 직업을 하고 싶은 사람이 상담 첫머리에 할 법한 말**을 한 문장씩 지어라.

규칙
1. **직업명을 그대로 쓰지 마라.** 이름을 쓰면 검색이 아니라 이름 찾기가 된다.
   («자동차전기·전자장치정비» → ✗ "자동차전기정비 하고 싶어요"  ○ "차 전기 계통 고치는 일 해보고 싶어요")
2. NCS 전문용어 대신 **일상어**로 써라. 실제 사용자는 그 용어를 모른다.
   («광의료기기개발» → ✗ "광기반 진단기기 개발"  ○ "의료기기 만드는 일에 관심 있어요")
3. 20~40자. "~하고 싶어요" · "~쪽 일 해보고 싶은데요" 같은 자연스러운 상담 말투.
4. 그 직업이 **다른 직업과 구별되게** 써라. 너무 뭉뚱그리면 정답을 찾을 수 없다.

[직업 목록]
{items}
"""


def _post_factory(body):
    def _post(key):
        url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'{MODEL}:generateContent?key={key}')
        req = urllib.request.Request(url, data=body,
                                     headers={'Content-Type': 'application/json'})
        return urllib.request.urlopen(req, timeout=120).read()
    return _post


async def make(batch):
    """batch: [(code, name, lcls, desc)] → {code: question}"""
    lines = [f"- code={c} | 직업: {n} | 분야: {l}\n  직무: {(d or '')[:150]}"
             for c, n, l, d in batch]
    body = json.dumps({
        'contents': [{'parts': [{'text': PROMPT.format(items='\n'.join(lines))}]}],
        'generationConfig': {'responseMimeType': 'application/json',
                             'responseSchema': _SCHEMA, 'temperature': 0.8,
                             'thinkingConfig': {'thinkingLevel': 'minimal'}},
    }).encode()
    j = await _gutil.call(_post_factory(body), ENV)
    txt = j['candidates'][0]['content']['parts'][0]['text']
    out = {str(r.get('code')): (r.get('question') or '').strip()
           for r in (json.loads(txt).get('items') or [])}
    um = j.get('usageMetadata') or {}
    return out, um.get('promptTokenCount', 0) + um.get('candidatesTokenCount', 0)


def sample_jobs(conn, n):
    """대분류 비례 계층 샘플 — 한쪽 분야에 쏠리지 않게. 대분류마다 최소 2개."""
    cur = conn.cursor()
    cur.execute("""SELECT job_code, job_name, job_lcls_name, job_description
                   FROM job_catalog WHERE job_description > '' ORDER BY RAND()""")
    rows = cur.fetchall()
    by = defaultdict(list)
    for r in rows:
        by[r[2] or '(기타)'].append(r)
    total = sum(len(v) for v in by.values())
    picked = []
    for lcls, js in by.items():
        k = max(2, round(n * len(js) / total))
        picked += js[:k]
    return picked[:n]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=150)
    ap.add_argument('--out', default=str(OUT_DEFAULT))
    a = ap.parse_args()

    conn = db_conn()
    jobs = sample_jobs(conn, a.n)
    conn.close()
    print(f'모델 {MODEL} · 직업 {len(jobs)}종 표본 · {CHUNK}개씩 생성\n')

    qs, tokens = {}, 0
    for i in range(0, len(jobs), CHUNK):
        chunk = jobs[i:i + CHUNK]
        try:
            got, tk = await make(chunk)
            qs.update(got)
            tokens += tk
        except Exception as e:
            print(f'  {i}~{i+len(chunk)} 실패: {type(e).__name__}: {str(e)[:60]}')
        print(f'  {min(i+CHUNK, len(jobs))}/{len(jobs)}  (토큰 {tokens:,})', flush=True)

    #  ★ 사후 검증 — 직업명이 질문에 그대로 들어갔으면 버린다(이름 찾기가 되어버린다).
    items, dropped = [], 0
    for code, name, lcls, desc in jobs:
        q = qs.get(str(code), '').strip()
        if not q:
            continue
        core = name.split('·')[0].split('(')[0].strip()
        if len(core) >= 3 and core in q:
            dropped += 1
            continue
        items.append({'question': q, 'job_code': str(code),
                      'job_name': name, 'lcls': lcls})

    Path(a.out).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\n생성 {len(items)}개 (직업명 노출로 버림 {dropped}개) · 토큰 {tokens:,}')
    print(f'저장 {a.out}')
    print('\n예시:')
    for it in items[:5]:
        print(f"  «{it['question']}»  →  [{it['job_name']}] ({it['lcls']})")


if __name__ == '__main__':
    asyncio.run(main())
