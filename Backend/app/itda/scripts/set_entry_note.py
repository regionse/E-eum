# -*- coding: utf-8 -*-
"""
certification.grade_std / entry_note 채우기 — 등급별 응시자격 조건
──────────────────────────────────────────────────────────
실행 :  python set_entry_note_등급조건.py         (--dry 로 미리보기)

무엇을 하나
  ① grade_std  — 종목명 접미사로 판정한 '실제 응시 등급'
  ② entry_note — 그 등급의 응시자격 조건 목록 (Q-Net 실측)

왜 grade 를 그대로 못 쓰나
  certification.grade 는 Q-Net 종목마스터의 seriesnm 을 그대로 넣은 값인데,
  seriesnm 은 산업기사를 '기사'로 뭉뚱그린다 (실측: 117종).
      전기산업기사  grade='기사'   ← 실제 등급은 산업기사
  이대로 조건을 붙이면 전기산업기사에 '관련학과 대학졸업자'가 달린다.
  실제 산업기사 조건은 '전문대졸' 또는 '기능사+1년'이라 훨씬 낮다.
  → 더 어려운 조건으로 잘못 표시하는 셈이고, 학업을 놓은 대상자에게 가장 나쁜 오류다.

  grade 는 건드리지 않는다(팀 ERD 의 정의이고 다른 코드가 쓸 수 있다).
  판정 결과는 grade_std 에 따로 담고, 잇다는 이쪽을 본다.
  ※ 근본 수정은 load_certification.py 에서 등급을 제대로 넣는 것. 지금은 여기서 보정한다.

조건 출처
  Q-Net InquiryExamQualItemSVC/getList — 등급별 응시자격 조건 128건.
  이 API 는 '등급 → 조건 목록'만 준다. '종목 → 조건'은 어디에서도 안 준다.
  국가기술자격은 응시자격이 등급별로 법정돼 있어 종목 간 차이가 거의 없다
  (613종 중 등급 규칙에서 벗어난 예외는 3종뿐 — set_entry_free_응시자격.py 참고).
  그래서 entry_note 는 "이 종목의 조건"이 아니라 "이 등급의 조건"으로 표시해야 한다.
"""
import os, sys, re, getpass
import urllib.request, urllib.parse
import pymysql

DRY = '--dry' in sys.argv
API = 'http://openapi.q-net.or.kr/api/service/rest/InquiryExamQualItemSVC/getList'


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


# ── ① 등급 판정 ────────────────────────────────────────────────────
#  grade(=seriesnm) 를 기본으로 믿되, '기사' 하나만 종목명으로 쪼갠다.
#
#  왜 grade 를 통째로 접미사로 갈아엎지 않나 — 실측(2026-07-23)으로 확인:
#    grade='기능사' 163종 중 13종은 이름이 '기능사'로 안 끝난다.
#      미용사(네일)·이용사·보석감정사        → 이름만 다를 뿐 기능사 등급이 맞다
#      염색기능사(날염)·광산보안기능사(화약분야) → 괄호 세부분야
#      공구제작기능사보 등 3종               → 기능사보(폐지된 하위등급)
#    grade='기능장' 29종 중 미용장·이용장도 '기능장'으로 안 끝난다.
#    → 이들에 접미사 규칙을 대면 전부 '단일등급'으로 오판한다. grade 가 더 정확하다.
#
#  어긋나는 건 '기사' 242종 하나뿐이다. seriesnm 이 산업기사·단일등급·1급·2급을
#  전부 '기사'로 뭉뚱그린다(실측 114+14+5+5=138종). 여기만 종목명으로 가른다.
def judge_grade(jm_name, grade, qual_gb):
    if qual_gb != '국가기술자격':
        return None                      # 국가전문자격은 이 등급 체계 밖
    if grade != '기사':
        return grade                     # 기능사·기술사·기능장은 그대로 신뢰
    n = (jm_name or '').strip()
    if n.endswith('산업기사'):
        return '산업기사'
    if n.endswith('기사'):
        return '기사'
    if '1급' in n:
        return '1급'
    if '2급' in n:
        return '2급'
    return '단일등급'                     # 등급 구분이 없는 국가기술자격


