# -*- coding: utf-8 -*-
"""
잇다 매칭 — 텍스트 → 임베딩 → Pinecone 검색 → 강좌 추천 (잇다의 '데이터 두뇌')
──────────────────────────────────────────────────────────
테스트 실행 :  python match.py "정보통신 클라우드 프로그래밍"
               python match.py --cert "실내에서 컴퓨터 다루는 일"
동작 :  ① 질의 텍스트를 Gemini로 임베딩
        ② Pinecone에서 가장 가까운 강좌/자격증 top-K 검색
        ③ 그 상세를 MySQL에서 꺼내 반환

네임스페이스
  하나의 인덱스를 둘로 나눠 쓴다.  course = 강좌 8,273 / cert = 자격증 613
  안 나누면 '강좌 추천'에 자격증이 섞여 나온다. 질의할 때 반드시 지정할 것.

※ 임베딩(embed_course_·embed_cert_) 끝난 뒤에 동작함.
"""
import os, re, sys, json, getpass
import urllib.request
import pymysql
from pinecone import Pinecone

MODEL = 'gemini-embedding-2'   # ※ embed_course_·embed_cert_ 의 MODEL과 반드시 동일할 것
NS_COURSE = 'course'
NS_CERT   = 'cert'


def read_env():
    d = {}
    for p in ['.env', 'etc/.env', '../etc/.env', r'C:\e-um-1\e-um\etc\.env']:
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
GEMINI_KEY   = next((v for k, v in ENV.items() if k.startswith('GEMINI_API_KEY') and v), None)
PINECONE_KEY = ENV.get('PINECONE_API_KEY')
INDEX_NAME   = ENV.get('PINECONE_INDEX', 'eum-courses')


# ── ① 질의 임베딩 (강좌와 같은 모델·plain) ─────────────────────────
def embed_query(text):
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:embedContent?key={GEMINI_KEY}'
    body = json.dumps({'model': f'models/{MODEL}', 'content': {'parts': [{'text': text}]}}).encode()
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())['embedding']['values']


# ── Pinecone + MySQL 연결 (한 번만) ─────────────────────────────────
_index = None
_conn = None
def _pinecone():
    global _index
    if _index is None:
        _index = Pinecone(api_key=PINECONE_KEY).Index(INDEX_NAME)
    return _index

def _db():
    global _conn
    if _conn is None:
        # DB_PW 는 itda_core 가 심어놓는 키. 단독 실행이면 .env 의 DB_PASSWORD 를 쓴다.
        pw = os.environ.get('DB_PW') or ENV.get('DB_PASSWORD') \
            or getpass.getpass('user2604 DB 비밀번호: ')
        _conn = pymysql.connect(host='localhost', port=3306, user='user2604',
                                password=pw, database='eum', charset='utf8mb4')
    return _conn


# ── ② 매칭: 질의 → 벡터검색 → 중복 제거 → 강좌 상세 ─────────────────
#  K-MOOC 은 같은 강좌를 학기마다 다시 개설한다(shortname 의 '과목코드|개설회차' 구조).
#  그래서 검색하면 같은 제목이 여러 번 올라온다 — 추천 3개 중 2개가 같은 강좌가 되는 문제.
#  DB 에 shortname 을 안 담았으므로 '제목'으로 거른다. (실측 중복률 약 5%)
def _norm(title):
    return re.sub(r'\s+', '', (title or '')).lower()


def _search(query_text, namespace, over_fetch, min_score):
    """질의 → 벡터 → 해당 네임스페이스에서 (id, score) 목록. 순서는 유사도 순."""
    vec = embed_query(query_text)
    res = _pinecone().query(vector=vec, namespace=namespace,
                            top_k=over_fetch, include_metadata=True)
    matches = res.get('matches', []) if isinstance(res, dict) else res.matches
    out = []
    for m in matches:
        mid = m['id'] if isinstance(m, dict) else m.id
        sc = m['score'] if isinstance(m, dict) else m.score
        if sc >= min_score:
            out.append((str(mid), sc))
    return out


