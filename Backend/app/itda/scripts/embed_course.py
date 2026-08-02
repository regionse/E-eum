# -*- coding: utf-8 -*-
"""
course 강좌 → Gemini 임베딩 → Pinecone 저장 배치
──────────────────────────────────────────────────────────
실행 :  python embed_course_강좌임베딩.py
동작 :  ① course 테이블에서 강좌(제목 + 분류)를 읽어
        ② Gemini(gemini-embedding-2, 3072차원)로 벡터화(배치)
        ③ Pinecone 인덱스에 저장(id=kmooc_id)
        ④ course.content_hash 기록 + itda_sync_log 에 실행 로그.
장치 :  · 인덱스 없으면 자동 생성   · Gemini 키 여러 개 자동 로테이션(429 대비)
        · 이미 저장된 강좌는 건너뜀(이어받기)   · 배치라 요청 수 적음

※ 2026-07-31 수정 — 로그 대상 테이블이 틀려서 마지막에 죽고 있었다.
   `course_embedding_result` 는 존재하지 않는 테이블이라 임베딩을 다 끝낸 뒤
   INSERT 에서 예외가 나고 commit 이 안 됐다(Pinecone 저장 자체는 되어 있었다).
   실제 스키마의 로그 테이블은 `itda_sync_log` 다 → 그쪽에 남기도록 교체.
   덜다·나누다의 관리자 임베딩 화면이 이 테이블을 읽는다.

※ 2026-07-23 변경 — 강좌상세(summary)를 임베딩에서 뺐다.
   상세는 강좌당 평균 1,300자인데 그 중 운영일정·이수기준·환불규정이 20~25%다.
   전 강좌에 거의 같은 문장이 들어 있어 변별력은 없고 벡터만 흐린다.
   상세는 DB에 그대로 있고 카드에서 보여주면 된다 — '검색에 쓸 값'과 '보여줄 값'은 다르다.
   토큰 약 1/10 (2.07M → 0.21M) → 무료 한도 안에서 8,273개를 하루에 끝낼 수 있다.
"""
import os
import sys
import time
import json
import hashlib
import urllib.request, urllib.error


#  ★ 2026-07-31 — env 로더·DB 접속·Pinecone 준비를 공용 모듈(_common.py)로 옮겼다.
#    전에는 배치 10개가 각자 갖고 있어서, 한 곳만 고치면 될 일을 매번 7~8곳에서 고쳤다.
try:
    from ._common import (setup_console, ENV, db_conn,     # noqa: F401
                          pinecone_index, already_ids, diff_by_hash, SyncLog)
except ImportError:                                       # 파일 직접 실행
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _common import (setup_console, ENV, db_conn,      # noqa: F401
                         pinecone_index, already_ids, diff_by_hash, SyncLog)

setup_console()

#  ★ 시작 시각을 여기서 잡는다 — 로그의 소요시간이 의미를 가지려면
#    write() 호출 시점이 아니라 스크립트가 뜬 시점이어야 한다.
SYNC = SyncLog('embed_course')

MODEL = 'gemini-embedding-2'   # 2026-07 실측: 차원 3072(001과 동일) · inputTokenLimit 8192(001은 2048)
DIM   = 3072                   # ※ match.py의 MODEL과 반드시 같아야 함. 다르면 검색이 전부 엉킴
BATCH = 100                    # 요청당 강좌 수. 텍스트가 짧아졌으니(≈25토큰) 100개도 2,500토큰뿐
SLEEP = 3.0                    # ★ 배치 간격(초). 분당 토큰 한도(TPM)를 안 넘기는 게 목적.
                               #   예전(상세 포함·250토큰)엔 700개에서 TPM이 터졌다. 429 잦으면 늘릴 것.
NAMESPACE = 'course'           # ★ 같은 인덱스에 자격증(cert)도 들어간다. 반드시 나눌 것.
                               #   안 나누면 '강좌 추천'에 자격증이 섞여 나오고, 그 반대도 마찬가지다.

# python embed_course_강좌임베딩.py --all  → 이미 넣은 것도 전부 다시 (텍스트 방식 바꿨을 때)
FORCE = '--all' in sys.argv


# ── 임베딩할 텍스트 만들기 ──────────────────────────────────────────
#  제목 + 대분류 + 중분류. 이게 전부다.
#
#  왜 제목만이 아니라 분류까지 넣나:
#    질의는 "정보통신 정보기기운용기능사" 같은 '자격증+직무분야' 문장이다.
#    제목 "파이썬 프로그래밍 기초" 하나로는 '정보통신'과 걸릴 실마리가 약한데,
#    분류 "공학 · 컴퓨터·통신" 이 붙으면 질의의 '정보통신'과 바로 이어진다.
#    토큰은 강좌당 10개쯤 더 드는 게 전부다 — 값이 거의 공짜인데 효과는 크다.
def build_text(row):
    """row = (kmooc_id, title, classfy_name, middle_classfy_name)"""
    _, title, classfy, middle = row
    return ' · '.join(x.strip() for x in (title, classfy, middle) if x and x.strip())


