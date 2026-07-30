# -*- coding: utf-8 -*-
"""
잇다 코어 — CLI와 백엔드가 함께 쓰는 순수 로직 (2026-07-24 async)
──────────────────────────────────────────────────────────
설계
  · import 시 아무 부작용이 없다(DB·API 미연결). 엔진은 커넥션을 들고 있지 않는다.
  · DB 세션은 요청마다 밖에서 받아 step()·search() 에 넘긴다(팀 get_db 방식).
    예전엔 전역 pymysql 커넥션을 스레드가 공유해 깨졌다(코드리뷰 HIGH) → 해소.

쓰는 법
    from app.itda.itda_core import ItdaEngine
    from app.itda.db import async_session
    eng = ItdaEngine()
    async with async_session() as db:
        r = await eng.step(db, profile, "컴퓨터 만지는 게 재밌어요")
    #  r = {kind, reply, profile, missing, can_land, card, near}

DB 접속정보 : app/itda/db.py 가 etc/.env 에서 읽는다(팀 database.py 는 경로가 안 맞음).
"""
import os, re, json
import urllib.request, urllib.parse
from sqlalchemy import text

# async 세션 팩토리 — 백엔드(패키지)와 CLI(스크립트) 양쪽에서 import 되게.
try:
    from .db import async_session
except ImportError:               # CLI: path 에 Backend/app/itda 가 들어와 있을 때
    from db import async_session

# Gemini 호출 공용(무료 우선·분당 대기·유료는 하루소진 때만) — 양쪽에서 import.
try:
    from . import gemini_util as _gutil
except ImportError:
    import gemini_util as _gutil

# Solar(Upstage) 어댑터 — provider='solar' 일 때 대화 모델을 교체(A/B용). 임베딩은 그대로 Gemini.
try:
    from . import solar_util as _solar
except ImportError:
    import solar_util as _solar

MODEL = 'gemini-3.6-flash'
#  (2026-07-28) GRADE='기능사' 제거 — 옛 자격증 검색에서 grade 필터로 쓰였으나 직업-먼저 전환으로 죽음.


# ── .env 읽기 (부작용 없음) ─────────────────────────────────────────
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


# ── 슬롯 정의 ───────────────────────────────────────────────────────
#  ※ Gemini 는 enum 에 빈 문자열을 허용하지 않는다(400).
#    required 에 넣지 않음 → '모르면 생략'이 곧 미확인.
#  ★ 슬롯마다 '근거'를 함께 받는다 — 프롬프트로 부탁하는 대신 코드가 검증하기 위해서다.
#    모델이 값을 지어내려면 근거도 지어내야 하는데, 그건 원문 대조에서 걸린다.
#    (실측: "컴퓨터가 재밌어요" 만 말했는데 환경선호=실내 를 채우는 일이 반복됨)
def _slot(desc, enum=None):
    v = {'type': 'STRING'}
    if enum:
        v['enum'] = enum
    return {'type': 'OBJECT',
            'properties': {'값': v,
                           '근거': {'type': 'STRING',
                                    'description': '사용자가 실제로 한 말에서 그대로 인용'}},
            'required': ['값', '근거'],
            'description': desc}

#  슬롯 재설계(2026-07-28) — 직업을 '특정'하는 축으로 5개. (환경·시간·비용 제거)
#    관심분야(무엇에) × 활동유형(어떻게) × 다루는대상(무엇으로) 이 직업을 가르고,
#    세부관심은 '넓게 남을 때' 좁히기(narrowing)로 채워지며, 강점성향은 보강 신호다.
#    활동유형·다루는대상은 enum('갇힌 출력') — 모델이 목록에서만 고른다.
PROFILE_SCHEMA = {'type': 'OBJECT', 'properties': {
    '관심분야': _slot('좋아한다·재밌다·해봤다고 말한 활동이나 대상 (일상어 그대로)'),
    '활동유형': _slot('무슨 행위를 좋아하나 (목록에서 가장 가까운 하나)',
                    ['만들기', '고치기·정비', '운전·조작', '돕기·돌봄', '가르치기',
                     '분석·연구', '관리·운영', '표현·창작', '판매·설득']),
    '다루는대상': _slot('일의 주 재료 (목록에서 가장 가까운 하나)',
                     ['사람', '기계·설비', '컴퓨터·데이터', '자연·생물', '창작물', '숫자·문서']),
    '세부관심': _slot('넓은 관심을 좁힌 구체 방향 (예: 웹/게임/앱, 한식/제빵). 구체적으로 말할 때만'),
    '강점성향': _slot('잘하거나 편한 것 (손재주·꼼꼼함·체력·사교성·인내심 등). 말할 때만'),
}}


# ── 근거 검증 : 모델이 댄 근거가 실제 발화에 있는가 ─────────────────
def _clean(s):
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', s or '')

