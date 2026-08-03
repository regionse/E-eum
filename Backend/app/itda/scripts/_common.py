# -*- coding: utf-8 -*-
"""잇다 배치 스크립트 공용 모듈

무엇을 담나
  '어느 배치든 똑같이 하는 일'만 담는다. 배치마다 다른 판단(무엇을 임베딩할지,
  어떤 텍스트를 만들지)은 각 스크립트에 남긴다 — 그건 그 배치의 본질이라 숨기면 안 된다.

쓰는 법
    from ._common import setup_console, ENV, db_conn, pinecone_index, SyncLog, sha
"""
import os
import sys
import hashlib
import datetime

import pymysql

try:                                   # 패키지 실행
    from ..env import ENV              # noqa: F401  (재수출 — 스크립트가 그대로 쓴다)
except ImportError:                    # 파일 직접 실행
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from env import ENV                # noqa: F401


# ── 콘솔 ────────────────────────────────────────────────────────────
def setup_console():
    """Windows 콘솔(cp949)에서 비ASCII 출력 시 죽는 것을 막는다.

    실측(2026-07-31): embed_course.py 가 임베딩·커밋을 다 끝낸 뒤
    마지막 print 의 '✅' 에서 UnicodeEncodeError 로 죽었다.
    "실패한 줄 알았는데 데이터는 들어가 있는" 헷갈리는 상황이 났다.
    """
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


# ── DB ──────────────────────────────────────────────────────────────
def db_conn():
    """.env 기반 pymysql 연결.

    ★ host='localhost' 를 박으면 안 된다 — 서버에서는 DB 가 RDS 에 있어
      자기 자신을 보고 죽는다. 관리자 화면의 「최신화」 버튼도 같은 이유로 실패한다.
    ★ getpass 로 비밀번호를 물어보지 않는다 — 헤드리스(서버·스케줄러)에서 영원히 멈춘다.
    """
    pw = ENV.get('DB_PASSWORD') or ENV.get('DB_PW')
    if not pw:
        raise SystemExit('DB_PASSWORD 없음 — app/.env 확인')
    return pymysql.connect(host=ENV.get('DB_HOST', 'localhost'),
                           port=int(ENV.get('DB_PORT', 3306)),
                           user=ENV.get('DB_USER', 'user2604'),
                           password=pw,
                           database=ENV.get('DB_NAME', 'eum'),
                           charset='utf8mb4')


# ── Pinecone ────────────────────────────────────────────────────────
def index_name():
    """팀 통합 .env 스키마. 구 키(PINECONE_INDEX)도 읽는다

    ⚠️ 잇다는 인덱스 1개(eum-itda)에 네임스페이스 3개(cert/course/job)다.
       키 이름이 COURSE 지만 강좌 전용 인덱스가 아니다.
    """
    return (ENV.get('PINECONE_COURSE_INDEX_NAME')
            or ENV.get('PINECONE_INDEX')
            or 'eum-itda')


def embed_dim():
    return int(ENV.get('COURSE_EMBEDDING_DIMENSION') or 3072)


def pinecone_index(create=True):
    """인덱스 핸들. 없으면 만든다(차원·metric 은 위 상수를 따른다)."""
    from pinecone import Pinecone, ServerlessSpec
    key = ENV.get('PINECONE_API_KEY')
    if not key:
        raise SystemExit('PINECONE_API_KEY 없음 — app/.env 확인')
    pc = Pinecone(api_key=key)
    name = index_name()
    try:
        names = pc.list_indexes().names()
    except Exception:
        names = [getattr(x, 'name', None) for x in pc.list_indexes()]
    if name not in names:
        if not create:
            raise SystemExit(f'인덱스 "{name}" 없음')
        print(f'인덱스 "{name}" 생성 중 (차원 {embed_dim()}, cosine)...')
        pc.create_index(name=name, dimension=embed_dim(), metric='cosine',
                        spec=ServerlessSpec(cloud='aws', region='us-east-1'))
    return pc.Index(name)


