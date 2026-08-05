# -*- coding: utf-8 -*-
"""잇다 · 강좌 커버리지 표 만들기 (오프라인 1회 배치, 2026-08-03 신설)

왜 필요한가
  벡터 검색은 **항상 가장 가까운 k개를 돌려준다.** "관련 없음"이라는 출력이 없다.
  그래서 K-MOOC 에 없는 직종을 물으면 엉뚱한 강의가 확신에 차서 나온다. 실측 —
      제빵   → 실용아트 메이크업   (K-MOOC 에 제빵/제과/베이킹 강의 0건)
      가구제작 → 스마트팩토리        (가구/목공 0건)
      특수주조 → 드론 특수촬영 활용
  K-MOOC 은 대학 MOOC(인문 2,220·공학 1,938·사회 1,852)이라 기능·실무 직종을 안 덮는다.

왜 점수 문턱으로 안 하나
  리랭커 점수에 문턱을 걸어 보려 했으나 **무작위 표본에서 경계가 없었다**(연속 기울기).
  0.02 를 걸면 60% 의 직업이 강좌 0개가 되고, 그 안에 진짜 쓸모있는 것들이 섞여 있다 —
      리튬이온전지셀개발 → 이차전지이야기 (0.032) · SW공급망보안 → 사이버보안 진로설계 (0.0057)
  점수를 보정할 라벨이 없으면 생점수 문턱은 표본만 바뀌어도 뒤집힌다.

그래서 어떻게 하나
  **판단을 실행 시점에서 오프라인으로 옮긴다.** 직업마다 한 번만 LLM 에게 물어
  "이 강의들로 이 직업을 준비할 수 있나"를 판정받아 표로 저장한다.
  실행 시에는 그 표만 본다 — 결정론적이고, 공짜고, 사람이 열어보고 고칠 수 있다.

실행 (Backend/ 에서)
    python -m app.itda.scripts.build_course_coverage --limit 60   # 시험 (60종만)
    python -m app.itda.scripts.build_course_coverage              # 전체 (아직 판정 안 된 것만)
    python -m app.itda.scripts.build_course_coverage --all        # 전체 재판정
"""
import asyncio
import datetime
import json
import sys
import urllib.request

#  이 배치는 실행 엔진(match·db)을 그대로 쓰므로 **모듈로만** 실행한다.
#  다른 배치와 달리 '파일 직접 실행' 갈래를 두지 않는다 — 두면 app 패키지를 못 찾아 더 헷갈린다.
from ._common import setup_console, ENV, db_conn, SyncLog
from .. import gemini_util as _gutil
from .. import match as m
from ..db import async_session

setup_console()

MODEL = ENV.get('COURSE_LLM_MODEL') or 'gemini-3.1-flash-lite'
CAND = 5             # 직업당 강좌 후보 수
CHUNK = 8            # LLM 한 번에 판정할 직업 수 (근거가 늘어 15 → 8)
JOB_DESC_LEN = 130   # NCS 직무 정의에서 쓸 길이 (평균 104자라 대부분 통째로 들어간다)
SUMM_LEN = 140       # 강의 요약에서 쓸 길이


#  ── 강의 요약 다듬기 ────────────────────────────────────────────────
#  summary 는 평균 1,479자인데 앞부분이 학사일정·수강신청 안내인 경우가 많다.
#  실측: "학사일정 ￭ 수강신청 : 2026. 2. 16.(월) ~ … 강 좌 명 객체지향형 도면해독 … 학습목표 …"
#  그대로 앞을 자르면 날짜만 들어가 판정에 쓸모가 없다 → '내용이 시작되는 표지'부터 자른다.
_MARKERS = ('학습목표', '수업내용', '강좌 소개', '강좌소개', '학습 목표', '강의에서')


def _summary_bit(s):
    s = ' '.join((s or '').split())
    if not s:
        return ''
    for mk in _MARKERS:
        i = s.find(mk)
        if i >= 0:
            return s[i:i + SUMM_LEN]
    return s[:SUMM_LEN]

