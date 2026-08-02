# -*- coding: utf-8 -*-
"""
certification 자격증 → Gemini 임베딩 → Pinecone 저장 배치
──────────────────────────────────────────────────────────
실행 :  python embed_cert_자격증임베딩.py           (미리보기 → 확인 후 진행)
        python embed_cert_자격증임베딩.py --dry     (텍스트만 보고 끝)
        python embed_cert_자격증임베딩.py --all     (이미 넣은 것도 전부 다시)

왜 필요한가
  지금 엔진은 자격증을 이렇게 고른다:
      슬롯 → 모델이 대직무분야 17개 중 1개 선택 → 그 분야 기능사만 조회 → 모델이 1개 선택
  대직무분야가 병목이다.
    · 기능사가 0개인 대직무분야가 7개 (사회복지·경영회계사무·보건의료 등)
    · 국가전문자격 100종은 oblig_fld 가 빈 문자열이라 17개 enum 에 아예 없다
      → 공인중개사·세무사·관세사·물류관리사가 통째로 도달 불가
  자격증을 직접 임베딩하면 대분류를 건너뛴다. 613종 전부가 후보가 된다.

※ 강좌와 같은 인덱스를 쓰되 네임스페이스로 나눈다(course / cert).
  안 나누면 '강좌 추천'에 자격증이 섞여 나온다.
"""
import os
import sys
import re
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

#  ★ 시작 시각을 여기서 잡는다 — 로그의 소요시간(started_at ~ finished_at)이 의미를 가지려면
#    write() 호출 시점이 아니라 스크립트가 뜬 시점이어야 한다.
SYNC = SyncLog('embed_cert')

MODEL = 'gemini-embedding-2'   # ※ embed_course·match.py 와 반드시 동일
DIM   = 3072
BATCH = 100
SLEEP = 3.0
NAMESPACE = 'cert'             # ★ 강좌(course)와 분리
JOB_DESC_LIMIT = 300           # 수행직무는 대개 100~200자. 넉넉히 잘라 잡음만 막는다

FORCE = '--all' in sys.argv
DRY   = '--dry' in sys.argv


# ── 임베딩할 텍스트 ────────────────────────────────────────────────
#  머리: 종목명 · 등급 · 대직무분야 · 중직무분야  (중복 제거)
#  몸통: 수행직무 (Q-Net 종목별 시험정보 CSV → load_cert_상세.py 로 적재)
#
#  왜 수행직무가 필요한가
#    자격증명은 전문용어고 사용자 발화는 일상어다. 머리만으로는 어휘가 안 겹친다.
#      "전기기능사 · 기능사 · 전기.전자 · 전기"      ← '고치는 거 좋아해요' 와 안 걸림
#      + "전선·케이블을 설치, 보수, 검사, 관리"      ← '보수'·'검사' 로 걸림
#
#  국가전문자격 100종은 grade 에 자격명이 그대로 들어있고 oblig_fld 가 비어 있다.
#  (예: jm_name='공인중개사', grade='공인중개사', oblig_fld='')
#  그래서 단순히 이어붙이면 "공인중개사 · 공인중개사" 가 된다 → 중복을 걷어낸다.
#
#  ★ 남은 한계 — 수행직무가 있는 건 389/613(63%) 뿐이다.
#    CSV 에 없는 202종(국가유산수리기능자·관광통역안내사 등)은 머리만으로 임베딩된다.
#    cert_job 이 채워지면 직업명을 덧붙이고 --all 로 다시 돌릴 것.
def build_text(row):
    """row = (cert_id, jm_name, grade_std, oblig_fld, mdoblig_fld, job_desc, entry_free)"""
    parts, seen = [], set()
    for x in row[1:5]:
        x = (x or '').strip()
        if x and x not in seen:
            seen.add(x)
            parts.append(x)
    head = ' · '.join(parts)
    desc = re.sub(r'\s+', ' ', row[5] or '').strip()[:JOB_DESC_LIMIT]
    return f'{head}\n{desc}' if desc else head


# ── content_hash — '이 자격증이 어떤 텍스트로 임베딩됐는가'의 지문 ───
#  왜 필요한가
#    이게 없으면 「최신화」를 누를 때마다 613종을 전부 다시 임베딩해야 한다.
#    무엇이 바뀌었는지 알 수 없기 때문이다. 관리자 화면의 "변경 N건" 도 이 비교에서 나온다.
#  ★ 해시 대상은 build_text() 그대로다 — '임베딩에 실제로 들어간 텍스트'여야 한다.
#    예: 진로전망(career_outlook)은 임베딩에 안 쓰므로 해시에도 안 들어간다.
#    안 그러면 표시용 필드만 고쳐도 "변경됨"으로 잡혀 쓸데없이 재임베딩한다.
def content_hash(row):
    return hashlib.sha256(build_text(row).encode('utf-8')).hexdigest()