# ── content_hash — '이 강좌가 어떤 텍스트로 임베딩됐는가'의 지문 ─────
#  왜 필요한가
#    이게 없으면 「최신화」를 누를 때마다 8,273개를 전부 다시 임베딩해야 한다.
#    무엇이 바뀌었는지 알 수 없기 때문이다. 해시가 있으면 값이 달라진 것만 고르면 된다.
#    관리자 화면의 "신규 N건 / 변경 N건" 도 이 비교에서 나온다.
#
#  ★ 해시 대상은 '임베딩에 실제로 들어간 텍스트'여야 한다.
#    summary 는 임베딩에서 뺐으므로(위 2026-07-23 주석) 해시에도 넣지 않는다.
#    안 그러면 요약만 고쳐도 "변경됨"으로 잡혀 쓸데없이 재임베딩한다.
def content_hash(row):
    return hashlib.sha256(build_text(row).encode('utf-8')).hexdigest()


# ── .env + 환경변수에서 키 읽기 ────────────────────────────────────
GEMINI_KEYS = list(dict.fromkeys(v for k, v in ENV.items()
                                 if k.startswith('GEMINI_API_KEY') and v))
PINECONE_KEY = ENV.get('PINECONE_API_KEY')
INDEX_NAME   = (ENV.get('PINECONE_COURSE_INDEX_NAME')
                or ENV.get('PINECONE_INDEX')      # 구 키 하위호환
                or 'eum-itda')
#  ★ 팀 통합 .env 스키마(2026-07-31) — 코드 상수를 env 로 덮어쓴다.
#    ⚠️ 임베딩 모델을 바꾸면 차원이 달라져 **인덱스를 통째로 다시 만들어야 한다.**
#       덜다의 gemini-embedding-002(768) 와 한 글자 차이인 다른 모델이다.
MODEL = ENV.get('COURSE_EMBEDDING_MODEL') or MODEL
DIM   = int(ENV.get('COURSE_EMBEDDING_DIMENSION') or DIM)
if not GEMINI_KEYS:
    raise SystemExit('GEMINI_API_KEY 없음 (.env 확인)')
if not PINECONE_KEY:
    raise SystemExit('PINECONE_API_KEY 없음 (.env에 추가)')
print(f'Gemini 키 {len(GEMINI_KEYS)}개 · Pinecone 인덱스 "{INDEX_NAME}" · 네임스페이스 "{NAMESPACE}"')


# ── Gemini 임베딩 (키 로테이션) ────────────────────────────────────
_ki = 0
def embed(texts):
    global _ki
    body = json.dumps({'requests': [
        {'model': f'models/{MODEL}', 'content': {'parts': [{'text': t}]}} for t in texts]}).encode()
    wait = 65          # 분당 토큰 한도(TPM)는 1분이면 회복된다 → 짧게 포기하지 말 것
    for attempt in range(1, 41):
        key = GEMINI_KEYS[_ki % len(GEMINI_KEYS)]
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:batchEmbedContents?key={key}'
        try:
            req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
            j = json.loads(urllib.request.urlopen(req, timeout=90).read().decode())
            return [e['values'] for e in j['embeddings']]
        except urllib.error.HTTPError as e:
            if e.code in (429, 403, 503):
                _ki += 1
                if attempt % len(GEMINI_KEYS) == 0:
                    # 키를 한 바퀴 다 돌았다 = 전부 한도 → '실제로' 기다린다
                    print(f'    ⏳ 한도 도달 — {wait}초 대기 후 재개 (시도 {attempt})', flush=True)
                    time.sleep(wait)
                    wait = min(wait + 30, 185)      # 65 → 95 → 125 → 155 → 185
                else:
                    time.sleep(2)                   # 다른 키로 즉시 전환
                continue
            raise
        except Exception:
            time.sleep(5)
    raise SystemExit('20분 넘게 기다려도 한도가 안 풀림 → 분당이 아니라 일일 한도로 보임.\n'
                     '내일 다시 실행하세요 (이미 넣은 건 건너뛰고 이어서 진행됩니다).')


# ── Pinecone 인덱스 준비 + 이어받기 ────────────────────────────────
#  인덱스 생성·id 수집 로직은 _common 에 있다(embed_cert·embed_jobs 와 공유).
index = pinecone_index()
already = already_ids(index, NAMESPACE)
print(f'Pinecone에 이미 {len(already)}개 있음')