def already_ids(index, namespace):
    """이미 넣은 벡터 id 집합 (이어받기용).

    ★ index.list() 는 문자열이 아니라 ListItem 객체를 준다.
      str(ListItem) 은 "ListItem(id='17585')" 이라 그대로 쓰면 id 비교가 전부 어긋난다.
      → 반드시 .id 를 꺼낸다. (2026-07-23 에 실제로 겪은 버그)
    """
    out = set()
    try:
        for batch in index.list(namespace=namespace):
            for it in batch:
                out.add(it.id if hasattr(it, 'id') else str(it))
    except Exception as e:
        print(f'  (기존 id 조회 실패 — 전체 재임베딩으로 진행: {e})')
    return out


# ── 해시 ────────────────────────────────────────────────────────────
def sha(text):
    """content_hash — '이 행이 어떤 텍스트로 임베딩됐는가'의 지문.

    이게 없으면 「최신화」마다 전체를 다시 임베딩해야 한다(무엇이 바뀌었는지 모르니까).
    관리자 화면의 "신규 N건 / 변경 N건" 도 이 비교에서 나온다.

    ★ 해시 대상은 '임베딩에 실제로 들어간 텍스트'여야 한다.
      표시용 필드(진로전망 등)를 넣으면 그것만 고쳐도 "변경됨"으로 잡혀 쓸데없이 재임베딩한다.
    """
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def diff_by_hash(conn, table, key_col, rows, hash_fn):
    """저장된 content_hash 와 비교해 (신규, 변경) 을 가른다.

    관리자 임베딩 화면의 **「신규 N건 / 변경된 N건」이 여기서 나온다.**
    덜다·나누다 화면과 같은 항목을 채우려면 이 구분이 필요하다.

        해시가 없음   → 신규 (한 번도 임베딩 안 된 것)
        해시가 다름   → 변경 (내용이 바뀐 것 → 재임베딩 대상)
        해시가 같음   → 그대로 (건너뛴다)

    ★ 2026-08-02 신설 — 그전에는 해시를 **쓰기만 하고 읽지 않았다.**
      건너뛰기 기준이 'Pinecone 에 id 가 있나' 뿐이라, 내용이 바뀌어도 건너뛰었다.
      그래서 재임베딩할 때마다 `--all` 로 전체를 다시 돌려야 했다.
      이제 바뀐 것만 골라내므로 `--all` 없이도 정확하고, 비용·시간이 준다.

    반환: (신규 id 집합, 변경 id 집합)  — 둘 다 str 로 정규화
    """
    with conn.cursor() as cur:
        cur.execute(f'SELECT {key_col}, content_hash FROM {table}')
        old = {str(k): v for k, v in cur.fetchall()}
    fresh, changed = set(), set()
    for r in rows:
        k = str(r[0])
        prev = old.get(k)
        if not prev:
            fresh.add(k)
        elif prev != hash_fn(r):
            changed.add(k)
    return fresh, changed


# ── 실행 로그 ───────────────────────────────────────────────────────
class SyncLog:
    """itda_sync_log 기록 — 관리자 임베딩 화면이 이 테이블을 읽는다.

    ★ 예전에 embed_course.py 가 존재하지 않는 `course_embedding_result` 에 INSERT 해서
      임베딩을 다 끝낸 뒤 마지막에 죽었다(커밋도 안 됐다). 테이블명을 여기 한 곳으로 모은다.
    """

    def __init__(self, target):
        self.target = target
        self.started_at = datetime.datetime.now()

    def write(self, conn, *, fetched=0, inserted=0, updated=0, embedded=0,
              status='ok', message=''):
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO itda_sync_log
                     (target, started_at, finished_at, fetched, inserted, updated,
                      embedded, status, message)
                   VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s)""",
                (self.target, self.started_at, fetched, inserted, updated,
                 embedded, status, message))
        conn.commit()
        print(f'itda_sync_log 기록: {self.target} · 상태 {status}')


#  공공데이터 API 호출은 여기에 두지 않는다.
#  배치마다 엔드포인트·파싱·재시도 조건이 달라 공용화해도 각자 다시 짜게 된다.
#  실제 호출 규칙(HTTP 200 인데 본문이 에러 · 커스텀 UA 는 403 · 큰 응답은 300초)은
#  load_cert_detail.py 의 fetch() 와 그 위 상수 주석에 실측값과 함께 적어 두었다.
