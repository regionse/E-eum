# -*- coding: utf-8 -*-
"""
Q-Net 종목별 시험정보 CSV → certification 상세 컬럼 적재
──────────────────────────────────────────────────────────
실행 :  python load_cert_상세.py
원본 :  etc/data/qnet_종목별시험정보_20251231.csv
        (공공데이터포털 · 한국산업인력공단_국가기술자격 종목별 시험정보)

왜 필요한가
  자격증 임베딩 텍스트가 너무 얇았다.
      "전기기능사 · 기능사 · 전기.전자 · 전기"
  자격증명은 전문용어라 "고치는 거 좋아해요" 같은 일상어와 어휘가 안 겹친다.
  CSV 의 '수행직무'가 그 간극을 메운다.
      "전기 장비·공구로 회전기, 제어장치, 전선·케이블을 설치, 보수, 검사, 관리"
      → '보수'·'검사'·'관리' 로 사용자 발화와 걸린다.

CSV 구조 (긴 형식)
  종목명 | 항목 | 내용     ← 한 종목이 8행으로 흩어져 있다
  항목 8종: 개요 / 수행직무 / 취득방법 / 진로 및 전망 / 변천과정 /
            실시기관명 / 실시기관 홈페이지 / 위 자격취득자에 대한 법령상 우대현황

실측 커버리지 (2026-07-23)
  CSV 488종 ↔ 우리 613종 → 매칭 411종(67%) · 수행직무 있음 389종(63%)
  국가유산수리기능자(24)·관광통역안내사(12) 등 국가전문자격 계열은 CSV에 아예 없다.
  → 나머지 224종은 기존 텍스트(종목명·등급·분야)만으로 임베딩된다. 알고 쓸 것.

※ '응시자격'은 여기서 안 채운다.
  취득방법 안에 '⑥ 응시자격' 이 있는 종목이 411종 중 18종뿐이라(서식 불일치) 파싱이 무의미하다.
  entry_free 는 등급 규칙(기능사=1, 기사·산업기사·기술사·기능장=0)으로 채우는 게 정확하다.
"""
import os, sys, csv, io, re, getpass
import pymysql

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', 'data', 'qnet_종목별시험정보_20251231.csv')

# CSV 항목명 → certification 컬럼
FIELDS = {
    '수행직무':      ('job_desc',       'TEXT', '수행직무 (임베딩·카드 표시)'),
    '진로 및 전망':  ('career_outlook', 'TEXT', '진로 및 전망'),
    '취득방법':      ('exam_method',    'TEXT', '시험과목·검정방법·합격기준'),
}

DRY = '--dry' in sys.argv


def read_env():
    d = {}
    for p in ['.env', 'etc/.env', '../etc/.env', '../../etc/.env',
              r'C:\e-um-1\e-um\etc\.env']:
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


# ── CSV 읽기 (긴 형식 → 종목별 dict) ────────────────────────────────
def norm(s):
    """종목명 대조용. 공백·괄호·가운뎃점·하이픈 차이를 무시한다."""
    return re.sub(r'[\s()·\-]', '', s or '')

txt = open(CSV_PATH, 'rb').read().decode('utf-8-sig')
byname = {}
for r in list(csv.reader(io.StringIO(txt)))[1:]:
    if len(r) > 2 and r[2].strip():
        byname.setdefault(r[0], {})[r[1]] = r[2].strip()

lookup = {}
dup = 0
for k, v in byname.items():
    n = norm(k)
    if n in lookup:
        dup += 1
        continue                     # 정규화 충돌 — 먼저 온 것을 유지
    lookup[n] = v
print(f'CSV 종목 {len(byname)}종 (정규화 충돌 {dup}건 무시)')


# ── DB ──────────────────────────────────────────────────────────────
pw = ENV.get('DB_PASSWORD') or getpass.getpass('user2604 DB 비밀번호: ')
conn = pymysql.connect(host='localhost', port=3306, user='user2604',
                       password=pw, database='eum', charset='utf8mb4')

# 컬럼이 없으면 만든다 (ADD COLUMN 은 기존 데이터를 건드리지 않는다)
with conn.cursor() as cur:
    cur.execute("""SELECT COLUMN_NAME FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='certification'""")
    have = {r[0] for r in cur.fetchall()}
    for _, (col, typ, comment) in FIELDS.items():
        if col in have:
            continue
        if DRY:
            print(f'  (--dry) 컬럼 추가 예정: {col} {typ}')
            continue
        cur.execute(f"ALTER TABLE certification ADD COLUMN `{col}` {typ} "
                    f"COMMENT '{comment}'")
        print(f'  컬럼 추가: certification.{col}')
    conn.commit()

with conn.cursor() as cur:
    cur.execute('SELECT cert_id, jm_name FROM certification')
    certs = cur.fetchall()

cols = [c for _, (c, _, _) in FIELDS.items()]
updates, miss = [], []
stat = {c: 0 for c in cols}
for cid, name in certs:
    src = lookup.get(norm(name))
    if not src:
        miss.append(name)
        continue
    vals = []
    for item, (col, _, _) in FIELDS.items():
        v = src.get(item) or None
        if v:
            stat[col] += 1
        vals.append(v)
    if any(vals):
        updates.append(tuple(vals) + (cid,))

print(f'\n우리 자격증 {len(certs)}종')
print(f'  CSV 매칭   {len(updates):>4}종 ({len(updates) * 100 // len(certs)}%)')
print(f'  미매칭     {len(miss):>4}종')
for c in cols:
    print(f'    {c:<16} {stat[c]:>4}종')
if miss:
    print(f'\n  미매칭 예시: {", ".join(miss[:8])}')

if DRY:
    print('\n--dry 지정 → 쓰지 않고 종료')
    conn.close()
    raise SystemExit

with conn.cursor() as cur:
    cur.executemany(
        f"UPDATE certification SET {', '.join(f'`{c}`=%s' for c in cols)} "
        f"WHERE cert_id=%s", updates)
conn.commit()
print(f'\n✅ {len(updates)}종 갱신 완료')
conn.close()
