# -*- coding: utf-8 -*-
"""직업(NCS) 임베딩 → Pinecone 네임스페이스 'job'  (2026-07-31 작성)

★   직업 1,094개가 이미 Pinecone 에 들어가 있는데 **그것을 넣은 코드가 어디에도 없었다.**
  (2026-07-29 NCS 전환 때 임시로 돌리고 남기지 않았다.)
  그래서 "무슨 텍스트를 임베딩했는지"를 알 수 없었고, 2026-07-30 에 **저장된 벡터와
  후보 텍스트의 코사인 유사도를 재서 역추적**해야 했다. 그 결과가 아래다.

  실측(요양지원 / 내선공사):
      이름 + 대/중/소분류 + 설명   0.959 / 0.947   ← 원본에 가장 가까움
      이름 + 중분류 + 설명         0.947 / 0.935
      설명만                       0.941 / 0.926
      이름 + 분류(설명 없음)       0.832 / 0.832
      이름만                       0.745 / 0.810
  ⇒ '이름 + 분류 + NCS 설명' 을 합쳐 임베딩한 것이 확실하다. 이 스크립트가 그것을 재현한다.

  인덱스가 날아가거나 새 환경(AWS 등)에 다시 구축할 때 **이 파일이 유일한 복구 수단**이다.

실행 (레포 루트에서)
    python -m app.itda.scripts.embed_jobs              # 아직 안 올라간 것만
    python -m app.itda.scripts.embed_jobs --all        # 전부 다시
    python -m app.itda.scripts.embed_jobs --namespace job2 --all
        └ 새 네임스페이스에 만들어 두고, 확인 후 itda/match.py 의 NS_JOB 을 바꾸면
          기존 인덱스를 건드리지 않고 안전하게 교체·롤백할 수 있다.

주의
  · 임베딩 모델은 **검색할 때와 반드시 같아야 한다**(match.py 의 MODEL). 다르면 검색이 전부 어긋난다.
  · 무료 티어는 분당 요청 한도가 있어 배치 사이에 쉰다(SLEEP).
"""
import sys
import time
import json
import argparse
import asyncio
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # …/Backend

from sqlalchemy import text                       # noqa: E402
from pinecone import Pinecone                     # noqa: E402

from app.itda.env import ENV                      # noqa: E402  (etc/.env + 환경변수)
from app.itda.db import async_session             # noqa: E402
from app.itda import gemini_util as gutil         # noqa: E402


#  ★ 팀 통합 .env 스키마(2026-07-31). 기본값은 코드에 남긴다.
#     ⚠️ 바꾸면 차원이 달라져 인덱스를 다시 만들어야 한다. match.py 와 반드시 동일할 것.
MODEL = ENV.get('COURSE_EMBEDDING_MODEL') or 'gemini-embedding-2'
BATCH = 20                        # 한 번에 임베딩할 개수
SLEEP = 1.0                       # 배치 사이 대기(초) — 분당 한도 회피
DIM = int(ENV.get('COURSE_EMBEDDING_DIMENSION') or 3072)   # 출력 차원


def embed_batch(texts):
    """여러 문장을 한 번에 임베딩 → [[float,...], ...]"""
    out = []
    for t in texts:                               # Gemini embedContent 는 1건씩
        body = json.dumps({'model': f'models/{MODEL}',
                           'content': {'parts': [{'text': t}]}}).encode()

        def _post(key, _b=body):
            url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
                   f'{MODEL}:embedContent?key={key}')
            req = urllib.request.Request(
                url, data=_b, headers={'Content-Type': 'application/json'})
            return urllib.request.urlopen(req, timeout=60).read()

        j = asyncio.run(gutil.call(_post, ENV))   # 한도 초과 시 대기 후 재시도
        out.append(j['embedding']['values'])
    return out


def build_text(row):
    """임베딩할 문장 — 역추적으로 확인된 구성: 이름 + 대/중/소분류 + NCS 설명.

    설명(job_description)이 없으면 분류만으로도 넣는다(이름만보다는 낫다).
    """
    code, name, lcls, mcls, scls, desc = row
    parts = [name, lcls or '', mcls or '', scls or '', (desc or '').strip()]
    return ' '.join(p for p in parts if p)


def build_meta(row):
    """벡터에 붙일 메타데이터 — 실제 인덱스에 저장돼 있던 것과 동일하게 맞춘다."""
    _, name, _, mcls, _, _ = row
    return {'job_name': name, 'job_mcls_name': mcls or ''}


async def fetch_jobs(only_missing, index, namespace):
    async with async_session() as db:
        rows = (await db.execute(text(
            "SELECT job_code, job_name, job_lcls_name, job_mcls_name, "
            "       job_scls_name, job_description "
            "FROM job_catalog ORDER BY job_code"))).fetchall()
    rows = [tuple(r) for r in rows]
    if not only_missing:
        return rows
    #  이미 올라간 것은 건너뛴다(중단 후 이어서 돌릴 때)
    have = set()
    for i in range(0, len(rows), 100):
        ids = [str(r[0]) for r in rows[i:i + 100]]
        try:
            got = index.fetch(ids=ids, namespace=namespace)
            vecs = getattr(got, 'vectors', None) or (got.get('vectors') if isinstance(got, dict) else {})
            have |= set((vecs or {}).keys())
        except Exception:
            break
    return [r for r in rows if str(r[0]) not in have]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true', help='이미 올라간 것도 다시 임베딩')
    ap.add_argument('--namespace', default='job', help="넣을 네임스페이스 (기본 'job')")
    ap.add_argument('--limit', type=int, default=0, help='앞에서 N개만(시험용)')
    a = ap.parse_args()

    key = ENV.get('PINECONE_API_KEY')
    if not key:
        raise SystemExit('PINECONE_API_KEY 없음 — etc/.env 또는 환경변수를 확인하세요.')
    index_name = (ENV.get('PINECONE_COURSE_INDEX_NAME')
                  or ENV.get('PINECONE_INDEX')      # 구 키 하위호환
                  or 'eum-itda')
    index = Pinecone(api_key=key).Index(index_name)

    todo = asyncio.run(fetch_jobs(not a.all, index, a.namespace))
    if a.limit:
        todo = todo[:a.limit]
    if not todo:
        print('올릴 것이 없습니다. (--all 로 전체 재임베딩 가능)')
        return

    print(f'인덱스 {index_name} · 네임스페이스 "{a.namespace}" · 모델 {MODEL}')
    print(f'대상 {len(todo)}개\n예시: {build_text(todo[0])[:90]}…\n')

    saved, t0 = 0, time.time()
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        vecs = embed_batch([build_text(r) for r in chunk])
        index.upsert(namespace=a.namespace,
                     vectors=[{'id': str(r[0]), 'values': v, 'metadata': build_meta(r)}
                              for r, v in zip(chunk, vecs)])
        saved += len(chunk)
        print(f'  {saved}/{len(todo)}  ({saved * 100 // len(todo)}%)  '
              f'경과 {int(time.time() - t0)}초', flush=True)
        if i + BATCH < len(todo):
            time.sleep(SLEEP)

    print(f'\n✅ 직업 임베딩 완료: {saved}개 → 네임스페이스 "{a.namespace}"')
    if a.namespace != 'job':
        print('   ※ 확인 후 app/itda/match.py 의 NS_JOB 을 바꾸면 교체됩니다(되돌리기도 한 줄).')


if __name__ == '__main__':
    main()
