# -*- coding: utf-8 -*-
"""
Q-Net 종목목록 API(#4) → MySQL `certification` 적재 배치
──────────────────────────────────────────────────────────
실행 :  python load_certification.py
설치 :  pip install pymysql cryptography      (한 번만)
동작 :  ① 공공API에서 국가자격 613종목을 가져와  ② eum.certification 에 넣는다(있으면 갱신).
※ 이게 '배치'의 정석: 외부 API에서 fetch → 파싱 → DB에 적재.
"""
import os
import sys
import time
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
import pymysql   # pip install pymysql cryptography



#  ★ 2026-07-31 — env 로더·DB 접속·Pinecone 준비를 공용 모듈(_common.py)로 옮겼다.
#    전에는 배치 10개가 각자 갖고 있어서, 한 곳만 고치면 될 일을 매번 7~8곳에서 고쳤다.
try:
    from ._common import setup_console, ENV, db_conn      # noqa: F401
except ImportError:                                       # 파일 직접 실행
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _common import setup_console, ENV, db_conn       # noqa: F401

setup_console()
# ── ① API 키 확보 (하드코딩 금지 — .env나 환경변수에서) ─────────────
#  ── DB 접속 정보도 .env 에서 읽는다 (2026-07-31) ──────────────────
#  전에는 host='localhost', user='user2604', database='eum' 이 박혀 있었다.
#  서버에서는 DB 가 RDS 에 있으므로 localhost 를 보면 죽는다.
#  관리자 화면의 「최신화」 버튼이 이 스크립트를 부르므로 헤드리스로도 돌아야 한다.
API_KEY = ENV.get('DATA_GO_KR_KEY')

# ── ② 공공API 호출 → 종목 리스트 (Q-Net 서버 불안정하니 재시도) ──────
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')   # 커스텀 UA는 403 → 브라우저 UA 필수
ENDPOINT = 'http://openapi.q-net.or.kr/api/service/rest/InquiryListNationalQualifcationSVC/getList'


def fetch_certs():
    url = ENDPOINT + '?' + urllib.parse.urlencode(
        {'serviceKey': API_KEY, 'numOfRows': 2000, 'pageNo': 1})
    body = ''
    for attempt in range(6):                       # 최대 6번 재시도
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            body = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'replace')
            if '<resultCode>00' in body:           # 정상코드 00
                break
        except Exception as e:
            print(f'  재시도 {attempt + 1}/6 ({type(e).__name__})')
            time.sleep(0.5)
    root = ET.fromstring(body)                      # XML 파싱
    return [{c.tag: (c.text or '').strip() for c in it}   # <item> 하나 = 종목 하나
            for it in root.findall('.//item')]


# ── ③ MySQL 접속 (비번은 실행 시 입력 — 코드에 안 남김) ──────────────
conn = db_conn()

# ── ④ 적재 (jm_cd가 UNIQUE → 있으면 UPDATE = 재실행해도 안전) ────────
SQL = """
INSERT INTO certification (jm_cd, jm_name, grade, oblig_fld, mdoblig_fld, qual_gb, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, NOW())
ON DUPLICATE KEY UPDATE
  jm_name=VALUES(jm_name), grade=VALUES(grade),
  oblig_fld=VALUES(oblig_fld), mdoblig_fld=VALUES(mdoblig_fld),
  qual_gb=VALUES(qual_gb), updated_at=NOW()
"""

print('API에서 가져오는 중...')
certs = fetch_certs()
print(f'  {len(certs)}종목 받음')

with conn.cursor() as cur:
    for c in certs:
        cur.execute(SQL, (c.get('jmcd'), c.get('jmfldnm'), c.get('seriesnm'),
                          c.get('obligfldnm'), c.get('mdobligfldnm'), c.get('qualgbnm')))
conn.commit()                                       # 반드시 commit 해야 실제 저장됨
print(f'✅ certification 적재 완료: {len(certs)}행')
conn.close()