def match_courses(query_text, top_k=5, min_score=0.0):
    # 중복·threshold 로 걸러질 것을 감안해 넉넉히 뽑는다
    id_score = _search(query_text, NS_COURSE, max(top_k * 4, 12), min_score)
    if not id_score:
        return []

    ids = [i for i, _ in id_score]
    with _db().cursor() as cur:
        fmt = ','.join(['%s'] * len(ids))
        cur.execute(f"SELECT kmooc_id, title, classfy_name, professor, course_url "
                    f"FROM course WHERE kmooc_id IN ({fmt})", ids)
        info = {str(r[0]): r for r in cur.fetchall()}

    out, seen = [], set()
    for cid, score in id_score:                 # 유사도 순서 유지
        r = info.get(cid)
        if not r:
            continue
        key = _norm(r[1])                       # 같은 제목이면 최초 1건만
        if key in seen:
            continue
        seen.add(key)
        out.append({'kmooc_id': r[0], 'title': r[1], 'classfy': r[2],
                    'professor': r[3], 'url': r[4], 'score': round(score, 3)})
        if len(out) >= top_k:
            break
    return out


# ── ③ 자격증 매칭 : 대직무분야를 거치지 않는다 ──────────────────────
#  기존 경로는 '모델이 대직무분야 17개 중 하나를 고른다'가 병목이었다.
#    · 기능사가 0개인 대직무분야가 7개
#    · 국가전문자격 100종은 oblig_fld 가 비어 있어 그 enum 에 아예 없다
#  벡터로 직접 찾으면 613종 전부가 후보가 된다.
#
#  grade / entry_free 로 좁히고 싶을 때가 있어 filters 를 받는다.
#    match_certs(q, grade='기능사')      → 응시자격 제한 없는 것만
#    match_certs(q)                      → 613종 전부
def match_certs(query_text, top_k=5, min_score=0.0, grade=None):
    id_score = _search(query_text, NS_CERT, max(top_k * 4, 20), min_score)
    if not id_score:
        return []

    ids = [i for i, _ in id_score]
    # grade 가 아니라 grade_std — grade(Q-Net seriesnm)는 산업기사 114종을 '기사'로 뭉갠다.
    # entry_free/entry_note 도 같이 꺼낸다. 카드에서 「지금 바로」·「응시자격」을 가르는 값이다.
    sql = ("SELECT cert_id, jm_name, COALESCE(grade_std, grade), oblig_fld, mdoblig_fld, "
           "       entry_free, entry_note "
           "FROM certification WHERE cert_id IN (%s)" % ','.join(['%s'] * len(ids)))
    params = list(ids)
    if grade:
        sql += " AND COALESCE(grade_std, grade)=%s"
        params.append(grade)
    with _db().cursor() as cur:
        cur.execute(sql, params)
        info = {str(r[0]): r for r in cur.fetchall()}

    out = []
    for cid, score in id_score:              # 유사도 순서 유지
        r = info.get(cid)
        if not r:
            continue                         # grade 필터에 걸러진 것
        out.append({'cert_id': r[0], 'jm_name': r[1], 'grade': r[2],
                    'oblig_fld': r[3], 'mdoblig_fld': r[4],
                    'entry_free': r[5] == 1,     # True=제한없음 확인 / False=미확인
                    'entry_note': r[6], 'score': round(score, 3)})
        if len(out) >= top_k:
            break
    return out


# ── 테스트용 CLI ────────────────────────────────────────────────────
if __name__ == '__main__':
    args = sys.argv[1:]
    cert = '--cert' in args
    q = ' '.join(a for a in args if a != '--cert') or '정보통신 클라우드 프로그래밍'
    print(f'질의: "{q}"   대상: {"자격증" if cert else "강좌"}\n')
    if cert:
        for i, c in enumerate(match_certs(q, top_k=8), 1):
            fld = ' · '.join(x for x in (c['oblig_fld'], c['mdoblig_fld']) if x) or '(분야 없음)'
            tag = '지금 바로' if c['entry_free'] else '응시자격 확인'
            print(f"{i}. [{c['score']}] {c['jm_name']}  ({c['grade']} · {tag})")
            print(f"     {fld}")
            if not c['entry_free'] and c['entry_note']:
                print(f"     {c['entry_note'].splitlines()[0][:60]}")
    else:
        for i, c in enumerate(match_courses(q, top_k=5), 1):
            print(f"{i}. [{c['score']}] {c['title']}  ({c['classfy']}·{c['professor']})")
            print(f"     {c['url']}")
