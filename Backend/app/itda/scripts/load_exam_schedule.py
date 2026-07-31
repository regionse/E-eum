# -*- coding: utf-8 -*-
"""
Q-Net 시험일정 API(#1) → MySQL `exam_schedule` 적재 배치
──────────────────────────────────────────────────────────
실행 :  python load_exam_schedule.py            (613종 전부)
        python load_exam_schedule.py 기능사     (특정 등급만)
동작 :  ① certification에서 jm_cd 목록을 읽고
        ② 자격증마다 API#1을 호출(루프)해서 회차별 시험일을 받아
        ③ exam_schedule에 cert_id로 연결해 저장한다.

★ 2026-07-23 수정 — 기능사만 받고 있었다.
  전에는 `WHERE grade='기능사'` 가 박혀 있어서 163종만 받았고,
  그래서 「그 다음 단계」로 산업기사·기사를 추천해놓고 시험일을 못 보여줬다.
  ("다음 시험 일정이 아직 공고되지 않았어요" 는 공고가 안 된 게 아니라 우리가 안 받아온 것)

★ qualgbCd 는 자격구분에 따라 달라진다 (실사 2026-07-23)
      국가기술자격 513종 → 'T'
      국가전문자격 100종 → 'S'     ※ 'T' 로 부르면 0건이 온다. 오래 못 찾던 이유
"""
import os, sys, time, getpass, json
import urllib.request, urllib.parse
import pymysql

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# ── ① API 키 (certification 배치와 동일) ───────────────────────────
def get_api_key():
    k = os.environ.get('DATA_GO_KR_KEY')
    if k:
        return k.strip()
    for p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env'),
              '.env', 'etc/.env', '../etc/.env', '../../etc/.env']:
        try:
            for line in open(p, encoding='utf-8'):
                if line.strip().startswith('DATA_GO_KR_KEY') and '=' in line:
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
        except FileNotFoundError:
            continue
    return input('DATA_GO_KR_KEY 붙여넣기: ').strip()


API_KEY = get_api_key()
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
ENDPOINT = 'http://apis.data.go.kr/B490007/qualExamSchd/getQualExamSchdList'
YEAR = '2026'   # 올해 시험일정 (Q-Net은 당해년도만 보유)


# ── ② 시험일정 fetch (JSON — certification의 XML과 다름) ─────────────
QUALGB = {'국가기술자격': 'T', '국가전문자격': 'S'}   # 실사로 확인한 코드

def fetch_schedule(jm_cd, qual_gb):
    url = ENDPOINT + '?' + urllib.parse.urlencode(
        {'serviceKey': API_KEY, 'dataFormat': 'json', 'implYy': YEAR,
         'qualgbCd': QUALGB.get(qual_gb, 'T'),
         'jmCd': jm_cd, 'numOfRows': 50, 'pageNo': 1})
    for _ in range(5):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            body = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', 'replace')
            j = json.loads(body)
            if j.get('header', {}).get('resultCode', '') in ('00', '0'):
                return j.get('body', {}).get('items') or []   # 성공(빈 것도 정상)
        except Exception:
            pass
        time.sleep(0.4)   # 실패/에러코드 → 재시도
    return []


def to_date(s):
    """'YYYYMMDD' → 'YYYY-MM-DD',  빈 값 → None(NULL)"""
    s = (s or '').strip()
    return f'{s[:4]}-{s[4:6]}-{s[6:]}' if len(s) == 8 else None


# ── ③ DB 접속 ──────────────────────────────────────────────────────
def _env(key):
    v = os.environ.get(key)
    if v:
        return v
    for p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env'),
              '.env', 'etc/.env', '../etc/.env', '../../etc/.env']:
        try:
            for line in open(p, encoding='utf-8'):
                if line.strip().startswith(key) and '=' in line:
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
        except FileNotFoundError:
            continue
    return None