#  ── 다수결 판정 (self-consistency, 2026-08-03) ──────────────────────
#  왜: 같은 프롬프트로도 경계에 있는 직업은 판정이 뒤집힌다.
#      실측 — 「기업영업」이 1차 덮음 → 2차 안덮음으로 바뀌었다.
#  그래서 여러 번 물어 다수결로 정하고, **몇 대 몇이었는지를 함께 저장한다.**
#      3:0 → 믿는다        2:1 → 경계. 사람이 나중에 이것만 열어보면 된다.
#  ⚠️ TEMP 를 0 으로 두면 매번 같은 답이 나와 투표가 무의미하다. 흔들림이 필요하다.
VOTES = 3
TEMP = 0.6
SYNC = SyncLog('course_coverage')

_SCHEMA = {
    'type': 'object',
    'properties': {
        'results': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'code': {'type': 'string'},
                    'covered': {'type': 'boolean'},
                    #  ★ hit 을 요구하는 이유 — 판단을 근거에 묶기 위해서다.
                    #    없으면 LLM 이 목록 전체의 인상으로 뭉뚱그려 판정한다(실측: DB엔지니어링이
                    #    「데이터엔지니어링」·「데이터베이스 보안」을 갖고도 탈락했다).
                    'hit': {'type': 'string'},
                    'why': {'type': 'string'},
                },
                'required': ['code', 'covered', 'hit', 'why'],
            },
        },
    },
    'required': ['results'],
}

PROMPT = """너는 직업훈련 상담사다. 아래 각 직업마다
  · 그 직업의 **직무 정의**(NCS)
  · K-MOOC 강의 후보 — 제목 [분류] 그리고 **강의 요약**
이 붙어 있다.

★ 제목만 보고 판단하지 마라. **직무 정의와 강의 요약을 대조해라.**
  제목은 사람도 속인다. 실제 사례 —
    「객체지향형 도면해독」은 소프트웨어가 아니라 제조 도면 해독이고,
     용접 직무 정의에 "주어진 도면에 따른 WPS 검토"가 있으므로 **관련이 있다**.
    「K-FOOD코디네이션」도 요약에 "한식조리법을 활용한 메뉴 실습"이 있어 **관련이 있다**.

물음은 딱 하나다 —
  **후보 중에 「하나라도」 이 직업의 지식·기술을 실제로 배울 수 있는 강의가 있는가?**

목록 전체를 평가하지 마라. 무관한 강의가 섞여 있어도 상관없다.
쓸만한 게 하나라도 있으면 true 다. 화면에는 상위 몇 개만 보여줄 것이므로 하나면 충분하다.

  covered=true  → hit 에 그 강의 제목을 **그대로** 적는다.
  covered=false → hit 은 빈 문자열("")로 둔다.

hit 에 적을 수 없으면 true 를 주지 마라. 지목할 강의가 없다는 뜻이다.

false 로 보아야 하는 것 (전부 실측 사례다):
  · "실기·취업·창업" 같은 말투만 겹칠 뿐 분야가 다른 것
      제빵 ← 실용아트 메이크업 · 코스메틱 엔지니어링
  · 같은 큰 범주일 뿐 이 직무를 안 가르치는 것
      특수주조 ← 드론 특수촬영 활용 / 고무배합 ← 통합재료역학
  · 교양·개론뿐이라 직무 준비가 안 되는 것

true 로 보아야 하는 것:
  · 분야가 같고 그 직무의 지식을 실제로 다루는 것
      요양보호 ← 사회복지실천과 요양보호 / 리튬이온전지셀개발 ← 이차전지이야기
      DB엔지니어링 ← 데이터엔지니어링 (다른 후보가 무관해도 이 하나로 true)

why 는 20자 이내 한국어.

[판정 대상]
{items}
"""


def _post_factory(body):
    def _post(key):
        url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'{MODEL}:generateContent?key={key}')
        req = urllib.request.Request(url, data=body,
                                     headers={'Content-Type': 'application/json'})
        return urllib.request.urlopen(req, timeout=120).read()
    return _post