def write_hash_and_log(conn, rows, saved, already_n, n_new, n_changed,
                       status='ok', msg=''):
    """content_hash 기록 + itda_sync_log 남기기.

    ★ '이번에 임베딩한 것'뿐 아니라 '이미 Pinecone 에 있던 것'에도 해시를 남긴다.
      반쪽만 채우면 다음 실행에서 해시 비교가 성립하지 않는다.

    ★ 2026-08-02 — 관리자 화면이 읽는 값을 바로잡았다.
      전에는 updated 에 '해시를 쓴 행 수'(=전체 613)를 넣어서, 화면에 "변경 613건" 처럼
      **거짓이 뜨는 상태**였다. 실제로 바뀐 건 277종이었다.
      이제 diff_by_hash() 가 가른 값을 그대로 넣는다:
          inserted = 신규(해시가 없던 것)   updated = 변경(해시가 다른 것)
    """
    hashed = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), 500):
            cur.executemany("UPDATE certification SET content_hash=%s WHERE cert_id=%s",
                            [(content_hash(r), r[0]) for r in rows[i:i + 500]])
            hashed += min(500, len(rows) - i)
    #  ★ --all 이면 already 와 saved 가 같은 대상을 두 번 세므로 더하면 안 된다
    #    (실측: 613 + 613 = 1226 으로 찍혔는데 실제 Pinecone 은 613)
    total = max(already_n, saved) if FORCE else already_n + saved
    SYNC.write(conn, fetched=len(rows), inserted=n_new, updated=n_changed,
               embedded=saved, status=status,
               message=msg or f'Pinecone "{NAMESPACE}" 누적 {total}개 · 해시 {hashed}행')
    print(f'content_hash 기록 {hashed}행 · 신규 {n_new} · 변경 {n_changed}')


# ── 검색할 때 거르는 데 쓸 메타데이터 ───────────────────────────────
#  entry_free 는 1일 때만 넣는다.
#    · Pinecone 은 None 을 못 받는다
#    · False 로 넣으면 '조건 있음'으로 읽혀, 사실은 미확인인 447종을 잘못 단정하게 된다
#  키가 없으면 '미확인'이다. 「지금 바로」 축은 filter={'entry_free': True} 로 166종만 뽑는다.
def build_meta(row):
    m = {'jm_name': row[1] or '', 'grade': row[2] or '', 'oblig_fld': row[3] or ''}
    if row[6] == 1:
        m['entry_free'] = True
    return m


# ── .env ───────────────────────────────────────────────────────────
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
    raise SystemExit('PINECONE_API_KEY 없음 (.env 확인)')


# ── DB 에서 자격증 읽기 ─────────────────────────────────────────────
conn = db_conn()
with conn.cursor() as cur:
    # grade 가 아니라 grade_std 를 쓴다 — grade(=Q-Net seriesnm)는 산업기사 114종을
    # '기사'로 뭉뚱그린다. set_entry_note_등급조건.py 가 보정한 값이 grade_std 다.
    cur.execute("SELECT cert_id, jm_name, COALESCE(grade_std, grade), oblig_fld, "
                "       mdoblig_fld, job_desc, entry_free "
                "FROM certification ORDER BY cert_id")
    rows = cur.fetchall()

texts = [build_text(r) for r in rows]
tot_chars = sum(len(t) for t in texts)
est_tok = int(tot_chars / 2.2)

print(f'자격증 {len(rows)}종')
print(f'평균 길이 {tot_chars // max(len(texts), 1)}자 · 총 {tot_chars:,}자 ≈ {est_tok:,} 토큰')
print(f'예상 비용 약 {est_tok / 1_000_000 * 0.20 * 1400:.0f}원\n')

