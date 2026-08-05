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
  하나의 인덱스를 둘로 나눠 쓴다.  job = 직업 1,094 / course = 강좌 8,371 / cert = 자격증 613 (2026-07-30 실측)
  안 나누면 '강좌 추천'에 자격증이 섞여 나온다. 질의할 때 반드시 지정할 것.

※ 임베딩(embed_course_·embed_cert_) 끝난 뒤에 동작함.
"""
import os, re, sys, json, asyncio
import urllib.request              # urllib.error 는 여기서 안 쓴다(HTTP 오류는 gemini_util 이 처리)
from sqlalchemy import text, bindparam
from pinecone import Pinecone

# async 세션 — 백엔드(패키지)와 CLI(스크립트) 양쪽에서 import 되게.
try:
    from .db import async_session
except ImportError:
    from db import async_session

# Gemini 호출 공용 (분당 한도는 기다렸다 재시도) — itda_core 와 같은 정책.
try:
    from . import gemini_util as _gutil
except ImportError:
    import gemini_util as _gutil

NS_COURSE = 'course'
NS_CERT   = 'cert'
NS_JOB    = 'job'              # 직업 먼저(2026-07-27) — understanding → 직업 벡터


# .env — 공용 로더 하나만 쓴다(2026-07-30). 예전엔 이 파일만 '../../etc/.env' 후보가 빠져
#  실행 위치에 따라 DB 는 붙는데 PINECONE_API_KEY 만 None 이 되는 조합이 있었다.
try:
    from .env import ENV
except ImportError:
    from env import ENV
# Gemini 키는 gemini_util 이 ENV 에서 찾는다(키 1개 · 분당 한도는 기다렸다 재시도).
PINECONE_KEY = ENV.get('PINECONE_API_KEY')

#  ★ 팀 통합 .env 스키마(2026-07-31) — 인덱스·임베딩 모델을 env 로 뺐다.
#    기본값은 코드에 남긴다: .env 에 키가 없어도 그대로 돌아가야 한다.
#    구 키(PINECONE_INDEX)도 계속 읽는다 — 팀원이 아직 .env 를 안 바꿨어도 안 깨지게.
#
#    ⚠️ 잇다는 **인덱스 1개(eum-itda)에 네임스페이스 3개**(cert / course / job)다.
#       키 이름이 COURSE 지만 강좌 전용 인덱스가 아니다.
#    ⚠️ 임베딩 모델을 바꾸면 **차원이 달라져 인덱스를 통째로 다시 만들어야 한다.**
#       덜다의 gemini-embedding-002(768) 와 한 글자 차이인 다른 모델이다. 임의로 바꾸지 말 것.
INDEX_NAME = (ENV.get('PINECONE_COURSE_INDEX_NAME')
              or ENV.get('PINECONE_INDEX')          # 구 키 하위호환
              or 'eum-itda')
MODEL = ENV.get('COURSE_EMBEDDING_MODEL') or 'gemini-embedding-2'
DIM   = int(ENV.get('COURSE_EMBEDDING_DIMENSION') or 3072)


# ── ① 질의 임베딩 (강좌와 같은 모델·plain) ─────────────────────────
#  content 파라미터명 주의 — sqlalchemy 의 text 를 import 했으므로 'text' 를 쓰면 가려진다.
async def embed_query(content):
    body = json.dumps({'model': f'models/{MODEL}',
                       'content': {'parts': [{'text': content}]}}).encode()

    def _post(key):
        url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'{MODEL}:embedContent?key={key}')
        req = urllib.request.Request(url, data=body,
                                     headers={'Content-Type': 'application/json'})
        return urllib.request.urlopen(req, timeout=30).read()

    j = await _gutil.call(_post, ENV)              # 분당 한도는 기다렸다 재시도
    return j['embedding']['values']


# ── Pinecone 클라이언트/인덱스 (한 번만 생성) ──────────────────────
#  Pinecone SDK 는 동기다. 쿼리·리랭크는 asyncio.to_thread 로 감싼다.
_client = None
def _pc():
    """Pinecone 클라이언트 — 인덱스(_pinecone)와 인퍼런스(리랭크) 둘 다 여기서 뻗는다."""
    global _client
    if _client is None:
        if not PINECONE_KEY:                       # 없으면 None 이 흘러가 첫 쿼리에서 불명확하게 실패(코드감사)
            raise RuntimeError('PINECONE_API_KEY 없음 — etc/.env 확인')
        _client = Pinecone(api_key=PINECONE_KEY)
    return _client

_index = None
def _pinecone():
    global _index
    if _index is None:
        _index = _pc().Index(INDEX_NAME)
    return _index


# ── 크로스인코더 리랭크 (Pinecone 인퍼런스 · bge-reranker-v2-m3) ─────
#  하이브리드(벡터+키워드 RRF)로 후보를 좁힌 뒤 '마지막 관련도 심판'.
#  벡터 임베딩은 본문이 얇아('직업명·중분류') 미세한 우열을 못 가린다. 크로스인코더는
#  질의와 후보를 '함께' 읽어 진짜 관련도를 매긴다 — 실측(2026-07-29):
#    "어르신 돌보는 일" → 요양지원 0.76 · 사회복지 0.58 · 간호 0.32 · 보육교사 0.09
#  실패(쿼터·네트워크·권한)하면 원래 순서를 그대로 쓴다 — 리랭크는 '개선'이지 '필수'가 아니다.
#  ★ 2026-08-04 — 공급자를 갈아끼울 수 있게 바꿨다. 왜:
#    Pinecone 인퍼런스 무료 등급은 **리랭크 월 500회**뿐이다. 8월 4일에 이미 소진되어
#    로컬·서버 양쪽이 조용히 폴백으로 돌고 있었다(RRF 1위 · 벡터 순서).
#    경고가 프로세스당 한 번만 찍히는 탓에 며칠간 아무도 몰랐다.
#    ⇒ 여러 공급자를 순서대로 시도하고, 쿼터가 끝난 곳은 이번 프로세스에서 건너뛴다.
#
#  실사용량 환산(실측): 후보 12개 문서 ≈ 811토큰, 턴당 리랭크 2회(직업+강좌) ≈ 1,622토큰
#    Pinecone 500회  = 약   250턴
#    Jina 1,000만토큰 = 약 6,165턴   ← 25배
RERANK_MODEL = os.environ.get('ITDA_RERANK_MODEL') or ENV.get('ITDA_RERANK_MODEL') or 'bge-reranker-v2-m3'

#  Jina — 카드 없이 키가 즉시 발급된다(https://jina.ai/reranker/). 한국어 포함 100+ 언어.
JINA_KEY = os.environ.get('JINA_API_KEY') or ENV.get('JINA_API_KEY')
#  모델명은 Jina 콘솔에서 고른 것과 맞춰야 한다(2026-08-04 기준 v3.5).
#  .env 의 ITDA_JINA_RERANK_MODEL 로 언제든 갈아끼울 수 있게 두었다 —
#  무료 등급에서 특정 모델이 막히면 콘솔에서 되는 걸 골라 그 이름만 넣으면 된다.
JINA_MODEL = (os.environ.get('ITDA_JINA_RERANK_MODEL')
              or ENV.get('ITDA_JINA_RERANK_MODEL')
              or 'jina-reranker-v3.5')

_RERANK_DEAD: set[str] = set()     # 쿼터·인증으로 끝난 공급자 — 매 요청 재시도하면 지연만 는다
_RERANK_WARNED: set[str] = set()   # 경고는 공급자당 한 번만
_RERANK_ACTIVE: str | None = None  # 마지막으로 성공한 공급자 (health 표시용)


def _rerank_warn(provider, e, fatal):
    if provider in _RERANK_WARNED:
        return
    _RERANK_WARNED.add(provider)
    tail = ' — 이번 실행에서는 더 쓰지 않습니다.' if fatal else ''
    print(f'[itda] ⚠️ 리랭커({provider}) 사용 불가{tail} '
          f'{type(e).__name__}: {str(e)[:140]}', flush=True)


def _is_fatal(e):
    """쿼터 소진·인증 실패면 이번 프로세스에서 그 공급자를 접는다.
    네트워크 순간 오류는 접지 않는다 — 다음 요청엔 될 수 있다."""
    s = f'{type(e).__name__} {e}'.lower()
    return any(k in s for k in ('429', 'ratelimit', 'resource_exhausted', 'quota',
                                '401', '402', '403', 'unauthorized', 'forbidden',
                                'payment', 'insufficient'))


def _jina_sync(q, docs, n):
    """Jina 리랭크 — 외부 의존성 없이 urllib 로 부른다(httpx 유무에 안 흔들리게)."""
    body = json.dumps({'model': JINA_MODEL, 'query': q,
                       'documents': list(docs), 'top_n': n,
                       'return_documents': False}).encode()
    #  ★ User-Agent 를 반드시 넣는다(2026-08-04 실측).
    #    안 넣으면 urllib 기본값(Python-urllib/3.x)이 Jina 앞단 Cloudflare 에 걸려
    #    **403 error code 1010** 이 온다. 키·모델과 무관하게 전부 막힌다.
    #    처음엔 키나 모델 문제로 오해했는데, UA 만 붙이니 그대로 통과했다.
    req = urllib.request.Request(
        'https://api.jina.ai/v1/rerank', data=body,
        headers={'Content-Type': 'application/json',
                 'Authorization': f'Bearer {JINA_KEY}',
                 'User-Agent': 'eum-itda/1.0 (+https://eum.r-e.kr)'})
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.loads(r.read())
    #  응답: {"results":[{"index":0,"relevance_score":0.98}, ...]}
    #  점수 키 이름은 버전에 따라 relevance_score / score 로 갈린다 — 둘 다 받는다.
    return [(int(x['index']), float(x.get('relevance_score', x.get('score', 0.0))))
            for x in out.get('results', [])]


async def _try_jina(q, docs, n):
    return await asyncio.to_thread(_jina_sync, q, docs, n)


async def _try_pinecone(q, docs, n):
    res = await asyncio.to_thread(lambda: _pc().inference.rerank(
        model=RERANK_MODEL, query=q, documents=list(docs),
        top_n=n, return_documents=False))
    return [(int(row.index), float(row.score)) for row in res.data]


def rerank_health():
    """지금 어떤 리랭커가 살아 있나 — 관리 화면·점검용.
    이번 사고(무료 한도 소진을 며칠간 아무도 모름)를 다시 겪지 않으려고 노출한다."""
    return {'active': _RERANK_ACTIVE,
            'dead': sorted(_RERANK_DEAD),
            'jina_key': bool(JINA_KEY),
            'pinecone_key': bool(PINECONE_KEY)}


async def rerank(query_text, docs, top_n=None):
    """[(문서문자열)] 을 질의와의 관련도로 재정렬 → [(원래인덱스, 점수)] 관련도 높은 순.

    공급자를 순서대로 시도한다(Jina → Pinecone). 전부 실패하면 [] 를 돌려주고,
    호출부는 원래 순서를 그대로 쓴다 — 리랭크는 '개선'이지 '필수'가 아니다.
    """
    global _RERANK_ACTIVE
    q = re.sub(r'\s+', ' ', (query_text or '')).strip()
    if not q or not docs:
        return []
    n = top_n or len(docs)

    providers = []
    if JINA_KEY:
        providers.append(('jina', _try_jina))
    if PINECONE_KEY:
        providers.append(('pinecone', _try_pinecone))

    for name, fn in providers:
        if name in _RERANK_DEAD:
            continue
        try:
            out = await fn(q, docs, n)
            if out:
                _RERANK_ACTIVE = name
                return out
        except Exception as e:                      # noqa: BLE001
            fatal = _is_fatal(e)
            if fatal:
                _RERANK_DEAD.add(name)
            _rerank_warn(name, e, fatal)
    return []                                       # 폴백은 호출부에서 (원래 순서 유지)


# ── ② 매칭: 질의 → 벡터검색 → 중복 제거 → 강좌 상세 ─────────────────
#  K-MOOC 은 같은 강좌를 학기마다 다시 개설한다(shortname 의 '과목코드|개설회차' 구조).
#  그래서 검색하면 같은 제목이 여러 번 올라온다 — 추천 3개 중 2개가 같은 강좌가 되는 문제.
#  DB 에 shortname 을 안 담았으므로 '제목'으로 거른다. (실측 중복률 약 5%)
def _norm(title):
    return re.sub(r'\s+', '', (title or '')).lower()


async def _search(query_text, namespace, over_fetch, min_score):
    """질의 → 벡터 → 해당 네임스페이스에서 (id, score) 목록. 순서는 유사도 순."""
    vec = await embed_query(query_text)
    res = await asyncio.to_thread(
        lambda: _pinecone().query(vector=vec, namespace=namespace,
                                  top_k=over_fetch, include_metadata=True))
    matches = res.get('matches', []) if isinstance(res, dict) else res.matches
    out = []
    for m in matches:
        mid = m['id'] if isinstance(m, dict) else m.id
        sc = m['score'] if isinstance(m, dict) else m.score
        if sc >= min_score:
            out.append((str(mid), sc))
    return out


async def match_courses(db, query_text, top_k=5, min_score=0.0):
    # 중복·threshold 로 걸러질 것을 감안해 넉넉히 뽑는다
    id_score = await _search(query_text, NS_COURSE, max(top_k * 4, 12), min_score)
    if not id_score:
        return []

    ids = [i for i, _ in id_score]
    #  summary 를 함께 뽑는다(2026-07-30) — 크로스인코더 리랭크의 판단 재료이자 화면 표시용.
    #    DB 채움률 99%인데 그동안 아무도 안 읽었다(코드감사 지적).
    stmt = text("SELECT kmooc_id, title, classfy_name, professor, course_url, course_id, summary "
                "FROM course WHERE kmooc_id IN :ids").bindparams(
                    bindparam("ids", expanding=True))
    rows = (await db.execute(stmt, {"ids": ids})).fetchall()
    info = {str(r[0]): r for r in rows}

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
                    'professor': r[3], 'url': r[4], 'score': round(score, 3),
                    'course_id': r[5],          # 미래설계지도 저장용 (itda_map_course FK)
                    'summary': r[6]})
        if len(out) >= top_k:
            break
    return out


# ── ③ 자격증 매칭 : 하이브리드(벡터 + 키워드) ───────────────────────
#  왜 대직무분야를 안 거치나
#    기존 경로는 '모델이 대직무분야 17개 중 하나를 고른다'가 병목이었다.
#    기능사가 0개인 대직무분야가 7개, 국가전문자격 100종은 oblig_fld 가 비어 있었다.
#    벡터로 직접 찾으면 613종 전부가 후보가 된다.
#
#  왜 벡터만으로 부족한가 (실측 2026-07-24)
#    벡터는 '뜻'은 잘 보지만 '정확한 이름'에 약하다.
#      "미용사 자격증"    → 미용사(일반) 0.623  (괄호 때문에 임계 미달로 놓침)
#      "전기산업기사"     → 전기기기산업기사가 1위 (엉뚱한 게 위로)
#    키워드(MySQL FULLTEXT ngram)는 정반대다 — 정확한 이름엔 강하고 뜻엔 약하다.
#      "미용사"          → 미용사(일반) 11.19  ✅
#      "요리"            → 결과 없음 (조리사엔 '조리'만 있어 글자가 안 겹침)
#    → 둘을 각각 돌려 순위를 RRF 로 합친다. 서로의 약점을 메운다.


KW_FLOOR = 3.0   # 이 점수 미만은 ngram 잡음으로 보고 버린다 (요리사→'리사'→관리사 2.11)


#  ★ 조사 제거 (2026-08-03) — ngram 이 '명사 끝 + 조사'를 한 낱말로 오인하는 것을 막는다.
#    증상: "간호조무사가 되고 싶어" → 「사가공」(섬유제조) 9.12 점으로 1위.
#          '간호조무사가' 의 「사가」(명사끝 사 + 조사 가)가 「사가공」과 겹친 것뿐이다.
#          "요리사가"·"작가가" 도 같은 방식으로 각각 사가공·감정평가가격정보제공을 불렀다.
#    왜 점수 문턱으로 못 막나 — 실측상 **잡음이 정상보다 높다**:
#          사가공(잡음) 9.12  >  전기기기설계 8.08 > 헤어미용 5.85 > 용접공통직무 4.48
#          제빵(정상)은 9.12 로 잡음과 동점이다. 어떤 문턱을 잡아도 정상을 먼저 죽인다.
#    그래서 점수가 아니라 **질의 쪽**을 고친다. 조사를 떼면 문제의 2글자 조각이 아예 사라진다.
#    어간 2글자 보장 — '요가'·'작가'·'결과' 처럼 조사처럼 끝나는 짧은 낱말을 지킨다.
#    '와/과/도/만/로' 는 뺐다: 학과·정형외과·상수도처럼 명사 일부인 경우가 너무 많다.
_JOSA = ('으로써', '으로서', '에서는', '에게서', '이라도',
         '으로', '에서', '에게', '부터', '까지', '이나', '라도', '한테', '보다', '처럼',
         '가', '이', '은', '는', '을', '를')


def _strip_josa(q):
    """키워드 검색용으로만 조사를 뗀다. 벡터 검색은 원문을 그대로 쓴다(뜻은 조사째로 봐야 한다)."""
    out = []
    for t in (q or '').split():
        for j in _JOSA:                                  # 긴 조사부터
            if t.endswith(j) and len(t) - len(j) >= 2:
                t = t[:-len(j)]
                break
        out.append(t)
    return ' '.join(out)


async def _keyword_certs(db, query_text, over_fetch):
    """FULLTEXT 키워드 검색 → [(cert_id, kw_score)]. 점수 높은 순.

    ★ 종목명(jm_name)만 검색한다. 수행직무(job_desc)까지 넣으면 '자격증'·'관리' 같은
      흔한 단어가 수백 종의 본문에 걸려 잡음이 된다(실측: "AWS 클라우드 자격증" →
      대기관리기술사 8.44). 우리가 키워드로 얻고 싶은 건 '정확한 이름'뿐이다.
      뜻은 벡터가 본다.
    ★ ngram 2글자는 서로 다른 단어를 우연히 잇는다("요리사"의 '리사' ↔ "관리사").
      KW_FLOOR 미만은 버려 이 잡음을 막는다.
    NATURAL LANGUAGE MODE 는 결과에 '글자가 실제로 겹친' 것만 올린다 → 없는 자격증엔 0건.
    """
    q = _strip_josa(re.sub(r'\s+', ' ', (query_text or '')).strip())
    if not q:
        return []
    # 종목명 전용 색인(ft_cert_name)을 쓴다. 두 컬럼 합친 ft_cert 로는 jm_name 만 못 짚는다.
    #  :q 는 SELECT·WHERE 두 곳에 쓰이지만 named param 이라 한 값이 재사용된다.
    #  LIMIT 는 우리 정수라 인라인(바인딩하면 MySQL 이 까다롭다).
    ft = "MATCH(jm_name) AGAINST (:q IN NATURAL LANGUAGE MODE)"
    stmt = text(f"SELECT cert_id, {ft} s FROM certification "
                f"WHERE {ft} ORDER BY s DESC LIMIT {int(over_fetch)}")
    rows = (await db.execute(stmt, {"q": q})).fetchall()
    return [(str(r[0]), float(r[1])) for r in rows if float(r[1]) >= KW_FLOOR]


def _rrf(*ranked_id_lists, k=60):
    """Reciprocal Rank Fusion — 여러 순위를 하나로 합친다.

    점수 스케일이 다른 검색(코사인 0~1 vs FULLTEXT 0~수십)을 그냥 더하면
    큰 쪽이 압도한다. 그래서 '순위'로 바꿔 합친다 — 어느 검색에서든 1등은 1등이다.
    두 검색에 다 있으면 점수가 커지고, 한쪽에만 있으면 작아진다.
    k=60 은 RRF 표준값(상위권 격차를 완만하게 해 한쪽 검색의 잡음에 덜 흔들린다).

    ★ '원문 가중치' 시도는 **측정으로 기각했다**(2026-08-04).
      가설: RRF 가 모든 순위에 똑같이 한 표를 주니, 사용자 원문 순위에 무게를 더 주면
            LLM 변형이 원문을 밀어내는 것을 막을 수 있다.
      실측: 「간호조무사가 되고 싶어요」의 정답(요양지원)이 무게 1.0→5.0 에서
            8위 → 7위로 **거의 안 움직였다.** 「전기기능사」는 4위 → 6위로 오히려 나빠졌다.
      왜 안 되나: k=60 이면 1/61 과 1/66 이 거의 같다. 즉 RRF 는 사실상 **표 세기**다 —
            「어느 목록에서 1등인가」보다 「몇 개 목록에 나오는가」가 이긴다.
            요양지원은 원문 목록에만 있고, 의료기기관리는 변형 3개 목록에 다 있었다.
            무게로 이길 수 있는 구조가 아니다. ⇒ **질의 목록 자체를 손봐야 한다**
            (그래서 DIRECT 는 변형을 아예 안 넘긴다 — itda_core 의 _alts 주석 참고).
    """
    score = {}
    for ids in ranked_id_lists:
        for rank, cid in enumerate(ids):
            score[cid] = score.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(score, key=score.get, reverse=True)


async def match_certs(db, query_text, top_k=5, min_score=0.0, grade=None):
    """하이브리드 자격증 검색.

    반환 dict 의 점수 두 개 — itda_core 가 '우리에게 있나'를 판정할 때 둘 다 본다.
      score    : 벡터 코사인 (0~1). 없으면 0.0
      kw_score : FULLTEXT 점수. 키워드에 안 걸리면 0.0
    정렬은 두 순위를 RRF 로 합친 순서다.
    """
    vec = await _search(query_text, NS_CERT, max(top_k * 4, 20), min_score)  # [(cid, cosine)]
    kw = await _keyword_certs(db, query_text, max(top_k * 4, 20))            # [(cid, kw_score)]
    if not vec and not kw:
        return []

    vec_score = {cid: s for cid, s in vec}
    kw_score = {cid: s for cid, s in kw}
    order = _rrf([c for c, _ in vec], [c for c, _ in kw])   # 합친 순위

    ids = list(vec_score.keys() | kw_score.keys())
    # grade 가 아니라 grade_std — grade(Q-Net seriesnm)는 산업기사 114종을 '기사'로 뭉갠다.
    sql = ("SELECT cert_id, jm_name, COALESCE(grade_std, grade), oblig_fld, mdoblig_fld, "
           "       entry_free, entry_note "
           "FROM certification WHERE cert_id IN :ids")
    params = {"ids": ids}
    if grade:
        sql += " AND COALESCE(grade_std, grade) = :grade"
        params["grade"] = grade
    stmt = text(sql).bindparams(bindparam("ids", expanding=True))
    rows = (await db.execute(stmt, params)).fetchall()
    info = {str(r[0]): r for r in rows}

    out = []
    for cid in order:                        # RRF 합친 순서
        r = info.get(cid)
        if not r:
            continue                         # grade 필터에 걸러진 것
        out.append({'cert_id': r[0], 'jm_name': r[1], 'grade': r[2],
                    'oblig_fld': r[3], 'mdoblig_fld': r[4],
                    'entry_free': r[5] == 1,     # True=제한없음 확인 / False=미확인
                    'entry_note': r[6],
                    'score': round(vec_score.get(cid, 0.0), 3),      # 벡터 코사인
                    'kw_score': round(kw_score.get(cid, 0.0), 2)})   # 키워드 점수
        if len(out) >= top_k:
            break
    return out


# ── ④ 직업 매칭 : 직업 먼저(2026-07-27) · 하이브리드(2026-07-28) ─────
#  understanding → 직업 후보. 각 후보에 '자격증 몇 개 붙었나'(n_cert)를 단다.
#  자격증 0인 직업(요양간호사·웹개발자 등)도 후보로 살린다 — 카드가 내일배움카드+강좌로 대체.
#  ★ 하이브리드(2026-07-28) — 직업 임베딩 본문이 얇아('직업명·중분류' ~21자) 벡터만으론
#    "컴퓨터 만들기"에 '작곡가' 같은 노이즈가 뜬다. 그래서 자격증(match_certs)과 똑같이
#    벡터(뜻) + 키워드(FULLTEXT ft_job_name, 정확한 이름)를 RRF 로 합친다.
KW_JOB_FLOOR = 3.0   # ngram 부분토큰 잡음 제거 (cert 의 KW_FLOOR 와 같은 값)


# 구어 → NCS 어휘 보강 (2026-07-29) — NCS 직무명이 formal 해서 '웹사이트'가 '응용SW엔지니어링'을
#  못 잡는다(벡터·키워드 둘 다 0). 사용자 말투를 NCS 검색어로 살짝 확장해 키워드 경로를 살린다.
_JOB_ALIAS = {
    '웹사이트': '응용SW', '웹개발': '응용SW', '홈페이지': '응용SW', '웹': '응용SW',
    '애플리케이션': '응용SW', '어플': '앱콘텐츠', '앱': '앱콘텐츠',
}


async def _keyword_jobs(db, query_text, over_fetch):
    """FULLTEXT 키워드 검색 → [(job_code, kw_score)]. job_name 전용 색인 ft_job_name.
    벡터가 얇어 놓치는 '정확한 이름'(게임·용접 등)을 키워드가 끌어올린다."""
    q = _strip_josa(re.sub(r'\s+', ' ', (query_text or '')).strip())
    if not q:
        return []
    for k, v in _JOB_ALIAS.items():            # 구어 → NCS 어휘 보강
        if k in q and v not in q:
            q += ' ' + v
    ft = "MATCH(job_name) AGAINST (:q IN NATURAL LANGUAGE MODE)"
    stmt = text(f"SELECT job_code, {ft} s FROM job_catalog "
                f"WHERE {ft} ORDER BY s DESC LIMIT {int(over_fetch)}")
    rows = (await db.execute(stmt, {"q": q})).fetchall()
    return [(str(r[0]), float(r[1])) for r in rows if float(r[1]) >= KW_JOB_FLOOR]


async def match_jobs(db, query_text, top_k=6, min_score=0.0):
    """질의(문자열 또는 문자열 목록) → 직업 후보. 하이브리드(벡터+키워드) RRF.

    ★ 다질의 융합(RAG-Fusion, 2026-07-30)
      query_text 에 **여러 질의**를 주면 각각 검색해 모든 순위를 RRF 로 함께 합친다.
      왜: 남은 품질 편차의 원인이 'LLM 이 만든 질의 한 개'였다. 표현이 조금 달라지면
      벡터 순위가 흔들려 카드/되묻기가 뒤집혔다(실측). 여러 표현으로 검색해 합치면
      한 표현의 운에 덜 좌우된다 — 여러 순위에 공통으로 오르는 후보가 위로 올라온다.
      이게 업계에서 말하는 Multi-Query Retrieval / RAG-Fusion 이고, 융합기(_rrf)는 이미 있었다.
      비용: 질의 변형은 **기존 턴 호출 한 번에서 함께 받으므로 LLM 추가 비용 0**.
      늘어나는 건 임베딩(실측 9회 34토큰 ≈ 0원)과 Pinecone 쿼리뿐이다.
    """
    queries = [q for q in ([query_text] if isinstance(query_text, str) else list(query_text or []))
               if q and q.strip()]
    if not queries:
        return []
    #  중복 제거 · 최대 4개(비용 상한). **앞자리가 우선**이므로 호출부는 결정론적 앵커
    #  (사용자 원문 · 슬롯 질의)를 앞에 두고 LLM 변형을 뒤에 둔다 — 잘려도 앵커는 남는다.
    queries = list(dict.fromkeys(queries))[:4]

    #  ★ 질의 변형별 검색을 **동시에** 던진다(2026-08-04). 예전엔 for 루프로 하나씩 기다렸다.
    #    실측: 카드 한 턴 10.21초 중 **4.52초가 여기**였다(벡터 1.26+1.07+0.97+1.19, 순차).
    #    변형끼리는 서로 의존하지 않으므로 기다릴 이유가 없다 — 결과·순서·점수는 그대로다.
    #    (키워드는 같은 MySQL 세션을 쓰므로 동시에 던지지 않는다. 실측 0.00초라 이득도 없다.)
    over = max(top_k * 3, 12)
    vecs = await asyncio.gather(*(_search(q, NS_JOB, over, min_score) for q in queries),
                                return_exceptions=True)
    ranked, vec_score, kw_score = [], {}, {}
    for q, vec in zip(queries, vecs):
        if isinstance(vec, BaseException):            # 한 변형이 실패해도 나머지로 진행한다
            print(f'[itda] 벡터검색 실패(변형 하나 건너뜀): {type(vec).__name__}: {vec}')
            vec = []
        kw = await _keyword_jobs(db, q, over)                                # [(job_code, kw_score)]
        ranked.append([c for c, _ in vec])
        ranked.append([c for c, _ in kw])
        for c, s in vec:                              # 점수는 '가장 높게 나온 값'을 남긴다
            vec_score[c] = max(vec_score.get(c, 0.0), s)   # (임계 판정은 최선의 표현을 기준으로)
        for c, s in kw:
            kw_score[c] = max(kw_score.get(c, 0.0), s)
    if not vec_score and not kw_score:
        return []
    order = _rrf(*ranked)                             # 모든 순위(질의×2)를 한 번에 RRF
    codes = list(vec_score.keys() | kw_score.keys())
    stmt = text("SELECT jc.job_code, jc.job_name, jc.job_mcls_name, jc.job_description, "
                "       COUNT(cj.cert_id) "
                "FROM job_catalog jc LEFT JOIN cert_job cj ON cj.job_code = jc.job_code "
                "WHERE jc.job_code IN :codes "
                "GROUP BY jc.job_code").bindparams(
                    bindparam("codes", expanding=True))
    rows = (await db.execute(stmt, {"codes": codes})).fetchall()
    info = {str(r[0]): r for r in rows}
    out = []
    for code in order:                           # RRF 합친 순서
        r = info.get(code)
        if not r:
            continue
        out.append({'job_code': str(r[0]), 'job_name': r[1], 'group': r[2],
                    'description': r[3],                              # NCS DUTY_DEF (카드 설명·2026-07-29)
                    'n_cert': int(r[4]),
                    'score': round(vec_score.get(code, 0.0), 3),      # 벡터 코사인 (_is_spread·notfound 판정용)
                    'kw_score': round(kw_score.get(code, 0.0), 2)})   # 키워드 점수
        if len(out) >= top_k:
            break
    return out


# ── 테스트용 CLI ────────────────────────────────────────────────────
async def _cli():
    args = sys.argv[1:]
    cert = '--cert' in args
    q = ' '.join(a for a in args if a != '--cert') or '정보통신 클라우드 프로그래밍'
    print(f'질의: "{q}"   대상: {"자격증" if cert else "강좌"}\n')
    async with async_session() as db:
        if cert:
            for i, c in enumerate(await match_certs(db, q, top_k=8), 1):
                fld = ' · '.join(x for x in (c['oblig_fld'], c['mdoblig_fld']) if x) or '(분야 없음)'
                tag = '지금 바로' if c['entry_free'] else '응시자격 확인'
                print(f"{i}. 벡터 {c['score']:.3f} · 키워드 {c['kw_score']:>5}  "
                      f"{c['jm_name']}  ({c['grade']} · {tag})")
                print(f"     {fld}")
                if not c['entry_free'] and c['entry_note']:
                    print(f"     {c['entry_note'].splitlines()[0][:60]}")
        else:
            for i, c in enumerate(await match_courses(db, q, top_k=5), 1):
                print(f"{i}. [{c['score']}] {c['title']}  ({c['classfy']}·{c['professor']})")
                print(f"     {c['url']}")


if __name__ == '__main__':
    asyncio.run(_cli())