async def judge(batch):
    """batch: [(code, job_name, job_desc, [(제목, 분류, 요약), ...])] → {code: (covered, note)}

    ★ 2026-08-03 — 판정 재료를 '제목만'에서 '직무 정의 + 강의 요약'까지 넓혔다.
      왜: 제목만 보면 사람도 못 가른다. 실제로 그래서 오판을 의심했다가 내용을 읽고 번복했다 —
          「객체지향형 도면해독」은 소프트웨어가 아니라 **제조 도면 해독**(공학)이고,
          피복아크용접 직무 정의에 "**주어진 도면에 따른** WPS 검토"가 들어 있다. 관련이 있었다.
          「K-FOOD코디네이션」도 요약에 "**한식조리법을 활용한 메뉴 실습**"이 적혀 있었다.
      즉 필요한 것은 더 엄격한 프롬프트가 아니라 **더 많은 근거**였다.
    """
    lines = []
    for code, name, desc, courses in batch:
        lines.append(f'- code={code}')
        lines.append(f'  직업: {name}')
        if desc:
            lines.append(f'  직무 정의: {desc}')
        if courses:
            for t, cls, summ in courses:
                bit = f'    · {t}'
                if cls:
                    bit += f' [{cls}]'
                if summ:
                    bit += f' — {summ}'
                lines.append(bit)
        else:
            lines.append('    · (후보 없음)')
    prompt = PROMPT.format(items='\n'.join(lines))

    body = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'application/json',
                             'responseSchema': _SCHEMA, 'temperature': TEMP,
                             'thinkingConfig': {'thinkingLevel': 'minimal'}},
    }).encode()

    j = await _gutil.call(_post_factory(body), ENV)
    txt = j['candidates'][0]['content']['parts'][0]['text']
    out = {}
    for r in (json.loads(txt).get('results') or []):
        cov = bool(r.get('covered'))
        hit = (r.get('hit') or '').strip()
        #  hit 을 못 대면 true 로 인정하지 않는다 — 근거 없는 통과를 막는 안전장치.
        if cov and not hit:
            cov = False
        #  기록은 '왜'보다 '무엇을 근거로'가 낫다. 나중에 사람이 표를 열어 검증할 수 있다.
        note = (f'← {hit}' if cov else (r.get('why') or ''))[:110]
        out[str(r.get('code'))] = (cov, note)
    um = j.get('usageMetadata') or {}
    return out, um.get('promptTokenCount', 0) + um.get('candidatesTokenCount', 0)


def ensure_columns(conn):
    """컬럼이 없으면 만든다(서버·RDS 에서도 스스로 낫는다)."""
    with conn.cursor() as cur:
        cur.execute("""SELECT COLUMN_NAME FROM information_schema.COLUMNS
                       WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='job_catalog'""")
        have = {r[0] for r in cur.fetchall()}
        add = []
        if 'course_covered' not in have:
            add.append("ADD COLUMN course_covered TINYINT NULL "
                       "COMMENT 'K-MOOC 가 이 직무를 덮는가 (1 덮음 / 0 안덮음 / NULL 미판정)'")
        if 'course_cov_note' not in have:
            add.append("ADD COLUMN course_cov_note VARCHAR(120) NULL COMMENT '판정 이유'")
        if 'course_cov_at' not in have:
            add.append("ADD COLUMN course_cov_at DATETIME NULL COMMENT '판정 시각'")
        if 'course_cov_vote' not in have:
            add.append("ADD COLUMN course_cov_vote TINYINT NULL "
                       f"COMMENT '{VOTES}회 중 덮음 표 수 — 만장일치가 아니면 경계(사람이 볼 것)'")
        if add:
            cur.execute('ALTER TABLE job_catalog ' + ', '.join(add))
            conn.commit()
            print(f'job_catalog 컬럼 {len(add)}개 추가')