print('── 텍스트 미리보기 ──')
# 등급이 다양하게 보이도록 앞·중간·뒤에서 뽑는다
n = len(texts)
for i in [0, 1, 2, n // 3, n // 2, n * 2 // 3, n - 3, n - 2, n - 1]:
    if 0 <= i < n:
        print(f'  [{rows[i][0]:>4}] {texts[i]}')
print()

# 분야가 비어 결과가 빈약한 것이 몇 개인지 — 알고 넘어가야 한다
thin = [t for t in texts if len(t) < 12]
print(f'텍스트가 12자 미만인 종목: {len(thin)}개'
      + (f'  예: {", ".join(thin[:5])}' if thin else ''))

if DRY:
    print('\n--dry 지정 → 임베딩하지 않고 종료')
    conn.close()
    raise SystemExit


# ── Gemini 임베딩 (키 로테이션) ────────────────────────────────────
_ki = 0
def embed(batch_texts):
    global _ki
    body = json.dumps({'requests': [
        {'model': f'models/{MODEL}', 'content': {'parts': [{'text': t}]}}
        for t in batch_texts]}).encode()
    wait = 65
    for attempt in range(1, 41):
        key = GEMINI_KEYS[_ki % len(GEMINI_KEYS)]
        url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'{MODEL}:batchEmbedContents?key={key}')
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={'Content-Type': 'application/json'})
            j = json.loads(urllib.request.urlopen(req, timeout=90).read().decode())
            return [e['values'] for e in j['embeddings']]
        except urllib.error.HTTPError as e:
            if e.code in (429, 403, 503):
                _ki += 1
                if attempt % len(GEMINI_KEYS) == 0:
                    print(f'    ⏳ 한도 도달 — {wait}초 대기 후 재개 (시도 {attempt})', flush=True)
                    time.sleep(wait)
                    wait = min(wait + 30, 185)
                else:
                    time.sleep(2)
                continue
            raise
        except Exception:
            time.sleep(5)
    raise SystemExit('한도가 오래 안 풀림 → 내일 다시 실행 (이미 넣은 건 건너뜁니다)')


# ── Pinecone ───────────────────────────────────────────────────────
#  인덱스 생성·id 수집 로직은 _common 에 있다(embed_course·embed_jobs 와 공유).
index = pinecone_index()
print(f'Gemini 키 {len(GEMINI_KEYS)}개 · 인덱스 "{INDEX_NAME}" · 네임스페이스 "{NAMESPACE}"')
already = already_ids(index, NAMESPACE)
print(f'네임스페이스 "{NAMESPACE}" 에 이미 {len(already)}개 있음')

#  ★ 저장된 해시와 비교해 '신규 / 변경'을 가른다(2026-08-02).
#    관리자 화면의 「신규 N건 · 변경된 N건」이 이 값이다.
n_new_set, n_chg_set = diff_by_hash(conn, 'certification', 'cert_id', rows, content_hash)
print(f'해시 비교 — 신규 {len(n_new_set)} · 변경 {len(n_chg_set)} · '
      f'그대로 {len(rows) - len(n_new_set) - len(n_chg_set)}')

pairs = list(zip(rows, texts))
if FORCE:
    todo = pairs
    print('★ --all 지정 → 전부 다시 임베딩')
else:
    #  ★ 건너뛰기 기준이 두 개다(2026-08-02).
    #    예전엔 'Pinecone 에 id 가 있나' 뿐이라, 내용이 바뀌어도 건너뛰었다.
    #    그래서 재임베딩할 때마다 --all 로 전체를 돌려야 했다. 이제 바뀐 것도 포함한다.
    todo = [(r, t) for r, t in pairs
            if str(r[0]) not in already or str(r[0]) in n_chg_set]
print(f'임베딩할 것 {len(todo)}개\n')

if not todo:
    #  임베딩할 게 없어도 해시는 남긴다 — 해시가 비어 있으면 관리자 화면의
    #  「변경 N건」이 계산되지 않고, 다음 실행에서도 비교 기준이 없다.
    print('임베딩할 것 없음 — content_hash 만 갱신한다.')
    write_hash_and_log(conn, rows, 0, len(already), len(n_new_set), len(n_chg_set),
                       msg='임베딩 없음(전부 최신)')
    conn.close()
    raise SystemExit


# ── 배치 임베딩 + upsert ───────────────────────────────────────────
saved = 0
t0 = time.time()
for i in range(0, len(todo), BATCH):
    chunk = todo[i:i + BATCH]
    vecs = embed([t for _, t in chunk])
    index.upsert(namespace=NAMESPACE,
                 vectors=[{'id': str(r[0]), 'values': v, 'metadata': build_meta(r)}
                          for (r, _), v in zip(chunk, vecs)])
    saved += len(chunk)
    el = time.time() - t0
    print(f'  {saved}/{len(todo)}  ({saved * 100 // len(todo)}%)  경과 {int(el)}초', flush=True)
    if i + BATCH < len(todo):
        time.sleep(SLEEP)

write_hash_and_log(conn, rows, saved, len(already), len(n_new_set), len(n_chg_set))
print(f'\n자격증 임베딩 완료: {saved}개 (네임스페이스 "{NAMESPACE}")')
conn.close()
