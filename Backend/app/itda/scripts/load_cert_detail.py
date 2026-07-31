# -*- coding: utf-8 -*-
"""
국가기술자격 종목 정보 API → certification 상세 컬럼 적재
──────────────────────────────────────────────────────────
실행 :  python -m app.itda.scripts.load_cert_detail          (적재)
        python -m app.itda.scripts.load_cert_detail --dry    (미리보기, DB 안 건드림)

원본 :  공공데이터포털 「한국산업인력공단_국가기술자격 종목 정보」
        https://www.data.go.kr/data/15041600/openapi.do
        http://openapi.q-net.or.kr/api/service/rest/InquiryQualInfo/getList

★ 2026-07-31 — CSV 방식을 폐기하고 API 로 전환했다.
  예전에는 `etc/data/qnet_종목별시험정보_20251231.csv` 를 읽었는데 두 가지가 문제였다.
    ① 파일이 유실되면 DB 를 재구축할 방법이 없다 (실제로 유실됐다).
    ② CSV 에는 종목코드가 없어 **종목명 문자열로 매칭**해야 했다.
       공백·괄호·가운뎃점을 지워 맞춰도 613종 중 411종(67%)까지가 한계였다.
  이 API 는 응답에 `jmCd`(종목코드)가 있어 **certification.jm_cd 와 정확히 조인**된다 → 매칭 손실 0.
  진로 및 전망 채움률도 실측상 CSV(217종)보다 크게 높다 (기술사 72/79 · 기능장 28/29).

왜 수행직무가 중요한가 (CSV 시절 주석 그대로 유효)
  자격증 임베딩 텍스트가 너무 얇았다 — "전기기능사 · 기능사 · 전기.전자 · 전기".
  사용자는 "뭐 고치는 거 좋아해요" 라고 말하는데 두 문장에 겹치는 단어가 하나도 없다.
  수행직무 "…전선·케이블을 설치, 보수, 검사, 관리" 의 '보수·검사'가 그 다리를 놓는다.
  → 이 값은 embed_cert.py 의 임베딩 텍스트에 들어간다. **채우면 검색 품질이 직접 올라간다.**

한계 (알고 쓸 것)
  · seriesCd 는 01~04(기술사·기능장·기사·기능사) 뿐 → **국가기술자격 513종만** 커버한다.
    국가전문자격 100종(관광통역안내사·공인노무사·변리사 등)은 이 API 에 없다. CSV 에도 없었다.
  · `취득방법(exam_method)` 은 이 API 에 없다. CSV 로 넣어둔 기존 값(410종)은 건드리지 않고 보존한다.
  · '응시자격'도 여기서 안 채운다 — entry_free/entry_note 는 set_entry_*.py 가 등급 규칙으로 채운다.

★ Q-Net 서버는 자주 흔들린다 (2026-07-31 실측)
  같은 요청이 성공했다 실패했다 한다. 게다가 **HTTP 200 으로 오면서 본문에 에러가 담긴다**:
      <resultCode>99</resultCode>
      <resultMsg>Failed to validate a newly established connection.</resultMsg>
  예외가 안 나므로 그냥 "0건"으로 보인다. → 재시도 조건에 resultCode 검사가 반드시 필요하다.
  응답이 클수록(기술사 86KB, 기사 그 3배) 더 잘 튕긴다.
"""
import os
import re
import sys
import time
import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

import pymysql

try:
    sys.stdout.reconfigure(encoding='utf-8')      # cp949 콘솔에서 비ASCII 출력 시 죽는 것 방지
except Exception:
    pass

try:                                              # 패키지 실행·파일 직접 실행 모두 지원
    from ..env import ENV
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from env import ENV

DRY = '--dry' in sys.argv

ENDPOINT = 'http://openapi.q-net.or.kr/api/service/rest/InquiryQualInfo/getList'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')   # 커스텀 UA 는 403 → 브라우저 UA 필수
SERIES = {'01': '기술사', '02': '기능장', '03': '기사', '04': '기능사'}
TRIES = 8            # 서버가 흔들리므로 넉넉히
TIMEOUT = 180
BACKOFF = 6          # 재시도 간격(초)

STARTED_AT = datetime.datetime.now()

API_KEY = ENV.get('DATA_GO_KR_KEY')
if not API_KEY:
    raise SystemExit('DATA_GO_KR_KEY 없음 — etc/.env 확인')