def _grounded(evidence, user_msg):
    """근거의 핵심 어절이 발화 안에 있으면 인정. 조사·어미 차이는 허용한다."""
    ev, msg = _clean(evidence), _clean(user_msg)
    if not ev or not msg:
        return False
    if ev in msg:                                   # 그대로 인용한 경우
        return True
    toks = [t for t in re.split(r'\s+', (evidence or '').strip()) if len(_clean(t)) >= 2]
    if not toks:
        return False
    hit = sum(1 for t in toks if _clean(t)[:2] in msg)   # 어간 2글자로 대조
    return hit >= max(1, (len(toks) + 1) // 2)           # 절반 이상 맞으면 인정


def verify_slots(raw, user_msg):
    """모델이 채운 슬롯 중 '발화에 근거가 있는 것'만 통과시킨다.

    반환: (통과한 슬롯 dict, 버려진 목록)
    """
    kept, dropped = {}, []
    for k, v in (raw or {}).items():
        if not isinstance(v, dict):                 # 혹시 옛 형식이 오면 그대로 통과
            if v:
                kept[k] = v
            continue
        val, ev = v.get('값'), v.get('근거')
        if not val:
            continue
        if _grounded(ev, user_msg):
            kept[k] = val
        else:
            dropped.append(f'{k}={val} (근거 "{ev}" 가 발화에 없음)')
    return kept, dropped

def notfound_reply(near):
    """'우리에게 없다'는 말은 코드가 쓴다.

    모델에게 맡기면 없는 자격증을 있다고 하거나, 얼버무리고 아무거나 권한다.
    없다는 사실 자체가 사용자에게 필요한 정보다 — 다른 데를 알아볼 수 있으니까.
    """
    #  직업 먼저(2026-07-28) — near 는 '가까운 직업'이다(예전엔 '가까운 자격증'이라 c['cert']였음).
    names = ' · '.join(n.get('job', '') for n in (near or [])[:3] if n.get('job'))
    msg = '말씀하신 일은 저희가 지금 다루는 범위에서는 딱 맞는 걸 찾지 못했어요.'
    if names:
        msg += f'\n\n비슷한 쪽으로는 {names} 같은 일이 있어요. 이 중에 끌리는 게 있으세요?'
    msg += '\n아니면 어떤 일을 하고 싶은지 편하게 말씀해 주셔도 좋아요.'
    return msg


def narrow_reply(options):
    """관심이 넓어 후보가 흩어졌을 때 '좁히는' 질문 — 실제 후보 직업에서 뽑은 선택지로 되묻는다.
    지어낸 선택지가 아니라 검색이 실제로 올린 직업들이라, 사용자가 자기 언어로 고를 수 있다."""
    opts = ' · '.join((options or [])[:4])
    return ('관심 방향이 여러 갈래로 보여요. 이 중 어디에 가까우세요?\n'
            f'{opts}\n(아니면 더 구체적으로 어떤 걸 하고 싶은지 말씀해 주셔도 좋아요.)')


# ── "잘 모르겠어요" 처리 — 못 정하는 사용자를 억지로 착지시키지 않는다(2026-07-29) ──
_UNCERTAIN = ('모르겠', '몰라', '글쎄', '아무거나', '상관없', '모르것', '모르겟')

def is_uncertain(msg):
    """'잘 모르겠어요' 류 — 좁히기 질문에 이게 오면 하나 골라 던지지 않는다."""
    m = re.sub(r'\s+', '', msg or '')
    return any(u in m for u in _UNCERTAIN)

def guide_reply(profile):
    """착지 대신 '같이 찾아보는' 되물음 — 왜 끌렸는지부터 연다(선고 금지)."""
    field = (profile or {}).get('세부관심') or (profile or {}).get('관심분야')
    if field:
        return (f'괜찮아요, 천천히 같이 찾아봐요. {field}에 관심이 생긴 계기가 있으세요? '
                f'어떤 점이 재밌어 보였는지 들려주시면 방향을 같이 좁혀볼게요.')
    return ('괜찮아요, 천천히 같이 찾아봐요. 요즘 시간 가는 줄 모르고 하게 되는 일이나, '
            '해보고 "이건 좀 나한테 맞는다" 싶었던 게 있으세요?')


def _match_mod():
    """match 모듈 — 백엔드(패키지)와 CLI(스크립트) 양쪽에서 import 되게."""
    try:
        from . import match          # 패키지로 import 될 때(백엔드)
    except ImportError:
        import match                 # 스크립트로 실행될 때(CLI)
    return match


ASK_ORDER = ['관심분야', '활동유형', '다루는대상']    # 되물어 채울 슬롯(세부관심=narrowing·강점성향=보강은 제외)

def missing_slots(p):
    return [k for k in ASK_ORDER if not (p or {}).get(k)]

# ASK 턴인데 모델이 질문 대신 '찾아볼게요' 류로 끝내는 막다른 답변 대비 — 슬롯별 실제 질문(2026-07-29)
_ASK_Q = {
    '관심분야': '어떤 걸 할 때 시간 가는 줄 모르세요? 좋아하거나 해봤던 걸 편하게 말해 주세요.',
    '활동유형': '그 일을 할 때 뭘 하는 게 제일 끌리세요? 만들기·고치기·돌보기·가르치기·분석하기 중에 가까운 걸로요.',
    '다루는대상': '주로 무엇을 다루는 일이 좋으세요? 사람·기계·컴퓨터·자연·창작물 중에 끌리는 게 있을까요?',
}
def ask_reply(profile):
    for k in ASK_ORDER:
        if not (profile or {}).get(k):
            return _ASK_Q[k]
    return '조금만 더 들려주시면 방향을 잡아볼게요 — 어떤 일이 끌리세요?'

def can_land(p):
    """착지 조건은 코드가 판정한다 — 모델의 자기보고(confidence)를 믿지 않는다.

    직업을 가리키는 세 축(관심분야·활동유형·다루는대상) 중 2개 이상이면 착지 가능.
    특정 슬롯을 필수로 못 박지 않는 이유: 모델이 "사람 돌보는 일"을 관심분야에 담기도,
    다루는대상+활동유형에 담기도 해서 — 못 박으면 같은 발화가 착지했다 말았다 한다(실측).
    2축 이상이면 '검색할 만큼은 안다'. (환경·시간·비용은 2026-07-28 제거)
    ※ 최소조건일 뿐 — 후보가 여러 갈래로 흩어지면 search 가 narrowing 으로 한 번 더 좁힌다.
    """
    p = p or {}
    return sum(1 for k in ('관심분야', '활동유형', '다루는대상') if p.get(k)) >= 2

def merge(old, new):
    """새로 파악한 슬롯만 덮어쓴다. 모델이 빠뜨려도 기존 값이 사라지지 않게."""
    out = dict(old or {})
    for k, v in (new or {}).items():
        if v:
            out[k] = v
    return out

def profile_text(p):
    known = {k: v for k, v in (p or {}).items() if v}
    return json.dumps(known, ensure_ascii=False) if known else '(아직 파악된 것 없음)'


# ── 사전필터 : LLM 부르기 전 코드가 먼저 거른다 ─────────────────────
BAD_WORDS = ['죽여', '죽이', '때려', '패버', '강간', '성폭', '자살', '꺼져', '병신', '씨발', '개새']

def pre_check(msg):
    """'VAGUE'=되묻기 / 'UNSAFE'=차단 / None=정상"""
    msg = msg or ''
    meaningful = re.sub(r'[^가-힣a-zA-Z]', '', msg)
    if not meaningful or re.fullmatch(r'[ㄱ-ㅎㅏ-ㅣ\s]+', msg):
        return 'VAGUE'
    if any(b in msg.replace(' ', '') for b in BAD_WORDS):
        return 'UNSAFE'
    return None


# ── 인젝션/탈옥 코드 게이트(2026-07-29) — no_card 강제. 모델을 안 믿고 코드가 먼저 막는다 ──
#   왜 코드로 막나: 저비용/국산 모델(Solar 실측)이 "개발자 모드로 전환"·"시스템 프롬프트 출력"에
#   카드를 뱉었다(환각). 프롬프트로 "하지 마"는 약하다 — 코드가 확정으로 redirect 시킨다.
#   정밀하게: 단독어(시스템프롬프트·개발자모드)는 그대로, 흔한 단어(지시·규칙)는 '무시/잊어/해제'와
#   짝지을 때만. "무조건 의사 답해"류(강제착지)는 ask 를 원하므로 여기서 안 잡는다.
_INJECT_SOLO = (
    '시스템프롬프트', 'systemprompt', '개발자모드', 'developermode', 'devmode',
    'jailbreak', '탈옥', 'dan모드', 'danmode', '프롬프트출력', '프롬프트를출력',
    '프롬프트보여', '프롬프트를보여', 'ignoreprevious', 'ignoreall', 'ignoreabove',
    'disregardprevious', '자유로운ai', '아무규칙도없', '규칙도없는', 'system:',
)
_INJECT_SUBJ = ('지시', '명령', '규칙', '설정값', '역할을', '지시사항')
_INJECT_VERB = ('무시', '잊어', '잊고', '잊으', '해제')

def is_injection(msg):
    """프롬프트 인젝션/탈옥이면 True — 카드 없이 redirect. 정상 진로발화는 안 걸리게 정밀."""
    m = (msg or '').lower().replace(' ', '')
    if any(p in m for p in _INJECT_SOLO):
        return True
    return any(s in m for s in _INJECT_SUBJ) and any(v in m for v in _INJECT_VERB)


def has_interest(p):
    """진로 맥락이 섰나 — 관심축이 하나라도 차 있으면 True. 이탈 게이트를 콜드 오픈에만 걸기 위함."""
    return any((p or {}).get(k) for k in ('관심분야', '활동유형', '다루는대상', '세부관심'))


# ── 가짜자격 주장 탐지(2026-07-30) — no_card/복창금지 강제 ──
#   "스마트팜 국가공인 마스터 3급 있는데" 처럼 실재하지 않는 자격을 보유했다 주장하면, 모델이
#   그걸 인정·복창하는 게 간헐적으로 샌다(실측: flashlite 2/6, solar 도 1회). 프롬프트로는 약하다.
#   규칙: (자격증류 명사 + 보유동사)로 '주장'을 감지. 그중 DB에 실존하지 않는 것만 코드가 되받는다
#   (진짜 자격 '전기기능사 있는데'는 _named_entity 가 실존을 확인 → 안 걸린다). 오탐 0 실측.
_CRED = ('자격증', '국가공인', '기능사', '산업기사', '기술사', '마스터')
_HAVE = ('있는데', '있어요', '있습니다', '있음', '취득', '땄', '따놨', '보유', '가지고있',
         '자격증있', '자격있')

def claims_credential(msg):
    """자격 '보유'를 주장하는 발화면 True (그 자격이 실재하는지는 호출부가 _named_entity 로 판정)."""
    m = (msg or '').replace(' ', '')
    cred = any(t in m for t in _CRED) or bool(re.search(r'\d+급', m))
    return bool(cred and any(t in m for t in _HAVE))


# ── 이탈 주제 게이트(2026-07-29) — no_card 강제의 마지막 조각. 전용 이진 판별기 ──
#   omnibus turn() 은 "김치찌개 레시피"에 김치가공 직업을 카드로 뱉기도 한다(solar 실측).
#   코드 키워드로는 못 막고('레시피'는 레시피개발자와 겹침), 리랭커 floor 로도 못 막는다
#   (정상 카드도 점수가 낮다 — 실측). 진짜 문제는 '의도'다 → 좁은 이진 질문으로 판별한다.
#   실측(2026-07-29): 이탈차단 6/6 · 정상통과 11/11 (solar·flashlite 모두 100%).
#   "레시피 개발자 되고 싶어"(진로=true)와 "레시피 알려줘"(이탈=false)를 정확히 가른다.
GATE_ONTOPIC = """너는 진로상담 봇의 '주제 판별기'다. 사용자 메시지가 진로 상담과 관련되는지 판단해라.

on_topic=true : 직업·진로·적성·하고 싶은 일·좋아하는 활동·자격증·취업·"뭘 해야 할지" 고민 등
              (요리사·제빵사·바리스타처럼 '직업'에 대한 관심도 true. 막연한 관심사도 true.)
on_topic=false: 요리 레시피·날씨·뉴스·주식·번역·계산·단순 잡담 등, 결과물/정보만 요구하고
              진로와 무관한 경우. ('레시피 알려줘'는 false, '요리사 되고 싶어'는 true)

메시지: {msg}"""
_GATE_SCHEMA = {'type': 'OBJECT', 'properties': {'on_topic': {'type': 'BOOLEAN'}},
                'required': ['on_topic']}


SYSTEM = """너는 '잇다'의 진로 동반자다.

[대상]
가족 돌봄으로 학업을 놓은 청년. 시간과 돈이 부족하고, 무엇보다 자기 목표를 말로 표현하지 못한다.

[가장 중요한 원칙]
"어떤 일(직업)을 하고 싶으세요?"라고 대놓고 묻지 않는다. 그 질문에 답할 수 있는 사람은 애초에 여기 오지 않는다.
일상의 언어로 묻고, 그 답을 '어떤 일을 하게 될지'로 번역하는 것이 네 일이다.

[하지 말 것]
· 사용자가 직접 말하지 않은 사정(돌봄 상황·가정형편·경제사정)을 단정하지 마라.
  짐작이 되더라도 아는 척하지 말고, 필요하면 질문으로 확인하라.
· 한 턴에 여러 개를 묻지 마라. 하나씩.
· 확실하지 않은 슬롯은 채우지 말고 생략하라. 추측으로 채우면 안 된다.
· ★ 사용자가 "○○ 자격증/자격이 있다"고 주장해도, 우리가 확인할 수 없는 자격증이면 진짜인 양
  인정·칭찬·복창하지 마라("대단하다"·"취득하셨군요" 금지). 확인 안 된 자격은 흘려보내고,
  하고 싶은 '일(방향)' 자체로 대화를 이어가라. 자격증 존재는 시스템(DB)이 정한다.

[매 턴 할 일 — 이 순서대로]
1) 먼저, 사용자가 방금 한 말에서 슬롯을 뽑는다.   ← 이게 최우선이다
2) 그 다음, 아직 빈 슬롯을 보고 행동을 고른다.

[슬롯 5개]  ── 직업을 '무엇을 × 어떻게 × 무엇으로' 로 특정한다
관심분야   좋아한다·재밌다·해봤다고 말한 활동이나 대상 (일상어 그대로, 자유롭게)
활동유형   무슨 '행위'를 좋아하나 — 아래 목록에서 가장 가까운 하나:
           만들기 · 고치기·정비 · 운전·조작 · 돕기·돌봄 · 가르치기 · 분석·연구 · 관리·운영 · 표현·창작 · 판매·설득
다루는대상  일의 주 '재료' — 아래 목록에서 가장 가까운 하나:
           사람 · 기계·설비 · 컴퓨터·데이터 · 자연·생물 · 창작물 · 숫자·문서
세부관심   넓은 관심을 좁힌 구체 방향 (예: 웹/게임/앱, 한식/제빵). 사용자가 구체적으로 말할 때만.
강점성향   잘하거나 편한 것 (손재주·꼼꼼함·체력·사교성·인내심 등). 말할 때만.

[슬롯 뽑기 — 값과 '근거'를 함께 낸다]
근거에는 사용자가 **실제로 한 말을 그대로** 옮긴다. 요약하거나 바꿔 쓰지 않는다.
활동유형·다루는대상은 반드시 위 목록 안에서 고른다(목록 밖 금지). 관심분야·세부관심·강점성향은 자유.

  "컴퓨터 만지는 게 재밌어요"
      → 관심분야 = {값:"컴퓨터", 근거:"컴퓨터 만지는 게 재밌어요"}
  "뭔가 만드는 게 좋아요"
      → 활동유형 = {값:"만들기", 근거:"뭔가 만드는 게 좋아요"}
  "사람 챙기고 돌보는 게 편해요"
      → 활동유형 = {값:"돕기·돌봄", 근거:"챙기고 돌보는 게 편해요"}, 다루는대상 = {값:"사람", 근거:"사람 챙기고"}
  "웹 쪽으로 만들고 싶어요"
      → 세부관심 = {값:"웹", 근거:"웹 쪽으로"}
  "잘 모르겠어요"
      → 아무 슬롯도 내지 않는다

★ 근거로 쓸 말이 발화에 없으면 그 슬롯을 아예 내지 마라.
  지어낸 근거는 시스템이 원문과 대조해서 걸러내므로, 채워도 버려진다.
  "모르겠다"는 슬롯을 내지 않는 쪽이다. 목록 안에서 억지로 고르지 마라.
★ 반대로, 발화에 '무엇을 다루는지'가 드러나면(사람·기계·컴퓨터·자연·창작물·숫자) 다루는대상을 꼭 채워라.
  이게 직업을 크게 가르는 축이다 — "사람 돌보는 일"이면 다루는대상=사람 을 빠뜨리지 마라.

[관심분야를 직업으로 바꾸지 않는다]
관심은 목적지가 아니라 성향의 단서다.
  "게임을 좋아한다"  → 컴퓨터·화면을 편해한다는 신호로 읽는다.
                      그냥 놀았다는 뜻일 수 있으니 '게임 업계'로 단정하지 않는다.
  "요리를 좋아한다"  → 조리사만이 아니라 식품·제과 등 여러 길이 있다.

[질문]
[아직 모르는 것] 중 가장 앞의 것을 하나만 묻는다.
둘 중 하나 고르기가 서술형보다 답하기 쉽다.

[행동 — 하나만 고른다]
DIRECT    ★ 사용자가 목표를 이미 분명히 말했다 → 슬롯을 더 묻지 말고 바로 찾는다
ASK       아직 모르는 슬롯이 있다 → 하나만 묻는다
CLARIFY   앞뒤 말이 실제로 모순된다 → 어느 쪽인지 확인한다
          (단순히 정보가 부족한 것은 모순이 아니다. 그건 ASK다)
SEARCH    착지 가능 상태다 → 찾는다
OFFRAMP   어떤 일에도 이어주기 어렵다 (돌봄 지원 등 다른 도움으로 안내)
REDIRECT  가해·해악의 의도, 선정적 표현, 욕설/도발 → 차분히 되돌린다
          ※ '군인·경찰·소방관' 같은 직업으로서의 관심은 정상이다. 절대 REDIRECT 하지 마라.

[DIRECT — 이미 답을 가진 사람에게 되묻지 마라]
목표를 분명히 말한 사람에게 "무슨 일을 좋아하세요?"를 다시 묻는 건 무례하고 시간 낭비다.
아래 셋 중 하나면 DIRECT 다. 슬롯이 비어 있어도 상관없다.
  자격증  "전기기능사 따고 싶어요"        → query = "전기기능사"
  직업    "제빵사가 되고 싶어요"          → query = "빵과 과자를 만드는 일"
  하는 일 "컴퓨터 고치는 일 하고 싶어요"   → query = "컴퓨터와 주변기기를 점검하고 수리하는 일"
자격증 이름을 그대로 말했으면 그 이름을 query 에 그대로 써라.
직업이나 일로 말했으면 '무슨 일을 하는지'로 풀어 써라.

★ 막연한 관심은 DIRECT 가 아니다.
  "컴퓨터 좋아해요"  → ASK (뭘 하고 싶은지 아직 모른다)
  "요리가 재밌어요"  → ASK
  목표를 말한 것과 관심을 말한 것은 다르다. 헷갈리면 ASK 를 골라라.

[착지 규칙]
직업을 가리키는 세 축(관심분야·활동유형·다루는대상) 중 2개 이상이 채워지면 착지 가능이다.
★ 판단은 '이번 턴에 네가 새로 파악한 것까지 포함한 상태'로 하라.
   이번 턴에 마지막 조건이 채워졌다면 곧바로 SEARCH로 가라. 한 턴 더 묻지 마라.
조건이 충족되지 않으면 SEARCH를 고르지 마라. 예외 없다.
※ 착지해도 후보가 여러 갈래로 흩어지면 시스템이 '어떤 쪽인지' 한 번 더 되물어 좁힌다(네가 할 일 아님).

[검색 질의 — SEARCH/DIRECT일 때만 query를 쓴다]
query에는 이 사람이 '어떤 일을 하게 될지'를 풀어 쓴다.
직업·자격증 이름을 짐작해서 쓰지 마라. 그건 시스템이 찾는다.
  관심분야=컴퓨터 / 활동유형=만들기 / 세부관심=게임
      → query = "컴퓨터로 게임을 만드는 일"
  관심분야=기계 / 활동유형=고치기·정비
      → query = "기계나 장비를 점검하고 수리하는 일"
  관심분야=요리 / 활동유형=만들기
      → query = "주방에서 재료를 손질하고 음식을 만드는 일"
★ 세부관심(좁혀진 방향)이 있으면 반드시 query에 넣어라 — 구체적일수록 잘 찾는다.
직업 설명은 '무슨 일을 하는지'로 적혀 있다. 그 말투에 맞춰 쓸수록 잘 찾는다.

[말투]
따뜻하되 과장하지 않는다. 상대의 상황을 앞질러 규정하지 않는다.
'고생 많으셨겠어요' 같은 말은 사용자가 실제로 그 상황을 말했을 때만 쓴다."""


class ItdaEngine:
    """import 시점에는 아무것도 연결하지 않는다. 필요할 때 붙는다."""

    def __init__(self, gemini_key=None, model=MODEL,
                 think_budget=None, think_level=None, provider=None):
        self.model = model
        # 대화 모델 제공자 — 'gemini'(기본) 또는 'solar'(A/B용). 임베딩은 항상 Gemini.
        self.provider = provider or ENV.get('ITDA_PROVIDER') or 'gemini'
        # Gemini 키 정책은 gemini_util 로 옮겼다(2026-07-24):
        #  무료 키 우선 · 분당 한도는 기다렸다 재시도 · 유료(키3)는 무료 '하루' 한도가 다 빠졌을 때만.
        #  여기선 '명시 키'만 기억한다(테스트용). 명시 없으면 util 이 ENV 에서 무료/유료를 가른다.
        self._explicit_key = bool(gemini_key)
        if gemini_key:
            self.gemini_keys = [gemini_key]
        else:
            self.gemini_keys, _ = _gutil.split_keys(ENV)      # 표시/호환용 (실제 회전은 util)
        # 사고(thinking) 토큰 — 화면엔 안 보이는데 출력 단가로 과금된다(실측: 비용의 약 69%).
        #  두 가지 조절 수단 — 둘 다 안 주면 모델 기본(dynamic thinking, 난이도별 자동조절).
        #   think_level : 'minimal'|'low'|'medium'|'high'  ← gemini-3.6-flash 의 현행 방식
        #                 실측(2026-07-24): minimal 이면 사고 0 인데도 쉬운/모호 입력 모두
        #                 dynamic 과 같은 슬롯·action 을 냈다. thinkingBudget=128 과 달리
        #                 '생각하다 잘림'이 아니라 '깔끔한 최소'라 품질이 덜 깨진다.
        #   think_budget: 정수 상한 (gemini-2.5 시절 방식). 128 이면 사고 0 이나 판단이 흔들림.
        #  ※ 둘 다 있으면 think_level 이 우선.
        self.think_level = think_level or (ENV.get('ITDA_THINK_LEVEL') or None)
        if think_budget is None:
            v = ENV.get('ITDA_THINK_BUDGET')
            think_budget = int(v) if v and v.strip().isdigit() else None
        self.think_budget = think_budget
        self._turn_schema = None
        self.last_usage = {'in': 0, 'out': 0, 'think': 0, 'cached': 0}
        self.total_usage = {'in': 0, 'out': 0, 'think': 0, 'cached': 0, 'calls': 0}

    # DB 는 더 이상 엔진이 커넥션을 들고 있지 않는다(2026-07-24 async 전환).
    #  예전엔 self.db 프로퍼티가 전역 pymysql 커넥션을 재사용했는데, 그걸 여러
    #  워커 스레드가 공유해 프로토콜이 깨졌다(코드리뷰 HIGH). 이제는 요청마다
    #  세션을 밖(get_db/async_session)에서 받아 step()·search() 에 넘긴다.
    #  oblig_flds 프로퍼티(대직무분야 enum)는 벡터 직결로 바뀌며 죽어 함께 제거.

    @property
    def turn_schema(self):
        """oblig_fld(대직무분야 17 enum)는 2026-07-23 에 뺐다.

        예전엔 모델이 대직무분야를 하나 고르고 그 안에서만 자격증을 찾았는데,
        그게 병목이었다 — 기능사가 0개인 대직무분야가 7개고, 국가전문자격 100종은
        oblig_fld 가 빈 문자열이라 애초에 후보에 못 들어왔다.
        지금은 query 로 613종 전체를 벡터 검색한다. 대분류를 거치지 않는다.
        """
        if self._turn_schema is None:
            self._turn_schema = {'type': 'OBJECT', 'properties': {
                'reply':   {'type': 'STRING'},
                'profile': PROFILE_SCHEMA,
                'action':  {'type': 'STRING',
                            'enum': ['DIRECT', 'ASK', 'CLARIFY', 'SEARCH',
                                     'OFFRAMP', 'REDIRECT']},
                'query':   {'type': 'STRING'}},
                'required': ['reply', 'action', 'profile']}
        return self._turn_schema

    # ── Gemini 구조화 출력 ──────────────────────────────────────────
    #  HTTP 자체는 동기(urllib)다. async 전환 후에도 검증된 이 코드를 지키되,
    #  네트워크 I/O 를 asyncio.to_thread 로 던져 이벤트 루프를 막지 않는다.
    #  (quota 풀리면 팀처럼 httpx.AsyncClient 로 바꿀 수 있다 — 그때 E2E 검증 가능)
    async def gemini(self, prompt, schema, temp=0.7):
        # Solar 제공자면 대화 모델을 교체 — 구조화 출력·usage 를 Gemini 형식으로 맞춰 받는다.
        if self.provider == 'solar':
            j, u = await _solar.call(prompt, schema, temp, ENV)
            self.last_usage = {**u}
            for k in ('in', 'out', 'think', 'cached'):
                self.total_usage[k] = self.total_usage.get(k, 0) + u.get(k, 0)
            self.total_usage['calls'] += 1
            return j
        cfg = {'responseMimeType': 'application/json',
               'responseSchema': schema, 'temperature': temp}
        if self.think_level:
            cfg['thinkingConfig'] = {'thinkingLevel': self.think_level}
        elif self.think_budget is not None:
            cfg['thinkingConfig'] = {'thinkingBudget': self.think_budget}
        body = json.dumps({'contents': [{'parts': [{'text': prompt}]}],
                           'generationConfig': cfg}).encode()

        # 무료 키 우선 · 분당 한도는 대기 · 유료는 하루소진 때만 (정책은 gemini_util).
        def _post(key):
            url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
                   f'{self.model}:generateContent?key={key}')
            req = urllib.request.Request(url, data=body,
                                         headers={'Content-Type': 'application/json'})
            return urllib.request.urlopen(req, timeout=90).read()

        j = await _gutil.call(_post, ENV,
                              keys_override=self.gemini_keys if self._explicit_key else None)
        # 과금 근거를 남긴다 — 사고 토큰은 화면에 안 보이므로 이걸로만 확인 가능
        #  cached: 프롬프트 캐싱으로 재사용된 입력 토큰. 있으면 그만큼 입력비가 싸진다.
        um = j.get('usageMetadata') or {}
        self.last_usage = {
            'in': um.get('promptTokenCount', 0),
            'out': um.get('candidatesTokenCount', 0),
            'think': um.get('thoughtsTokenCount', 0),
            'cached': um.get('cachedContentTokenCount', 0),
        }
        for k in ('in', 'out', 'think', 'cached'):
            self.total_usage[k] = self.total_usage.get(k, 0) + self.last_usage[k]
        self.total_usage['calls'] += 1

        c = (j.get('candidates') or [{}])[0]
        if not c.get('content', {}).get('parts'):
            return None                            # 안전필터 차단
        return json.loads(c['content']['parts'][0]['text'])

    # gemini-3.6-flash 단가(2026-07) — 사고 토큰은 출력 단가로 과금된다
    PRICE_IN, PRICE_OUT, FX = 1.50, 7.50, 1400

    def cost_krw(self, u=None):
        u = u or self.total_usage
        return (u['in'] * self.PRICE_IN + (u['out'] + u['think']) * self.PRICE_OUT) / 1e6 * self.FX

    # ── 한 턴 ───────────────────────────────────────────────────────
    #  temperature 0.7 → 0.3 : 같은 발화인데 슬롯을 담았다 말았다 하는 흔들림이 실측됨
    #  (말투 다양성보다 "말한 것을 빠뜨리지 않는" 일관성이 훨씬 중요하다)
    TEMP_TURN = 0.3

    async def turn(self, profile, user_msg):
        miss = missing_slots(profile)
        prompt = (f"{SYSTEM}\n\n"
                  f"[지금까지 파악한 것]\n{profile_text(profile)}\n\n"
                  f"[아직 모르는 것]\n{', '.join(miss) if miss else '(없음)'}\n\n"
                  f"[이번 턴 입력 전 착지 조건]\n"
                  f"{'이미 충족 — SEARCH 가능' if can_land(profile) else '아직 미충족 (이번 턴에 채워지면 충족될 수 있다. 착지 규칙 참고)'}\n\n"
                  f"[사용자]\n{user_msg}")
        return await self.gemini(prompt, self.turn_schema, self.TEMP_TURN)

    # ── 검색 상수 ────────────────────────────────────────────────────
    #  (2026-07-28 cert-먼저 잔재 청소) 예전 자격증 벡터검색 상수
    #  CAND_POOL·N_NOW·DIRECT_MIN_SCORE·KW_MIN_SCORE 제거 — 직업-먼저 전환으로
    #  런타임이 match_jobs 를 쓰면서 죽었다. 직업 검색 상수는 JOB_* (아래).

    # 강좌를 '관련 있다'고 부를 최소 유사도.
    #  K-MOOC 은 대학 강의라 자격증 분야를 다 덮지 못한다. 임계가 없으면 아무거나 붙는다.
    #  실측(2026-07-23):
    #      전기기능사   0.813 전기전자기초 · 0.786 회로이론          ← 관련
    #      정보처리기사 0.837 정보통신 보안 · 0.804 …                ← 관련
    #      제빵기능사   0.693 컴퓨터활용능력 1급 ← 1위가 이것. 무관  ★ K-MOOC 에 제빵 강좌가 없다
    #  "제빵기능사 준비하려면 컴퓨터활용능력 1급을 들으세요" 가 나가면 거기서 신뢰가 끝난다.
    #  강좌가 0개면 카드가 국민내일배움카드 안내로 대체되므로, 걸러도 사용자는 갈 곳이 있다.
    #  ※ 임시값이다. eval_match_매칭평가.py 로 사람이 판정해 다시 정할 것.
    COURSE_MIN_SCORE = 0.70

    # ── 직업 먼저(2026-07-27) — 직업을 벡터로 찾고, 그 직업의 자격증(≤3)을 역방향으로 붙인다 ──
    JOB_CAND_POOL = 8         # 직업 후보 수
    JOB_MIN_SCORE = 0.45      # DIRECT '없음' 판정선 — 직업 벡터가 얇어('직업명·중분류') cert 0.70보다 낮게 잡는다
    N_CERTS       = 3         # 직업당 자격증 최대 (「지금 바로」 우선)
    JOB_NARROW_GAP = 0.04     # 1위가 3위를 이만큼 확실히 앞서면 '뚜렷한 승자' → 안 좁히고 착지 (narrowing 문턱)

    #  (2026-07-28) _named_pick(자격증 이름 지목) 제거 — 직업-먼저에선 _named_job(직업 이름 지목)이 대신한다.
    @staticmethod
    def _named_job(query, jobs):
        """발화에 '직업 이름'이 그대로 들어 있으면 그 후보를 돌려준다(없으면 None).
        "웹개발자가 되고 싶어요" → 후보 중 job_name 이 발화에 통째로 있으면 지목으로 본다."""
        nq = _clean(query)
        if not nq:
            return None
        for j in jobs:
            nm = _clean(j['job_name'])
            if nm and len(nm) >= 2 and nm in nq:
                return j
        return None


    # ── 코드 DIRECT 탐지(2026-07-29) — LLM 의 action 을 안 믿고, '이름'을 코드가 직접 본다 ──
    #   저비용 모델(minimal·flashlite)이 "전기기능사 따고 싶어요"를 ASK 로 흘리던 것(NRM-direct-cert)
    #   을 코드가 잡는다. 부분 ngram(키워드 점수)은 '김치찌개'→김치가공, '시스템 프롬프트'→시스템 처럼
    #   이탈·인젝션을 오탐한다(실측). 그래서 '정확 포함'만 신뢰한다 — 발화가 DB 의 완전한 이름을
    #   통째로 담을 때만. 모호·이탈·인젝션·가짜주장은 완전한 이름이 없어 안 걸린다(오탐 0, 20케이스 실측).
    async def _on_topic(self, user_msg):
        """이탈(레시피·날씨·번역·잡담)이면 False, 진로 관련이면 True. 전용 이진 판별기.
        omnibus turn() 이 이탈에 카드를 뱉는 걸 막는다. 실패(None)하면 True(막지 않음) —
        게이트 오류로 정상 대화를 끊지 않는다(위험군은 pre_check·인젝션 게이트가 이미 막았다)."""
        j = await self.gemini(GATE_ONTOPIC.format(msg=user_msg), _GATE_SCHEMA, 0.0)
        return True if j is None else bool(j.get('on_topic', True))

    async def _named_entity(self, db, user_msg):
        """발화가 실재 직업/자격증 이름을 통째로 담으면 그 '직업코드'를 돌려준다(없으면 None).

        직업명이면 그 코드, 자격증명이면 cert_job 으로 대표 직업(검증·점수 우선)으로 바꾼다.
        공백은 무시(‘컴퓨터활용능력 1급’=‘컴퓨터활용능력1급’). 가장 긴 이름을 채택(구체 우선).
        """
        msg = re.sub(r'\s+', '', user_msg or '')
        if len(msg) < 3:
            return None
        # ① 직업 이름 직접 포함 (공백 무시, 3자 이상)
        row = (await db.execute(text(
            "SELECT job_code FROM job_catalog "
            "WHERE CHAR_LENGTH(REPLACE(job_name, ' ', '')) >= 3 "
            "  AND :m LIKE CONCAT('%', REPLACE(job_name, ' ', ''), '%') "
            "ORDER BY CHAR_LENGTH(job_name) DESC LIMIT 1"), {'m': msg})).fetchone()
        if row:
            return str(row[0])
        # ② 자격증 이름 직접 포함 → 그 자격증으로 이어지는 대표 직업
        row = (await db.execute(text(
            "SELECT cert_id FROM certification "
            "WHERE CHAR_LENGTH(REPLACE(jm_name, ' ', '')) >= 3 "
            "  AND :m LIKE CONCAT('%', REPLACE(jm_name, ' ', ''), '%') "
            "ORDER BY CHAR_LENGTH(jm_name) DESC LIMIT 1"), {'m': msg})).fetchone()
        if row:
            jr = (await db.execute(text(
                "SELECT job_code FROM cert_job WHERE cert_id = :c "
                "ORDER BY verified DESC, score DESC LIMIT 1"), {'c': int(row[0])})).fetchone()
            if jr:
                return str(jr[0])
        return None

    async def _job_by_code(self, db, code):
        """직업코드 → 카드가 쓰는 직업 dict(없으면 None). 코드 DIRECT 확정 직업을 그대로 세운다."""
        row = (await db.execute(text(
            "SELECT job_code, job_name, job_mcls_name, job_description "
            "FROM job_catalog WHERE job_code = :c"), {'c': str(code)})).fetchone()
        if not row:
            return None
        return {'job_code': str(row[0]), 'job_name': row[1], 'group': row[2],
                'description': row[3], 'score': 1.0, 'kw_score': 0.0}

    def _search_query(self, profile, query=''):
        """모델이 query 를 안 줬을 때 쓸 대체 질의 — 슬롯을 이어붙인다."""
        if query:
            return query
        p = profile or {}
        #  세부관심(좁혀진 방향)을 관심분야 바로 뒤에 둬 검색을 구체화한다.
        bits = [p.get('관심분야'), p.get('세부관심'), p.get('활동유형'),
                p.get('다루는대상'), p.get('강점성향')]
        return ' '.join(x for x in bits if x)

    async def _next_exam(self, db, cert_id):
        """'다음' 시험 — 회차 번호가 아니라 '오늘 이후 날짜' 중 가장 가까운 것.

        회차순 정렬은 제0회(필기 없는 특별회차)나 이미 지난 회차를 뽑아버린다(실측).
        """
        SEL = ("SELECT impl_seq, doc_exam_start, prac_exam_start, prac_pass_dt "
               "FROM exam_schedule WHERE cert_id = :cid ")
        r = await db.execute(text(
            SEL + " AND (doc_exam_start >= CURDATE() OR prac_exam_start >= CURDATE())"
                  " ORDER BY COALESCE(doc_exam_start, prac_exam_start) LIMIT 1"), {"cid": cert_id})
        exam = r.fetchone()
        if not exam:                           # 남은 일정이 없으면 가장 최근 것이라도
            r = await db.execute(text(
                SEL + " ORDER BY COALESCE(doc_exam_start, prac_exam_start) DESC LIMIT 1"),
                {"cid": cert_id})
            exam = r.fetchone()
        return exam

    #  (2026-07-28) _jobs_for(자격증→직업) 제거 — cert-먼저에서 '자격증 카드에 직업을 얹던' 함수.
    #  직업-먼저에선 직업이 주인공이고, 그 직업의 자격증을 붙이는 _certs_for(역방향)가 대신한다.
    async def _certs_for(self, db, job_code, k=3):
        """직업 → 그 직업으로 이어지는 자격증 (cert_job 역방향). 「지금 바로」(entry_free) 우선.

        직업 먼저(2026-07-27)의 심장 — 직업을 정한 뒤 그 직업의 자격증 최대 3개를 붙인다.
        정렬: 지금 바로 응시 가능 → 검증된 연결 → 유사도.
        빈 리스트면 그 직업엔 국가기술자격이 없다는 뜻 → 카드가 내일배움카드+강좌로 대체한다.
        """
        r = await db.execute(text(
            "SELECT c.cert_id, c.jm_name, COALESCE(c.grade_std, c.grade), c.oblig_fld, "
            "       c.entry_free, c.entry_note, cj.verified "
            "FROM cert_job cj JOIN certification c ON c.cert_id = cj.cert_id "
            "WHERE cj.job_code = :jc "
            "ORDER BY (c.entry_free = 1) DESC, cj.verified DESC, cj.score DESC "
            f"LIMIT {int(k)}"), {"jc": str(job_code)})
        return [{'cert_id': row[0], 'jm_name': row[1], 'grade': row[2], 'oblig_fld': row[3],
                 'entry_free': row[4] == 1, 'entry_note': row[5], 'verified': bool(row[6])}
                for row in r.fetchall()]

    #  (2026-07-28) GRADE_LADDER·_next_step·_ladder 제거 — cert-먼저 카드가 '기능사→산업기사→기사'
    #  등급 사다리를 그리던 것. 직업-먼저 카드는 '그 직업의 자격증 ≤3개'(certs)를 보여줘 사다리가 불필요.
    @staticmethod
    def _is_spread(jobs):
        """후보가 여러 갈래로 흩어졌나 — 뚜렷한 1등이 없으면 True(좁혀야 함).

        (2026-07-28 하이브리드) 키워드가 1위를 확실히 집었으면(정확한 이름 매칭) 흩어진 게
        아니다 → 좁히지 않고 착지. 아니면 벡터 1위가 3위를 확실히 앞서는지로 판정한다.
        """
        if len(jobs) < 3:
            return False        # 후보가 적으면 좁힐 게 없다
        top = jobs[0]
        if top.get('kw_score', 0) >= 5.0 and top.get('kw_score', 0) > jobs[1].get('kw_score', 0):
            return False        # 키워드가 정확한 이름을 집음 → 이미 정해진 것
        return (top['score'] - jobs[2]['score']) < ItdaEngine.JOB_NARROW_GAP

    async def search(self, db, profile, query='', direct=False, force_code=None):
        """착지 후 카드 만들기 — 직업 먼저(2026-07-27).

        직업을 벡터로 찾고, 그 직업의 자격증(≤3)을 cert_job 역방향으로 붙인다.
        자격증이 없는 직업(요양간호사·웹개발자 등)도 그대로 보여주되, 자격증칸 대신
        국민내일배움카드 + K-MOOC 강좌로 대체한다(사용자 결정 2026-07-27).

        direct=True 는 사용자가 목표(직업)를 콕 집어 말한 경우다.
          · 직업명이 발화에 그대로 있으면 그걸 고른다(모델에게 다시 안 물어봄).
          · 지목도 아니고 1위 유사도가 JOB_MIN_SCORE 미만이면 '우리에게 없다'고 한다.
        """
        q = self._search_query(profile, query)

        # ★ 코드 DIRECT 확정(2026-07-29) — 발화에 실재 이름이 통째로 있으면 그 직업으로 바로 세운다.
        #   벡터 드리프트·narrow·not_found 를 전부 우회한다(가장 결정론적인 착지). force_code 는
        #   step() 의 _named_entity 가 넘긴 직업코드. 후보(jobs)는 대안 표시용으로만 참고.
        forced = await self._job_by_code(db, force_code) if force_code else None
        if not q and not forced:
            return None
        m = _match_mod()

        # ① 직업 후보 — ns=job 벡터. 자격증 못 잇는 직업도 후보로 살린다(내일배움카드로 대체).
        jobs = await m.match_jobs(db, q, top_k=self.JOB_CAND_POOL) if q else []
        if not jobs and not forced:
            return None

        # ★ 직업 이름을 그대로 말했는가 — '없음' 판정보다 먼저 본다. (forced 면 이미 확정이라 스킵)
        named = self._named_job(q, jobs) if (direct and not forced) else None

        # ★ 지목도 아니고 1위 점수도 낮으면 → 우리에게 없다(지어내지 않는다). (forced 면 스킵)
        if direct and not forced and not named and jobs and jobs[0]['score'] < self.JOB_MIN_SCORE:
            return {'not_found': True, 'query': q,
                    'near': [{'job': j['job_name'], 'group': j['group']} for j in jobs[:3]]}

        # ★ 넓게 흩어졌나(narrowing) — 뚜렷한 1등이 없고 세부관심도 아직 없으면 한 번 좁힌다.
        #   "컴퓨터로 만드는 일" → 게임/웹/앱/응용SW 로 흩어질 때 바로 확정하지 않고 되묻는다.
        #   목표를 콕 집어 말했으면(named/forced) 넘어가고, 좁힌 뒤엔 세부관심이 차서 재검색 때 통과한다.
        if not forced and not named and not (profile or {}).get('세부관심') and self._is_spread(jobs):
            return {'narrow': True, 'query': q,
                    'options': [j['job_name'] for j in jobs[:4]]}

        # ② 직업 1개 선택 — 코드확정(forced)이면 코드, 지목이면 코드, 키워드 확정승자면 코드, 아니면 모델
        if forced:
            chosen, job_reason = forced, '말씀하신 걸 바로 찾아봤어요.'
        elif named:
            chosen, job_reason = named, '말씀하신 일이에요.'
        elif jobs[0].get('kw_score', 0) >= 5.0 and jobs[0].get('kw_score', 0) > (jobs[1].get('kw_score', 0) if len(jobs) > 1 else 0):
            #  ★ 키워드가 1위를 확실히 집으면(예: '요양'→요양지원 kw 9.12) LLM 픽을 건너뛰고 그대로 — (2026-07-29)
            #    벡터가 '돌봄' 클러스터로 뭉쳐 LLM 픽이 옆(아이돌봄·자원봉사)으로 흔들리던 것 차단.
            chosen, job_reason = jobs[0], '말씀하신 것과 가장 맞닿은 일이에요.'
        else:
            # ★ 크로스인코더 리랭크(2026-07-29) — 벡터+키워드로 좁힌 후보의 '마지막 관련도 심판'.
            #   기존엔 여기서 LLM(enum)에게 1개를 고르게 했다. 리랭커로 대체한다 —
            #   질의·후보를 함께 읽어 더 정확하고, LLM 콜 하나를 없애 비용·지연·드리프트를 줄인다.
            #   리랭크가 실패하면(쿼터·권한·네트워크) RRF 1위로 폴백한다(리랭크는 개선이지 필수가 아니다).
            docs = [f"{j['job_name']} {j['group'] or ''} {(j.get('description') or '')[:120]}".strip()
                    for j in jobs]
            ranked = await m.rerank(q, docs)
            chosen = jobs[ranked[0][0]] if ranked else jobs[0]
            job_reason = '말씀하신 내용과 가장 관련도가 높은 일이에요.'

        # ③ 그 직업의 자격증 (cert_job 역방향, ≤3) — 「지금 바로」 우선. 없으면 빈 리스트.
        certs = []
        for c in await self._certs_for(db, chosen['job_code'], k=self.N_CERTS):
            certs.append({
                'cert': c['jm_name'], 'cert_id': c['cert_id'], 'grade': c['grade'],
                'entry_free': c['entry_free'], 'entry_note': c['entry_note'],
                'verified': c['verified'],
                'exam': await self._next_exam(db, c['cert_id']),
            })
        no_cert = not certs

        # ④ 강좌 — 자격증 대신 '직업 맛보기'. 직업명·분야·관심사로 던진다.
        cq = ' '.join(x for x in [chosen['job_name'], chosen['group'],
                                  (profile or {}).get('관심분야')] if x)
        courses, course_err = [], None
        try:
            courses = await m.match_courses(db, cq, top_k=3, min_score=self.COURSE_MIN_SCORE)
        except Exception as e:
            course_err = f'{type(e).__name__}: {str(e)[:80]}'

        # ⑤ 국비 실전훈련 — 고용24(HRD-Net) 훈련검색 딥링크(핸드오프, 2026-07-29).
        #   카탈로그 API 는 게이트라 못 당김 → '이 직무로 검색된 화면' 링크로 넘긴다(PC 차단·모바일만).
        hire_url = ('https://m.work24.go.kr/hr/a/a/1100/trnnCrsInf.do?'
                    f"keyword={urllib.parse.quote(chosen['job_name'])}&searchYn=Y")
        return {
            # ★ 카드의 주인공 — '직업'(=방향). 선고가 아니라 안내: 설명으로 '이 방향'을 보여준다.
            'job': {'name': chosen['job_name'], 'group': chosen['group'],
                    'code': chosen['job_code'],                  # 미래설계지도 저장용(itda_map FK)
                    'description': chosen.get('description')},   # NCS DUTY_DEF(설명·2026-07-29)
            'job_reason': job_reason,
            'certs': certs,                        # 「지금 바로」 우선 정렬된 ≤3
            'no_cert_path': no_cert,               # True → 자격증 대신 내일배움카드
            'guide': ('이 방향은 국가기술자격으로 바로 이어지진 않아요. '
                      '국민내일배움카드로 훈련비를 지원받아 아래 강좌부터 시작할 수 있어요.')
                     if no_cert else '',
            'courses': courses, 'course_error': course_err,
            'hire': {'label': f"'{chosen['job_name']}' 국비 훈련 찾기",
                     'url': hire_url,
                     'note': '국민내일배움카드로 훈련비 지원 · 고용24(HRD-Net)에서 검색'},
            'alternatives': [j['job_name'] for j in jobs
                             if j['job_name'] != chosen['job_name']][:2],
        }

    # ── 백엔드가 부를 단일 진입점 ───────────────────────────────────
    async def step(self, db, profile, user_msg):
        """한 턴을 통째로 처리. HTTP 응답으로 그대로 옮길 수 있는 모양으로 돌려준다.

        db 는 요청마다 밖에서 받은 async 세션(get_db). 엔진은 커넥션을 안 들고 있다.
        """
        profile = profile or {}

        pc = pre_check(user_msg)
        if pc == 'VAGUE':
            return {'kind': 'blocked', 'profile': profile,
                    'reply': '잘 못 알아들었어요. 관심 있는 것이나 좋아하는 걸 다시 말씀해 주실래요?',
                    'missing': missing_slots(profile), 'can_land': can_land(profile), 'card': None}
        if pc == 'UNSAFE':
            return {'kind': 'blocked', 'profile': profile,
                    'reply': '그런 이야기는 도와드리기 어려워요. 되고 싶은 모습이나 관심 있는 걸 들려주세요.',
                    'missing': missing_slots(profile), 'can_land': can_land(profile), 'card': None}

        # ★ 인젝션/탈옥 코드 게이트(2026-07-29) — LLM 부르기 전에 코드가 확정 차단(no_card 강제).
        #   문구는 코드가 쓴다 → 시스템 프롬프트·지시가 유출될 여지 자체가 없다. LLM 콜도 아낀다.
        if is_injection(user_msg):
            return {'kind': 'redirect', 'profile': profile,
                    'reply': '진로 상담에 집중할게요 — 요즘 어떤 일이나 활동에 마음이 가는지 편하게 들려주세요.',
                    'missing': missing_slots(profile), 'can_land': can_land(profile), 'card': None}

        # ★ 이탈 주제 게이트(2026-07-29) — 진로 무관 요청(레시피·날씨·잡담)에 카드가 나가는 걸 막는다.
        #   콜드 오픈(관심축이 아직 빔)에서만 건다 — 진로맥락이 서면 짧은 이어말('네')을 오판하지 않게
        #   건너뛴다. '모르겠어요' 류(is_uncertain)도 건너뛴다 — 진로 고민의 정상 표현이라 되묻기(guide)로
        #   받아야지 이탈로 되돌리면 안 된다. 위험군(인젝션·유해)은 위에서 처리. 여기선 '양성 이탈'만 되돌린다.
        if not has_interest(profile) and not is_uncertain(user_msg) and not await self._on_topic(user_msg):
            return {'kind': 'redirect', 'profile': profile,
                    'reply': '저는 진로·적성 상담을 도와드려요 — 요즘 어떤 일이나 활동에 마음이 가는지 '
                             '들려주시면 잘 맞는 길을 함께 찾아볼게요.',
                    'missing': missing_slots(profile), 'can_land': can_land(profile), 'card': None}

        # ★ 가짜자격 복창 가드(2026-07-30) — 실재하지 않는 자격 보유 주장은 코드가 확정 문구로 되받는다.
        #   모델이 복창·인정하는 걸(프롬프트로 못 막던) 원천 차단. 진짜 자격은 _named_entity 가 살려준다.
        if claims_credential(user_msg) and not await self._named_entity(db, user_msg):
            return {'kind': 'ask', 'profile': profile,
                    'reply': '말씀하신 자격은 제가 확인해 드리기 어려워요. 제가 함께 찾아드릴 수 있는 건 '
                             '국가공인 자격증이에요 — 먼저 어떤 일을 해보고 싶으신지 들려주시면 거기에 맞는 '
                             '자격증을 같이 찾아볼게요.',
                    'missing': missing_slots(profile), 'can_land': can_land(profile), 'card': None}

        t = await self.turn(profile, user_msg)
        if not t:                                   # 안전필터 차단
            return {'kind': 'blocked', 'profile': profile,
                    'reply': '그 부분은 도와드리기 어려워요. 다른 관심사를 편하게 말씀해 주세요.',
                    'missing': missing_slots(profile), 'can_land': can_land(profile), 'card': None}

        # ★ 근거 검증 — 발화에 없는 근거를 댄 슬롯은 버린다 (프롬프트가 아니라 코드가 막는다)
        new_slots, dropped = verify_slots(t.get('profile'), user_msg)
        profile = merge(profile, new_slots)
        act = t.get('action', 'ASK')

        # ★ 코드 DIRECT 탐지(2026-07-29) — 발화가 DB 실재 직업/자격증 이름을 통째로 담으면
        #   LLM 이 ASK/SEARCH 라 해도 코드가 그 직업으로 확정(DIRECT)한다. 저비용 모델(minimal·
        #   flashlite)이 "전기기능사 따고 싶어요"를 되묻던 것(NRM-direct-cert) 차단. '정확 포함'만
        #   신뢰하므로 이탈·인젝션·모호엔 안 걸린다(오탐 0, 20케이스 실측). 단, 모델이 명시적으로
        #   funnel 을 벗어난(REDIRECT/OFFRAMP) 건 존중한다(안전 우선 — 이름이 섞여도 뒤집지 않음).
        forced_code = None
        if act not in ('REDIRECT', 'OFFRAMP'):
            forced_code = await self._named_entity(db, user_msg)
            if forced_code:
                act = 'DIRECT'

        # ★ 착지 가드(양방향) — 착지 여부는 코드가 판정한다. 모델의 SEARCH/ASK 자기판단을 안 믿는다.
        #   DIRECT 는 슬롯이 아니라 '목표를 말했는가'로 판단하므로 이 가드를 안 받는다(search 안 유사도로 검증).
        #   ↓ 미착지인데 SEARCH → 되묻기로 내림 (성급한 추천 방지)
        #   ↑ 착지 가능인데 ASK → 검색으로 올림. 프롬프트가 "채워지면 바로 SEARCH"라 부탁해도
        #     사고 적은 모델(minimal)이 흘려 한 턴 더 되묻는 게 실측됨(HAP-004·ADV-005: 슬롯은 dynamic과
        #     동일한데 ask). "충분한가"는 슬롯이 정하므로 코드가 강제한다. CLARIFY(모순확인)는 안 건드린다.
        if act == 'SEARCH' and not can_land(profile):
            act = 'ASK'
        elif act == 'ASK' and can_land(profile):
            act = 'SEARCH'

        # ★ "잘 모르겠어요" 가드(2026-07-29) — 못 정하는 사용자를 억지로 착지시키지 않는다.
        #   좁히기 질문에 '모르겠다'가 오면 하나 골라 던지지 말고, 왜 끌렸는지부터 같이 연다.
        guided = act == 'SEARCH' and is_uncertain(user_msg)
        if guided:
            act = 'ASK'

        out = {'kind': act.lower(), 'reply': t.get('reply', ''), 'profile': profile,
               'missing': missing_slots(profile), 'can_land': can_land(profile),
               'dropped': dropped, 'card': None, 'near': None}
        if guided:
            out['reply'] = guide_reply(profile)
        elif act == 'ASK' and '?' not in (out['reply'] or ''):
            out['reply'] = ask_reply(profile)   # ASK인데 질문 없이 '찾아볼게요' 류로 끝냄 → 진짜 질문으로(막다른 답변 방지)

        if act in ('SEARCH', 'DIRECT'):
            #  검색어 앵커(2026-07-29) — 벡터가 '돌봄' 등 종류로 뭉쳐 드리프트하는 걸 사용자 원문 키워드로 고정.
            #  DIRECT(콕 집음)는 LLM 재작성이 '아이/청소년' 같은 엉뚱한 키워드를 섞어 오염시키므로 원문만 쓴다.
            #  SEARCH(누적·좁힘)는 슬롯 기반 query 가 필요하니 query + 원문.
            q = user_msg if act == 'DIRECT' else f"{t.get('query', '')} {user_msg}".strip()
            card = await self.search(db, profile, q, direct=(act == 'DIRECT'), force_code=forced_code)
            if card and card.get('narrow'):
                out['kind'] = 'ask'                           # 넓게 흩어짐 → 좁히는 되물음(코드가 문구 씀)
                out['reply'] = narrow_reply(card['options'])
            elif card and card.get('not_found'):
                out['kind'] = 'notfound'
                out['near'] = card['near']
                out['reply'] = notfound_reply(card['near'])   # 모델 말 대신 코드가 쓴다
            elif card:
                out['kind'], out['card'] = 'card', card
                # 카드를 내놓으면 되물으면 안 된다 — ASK→SEARCH 승격 시 모델 답이 질문일 수 있다.
                if (out['reply'] or '').rstrip().endswith('?'):
                    out['reply'] = '말씀해 주신 걸 바탕으로 이 길을 찾아봤어요.'
            else:
                out['kind'] = 'ask'
                out['reply'] += '\n(아직 딱 맞는 자격증을 못 찾았어요 — 조금 더 얘기해볼까요?)'
        return out
