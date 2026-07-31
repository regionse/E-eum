# -*- coding: utf-8 -*-
"""
certification.entry_free 채우기 — '지금 바로 응시 가능한가'
──────────────────────────────────────────────────────────
실행 :  python set_entry_free_응시자격.py         (--dry 로 미리보기)

값의 의미 (3값)
  1     응시자격 제한 없음 — 근거 있음. 「지금 바로」로 밀어도 되는 것
  NULL  미확인 — 조건이 있는지 없는지 우리가 모른다. 「응시자격 확인 필요」로 표시
  (0 은 쓰지 않는다. '조건이 있다'를 확신할 근거가 없으면 NULL 이 정직하다)

근거 1 — 등급 (163종)
  Q-Net InquiryExamQualItemSVC/getList 실측(2026-07-23):
    기능사 등급에 걸린 응시자격 조건은 [T999] '제한없음' 단 1건.
    조건 카탈로그에 다른 항목이 없으므로 기능사에 응시자격이 붙는 종목은 존재할 수 없다.
    ("어떤 기능사는 자격요건이 있을 것"이라는 의심을 이 데이터가 부정한다)
  같은 API 기준 '제한없음' 항목을 가진 등급은 기능사·2급 둘뿐이고,
  단일등급·산업기사·기사·1급·기술사·기능장에는 그 항목이 아예 없다.

근거 2 — 종목별 명시 (소수)
  CSV(취득방법)에 '응시자격 : 제한없음'이 직접 적힌 종목.
  기능사가 아닌데 제한이 없는 예외를 여기서 건진다
  (실측 예: 텔레마케팅관리사·멀티미디어콘텐츠제작전문가·소비자전문상담사2급).
  ※ 우리 DB 의 grade 는 Q-Net 종목마스터의 seriesnm 을 그대로 쓴 값이라
    서비스분야 종목이 '기사'로 뭉뚱그려져 있다. 등급만으로는 이 예외를 못 잡는다.

나머지 450종은 NULL 로 둔다. 카드에서는 exam_method(취득방법) 원문을 그대로 보여주고
사용자가 직접 판단하게 한다 — 우리가 해석해서 틀리는 것보다 낫다.
"""
import os, sys, re, getpass
import pymysql

DRY = '--dry' in sys.argv


def read_env():
    d = {}
    for p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env'),
              '.env', 'etc/.env', '../etc/.env', '../../etc/.env']:
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
pw = ENV.get('DB_PASSWORD') or getpass.getpass('user2604 DB 비밀번호: ')
conn = pymysql.connect(host=ENV.get('DB_HOST', 'localhost'),
                       port=int(ENV.get('DB_PORT', 3306)),
                       user=ENV.get('DB_USER', 'user2604'),
                       password=pw,
                       database=ENV.get('DB_NAME', 'eum'),
                       charset='utf8mb4')

# 컬럼 준비
with conn.cursor() as cur:
    cur.execute("""SELECT COLUMN_NAME FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='certification'
                     AND COLUMN_NAME='entry_free'""")
    if not cur.fetchone():
        if DRY:
            print('  (--dry) 컬럼 추가 예정: entry_free BOOLEAN NULL')
        else:
            cur.execute("ALTER TABLE certification ADD COLUMN entry_free BOOLEAN NULL "
                        "COMMENT '응시자격 제한 없음(1) / 미확인(NULL)'")
            print('  컬럼 추가: certification.entry_free')
            conn.commit()

# 근거 1 — 기능사
with conn.cursor() as cur:
    cur.execute("SELECT cert_id, jm_name FROM certification WHERE grade='기능사'")
    by_grade = cur.fetchall()

# 근거 2 — 취득방법에 '응시자격 … 제한없음' 이 적힌 비(非)기능사
#   '응시자격' 뒤 40자 안에 '제한' 과 '없' 이 함께 나오면 인정한다.
#   (원문 서식이 '제한 없음' / '제한없음' 으로 갈리고 뒤에 ③④⑤ 가 붙어 이어진다)
PAT = re.compile(r'응시자격[^가-힣]{0,4}(.{0,40})', re.S)
with conn.cursor() as cur:
    cur.execute("SELECT cert_id, jm_name, grade, exam_method FROM certification "
                "WHERE grade<>'기능사' AND exam_method IS NOT NULL")
    rest = cur.fetchall()

by_text = []
for cid, name, grade, txt in rest:
    m = PAT.search(txt or '')
    if not m:
        continue
    seg = m.group(1)
    if '제한' in seg and '없' in seg:
        by_text.append((cid, name, grade))

ids = {c for c, _ in by_grade} | {c for c, _, _ in by_text}

print(f'\nentry_free = 1 로 표시할 종목')
print(f'  근거1 등급(기능사)          {len(by_grade):>4}종')
print(f'  근거2 취득방법 명시(비기능사) {len(by_text):>4}종')
for cid, name, grade in by_text:
    print(f'       · {name} ({grade})')
print(f'  합계                       {len(ids):>4}종')

with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM certification")
    total = cur.fetchone()[0]
print(f'  NULL(미확인) 로 남는 것      {total - len(ids):>4}종')

if DRY:
    print('\n--dry 지정 → 쓰지 않고 종료')
    conn.close()
    raise SystemExit

with conn.cursor() as cur:
    cur.execute("UPDATE certification SET entry_free=NULL")     # 매번 다시 계산
    cur.executemany("UPDATE certification SET entry_free=1 WHERE cert_id=%s",
                    [(c,) for c in ids])
conn.commit()

with conn.cursor() as cur:
    cur.execute("""SELECT COALESCE(entry_free,-1), COUNT(*) FROM certification
                   GROUP BY 1 ORDER BY 1 DESC""")
    print()
    for v, n in cur.fetchall():
        print(f'  entry_free = {"1   (제한없음)" if v == 1 else "NULL(미확인)"}   {n:>4}종')
print('\n✅ 완료')
conn.close()