# ── 응답 텍스트 정제 ────────────────────────────────────────────────
#  일부 필드에 <BODY>·<LI> 스타일시트가 통째로 섞여 온다. 실측(배관기능장 trend):
#      "LI { MARGIN-BOTTOM: 0px; ... }- 필기시험의 내용은 고객만족>자료실의 출제기준을…"
#  그대로 넣으면 카드에 CSS 가 노출되고 임베딩에도 잡음이 된다.
_CSS = re.compile(r'\b(?:BODY|P|LI|TD|TR|SPAN|DIV|TABLE|UL|OL)\s*\{[^}]*\}', re.I)
_TAG = re.compile(r'<[^>]+>')
_ENT = {'&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'"}


def clean(s):
    s = _CSS.sub(' ', s or '')
    s = _TAG.sub(' ', s)
    for k, v in _ENT.items():
        s = s.replace(k, v)
    return ' '.join(s.split()).strip()


# ── API 호출 (본문 resultCode 까지 검사하고 재시도) ─────────────────
def fetch(series_cd):
    url = ENDPOINT + '?' + urllib.parse.urlencode(
        {'serviceKey': API_KEY, 'seriesCd': series_cd})
    for t in range(1, TRIES + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            root = ET.fromstring(urllib.request.urlopen(req, timeout=TIMEOUT).read())

            #  ★ 핵심 — HTTP 200 이어도 본문이 에러일 수 있다.
            code = (root.findtext('.//resultCode') or '').strip()
            if code and code not in ('00', '0'):
                msg = (root.findtext('.//resultMsg') or '').strip()
                print(f'    시도 {t}/{TRIES} — 서버 오류 [{code}] {msg}', flush=True)
                time.sleep(BACKOFF)
                continue

            items = root.findall('.//item')
            if not items:
                print(f'    시도 {t}/{TRIES} — 0건 (서버 불안정으로 보임)', flush=True)
                time.sleep(BACKOFF)
                continue
            return items
        except Exception as e:
            print(f'    시도 {t}/{TRIES} — {type(e).__name__}: {str(e)[:70]}', flush=True)
            time.sleep(BACKOFF)
    return []


# ── 수집 ────────────────────────────────────────────────────────────
collected = {}          # jm_cd → {job_desc, career_outlook}
fetched = 0
failed_series = []

for cd, label in SERIES.items():
    print(f'[{cd} {label}] 요청...', flush=True)
    items = fetch(cd)
    if not items:
        failed_series.append(label)
        print(f'[{cd} {label}] 최종 실패 — 이 계열은 이번 실행에서 건너뜀\n', flush=True)
        continue
    fetched += len(items)
    n_job = n_car = 0
    for it in items:
        jm = (it.findtext('jmCd') or '').strip()
        if not jm:
            continue                                # 조인 키가 없으면 쓸 수 없다
        job = clean(it.findtext('job'))
        car = clean(it.findtext('career'))          # ★ 소문자 career. 포털 문서 표기(Career)와 다르다
        n_job += bool(job)
        n_car += bool(car)
        collected[jm] = {'job_desc': job, 'career_outlook': car}
    print(f'[{cd} {label}] {len(items)}건 — 수행직무 {n_job} · 진로전망 {n_car}\n', flush=True)

print(f'수집 완료: {len(collected)}종목 (응답 {fetched}건)')
if failed_series:
    print(f'※ 실패한 계열: {", ".join(failed_series)} — 다시 실행하면 그 계열만 채워진다')
if not collected:
    raise SystemExit('수집된 종목이 없어 종료 (DB 를 건드리지 않음)')


# ── DB 반영 ─────────────────────────────────────────────────────────
pw = ENV.get('DB_PASSWORD')
if not pw:
    raise SystemExit('DB_PASSWORD 없음 — etc/.env 확인')
conn = pymysql.connect(host=ENV.get('DB_HOST', 'localhost'),
                       port=int(ENV.get('DB_PORT', 3306)),
                       user=ENV.get('DB_USER', 'user2604'),
                       password=pw,
                       database=ENV.get('DB_NAME', 'eum'),
                       charset='utf8mb4')

with conn.cursor() as cur:
    cur.execute("SELECT jm_cd, jm_name, job_desc, career_outlook FROM certification")
    before = {r[0]: r for r in cur.fetchall()}

matched = [j for j in collected if j in before]
print(f'DB {len(before)}종 중 매칭 {len(matched)}종 '
      f'(API 에만 있는 코드 {len(collected) - len(matched)}개는 무시)')

#  ★ 빈 값으로 덮어쓰지 않는다.
#    API 가 그 종목의 값을 안 주는 경우가 있는데(기술사 job 74/79),
#    그때 기존 값을 지워버리면 순수한 손실이다. → 값이 있을 때만 바꾼다.
up_job = up_car = 0
rows = []
for jm in matched:
    v = collected[jm]
    _, _name, old_job, old_car = before[jm]
    if v['job_desc'] and v['job_desc'] != (old_job or ''):
        up_job += 1
    if v['career_outlook'] and v['career_outlook'] != (old_car or ''):
        up_car += 1
    rows.append((v['job_desc'] or old_job, v['career_outlook'] or old_car, jm))

print(f'변경될 것 — 수행직무 {up_job}종 · 진로전망 {up_car}종')

if DRY:
    print('\n--dry 지정 → DB 를 건드리지 않고 종료. 샘플 3건:')
    for jm in matched[:3]:
        print(f'  [{jm}] {before[jm][1]}')
        print(f'      수행직무: {(collected[jm]["job_desc"] or "(없음)")[:80]}')
        print(f'      진로전망: {(collected[jm]["career_outlook"] or "(없음)")[:80]}')
    conn.close()
    raise SystemExit(0)

with conn.cursor() as cur:
    for i in range(0, len(rows), 200):
        cur.executemany(
            "UPDATE certification SET job_desc=%s, career_outlook=%s WHERE jm_cd=%s",
            rows[i:i + 200])
conn.commit()

with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*), SUM(job_desc<>''), SUM(career_outlook<>'') FROM certification")
    tot, has_job, has_car = cur.fetchone()
print(f'적재 후 — 전체 {tot}종 · 수행직무 {has_job}종 · 진로전망 {has_car}종')

#  실행 로그 (관리자 임베딩 화면이 읽는다)
with conn.cursor() as cur:
    cur.execute(
        """INSERT INTO itda_sync_log
             (target, started_at, finished_at, fetched, inserted, updated, embedded, status, message)
           VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s)""",
        ('load_cert_detail', STARTED_AT, fetched, 0, up_job + up_car, 0,
         'partial' if failed_series else 'ok',
         f'매칭 {len(matched)}종 · 수행직무 {up_job} · 진로전망 {up_car}'
         + (f' · 실패계열 {",".join(failed_series)}' if failed_series else '')))
conn.commit()
conn.close()

print('완료. 수행직무가 바뀌었으므로 embed_cert.py --all 을 다시 돌려야 검색에 반영된다.')
