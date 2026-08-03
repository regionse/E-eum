# -*- coding: utf-8 -*-
"""
K-MOOC 강좌 → MySQL `course` 적재 배치 (목록 + 상세)
──────────────────────────────────────────────────────────
실행 :  python load_course_강좌.py
동작 :  ① 목록 API로 '공개(public)' 강좌 id를 모으고
        ② 각 강좌의 상세 API로 분류·요약까지 받아 course에 넣는다.
왜 공개만? : 상세를 17,417개 다 부르면 하루 한도(10,000)를 넘어서.
             들을 수 있는 '공개' 강좌만 받으면 한도 안에 들어오고, 어차피 추천도 공개만 함.

★ 서버 보호(제한) 장치 3개:
   1) 호출 사이 sleep(0.15)      → 초당 과다호출 방지
   2) MAX_CALLS(9,500) 가드       → 하루 한도 넘기 전에 멈춤
   3) 이미 넣은 강좌는 건너뜀       → 재실행 시 한도 절약 + 이어받기
"""
import os
import sys
import re
import time
import json
import urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed


#  ★ 2026-07-31 — env 로더·DB 접속·Pinecone 준비를 공용 모듈(_common.py)로 옮겼다.
#    전에는 배치 10개가 각자 갖고 있어서, 한 곳만 고치면 될 일을 매번 7~8곳에서 고쳤다.
try:
    from ._common import setup_console, ENV, db_conn      # noqa: F401
except ImportError:                                       # 파일 직접 실행
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _common import setup_console, ENV, db_conn       # noqa: F401

setup_console()
MAX_CALLS = 9500     # 하루 한도(10,000) 버퍼
SIZE      = 100
WORKERS   = 10       # ★ 동시 요청 수. 10≈초당 ~20개. 늘리면 빠름(근데 너무 크면 data.go.kr 오류↑). 25쯤이면 ~50/초(위험)
LIST_URL   = 'http://apis.data.go.kr/B552881/kmooc_v2_0/courseList_v2_0'
DETAIL_URL = 'http://apis.data.go.kr/B552881/kmooc_v2_0/courseDetail_v2_0'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')


#  ── DB 접속 정보도 .env 에서 읽는다 (2026-07-31) ──────────────────
#  전에는 host='localhost', user='user2604', database='eum' 이 박혀 있었다.
#  서버에서는 DB 가 RDS 에 있으므로 localhost 를 보면 죽는다.
#  관리자 화면의 「최신화」 버튼이 이 스크립트를 부르므로 헤드리스로도 돌아야 한다.
API_KEY = ENV.get('DATA_GO_KR_KEY')
calls = 0   # ← 오늘 호출한 총 횟수 (제한 가드용)


def api_get(url):
    """호출 1회 + 재시도. 호출할 때마다 calls 증가 + sleep(0.15)."""
    global calls
    calls += 1
    for _ in range(5):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            body = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'replace')
            j = json.loads(body)
            if j.get('resultCode') == '00':
                time.sleep(0.05)     # ← 제한장치 ①: 초당 과다호출 방지
                return j
        except Exception:
            pass
        time.sleep(0.5)
    time.sleep(0.15)
    return None


def strip_html(s):
    s = re.sub(r'<[^>]+>', ' ', s or '')
    s = s.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return re.sub(r'\s+', ' ', s).strip()[:3000]


# ── DB 접속 ─────────────────────────────────────────────────────────
conn = db_conn()

# ── ① 목록에서 '공개' 강좌 id 수집 ──────────────────────────────────
public_ids, page, total = [], 1, None
print('목록에서 공개 강좌 id 수집 중...')
while calls < MAX_CALLS:
    j = api_get(LIST_URL + '?' + urllib.parse.urlencode(
        {'ServiceKey': API_KEY, 'Page': page, 'Size': SIZE}))
    if not j:
        break
    if total is None:
        total = int(j.get('totalCount', 0))
    items = j.get('items') or []
    if not items:
        break
    public_ids += [str(c['id']) for c in items if c.get('public_yn') == 'Y' and c.get('id')]
    if total and page * SIZE >= total:
        break
    page += 1
print(f'  전체 {total}강좌 중 공개 {len(public_ids)}개')

# ── 이미 넣은 것 제외 (제한장치 ③: 재실행 절약 + 이어받기) ──────────
with conn.cursor() as cur:
    cur.execute("SELECT kmooc_id FROM course")
    have = {r[0] for r in cur.fetchall()}
todo = [cid for cid in public_ids if cid not in have]
print(f'  새로 받을 것 {len(todo)}개 (이미 {len(have)}개 있음) · 남은 호출 여유 {MAX_CALLS - calls}회')

UPSERT = """
INSERT INTO course
  (kmooc_id, title, classfy_name, middle_classfy_name, summary,
   course_url, certificate_yn, public_yn, professor)
VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
  title=VALUES(title), classfy_name=VALUES(classfy_name),
  middle_classfy_name=VALUES(middle_classfy_name), summary=VALUES(summary),
  certificate_yn=VALUES(certificate_yn), professor=VALUES(professor)
"""

# 하루 한도 가드: 오늘 여유보다 받을 게 많으면 여유만큼만 (나머지는 내일 이어받기)
budget = MAX_CALLS - calls
if len(todo) > budget:
    print(f'⚠ 오늘 여유({budget}) < 받을 것({len(todo)}) → 오늘은 {budget}개만. 내일 재실행하면 나머지.')
    todo = todo[:budget]

# ── ② 강좌별 상세를 '병렬'로 받아 저장 (WORKERS개 동시 요청) ─────────
def fetch_detail(cid):
    j = api_get(DETAIL_URL + '?' + urllib.parse.urlencode(
        {'ServiceKey': API_KEY, 'CourseId': cid}))
    return (j or {}).get('results') or {}

saved = 0
with conn.cursor() as cur:
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:      # ← 동시에 WORKERS개씩
        futures = [ex.submit(fetch_detail, cid) for cid in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            if not r.get('id') or not r.get('name'):
                continue
            cur.execute(UPSERT, (
                str(r['id'])[:50],
                (r.get('name') or '')[:300],
                r.get('classfy_name') or '미분류',
                r.get('middle_classfy_name'),
                strip_html(r.get('summary')),
                r.get('url'),
                1 if r.get('certificate_yn') == 'Y' else 0,
                1,                                   # 공개 강좌만 담음
                (r.get('professor') or '')[:30],
            ))
            conn.commit()
            saved += 1
            if i % 200 == 0:
                print(f'  {i}/{len(todo)} 저장 (오늘 API 약 {calls}회)')

print(f'✅ course 적재 완료: 이번에 {saved}행 저장 (오늘 총 API 약 {calls}회)')
conn.close()