# ── ② Q-Net 등급별 조건 ────────────────────────────────────────────
def fetch_conditions():
    url = API + '?' + urllib.parse.urlencode(
        {'serviceKey': ENV['DATA_GO_KR_KEY'], 'numOfRows': '500', 'pageNo': '1'}, safe='%')
    raw = urllib.request.urlopen(url, timeout=40).read().decode('utf-8', 'replace')
    if '<resultCode>00</resultCode>' not in raw:
        rc = re.search(r'<resultCode>(.*?)</resultCode>', raw)
        raise SystemExit(f'API 실패 resultCode={rc.group(1) if rc else "?"} — 그대로 중단한다')
    out = {}
    for it in re.findall(r'<item>(.*?)</item>', raw, re.S):
        def g(t):
            m = re.search(f'<{t}>(.*?)</{t}>', it, re.S)
            return m.group(1).strip() if m else ''
        out.setdefault(g('grdNm'), []).append(g('emqualDispNm'))
    return out

COND = fetch_conditions()
print(f'Q-Net 응시자격 조건 {sum(len(v) for v in COND.values())}건 · 등급 {len(COND)}종')
for k, v in sorted(COND.items(), key=lambda x: -len(x[1])):
    print(f'    {k:<10} {len(v):>3}건')


# ── DB ──────────────────────────────────────────────────────────────
pw = ENV.get('DB_PASSWORD') or getpass.getpass('user2604 DB 비밀번호: ')
conn = pymysql.connect(host='localhost', port=3306, user='user2604',
                       password=pw, database='eum', charset='utf8mb4')

NEW_COLS = [('grade_std', "VARCHAR(20)", '실제 응시 등급 (종목명 접미사 판정 · grade 보정)'),
            ('entry_note', 'TEXT',       '해당 등급의 응시자격 조건 (Q-Net)')]
with conn.cursor() as cur:
    cur.execute("""SELECT COLUMN_NAME FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='certification'""")
    have = {r[0] for r in cur.fetchall()}
    for col, typ, cmt in NEW_COLS:
        if col in have:
            continue
        if DRY:
            print(f'  (--dry) 컬럼 추가 예정: {col} {typ}')
        else:
            cur.execute(f"ALTER TABLE certification ADD COLUMN `{col}` {typ} COMMENT '{cmt}'")
            print(f'  컬럼 추가: certification.{col}')
    conn.commit()

with conn.cursor() as cur:
    cur.execute("SELECT cert_id, jm_name, grade, qual_gb FROM certification")
    rows = cur.fetchall()

updates, changed, nocond = [], [], []
import collections
tally = collections.Counter()
for cid, name, grade, qgb in rows:
    gs = judge_grade(name, grade, qgb)
    tally[gs] += 1
    if gs and gs != grade:
        changed.append((name, grade, gs))
    conds = COND.get(gs) if gs else None
    note = ('· ' + '\n· '.join(conds)) if conds else None
    if gs and not conds:
        nocond.append((name, gs))
    updates.append((gs, note, cid))

print(f'\n── 등급 판정 결과 ({len(rows)}종) ──')
for g, n in tally.most_common():
    src = f"조건 {len(COND.get(g, []))}건" if g else '국가전문자격 — 등급 체계 밖'
    print(f'  {str(g or "(없음)"):<12} {n:>4}종   {src}')

print(f'\n── grade 와 달라진 것 {len(changed)}종 ──')
sample = collections.Counter((a, b) for _, a, b in changed)
for (old, new), n in sample.most_common():
    ex = next(nm for nm, o, s in changed if o == old and s == new)
    print(f'  {old} → {new}  {n:>4}종   예) {ex}')
if nocond:
    print(f'\n  ⚠ 등급은 정해졌는데 조건이 없는 것 {len(nocond)}종: {[n for n,_ in nocond[:5]]}')

with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM certification WHERE grade='기능사'")
    old_fn = cur.fetchone()[0]
print(f'\n  기능사 판정 검증: 접미사 {tally.get("기능사", 0)}종  vs  기존 grade {old_fn}종'
      f'   {"일치 ✅" if tally.get("기능사") == old_fn else "★ 불일치 — 확인 필요"}')

if DRY:
    print('\n--dry 지정 → 쓰지 않고 종료')
    conn.close()
    raise SystemExit

with conn.cursor() as cur:
    cur.executemany("UPDATE certification SET grade_std=%s, entry_note=%s WHERE cert_id=%s",
                    updates)
conn.commit()
print(f'\n✅ {len(updates)}종 갱신 완료')

with conn.cursor() as cur:
    cur.execute("SELECT jm_name, grade, grade_std, entry_note FROM certification "
                "WHERE jm_name IN ('전기산업기사','전기기능사','일반기계기사')")
    for n, g, gs, note in cur.fetchall():
        print(f'\n  {n}   grade={g} → grade_std={gs}')
        for line in (note or '(조건 없음)').split('\n')[:3]:
            print(f'     {line[:66]}')
conn.close()