async def main():
    limit = None
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
    force = '--all' in sys.argv

    conn = db_conn()
    ensure_columns(conn)

    with conn.cursor() as cur:
        #  ★ 사람이 확정한 판정은 --all 로도 덮지 않는다 (2026-08-05)
        #    왜: 이 배치는 경계에서 흔들린다 — 실측상 2:1 로 갈린 직업이 51종이고,
        #    그중 「제빵」이 「식품재료학」 하나를 근거로 '덮음'이 되어 미래설계지도 카드에
        #    무관한 「식물공장」(스마트팜)까지 실렸다. 사람이 열어 바로잡아 놓아도
        #    다음 --all 이 조용히 되돌리면 같은 버그가 그대로 되살아난다.
        #    표식은 note 앞머리 한 조각으로 둔다 — 컬럼을 늘리면 RDS 마이그레이션이 따라붙는다.
        #    (이 SELECT 는 파라미터 없이 실행되므로 LIKE 의 % 가 그대로 나간다.)
        human = "COALESCE(course_cov_note,'') NOT LIKE '[사람확정]%'"
        where = f' WHERE {human}' if force else f' WHERE course_covered IS NULL AND {human}'
        #  --limit 은 '시험 실행'이다. job_code 순으로 자르면 한 대분류에만 몰려
        #  대표성이 없으므로 무작위로 뽑는다. 전체 실행은 순서대로 간다(재개 편의).
        #  --all --limit 은 '방금 판정한 것을 다시 판정해 비교'하는 용도다 → 판정된 것부터.
        order = ('course_cov_at DESC' if force else 'RAND()') if limit else 'job_code'
        cur.execute(f'SELECT job_code, job_name, job_mcls_name, job_description '
                    f'FROM job_catalog{where} '
                    f'ORDER BY {order}' + (f' LIMIT {int(limit)}' if limit else ''))
        todo = cur.fetchall()

    if not todo:
        print('판정할 직업 없음 (전부 판정됨 — 다시 하려면 --all)')
        conn.close()
        return

    print(f'모델 {MODEL} · 대상 {len(todo)}종 · 후보 {CAND}개씩 · {CHUNK}종 묶어 판정\n')

    # ① 직업마다 강좌 후보 뽑기
    prepared = []
    async with async_session() as db:
        for i, (code, name, mcls, desc) in enumerate(todo, 1):
            q = ' '.join(x for x in [name, mcls] if x)
            try:
                pool = await m.match_courses(db, q, top_k=CAND, min_score=0.0)
                cs = [(c['title'], c.get('classfy') or '', _summary_bit(c.get('summary')))
                      for c in pool]
            except Exception as e:
                cs = []
                print(f'  ({name}: 검색 실패 {type(e).__name__})')
            prepared.append((str(code), name, (desc or '').strip()[:JOB_DESC_LEN], cs))
            if i % 50 == 0:
                print(f'  후보 수집 {i}/{len(todo)}', flush=True)

    # ② LLM 판정 — 같은 물음을 VOTES 회 물어 다수결로 정한다
    tally, tokens = {}, 0       # code → [덮음 표, 총 표, 근거]
    for v in range(1, VOTES + 1):
        for i in range(0, len(prepared), CHUNK):
            chunk = prepared[i:i + CHUNK]
            try:
                got, tk = await judge(chunk)
                tokens += tk
            except Exception as e:
                print(f'  {v}회차 {i}~{i+len(chunk)} 실패: {type(e).__name__}: {str(e)[:60]}')
                continue
            for code, (cov, note) in got.items():
                t = tally.setdefault(code, [0, 0, ''])
                t[1] += 1
                if cov:
                    t[0] += 1
                #  근거는 '덮음' 쪽 것을 우선 남긴다 — 지목된 강의 제목이 검증에 더 쓸모있다.
                if (cov and not t[2].startswith('←')) or not t[2]:
                    t[2] = note
        print(f'  {v}/{VOTES}회차 완료  (누적 토큰 {tokens:,})', flush=True)

    # ③ 저장
    now = datetime.datetime.now()
    saved = covered = split = 0
    with conn.cursor() as cur:
        for code, name, _desc, _cs in prepared:
            t = tally.get(code)
            if not t or t[1] == 0:
                continue
            cov = t[0] * 2 > t[1]                       # 과반
            if 0 < t[0] < t[1]:                         # 만장일치가 아니면 경계
                split += 1
            cur.execute('UPDATE job_catalog SET course_covered=%s, course_cov_note=%s, '
                        'course_cov_vote=%s, course_cov_at=%s WHERE job_code=%s',
                        (1 if cov else 0, t[2], t[0], now, code))
            saved += 1
            covered += cov
    conn.commit()

    print(f'\n판정 {saved}종 — 덮음 {covered} · 안덮음 {saved - covered} '
          f'({(saved-covered)/saved*100:.0f}% 가 강좌 없이 국비훈련으로)')
    print(f'  만장일치 {saved - split} · 갈림 {split}  ← 갈린 것만 사람이 보면 된다:')
    print(f"  SELECT job_name, course_cov_vote, course_cov_note FROM job_catalog "
          f"WHERE course_cov_vote NOT IN (0,{VOTES});")
    SYNC.write(conn, fetched=len(todo), inserted=0, updated=saved, embedded=0,
               status='ok' if saved == len(todo) else 'partial',
               message=f'덮음 {covered} · 안덮음 {saved - covered} · 갈림 {split} · 토큰 {tokens:,}')
    conn.close()


if __name__ == '__main__':
    asyncio.run(main())