# ── DB에서 강좌 읽기 ────────────────────────────────────────────────
conn = db_conn()
with conn.cursor() as cur:
    # summary(강좌상세)는 안 읽는다 — 임베딩에 안 쓰고, 8,273행 × 1,300자면 읽기만 16MB다.
    cur.execute("SELECT kmooc_id, title, classfy_name, middle_classfy_name FROM course")
    rows = cur.fetchall()

#  ★ 저장된 해시와 비교해 '신규 / 변경'을 가른다(2026-08-02).
#    관리자 화면의 「신규 N건 · 변경된 N건」이 이 값이다.
n_new_set, n_chg_set = diff_by_hash(conn, 'course', 'kmooc_id', rows, content_hash)
print(f'해시 비교 — 신규 {len(n_new_set)} · 변경 {len(n_chg_set)} · '
      f'그대로 {len(rows) - len(n_new_set) - len(n_chg_set)}')

if FORCE:
    todo = list(rows)
    print(f'★ --all 지정 → 이미 있는 것도 전부 다시 임베딩 (텍스트 방식 변경 시 사용)')
else:
    #  ★ 건너뛰기 기준이 두 개다(2026-08-02) — Pinecone 에 없거나, 내용이 바뀌었거나.
    #    예전엔 앞의 것만 봐서 제목이 바뀌어도 옛 벡터가 그대로 남았다.
    todo = [r for r in rows
            if str(r[0]) not in already or str(r[0]) in n_chg_set]
print(f'강좌 {len(rows)}개 중 임베딩할 것 {len(todo)}개')


# ── 배치 임베딩 + Pinecone upsert ──────────────────────────────────
saved = 0
t0 = time.time()
print(f'배치 {BATCH}개씩 · 배치 간격 {SLEEP}초 → 예상 {int(len(todo)/BATCH*(SLEEP+2)/60)}분 내외\n')
for i in range(0, len(todo), BATCH):
    chunk = todo[i:i + BATCH]
    texts = [build_text(r) for r in chunk]      # 제목 · 대분류 · 중분류
    vecs = embed(texts)
    index.upsert(namespace=NAMESPACE, vectors=[
        {'id': str(r[0]), 'values': v,
         'metadata': {'title': (r[1] or '')[:200], 'classfy': r[2] or ''}}
        for r, v in zip(chunk, vecs)])
    saved += len(chunk)
    el = time.time() - t0
    eta = el / saved * (len(todo) - saved)
    print(f'  {saved}/{len(todo)}  ({saved*100//len(todo)}%)  경과 {int(el//60)}분 · 남은시간 약 {int(eta//60)}분',
          flush=True)
    time.sleep(SLEEP)   # ★ 분당 토큰 한도(TPM) 대비 속도 제한. 이게 핵심

# ── content_hash 기록 ───────────────────────────────────────────────
#  이번에 임베딩한 것뿐 아니라 '이미 Pinecone 에 있던 것'에도 해시를 남긴다.
#  그래야 다음 실행부터 해시 비교가 전 행에 대해 성립한다(반쪽이면 의미가 없다).
#  트레이드오프: 예전에 임베딩된 뒤 제목이 바뀐 강좌가 있다면, 지금 해시를 쓰는 순간
#  '최신'으로 굳어져 그 어긋남을 못 잡는다. 다만 그 강좌는 지금도 이미 어긋나 있고,
#  전체를 다시 맞추고 싶으면 `--all` 이 그대로 escape hatch 로 남아 있다.
hashed = 0
with conn.cursor() as cur:
    for i in range(0, len(rows), 500):
        cur.executemany(
            "UPDATE course SET content_hash=%s WHERE kmooc_id=%s",
            [(content_hash(r), r[0]) for r in rows[i:i + 500]])
        hashed += min(500, len(rows) - i)
conn.commit()
print(f'content_hash 기록 {hashed}행')


# ── 실행 로그 (관리자 임베딩 화면이 읽는다) ─────────────────────────
#  ★ 2026-08-02 — inserted/updated 에 '해시를 쓴 행 수'(=전체)를 넣던 것을 바로잡았다.
#    화면에 "변경 8,273건" 처럼 거짓이 뜨고 있었다. 이제 해시 비교 결과를 그대로 넣는다.
total = max(len(already), saved) if FORCE else len(already) + saved
SYNC.write(conn, fetched=len(rows), inserted=len(n_new_set), updated=len(n_chg_set),
           embedded=saved, status='ok',
           message=f'Pinecone "{NAMESPACE}" 누적 {total}개 · 해시 {hashed}행')
print(f'임베딩 완료: 이번에 {saved}개 저장 · 신규 {len(n_new_set)} · 변경 {len(n_chg_set)}')
conn.close()
