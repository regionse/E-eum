# -*- coding: utf-8 -*-
"""
course 강좌 → Gemini 임베딩 → Pinecone 저장 배치
──────────────────────────────────────────────────────────
실행 :  python embed_course_강좌임베딩.py
동작 :  ① course 테이블에서 강좌(제목 + 분류)를 읽어
        ② Gemini(gemini-embedding-2, 3072차원)로 벡터화(배치)
        ③ Pinecone 인덱스에 저장(id=kmooc_id)
        ④ course_embedding_result에 로그.
장치 :  · 인덱스 없으면 자동 생성   · Gemini 키 여러 개 자동 로테이션(429 대비)
        · 이미 저장된 강좌는 건너뜀(이어받기)   · 배치라 요청 수 적음

※ 2026-07-23 변경 — 강좌상세(summary)를 임베딩에서 뺐다.
   상세는 강좌당 평균 1,300자인데 그 중 운영일정·이수기준·환불규정이 20~25%다.
   전 강좌에 거의 같은 문장이 들어 있어 변별력은 없고 벡터만 흐린다.
   상세는 DB에 그대로 있고 카드에서 보여주면 된다 — '검색에 쓸 값'과 '보여줄 값'은 다르다.
   토큰 약 1/10 (2.07M → 0.21M) → 무료 한도 안에서 8,273개를 하루에 끝낼 수 있다.
"""
import os, sys, time, getpass, json
import urllib.request, urllib.error
import pymysql
from pinecone import Pinecone, ServerlessSpec

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


# ── .env + 환경변수에서 키 읽기 ────────────────────────────────────
def read_env():
    d = {}
    for p in ['.env', 'etc/.env', '../etc/.env', '../../etc/.env', r'C:\e-um-1\e-um\etc\.env']:
        try:
            for line in open(p, encoding='utf-8'):
                s = line.strip()
                if '=' in s and not s.startswith('#'):
                    k, v = s.split('=', 1)
                    d.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except FileNotFoundError:
            continue
    return d

ENV = {**read_env(), **os.environ}
GEMINI_KEYS = list(dict.fromkeys(v for k, v in ENV.items()
                                 if k.startswith('GEMINI_API_KEY') and v))
PINECONE_KEY = ENV.get('PINECONE_API_KEY')
INDEX_NAME   = ENV.get('PINECONE_INDEX', 'eum-itda')
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


# ── Pinecone 인덱스 준비 (없으면 생성) ─────────────────────────────
pc = Pinecone(api_key=PINECONE_KEY)
try:
    names = pc.list_indexes().names()
except Exception:
    names = [getattr(x, 'name', None) for x in pc.list_indexes()]
if INDEX_NAME not in names:
    print(f'인덱스 "{INDEX_NAME}" 생성 중 (차원 {DIM}, cosine)...')
    pc.create_index(name=INDEX_NAME, dimension=DIM, metric='cosine',
                    spec=ServerlessSpec(cloud='aws', region='us-east-1'))
index = pc.Index(INDEX_NAME)

# 이미 저장된 id 수집 (이어받기 — 실패해도 무시하고 전체 재임베딩)
#  ※ index.list()는 문자열이 아니라 ListItem 객체를 준다.
#    str(ListItem) 은 "ListItem(id='17585')" 이라서 그대로 쓰면 id 비교가 전부 어긋난다.
#    → 반드시 .id 를 꺼내야 이어받기가 동작한다. (2026-07-23 수정)
already = set()
try:
    for batch in index.list(namespace=NAMESPACE):
        for it in batch:
            already.add(it.id if hasattr(it, 'id') else str(it))
except Exception as e:
    print(f'  (기존 id 조회 실패 — 전체 재임베딩으로 진행: {e})')
print(f'Pinecone에 이미 {len(already)}개 있음')


# ── DB에서 강좌 읽기 ────────────────────────────────────────────────
pw = ENV.get('DB_PASSWORD') or getpass.getpass('user2604 DB 비밀번호: ')
conn = pymysql.connect(host='localhost', port=3306, user='user2604',
                       password=pw, database='eum', charset='utf8mb4')
with conn.cursor() as cur:
    # summary(강좌상세)는 안 읽는다 — 임베딩에 안 쓰고, 8,273행 × 1,300자면 읽기만 16MB다.
    cur.execute("SELECT kmooc_id, title, classfy_name, middle_classfy_name FROM course")
    rows = cur.fetchall()

if FORCE:
    todo = list(rows)
    print(f'★ --all 지정 → 이미 있는 것도 전부 다시 임베딩 (텍스트 방식 변경 시 사용)')
else:
    todo = [r for r in rows if str(r[0]) not in already]
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

# ── 로그 ────────────────────────────────────────────────────────────
with conn.cursor() as cur:
    cur.execute("""INSERT INTO course_embedding_result
                   (api_sync_at, embedding_at, new_count, updated_count)
                   VALUES (NOW(), NOW(), %s, %s)""", (saved, 0))
conn.commit()
print(f'✅ 임베딩 완료: 이번에 {saved}개 Pinecone에 저장 (총 {len(already)+saved}개)')
conn.close()