pw = _env('DB_PASSWORD') or getpass.getpass('user2604 DB 비밀번호: ')
conn = pymysql.connect(host=_env('DB_HOST', 'localhost'),
                       port=int(_env('DB_PORT', 3306)),
                       user=_env('DB_USER', 'user2604'),
                       password=pw,
                       database=_env('DB_NAME', 'eum'),
                       charset='utf8mb4')

# ── ④ 대상 목록 (루프의 '재료') ─────────────────────────────────────
#  등급 인자를 주면 그 등급만, 없으면 613종 전부.
ONLY = next((a for a in sys.argv[1:] if not a.startswith('-')), None)
SQL = ("SELECT cert_id, jm_cd, jm_name, qual_gb, COALESCE(grade_std, grade) "
       "FROM certification ")
params = ()
if ONLY:
    SQL += "WHERE COALESCE(grade_std, grade)=%s "
    params = (ONLY,)
SQL += "ORDER BY cert_id"
with conn.cursor() as cur:
    cur.execute(SQL, params)
    certs = cur.fetchall()
if not certs:
    raise SystemExit(f'대상이 없습니다 (등급 "{ONLY}")')
print(f'대상 {len(certs)}종{f" — 등급 {ONLY}" if ONLY else " (전체)"}')
print(f'예상 시간 약 {len(certs) * 0.6 / 60:.0f}분 · API 무료\n')

INSERT = """
INSERT INTO exam_schedule
  (cert_id, impl_year, impl_seq, round_name,
   doc_reg_start, doc_reg_end, doc_exam_start, doc_exam_end, doc_pass_dt,
   prac_reg_start, prac_reg_end, prac_exam_start, prac_exam_end, prac_pass_dt)
VALUES (%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s,%s,%s)
"""

# ── ⑤ 루프: 자격증마다 API 호출 → 회차들 저장 ────────────────────────
import collections
total, empty = 0, 0
by_grade = collections.defaultdict(lambda: [0, 0])   # 등급 → [종목수, 일정있음]
t0 = time.time()
with conn.cursor() as cur:
    for i, (cert_id, jm_cd, jm_name, qual_gb, grade) in enumerate(certs, 1):
        rows = fetch_schedule(jm_cd, qual_gb)
        cur.execute("DELETE FROM exam_schedule WHERE cert_id=%s", (cert_id,))  # 재실행 안전
        g = grade or '(전문자격)'
        by_grade[g][0] += 1
        if rows:
            by_grade[g][1] += 1
        else:
            empty += 1
        for r in rows:
            if not r.get('implYy') or r.get('implSeq') is None:
                continue   # 필수값 없으면 건너뜀
            cur.execute(INSERT, (
                cert_id, r.get('implYy'), r.get('implSeq'), r.get('description'),
                to_date(r.get('docRegStartDt')), to_date(r.get('docRegEndDt')),
                to_date(r.get('docExamStartDt')), to_date(r.get('docExamEndDt')),
                to_date(r.get('docPassDt')),
                to_date(r.get('pracRegStartDt')), to_date(r.get('pracRegEndDt')),
                to_date(r.get('pracExamStartDt')), to_date(r.get('pracExamEndDt')),
                to_date(r.get('pracPassDt'))))
            total += 1
        conn.commit()          # 자격증마다 커밋 → 중간에 끊겨도 진행분 저장
        if i % 50 == 0:
            el = time.time() - t0
            eta = el / i * (len(certs) - i)
            print(f'  {i}/{len(certs)}  누적 {total:,}행 · 경과 {int(el)}초 · 남은시간 약 {int(eta)}초',
                  flush=True)
        time.sleep(0.1)        # 서버 예의상 살짝 쉼

print(f'\n✅ exam_schedule 적재 완료: {total:,}행 '
      f'({len(certs)}종 중 일정없음 {empty}종)')
print(f'\n{"등급":<14}{"종목":>5}{"일정있음":>8}')
for g, (n, h) in sorted(by_grade.items(), key=lambda x: -x[1][0]):
    print(f'  {g:<14}{n:>5}{h:>8}')
conn.close()
