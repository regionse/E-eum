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
import re, json, asyncio
import urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone


#  ── 한국 날짜 (2026-07-31) ────────────────────────────────────────────
#   '오늘'을 서버 시계로 정하면 배포 환경에 따라 하루가 어긋난다(AWS 는 기본 UTC).
#   시험 접수 마감·D-day 처럼 하루가 중요한 계산은 **항상 한국 기준**이어야 하므로 코드가 정한다.
KST = timezone(timedelta(hours=9))

def kst_today():
    """한국 기준 오늘 날짜 — 서버가 어디에 있든 같은 값."""
    return datetime.now(KST).date()

def kst_now():
    """한국 기준 현재 시각(타임존 정보 없는 naive) — DB DATETIME 컬럼에 그대로 넣기 위함."""
    return datetime.now(KST).replace(tzinfo=None)
from sqlalchemy import text

#  (2026-07-30) async_session import 제거 — 본문에서 한 번도 쓰지 않았는데, 이 import 때문에
#   itda_core 를 import 하는 순간 db.py 가 실행돼 SQLAlchemy 엔진이 생겼다. 모듈 첫 줄 도크스트링의
#   "import 시 아무 부작용이 없다"가 실제로는 거짓이었다. DB 세션은 전부 step()·search() 인자로 받는다.

# Gemini 호출 공용(무료 우선·분당 대기·유료는 하루소진 때만) — 양쪽에서 import.
try:
    from . import gemini_util as _gutil
except ImportError:
    import gemini_util as _gutil

# ── .env 읽기 — 공용 로더 하나만 쓴다(2026-07-30, app/itda/env.py). 부작용 없음 ──
#   ※ MODEL 이 이 값을 쓰므로 반드시 MODEL 정의보다 위에 있어야 한다(2026-07-31 순서 조정).
try:
    from .env import ENV
except ImportError:                     # CLI: path 에 app/itda 가 들어와 있을 때
    from env import ENV


# ★ 대화 모델 — 팀 통합 .env 스키마에 맞춰 env 로 뺐다(2026-07-31).
#   전에는 상수로 고정했다(비용 사고 방지). 이제 3축이 같은 방식으로 관리하기로 해서 외부화한다.
#   기본값은 코드에 남긴다 — clone 한 사람이 .env 에 이 키가 없어도 그대로 돌아가야 한다.
#
#   선정 근거(실측): 3.6-flash vs 3.1-lite 골든셋 34/34 동일 · 흔들림은 3.6 이 더 큼(3/7 vs 2/7)
#                    · 비용 15배 차 → lite 채택. 말투 우위는 착시였다(카드 턴에서 답이 폐기되고 있었음).
#   ※ 2.5-flash-lite 는 목록엔 있으나 이 키로 404(사용불가).
MODEL = ENV.get('COURSE_LLM_MODEL') or 'gemini-3.1-flash-lite'
#  (2026-07-28) GRADE='기능사' 제거 — 옛 자격증 검색에서 grade 필터로 쓰였으나 직업-먼저 전환으로 죽음.


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
    #  (2026-07-30) 선택지를 문구에 나열하지 않는다 — 프론트가 클릭 chip 으로 그린다(응답의 options).
    #    예전엔 'CO₂용접 · 로봇용접' 같은 NCS 원문을 글로만 던져 사용자가 손으로 타이핑해야 했다.
    return ('관심 방향이 여러 갈래로 보여요. 아래에서 가까운 쪽을 눌러 주세요.\n'
            '(딱 맞는 게 없으면 더 구체적으로 말씀해 주셔도 좋아요.)')


# ── "잘 모르겠어요" 처리 — 못 정하는 사용자를 억지로 착지시키지 않는다(2026-07-29) ──
#  (2026-07-30) '생각 안 해봤어요' 계열 추가 — 실사용 로그에서 사용자가 두 턴 연속
#  "거기까지는 생각 안해봤는데" · "그것도 크게는 생각해보지않았어" 라고 했는데 이 목록에 없어서
#  못 알아채고 같은 결의 열린 질문을 반복했다(대화가 막혔다).
_UNCERTAIN = ('모르겠', '몰라', '글쎄', '아무거나', '상관없', '모르것', '모르겟',
              '생각안해', '생각해본적', '생각해보지', '생각못해', '생각안', '안해봤',
              '떠오르지', '떠오르는게없', '딱히없', '없는것같', '잘안떠')

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


# ── '모르겠다'가 반복될 때 — 같은 질문을 두 번 하지 않는다 (2026-07-30) ──────────────
#   실사용 로그: "생각 안 해봤다"가 두 번 왔는데 코드가 같은 질문을 글자 그대로 반복했다.
#   못 정하는 사람에게 같은 걸 다시 묻는 건 압박이다. 턴마다 **각도를 바꾼다** —
#   좋아하는 것 → 싫은 것(빼기가 더 쉽다) → 아예 보기 제시(고르기만 하면 되게).
_UNSURE_STEPS = [
    None,      # 1회: 빠진 슬롯의 보기 질문(ask_reply)을 그대로 쓴다
    ('그럼 반대로 여쭤볼게요 — 이건 좀 아니다 싶은 게 있으세요?\n'
     '사람 많은 곳 · 몸 많이 쓰는 일 · 하루 종일 앉아 있는 일 중에 하나만 빼주셔도 좁혀져요.'),
    ('괜찮아요, 지금 정하지 않아도 돼요. 그럼 제가 몇 가지 방향을 보여드릴게요 —\n'
     '· 사람 돌보는 일 (요양·간호 쪽)\n'
     '· 손으로 만드는 일 (제과제빵·가구 쪽)\n'
     '· 컴퓨터로 하는 일 (사무·데이터 쪽)\n'
     '· 자격증 따서 현장 가는 일 (전기·용접 쪽)\n'
     '이 중에 그나마 덜 부담스러운 게 있으세요? 아니면 "다 모르겠다"고 하셔도 돼요.'),
]

def unsure_reply(profile, n):
    """'모르겠다' n번째(1부터)에 맞는 되물음. 3회 이상이면 보기를 제시한다."""
    i = min(max(n, 1), len(_UNSURE_STEPS)) - 1
    return _UNSURE_STEPS[i] or ask_reply(profile)


# ── 돌봄·사정 이야기 감지 (2026-07-30) — 🔴 실사용 사고에서 나왔다 ────────────────
#   사고: 사용자가 "그냥 모르겠어 크게 생각해본 적 없는데. **어머니가 아프셔서 돌봐드리느라**
#   그런 생각 한 적 없어." 라고 했는데, 코드가 '모르겠어'만 보고 모델의 공감 답변을
#   통조림 슬롯 질문("사람·기계·컴퓨터 중 끌리는 게…")으로 덮어썼다.
#   가족돌봄청년이 돌봄 부담을 처음 털어놓은 순간에 그걸 못 들은 척한 셈이다 —
#   이 서비스가 존재하는 이유가 바로 그 이야기인데.
#   ⇒ 사정을 말한 턴에는 **코드가 문구를 덮어쓰지 않는다**(모델이 받아주게 둔다).
_CARE_CTX = ('돌봐', '돌보', '간병', '아프', '아팠', '병원', '입원', '수술', '치매', '요양원',
             '어머니', '엄마', '아버지', '아빠', '할머니', '할아버지', '동생', '가족',
             '보호자', '장애', '투석', '항암', '거동', '누워')

def tells_situation(msg):
    """자기 사정(돌봄·질병·가족)을 이야기한 발화면 True → 통조림 응답 금지."""
    return any(t in (msg or '').replace(' ', '') for t in _CARE_CTX)


# ── META(대화 자체에 대한 말) 코드 안전망 (2026-07-30) ─────────────────────────
#   모델이 META 를 놓치면(저비용 모델은 흘린다) 그 발화가 진로 발화로 처리돼 엉뚱한 카드가 나간다.
#   실측 사고: "알아들었어?" → 벡터가 '알아듣다'를 청각으로 읽어 **[청각관리]** 카드.
#   그래서 '짧고 명백한' 메타 발화는 코드가 먼저 확정한다(길면 모델 판단에 맡긴다).
_META_SOLO = ('알아들었', '알아들어', '이해했', '이해돼', '이해감', '내말알', '무슨말인지알',
              '뭐라고', '뭐래', '다시말', '다시한번', '아까뭐', '방금뭐', '무슨소리야',
              '너누구', '넌누구', '누구세요', '어떻게써', '사용법', '잠깐만', '잠시만',
              '고마워', '감사합니다', '고맙', '알겠어', '오케이', 'ok')
_UNDERSTAND = ('알아들었', '알아들어', '이해했', '이해돼', '이해감', '내말알', '무슨말인지알')

def asks_understanding(msg):
    """'내 말 알아들었어?' 류인가 — 이해한 내용을 되짚어 답해야 하는 발화."""
    return any(t in (msg or '').replace(' ', '') for t in _UNDERSTAND)


def is_meta(msg):
    """대화 자체에 대한 짧은 말이면 True(진로 내용이 아니다). 긴 발화는 모델에 맡긴다."""
    m = (msg or '').replace(' ', '').lower()
    return bool(m) and len(m) <= 16 and any(t in m for t in _META_SOLO)

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
    #  '_' 로 시작하는 키는 내부 상태(좁히기 이력 등)다 — 모델에게 보내지 않는다.
    known = {k: v for k, v in (p or {}).items() if v and not k.startswith('_')}
    return json.dumps(known, ensure_ascii=False) if known else '(아직 파악된 것 없음)'


# ── 좁히기 상태(2026-07-30) — 같은 선택지로 무한 되물음 방지 + '순서'로 답하기 ────────────
#   문제: 좁히기 질문("헤어미용 · 피부미용 · 네일미용 중 어디에 가까우세요?")에 사용자가
#   "첫 번째요" · "그거요" 로 답하면 근거가 없어 슬롯이 버려지고(verify_slots) 이름도 없어
#   (_named_entity) 같은 질문이 다시 나갔다. 좁혔다는 사실과 그때 보여준 선택지를 기억해
#   ① 순서·번호로 답해도 받아들이고 ② 두 번은 좁히지 않는다.
_ORDINAL = {'첫': 0, '처음': 0, 'первый': 0, '하나': 0, '일번': 0, '1번': 0, '1': 0,
            '두번': 1, '둘': 1, '이번째': 1, '2번': 1, '2': 1, '세번': 2, '셋': 2, '3번': 2, '3': 2,
            '네번': 3, '넷': 3, '4번': 3, '4': 3, '마지막': -1}

def pick_from_options(msg, options):
    """좁히기 선택지에 대한 답을 해석 → 고른 항목(없으면 None).

    ① 선택지 이름을 그대로 말했으면 그것 ② '첫 번째/2번/마지막' 같은 순서 표현이면 그 위치.
    """
    if not options:
        return None
    m = re.sub(r'\s+', '', msg or '')
    if not m:
        return None
    for o in options:                       # ① 이름 직접 언급(가장 확실)
        if re.sub(r'\s+', '', o) in m:
            return o
    if len(m) > 14:                          # 긴 문장은 순서 답변이 아니다(오해석 방지)
        return None
    for k, i in _ORDINAL.items():            # ② 순서 표현
        if k in m:
            try:
                return options[i]
            except IndexError:
                return None
    #  ③ 짧게 줄여 답한 경우('피부' → 피부미용). 여러 선택지에 걸리면('미용') 고르지 않는다.
    if 2 <= len(m) <= 8:
        hits = [o for o in options if m in re.sub(r'\s+', '', o)]
        if len(hits) == 1:
            return hits[0]
    return None


# ── 사전필터 : LLM 부르기 전 코드가 먼저 거른다 ─────────────────────
#  ★ 2026-07-30 — '자살'을 욕설과 같은 목록에 두고 "그런 이야기는 도와드리기 어려워요"로 차단하고 있었다.
#    우리 사용자는 가족 돌봄으로 학업·진로를 놓은 청년이다. 이 서비스가 받을 수 있는 가장 위험한 입력에
#    가장 나쁜 응답을 하고 있었던 셈이다. → 자기 위해 신호를 **분리**하고, 차단이 아니라 **연결**한다.
#    (대화를 닫지 않는다: kind='ask' 로 돌려보내 이야기를 이어갈 수 있게 둔다.)
SELF_HARM = ('자살', '죽고싶', '죽어버리', '죽고싶다', '살기싫', '살고싶지않', '사라지고싶',
             '없어지고싶', '자해', '손목', '끝내고싶', '죽는게', '죽어야', '살아갈이유')
HARM_OTHERS = ('죽여', '죽이', '때려', '패버', '강간', '성폭')
ABUSE = ('꺼져', '병신', '씨발', '개새')
BAD_WORDS = list(HARM_OTHERS + ABUSE)      # 하위호환(외부에서 import 하는 곳이 있을 수 있음)

#  ★ 문구 원칙(2026-07-30 정준 지시 반영) — **상대의 상황을 앞질러 규정하지 않는다.**
#    (이건 SYSTEM 프롬프트 [말투] 규칙과 같은 원칙이다.)
#    키워드는 의도를 알 수 없다. "죽고 싶어요"(본인)와 "아버지가 자살하셨어요"(사별 이야기)가
#    같은 단어로 걸린다. 그래서
#      · "많이 힘드시죠" 처럼 본인 위기라고 단정하지 않는다.
#      · "부정적인 언어입니다" 처럼 꾸짖지도 않는다 — 사별을 말한 사람에게는 더 가혹하다.
#    ⇒ 이 봇의 역할(진로 상담)만 담백하게 알리고, 도움처는 '혹시 필요하면' 정도로 한 줄만 둔다.
#    상담 연락처는 발표 전 팀에서 최신 번호를 한 번 더 확인할 것.
CRISIS_REPLY = (
    '이 대화는 진로·적성 상담을 도와드리는 곳이라, 그 이야기는 제가 잘 받아드리기 어려워요.\n'
    '혹시 지금 마음이 많이 무거우시면 자살예방 상담전화 109(24시간)에서 사람과 바로 이야기하실 수 있어요.\n\n'
    '괜찮으시면, 요즘 관심 있는 일이나 해보고 싶은 것부터 편하게 말씀해 주세요.'
)


def pre_check(msg):
    """'VAGUE'=되묻기 / 'SELFHARM'=위기 안내(대화 유지) / 'UNSAFE'=차단 / None=정상"""
    msg = msg or ''
    meaningful = re.sub(r'[^가-힣a-zA-Z]', '', msg)
    if not meaningful or re.fullmatch(r'[ㄱ-ㅎㅏ-ㅣ\s]+', msg):
        return 'VAGUE'
    flat = msg.replace(' ', '')
    if any(b in flat for b in SELF_HARM):      # 자기 위해가 먼저다 — 욕설 판정보다 우선
        return 'SELFHARM'
    if any(b in flat for b in HARM_OTHERS + ABUSE):
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
#  ★ 인접 조건(2026-07-30) — 예전엔 '주어 아무데나 + 동사 아무데나'라 평범한 한국어를 인젝션으로 오탐했다.
#    실측 오탐: "규칙적인 생활을 좋아하는데 자꾸 잊어버려요"('규칙'…15자…'잊어') → 인젝션 차단(!),
#              "명령어 외우는 걸 자꾸 잊어요" → 인젝션 차단(!). 사용자는 차단 이유도 모른다.
#    진짜 인젝션은 둘이 붙어 있다("규칙 무시하고"=2자, "지시는 다 무시하고"=5자). → 6자 이내만 인정.
_INJECT_NEAR = 6

def _near(m, subjects, verbs, window):
    """주어 토큰과 동사 토큰이 window 자 이내로 붙어 나오면 True (순서 무관)."""
    for s in subjects:
        i = m.find(s)
        while i != -1:
            for v in verbs:
                j = m.find(v)
                while j != -1:
                    if (0 <= j - (i + len(s)) <= window) or (0 <= i - (j + len(v)) <= window):
                        return True
                    j = m.find(v, j + 1)
            i = m.find(s, i + 1)
    return False


def is_injection(msg):
    """프롬프트 인젝션/탈옥이면 True — 카드 없이 redirect. 정상 진로발화는 안 걸리게 정밀."""
    m = (msg or '').lower().replace(' ', '')
    if any(p in m for p in _INJECT_SOLO):
        return True
    return _near(m, _INJECT_SUBJ, _INJECT_VERB, _INJECT_NEAR)


def has_interest(p):
    """진로 맥락이 섰나 — 관심축이 하나라도 차 있으면 True. 이탈 게이트를 콜드 오픈에만 걸기 위함."""
    return any((p or {}).get(k) for k in ('관심분야', '활동유형', '다루는대상', '세부관심'))


# ── 거부·되물음 가드(2026-07-30) — 🔴 실사용 버그 수정 ────────────────────────────
#   재현된 사고: 좁히기 선택지로 '가구제작'을 보여줬더니 사용자가 "가구제작은 무슨 소리야?"라고
#   되물었는데, 코드 DIRECT(_named_entity)가 '이름이 통째로 들어있다'는 이유만으로 강제 확정 →
#   카드가 [가구제작]으로 박혔다. 답변은 사과·되묻기인데 카드는 확정이라 화면이 앞뒤가 안 맞았다.
#   같이 재현된 것: "요양지원은 싫어요" · "네일미용은 관심 없어요" · "내선공사가 뭔지 모르겠어요".
#   ⇒ 사용자가 그 이름을 '거부'하거나 '뜻을 묻는' 발화면 코드는 확정하지 않고 모델 판단에 맡긴다.
#     (코드 DIRECT 는 '되묻지 말라'는 안전망이지 사용자 의사를 뒤집는 장치가 아니다.)
_REJECT = ('아니', '말고', '빼고', '제외', '싫', '관심없', '별로', '안할', '안해', '안내키',
           '모르겠', '아닌', '다른거', '다른것', '다른직업', '외에')
#  '그게 뭐예요?' — 뜻을 묻는 발화. 거부와 달리 **카드로 답할 질문이 아니다**(설명으로 답한다).
_ASK_MEANING = ('무슨소리', '뭔소리', '무슨뜻', '뭐야', '뭐예요', '뭐임', '뭔가요',
                '무엇인가요', '뭔지모르', '이해안', '이해못', '뜻이', '어떤일', '무슨일')

def asks_meaning(msg):
    """'그게 뭐예요?'처럼 뜻을 묻는 발화면 True → 카드가 아니라 설명으로 답한다."""
    return any(t in (msg or '').replace(' ', '') for t in _ASK_MEANING)


def _eun_neun(word):
    """받침 유무로 조사를 고른다 — '내선공사는' / '가구제작은'. (한글 아니면 '은')"""
    ch = (word or '')[-1:]
    if ch and '가' <= ch <= '힣':
        return '은' if (ord(ch) - 0xAC00) % 28 else '는'
    return '은'


def rejects_or_questions(msg):
    """이름을 말했더라도 그것을 거부·되묻는 발화면 True → 코드가 DIRECT 로 확정하지 않는다."""
    m = (msg or '').replace(' ', '')
    return any(t in m for t in _REJECT) or asks_meaning(msg)


# ── 가짜자격 주장 탐지(2026-07-30) — no_card/복창금지 강제 ──
#   "스마트팜 국가공인 마스터 3급 있는데" 처럼 실재하지 않는 자격을 보유했다 주장하면, 모델이
#   그걸 인정·복창하는 게 간헐적으로 샌다(실측: flashlite 2/6, solar 도 1회). 프롬프트로는 약하다.
#   규칙: (자격증류 명사 + 보유동사)로 '주장'을 감지. 그중 DB에 실존하지 않는 것만 코드가 되받는다
#   (진짜 자격 '전기기능사 있는데'는 _named_entity 가 실존을 확인 → 안 걸린다). 오탐 0 실측.
_CRED = ('자격증', '국가공인', '기능사', '산업기사', '기술사', '마스터')
_HAVE = ('있는데', '있어요', '있습니다', '있음', '취득', '땄', '따놨', '보유', '가지고있',
         '자격증있', '자격있')
#  ★ '갖고 싶다'와 '갖고 있다'를 가른다(2026-07-30). 예전엔 (자격명사 + 있어요)만 보고 잡아서
#    실측 오탐: "자격증 따고 싶은 마음이 있어요" · "자격증에 관심이 있어요" ·
#              "기능사 시험이 어떤 건지 궁금한 게 있어요" → 전부 "말씀하신 자격은 확인 어려워요"로
#    차단됐다. 자격증을 '원하는' 사람을 '거짓 주장'으로 취급한 셈 — 가장 도와야 할 발화였다.
#    ⇒ ① 희망·질문 표지가 있으면 주장이 아니다  ② 자격명사와 보유동사가 붙어 있어야 주장이다.
_WANT = ('싶', '관심', '궁금', '궁그', '어떻게', '어떤가', '방법', '준비', '알고', '배우',
         '되려면', '하려면', '따려면', '딸수', '딸까', '목표')
#  ★ '무엇이 있나요?'는 질문이다 — 보유 주장이 아니다(2026-07-30 2차 수정).
#    실측 반례: "자격증이 뭐가 있어요?" · "자격증 뭐 있어요" 가 허위주장으로 차단됐다.
#    '있어요'가 '보유'가 아니라 '존재하나요'로 쓰인 경우다.
#    단어 단위('어떤'·'알려주')로 잡으면 "기능사 있는데 어떤 일 할 수 있어요?" 같은 진짜 주장까지
#    놓친다(실측). 그래서 **존재 질문에만 나타나는 구절**로 좁힌다(공백 제거 기준).
_ASK_EXIST = ('뭐가있', '뭐있', '무엇이있', '어떤게있', '어떤것이있', '뭔가있',
              '어떤자격', '무슨자격', '있나요', '있을까', '있는지', '종류', '목록', '리스트')
#  ★ 자격증이 아닌 '급'(2026-07-30) — \d+급 만 보고 잡으면 복지 등급까지 걸린다.
#    실측 반례: "장애 3급 있어요" · "기초생활 수급자" → 우리 사용자층에 실제로 흔한 발화다.
_NOT_CRED = ('장애', '등급', '학년', '수급', '기초생활', '차상위', '보훈', '중증', '경증')
_CRED_NEAR = 10

def claims_credential(msg):
    """자격 '보유'를 주장하는 발화면 True (그 자격이 실재하는지는 호출부가 _named_entity 로 판정)."""
    m = (msg or '').replace(' ', '')
    if any(t in m for t in _WANT):          # '따고 싶어요'·'관심 있어요' = 희망 → 주장 아님
        return False
    if any(t in m for t in _ASK_EXIST):     # '뭐가 있어요?' = 존재 질문 → 주장 아님
        return False
    if any(t in m for t in _NOT_CRED):      # '장애 3급' 등 복지 등급 → 자격증 아님
        return False
    has_cred = any(t in m for t in _CRED) or bool(re.search(r'\d+급', m))
    if not has_cred:
        return False
    creds = tuple(t for t in _CRED if t in m) or ('급',)
    return _near(m, creds, _HAVE, _CRED_NEAR)


#  ★ 2026-08-02 — 프롬프트(GATE_ONTOPIC · _GATE_SCHEMA · SYSTEM)를 prompts.py 로 옮겼다.
#    이 파일이 1,561줄이었고 그중 156줄이 문자열이었다. 프롬프트는 데이터지 로직이 아니다.
#    ⚠️ SYSTEM 은 아래 turn_schema 의 슬롯 이름·action enum 과 짝이다. 함께 고칠 것.
try:
    from .prompts import GATE_ONTOPIC, _GATE_SCHEMA, SYSTEM      # noqa: F401
except ImportError:                                              # CLI 실행
    from prompts import GATE_ONTOPIC, _GATE_SCHEMA, SYSTEM       # noqa: F401


#  검색으로 이어지는 턴 결과 캐시 — 프로세스 공용(엔진이 여러 개 생겨도 공유).
#  삽입순 dict 를 LRU 로 쓴다(세션 캐시와 같은 방식). 재시작하면 비워진다.
_TURN_CACHE: dict[str, dict] = {}


class ItdaEngine:
    """import 시점에는 아무것도 연결하지 않는다. 필요할 때 붙는다."""

    def __init__(self, gemini_key=None, model=MODEL,
                 think_budget=None, think_level=None):
        self.model = model
        # Gemini 키는 gemini_util 이 ENV 에서 찾는다(키 1개 · 분당 한도는 기다렸다 재시도).
        #  여기선 '명시 키'만 기억한다(테스트용).
        self.gemini_key = gemini_key or _gutil.get_key(ENV)   # 유료 키 1개(테스트는 명시 주입)
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
                            #  ※ 이 enum 은 프롬프트 [행동] 목록·step() 분기와 **반드시 일치**해야 한다.
                            #    한 곳만 바꾸면 조용히 깨진다(코드감사 지적) → 세 곳을 같이 고칠 것.
                            'enum': ['DIRECT', 'ASK', 'CLARIFY', 'SEARCH',
                                     'OFFRAMP', 'REDIRECT', 'META']},
                'query':   {'type': 'STRING'},
                #  ★ 질의 변형(2026-07-30) — 같은 뜻을 다른 표현으로 2개 더. 검색을 각각 돌려
                #    RRF 로 합친다(RAG-Fusion). **같은 호출에서 받으므로 LLM 비용이 늘지 않는다.**
                'query_alts': {'type': 'ARRAY', 'items': {'type': 'STRING'}}},
                'required': ['reply', 'action', 'profile']}
        return self._turn_schema

    # ── Gemini 구조화 출력 ──────────────────────────────────────────
    #  HTTP 자체는 동기(urllib)다. async 전환 후에도 검증된 이 코드를 지키되,
    #  네트워크 I/O 를 asyncio.to_thread 로 던져 이벤트 루프를 막지 않는다.
    #  (quota 풀리면 팀처럼 httpx.AsyncClient 로 바꿀 수 있다 — 그때 E2E 검증 가능)
    async def gemini(self, prompt, schema, temp=0.7, think=None):
        """think 를 주면 그 호출만 사고량을 덮어쓴다(예/아니오 판정에 dynamic 사고를 쓰지 않게)."""
        cfg = {'responseMimeType': 'application/json',
               'responseSchema': schema, 'temperature': temp}
        level = think or self.think_level
        if level:
            cfg['thinkingConfig'] = {'thinkingLevel': level}
        elif self.think_budget is not None:
            cfg['thinkingConfig'] = {'thinkingBudget': self.think_budget}
        body = json.dumps({'contents': [{'parts': [{'text': prompt}]}],
                           'generationConfig': cfg}).encode()

        # 분당 한도(429)는 gemini_util 이 기다렸다 재시도한다.
        def _post(key):
            url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
                   f'{self.model}:generateContent?key={key}')
            req = urllib.request.Request(url, data=body,
                                         headers={'Content-Type': 'application/json'})
            return urllib.request.urlopen(req, timeout=90).read()

        j = await _gutil.call(_post, ENV, key=self.gemini_key)
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

    #  ★ 2026-08-02 — 단가 상수(PRICE_IN/PRICE_OUT/FX)와 cost_krw() 를 지웠다.
    #    ① 아무도 부르지 않았다(서빙·배치·대시보드 어디에서도).
    #    ② 그리고 위험했다 — 모델을 .env(COURSE_LLM_MODEL)로 뺀 뒤부터는
    #       모델만 바꾸고 단가를 안 고치면 비용 보고가 조용히 틀어진다.
    #       실제로 2026-07-30까지 3.6-flash 단가가 남아 약 15배 과대 보고된 전례가 있다.
    #    토큰 수(total_usage)는 남긴다 — 그건 모델이 바뀌어도 낡지 않는 값이다.
    #    비용이 다시 필요하면 '토큰 수 × 그때의 단가'로 바깥에서 계산하면 된다.

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

        #  ★ 자기일관성(self-consistency, 2026-07-30) — 싼 모델을 N번 뽑아 **다수결**로 정한다.
        #    왜: 실패가 '틀림'보다 '편차'였다. 같은 입력에 action 이 흔들려 [청각관리]·
        #        [건강기능식품제조가공] 같은 카드가 나왔다. 편차는 표본을 늘려 잡는 게 정석이다.
        #    비용: 3.1-flash-lite 턴당 약 0.38원 × N=3 ≈ 1.1원 — 예전 3.6-flash 1회(4.3~13원)보다 싸다.
        #    지연: asyncio.gather 로 **동시에** 던지므로 1회와 비슷하다(직렬로 하면 3배가 된다).
        #    N=1 이면 예전과 동일 동작 → 언제든 되돌릴 수 있다.
        #  ★ 캐시 조회 — 같은 상태·같은 말이면 저장된 결과를 그대로 쓴다(LLM 호출 없음).
        #    키는 (슬롯 상태, 정규화한 발화). '_' 로 시작하는 내부 상태는 키에서 뺀다 —
        #    좁히기 이력·'모르겠다' 카운터가 달라졌다고 검색어까지 달라질 이유는 없다.
        ck = self._cache_key(profile, user_msg) if self.QUERY_CACHE else None
        if ck and ck in _TURN_CACHE:
            hit = _TURN_CACHE[ck]
            _TURN_CACHE[ck] = _TURN_CACHE.pop(ck)      # LRU 갱신
            return dict(hit)

        n = max(1, int(self.SELF_CONSISTENCY))
        if n == 1:
            got = await self.gemini(prompt, self.turn_schema, self.TEMP_TURN)
        else:
            outs = await asyncio.gather(
                *(self.gemini(prompt, self.turn_schema, self.TEMP_TURN) for _ in range(n)),
                return_exceptions=True)
            cands = [o for o in outs if isinstance(o, dict) and o.get('action')]
            got = self._vote(cands, user_msg) if cands else None

        #  캐시 저장 — **모든 action 을 담는다**(2026-07-30 2차).
        #    처음엔 SEARCH/DIRECT 만 담았는데(문구가 굳는 걸 피하려고) 흔들림이 안 잡혔다.
        #    실측으로 원인이 드러났다: 흔들리는 것은 검색어가 아니라 **ASK↔SEARCH 판단 자체**였다.
        #    ASK 를 캐싱하지 않으면 다음 턴에 LLM 이 새로 판단해 또 갈린다.
        #    ⇒ 전부 담는다. 키가 (같은 슬롯 + 같은 말)로 정확히 일치할 때만 재사용하므로,
        #      '같은 말을 다시 했을 때 같은 답'이 되는 것이고 그건 이상한 동작이 아니다.
        if ck and isinstance(got, dict) and got.get('action'):
            while len(_TURN_CACHE) >= self.QUERY_CACHE_MAX:
                _TURN_CACHE.pop(next(iter(_TURN_CACHE)), None)
            _TURN_CACHE[ck] = dict(got)
        return got

    @staticmethod
    def _cache_key(profile, user_msg):
        """(슬롯 상태, 정규화 발화) → 캐시 키. 내부 상태('_' 접두)와 공백·구두점 차이는 무시한다."""
        slots = {k: v for k, v in (profile or {}).items() if v and not str(k).startswith('_')}
        norm = re.sub(r'[\s.,!?~…]+', '', (user_msg or '')).lower()
        return json.dumps([sorted(slots.items(), key=lambda x: x[0]), norm],
                          ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _vote(cands, user_msg):
        """N개 표본 → 하나로 합친다.

        · action : 다수결. 동수면 '보수적인 쪽'(ASK/META 우선 — 카드를 함부로 내지 않는다).
        · profile: 표본 과반이 같은 값을 낸 슬롯만 채택(근거 검증은 뒤에서 또 한다).
        · reply  : 채택된 action 을 낸 표본 중 첫 번째 것(문구는 원래 하나만 쓴다).
        · query  : 채택된 action 을 낸 표본 중 가장 긴 것(정보량이 많은 쪽).
        """
        from collections import Counter
        n = len(cands)
        votes = Counter(c['action'] for c in cands)
        top = votes.most_common()
        best = top[0][1]
        tied = [a for a, v in top if v == best]
        #  동수일 때의 우선순위 — 되묻기·메타가 카드보다 안전하다.
        order = ['META', 'ASK', 'CLARIFY', 'REDIRECT', 'OFFRAMP', 'DIRECT', 'SEARCH']
        action = min(tied, key=lambda a: order.index(a) if a in order else 99)

        same = [c for c in cands if c['action'] == action]
        slot_votes = {}
        for c in cands:                       # 슬롯은 action 과 무관하게 전체 표본에서 센다
            for k, v in (c.get('profile') or {}).items():
                val = (v or {}).get('값') if isinstance(v, dict) else v
                if val:
                    slot_votes.setdefault(k, Counter())[str(val)] += 1
        profile = {}
        for k, cnt in slot_votes.items():
            val, hits = cnt.most_common(1)[0]
            if hits * 2 > n:                  # 과반만 채택
                src = next((c for c in cands
                            if str(((c.get('profile') or {}).get(k) or {}).get('값')) == val), None)
                profile[k] = (src.get('profile') or {}).get(k) if src else {'값': val, '근거': user_msg}

        queries = [c.get('query') or '' for c in same]
        #  표본들의 query·query_alts 를 모두 변형 후보로 모은다(RAG-Fusion 재료).
        alts, main = [], max(queries, key=len) if queries else ''
        for c in cands:
            for a in [c.get('query')] + list(c.get('query_alts') or []):
                if a and a.strip() and a.strip() != main:
                    alts.append(a.strip())
        return {'action': action, 'reply': same[0].get('reply', ''),
                'profile': profile, 'query': main,
                'query_alts': list(dict.fromkeys(alts))[:2]}

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
    #  ※ 2026-07-30 부터 이 값은 **리랭크 실패 시 폴백 전용**이다. 평시 선별은 크로스인코더가 한다.
    #    절대 임계의 한계 실측(2026-07-30): 가구제작 0.598 · 요양지원 0.696 · 내선공사 0.651 → 0개 통과
    #    (사용자 화면에서 '1단계 무료강의'가 통째로 사라짐). 반대로 제빵은 0.713+ 로 무관 강좌가 통과.
    COURSE_MIN_SCORE = 0.70
    COURSE_POOL = 12          # 리랭커에 넘길 강좌 후보 수 (넓게 받아 크로스인코더가 고른다)

    # ── 직업 먼저(2026-07-27) — 직업을 벡터로 찾고, 그 직업의 자격증(≤3)을 역방향으로 붙인다 ──
    JOB_CAND_POOL = 8         # 직업 후보 수
    JOB_MIN_SCORE = 0.45      # DIRECT '없음' 판정선 — 직업 벡터가 얇어('직업명·중분류') cert 0.70보다 낮게 잡는다
    N_CERTS       = 3         # 직업당 자격증 최대 (「지금 바로」 우선)
    JOB_NARROW_GAP = 0.04     # 1위가 3위를 이만큼 확실히 앞서면 '뚜렷한 승자' → 안 좁히고 착지 (narrowing 문턱)
    #  FULLTEXT 키워드 점수가 이 값 이상이고 2위보다 크면 '정확한 이름을 집었다'고 본다.
    #  실측 근거: '요양' → 요양지원 kw 9.12 (벡터는 '돌봄' 클러스터로 뭉쳐 옆으로 흔들렸다).
    #  ※ _is_spread(좁히기 판정)와 직업 픽커가 **반드시 같은 값을 봐야 한다** → 상수 하나로 묶었다.
    KW_WINNER = 5.0
    #  1위와 2위의 유사도 차가 이보다 작으면 '정답이 둘'로 보고 고르지 않는다(선택지로 되묻는다).
    #  애매함 처리의 정석 3임계(최소확신도·1·2위 차·개체 최소점수) 중 '1·2위 차'에 해당한다.
    JOB_MARGIN = 0.02

    #  ★ 검색어 캐싱(2026-07-30) — 같은 상태·같은 말이면 **LLM 을 다시 부르지 않고** 저장된 검색어를 쓴다.
    #    근거(실측): 같은 검색어로 6회 검색 → 결과 6/6 완전 동일. 즉 이 파이프라인에서
    #    비결정적인 곳은 **LLM 이 쓰는 검색어 딱 하나**이고, 그 아래(임베딩·벡터·FULLTEXT·RRF·
    #    리랭크·DB)는 전부 결정론적이다. ⇒ 검색어를 고정하면 시스템 전체가 결정론이 된다.
    #    덤: 반복 발화에서 LLM 호출 자체를 건너뛰어 비용·지연도 줄어든다.
    #    한계: 첫 호출은 여전히 비결정적이다(캐싱은 '두 번째부터 같다'를 보장한다).
    #    False 로 두면 예전 동작(매번 LLM).
    QUERY_CACHE = True
    QUERY_CACHE_MAX = 2000

    #  자기일관성 표본 수 — 싼 모델을 N번 뽑아 다수결로 정한다(turn()/_vote 참고).
    #  ★ 실측 결과 기본값은 1(끔)이다 (2026-07-30 A/B, 4케이스×4반복):
    #      N=1 → 흔들림 1건 · 0.50원/턴 · 3.7s/턴
    #      N=3 → 흔들림 1건(그대로) · 1.46원/턴(3배) · 3.0s/턴
    #    지연은 동시호출이라 안 늘었지만 **품질 이득이 측정되지 않았다.**
    #    이유: 남은 편차가 action 결정이 아니라 **검색 단계**에 있다 — LLM 이 만든 query 가
    #    매 표본마다 달라 벡터 점수가 JOB_MIN_SCORE 를 넘나든다. action 다수결로는 안 잡힌다.
    #    → 제대로 하려면 '표본별 query 로 각각 검색해 리랭커 점수가 가장 높은 결과를 채택'
    #      (best-of-N at search) 이어야 한다. 그때 이 값을 3 으로 올리면 재료가 준비된다.
    #  N>1 로 올리면 즉시 활성화된다(코드는 검증돼 있고 되돌리기도 값 하나다).
    SELF_CONSISTENCY = 1

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
        #  ★ 'minimal' 고정(2026-07-30) — on_topic 은 true/false 한 비트다. 기본값(dynamic)이면
        #    화면에 안 보이는 사고 토큰이 출력 단가로 붙어, 이 게이트 하나가 본 턴에 맞먹는 비용을 낸다.
        j = await self.gemini(GATE_ONTOPIC.format(msg=user_msg), _GATE_SCHEMA, 0.0, think='minimal')
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
            #  이름이 LIKE 패턴 쪽에 들어가므로 와일드카드(_ %)를 이스케이프한다(2026-07-30).
            #  안 하면 'CNC_가공' 같은 이름의 '_'가 '임의 1자'로 해석돼 무관한 발화에 과대매칭된다.
            "  AND :m LIKE CONCAT('%', REPLACE(REPLACE(REPLACE("
            "        job_name, ' ', ''), '_', '\\\\_'), '%', '\\\\%'), '%') "
            "ORDER BY CHAR_LENGTH(job_name) DESC LIMIT 1"), {'m': msg})).fetchone()
        if row:
            return str(row[0])
        # ② 자격증 이름 직접 포함 → 그 자격증으로 이어지는 대표 직업
        row = (await db.execute(text(
            "SELECT cert_id FROM certification "
            "WHERE CHAR_LENGTH(REPLACE(jm_name, ' ', '')) >= 3 "
            "  AND :m LIKE CONCAT('%', REPLACE(REPLACE(REPLACE("
            "        jm_name, ' ', ''), '_', '\\\\_'), '%', '\\\\%'), '%') "
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
            "SELECT job_code, job_name, job_mcls_name, job_description, job_scls_name "
            "FROM job_catalog WHERE job_code = :c"), {'c': str(code)})).fetchone()
        if not row:
            return None
        return {'job_code': str(row[0]), 'job_name': row[1], 'group': row[2],
                'description': row[3], 'scls': row[4], 'score': 1.0, 'kw_score': 0.0}

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
        #  ★ 접수 마감일을 함께 뽑는다(2026-07-30) — 사용자가 실제로 '놓칠 수 있는' 날짜는
        #    시험일이 아니라 **접수 마감일**이다. 놓치면 다음 회차까지 기다려야 한다.
        #    exam_schedule 에 컬럼이 있는데 그동안 읽지 않았다(코드감사 지적).
        #  ★ 반환을 튜플 → dict 로 바꿨다. 예전엔 controllers._exam_text 가 위치로 언패킹해서
        #    (seq, doc, prac, pas) SELECT 에 컬럼 하나만 추가해도 카드가 조용히 사라졌다.
        SEL = ("SELECT impl_seq, doc_exam_start, prac_exam_start, prac_pass_dt, "
               "       doc_reg_start, doc_reg_end "
               "FROM exam_schedule WHERE cert_id = :cid ")
        #  ★ 우선순위(2026-07-31) — 사용자가 **지금 신청할 수 있는** 회차를 먼저 보여준다.
        #    예전엔 '시험일이 미래인 회차'만 봐서, 실기가 남았지만 **접수는 이미 끝난** 회차가
        #    잡혔다(실측: 전기기능사 → 접수 ~2026-06-11 (마감)). 마감된 날짜를 첫 줄에 보여주면
        #    사용자는 '이번엔 못 하는구나'로 읽고 닫는다. 접수가 열려 있는 회차가 있으면 그게 먼저다.
        #      ① 접수 마감이 아직 안 지난 회차 (가장 가까운 것)
        #      ② 없으면 시험일이 미래인 회차 (접수는 지났지만 일정 안내는 된다)
        #      ③ 그것도 없으면 가장 최근 회차
        #  ★ 날짜 기준은 **한국 날짜**를 코드가 직접 계산해 넘긴다(2026-07-31 · 배포 대비).
        #    예전엔 SQL 의 CURDATE() 를 썼는데 그건 **DB 서버의 시계**다. AWS RDS 는 기본이 UTC 라
        #    한국보다 9시간 느리다 → 밤에는 '오늘'이 하루 전이 되어 접수 마감 판정이 틀린다.
        #    설정(파라미터 그룹 time_zone)에 기대지 않고 코드가 정하면 어디에 올려도 같게 동작한다.
        today = kst_today()
        for cond, order in (
            (" AND doc_reg_end >= :today", " ORDER BY doc_reg_end"),
            (" AND (doc_exam_start >= :today OR prac_exam_start >= :today)",
             " ORDER BY COALESCE(doc_exam_start, prac_exam_start)"),
            ("", " ORDER BY COALESCE(doc_exam_start, prac_exam_start) DESC"),
        ):
            row = (await db.execute(text(SEL + cond + order + " LIMIT 1"),
                                    {"cid": cert_id, "today": today})).fetchone()
            if row:
                break
        if not row:
            return None
        return {'seq': row[0], 'doc': row[1], 'prac': row[2], 'pass': row[3],
                'reg_start': row[4], 'reg_end': row[5]}

    async def _course_covered(self, db, job_code) -> bool:
        """K-MOOC 이 이 직무를 실제로 덮는가 — scripts/build_course_coverage.py 가 채운 표를 본다.

        왜 표를 보나 (2026-08-03)
          벡터 검색에는 '관련 없음'이라는 출력이 없다. 항상 **가장 가까운 k개**를 준다.
          그래서 K-MOOC(대학 MOOC)에 없는 직종을 물으면 엉뚱한 강의가 확신에 차서 나왔다 —
              제빵 → 실용아트 메이크업 · 가구제작 → 스마트팩토리 · 특수주조 → 드론 특수촬영
          (K-MOOC 8,273개 중 제빵·제과·베이킹·조리·용접·가구·목공·배관 강의는 **0건**이다.)

        왜 점수 문턱이 아니라 표인가
          리랭커 점수에 문턱을 걸어 봤으나 무작위 표본에서 **경계가 없었다**(연속 기울기).
          0.02 를 걸면 60% 가 강좌 0개가 되고 그 안에 쓸모있는 것이 섞인다 —
              리튬이온전지셀개발 → 이차전지이야기(0.032) · SW공급망보안 → 사이버보안(0.0057)
          보정할 라벨이 없으면 생점수 문턱은 표본만 바뀌어도 뒤집힌다. 그래서 판단을
          **오프라인으로 옮겨** 직업마다 한 번 LLM 다수결로 정하고 여기서는 조회만 한다.

        ★ 미판정(NULL)·컬럼 없음은 True 로 본다 — 표가 아직 없다고 기능이 죽으면 안 된다.
        """
        try:
            r = (await db.execute(text(
                'SELECT course_covered FROM job_catalog WHERE job_code = :c'),
                {'c': job_code})).fetchone()
        except Exception:
            return True                      # 구 스키마(컬럼 없음)에서도 지금까지대로 동작
        return not (r and r[0] == 0)

    #  (2026-07-28) _jobs_for(자격증→직업) 제거 — cert-먼저에서 '자격증 카드에 직업을 얹던' 함수.
    #  직업-먼저에선 직업이 주인공이고, 그 직업의 자격증을 붙이는 _certs_for(역방향)가 대신한다.
    async def _certs_for(self, db, job_code, k=3):
        """직업 → 그 직업으로 이어지는 자격증 (cert_job 역방향). 「지금 바로」(entry_free) 우선.

        직업 먼저(2026-07-27)의 심장 — 직업을 정한 뒤 그 직업의 자격증 최대 3개를 붙인다.
        정렬: 지금 바로 응시 가능 → 검증된 연결 → 유사도.
        빈 리스트면 그 직업엔 국가기술자격이 없다는 뜻 → 카드가 내일배움카드+강좌로 대체한다.
        """
        #  (2026-07-30) oblig_fld 제거 — SELECT 만 하고 카드가 쓰지 않던 죽은 컬럼(코드감사).
        #  대신 그동안 안 읽던 실데이터 3개를 붙인다:
        #    exam_method(시험방법, 채움 66%) · career_outlook(전망, 35%) · qual_gb(국가기술/국가전문)
        r = await db.execute(text(
            "SELECT c.cert_id, c.jm_name, COALESCE(c.grade_std, c.grade), "
            "       c.entry_free, c.entry_note, cj.verified, "
            "       c.exam_method, c.career_outlook, c.qual_gb, cj.evidence "
            "FROM cert_job cj JOIN certification c ON c.cert_id = cj.cert_id "
            "WHERE cj.job_code = :jc "
            "ORDER BY (c.entry_free = 1) DESC, cj.verified DESC, cj.score DESC "
            f"LIMIT {int(k)}"), {"jc": str(job_code)})

        def _tidy(s, n):
            """TEXT 컬럼을 카드에 넣을 만큼만 — 공백 정리 후 n자 컷."""
            s = re.sub(r'\s+', ' ', (s or '')).strip()
            return (s[:n].rstrip() + '…') if len(s) > n else s

        return [{'cert_id': row[0], 'jm_name': row[1], 'grade': row[2],
                 'entry_free': row[3] == 1, 'entry_note': row[4], 'verified': bool(row[5]),
                 'exam_method': _tidy(row[6], 120), 'outlook': _tidy(row[7], 160),
                 'qual_gb': row[8] or '', 'evidence': row[9] or ''}
                for row in r.fetchall()]

    #  (2026-07-28) GRADE_LADDER·_next_step·_ladder 제거 — cert-먼저 카드가 '기능사→산업기사→기사'
    #  등급 사다리를 그리던 것. 직업-먼저 카드는 '그 직업의 자격증 ≤3개'(certs)를 보여줘 사다리가 불필요.
    @staticmethod
    def _is_spread(jobs):
        """후보가 여러 갈래로 흩어졌나 — 뚜렷한 1등이 없으면 True(좁혀야 함).

        (2026-07-28 하이브리드) 키워드가 1위를 확실히 집었으면(정확한 이름 매칭) 흩어진 게
        아니다 → 좁히지 않고 착지. 아니면 벡터 1위가 3위를 확실히 앞서는지로 판정한다.
        """
        if len(jobs) < 2:
            return False        # 후보가 적으면 좁힐 게 없다
        if ItdaEngine._kw_winner(jobs):
            return False        # 키워드가 정확한 이름을 집음 → 이미 정해진 것

        #  ★ 2026-07-31 — 순위와 점수의 기준이 달라 오판하던 것을 고쳤다.
        #    match_jobs 가 주는 목록의 **순서는 RRF(벡터 순위 + 키워드 순위 융합)** 이고,
        #    각 항목의 `score` 는 **벡터 코사인만** 담는다(키워드로만 걸린 후보는 0.0).
        #    그래서 2위가 키워드 전용 후보이면 jobs[0]-jobs[1] 이 통째로 1위 점수가 되어
        #    "1위가 압도적"으로 읽혔다.
        #      실측(«간호조무사가 되고 싶어요»): score = [0.554, 0.0, 0.510, 0.507, 0.506]
        #        예전 계산 → 1·2위 차 0.554  (뚜렷한 승자로 오판)
        #        실제 분포 → 0.554·0.510·0.507·0.506  (거의 붙어 있음 = 흩어진 것)
        #    ⇒ 벡터 점수가 있는 후보만 골라 **내림차순으로 정렬한 뒤** 비교한다.
        #      (키워드 전용 후보는 _kw_winner 가 위에서 이미 판단한다 — 여기서 또 볼 일이 없다)
        ss = sorted((j['score'] for j in jobs if j.get('score', 0) > 0), reverse=True)
        if len(ss) < 2:
            return False        # 벡터로 걸린 게 하나뿐 → 비교 대상이 없다

        #  1·2위 차(margin) — 애매함 처리의 정석 세 임계 중 하나. 1위와 2위가 붙어 있으면
        #  그건 '정답이 둘'이라는 뜻이다. 그때 하나를 고르면 매번 다른 게 뽑힌다
        #  (실측: "사람에게 도움이 되는 일" → 보육·가사지원·공공복지·요양지원이 번갈아 나왔다.
        #   어느 것도 틀리지 않았다). ⇒ 억지로 고르지 않고 선택지로 보여준다.
        if (ss[0] - ss[1]) < ItdaEngine.JOB_MARGIN:
            return True
        if len(ss) < 3:
            return False
        return (ss[0] - ss[2]) < ItdaEngine.JOB_NARROW_GAP

    @staticmethod
    def _kw_winner(jobs):
        """키워드 점수가 1위를 '확실히' 집었나 — 좁히기 판정과 직업 선택이 **같은 기준**을 쓰게.

        (2026-07-30) 예전엔 이 조건이 _is_spread 와 직업 픽커 두 곳에 리터럴 5.0 으로 중복돼 있었다.
        한쪽만 고치면 '좁혀 묻지도 않으면서 키워드가 집은 후보를 버리는' 조합이 되고 로그도 안 남는다.
        """
        if not jobs:
            return False
        top = jobs[0].get('kw_score', 0) or 0
        second = (jobs[1].get('kw_score', 0) or 0) if len(jobs) > 1 else 0
        return top >= ItdaEngine.KW_WINNER and top > second

    async def search(self, db, profile, query='', direct=False, force_code=None, alts=None):
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
        #  ★ forced(코드 DIRECT로 직업이 이미 확정) 면 벡터검색을 아예 건너뛴다(2026-07-30).
        #    예전엔 돌려놓고 결과를 '대안 2개' 문자열에만 썼다 — 임베딩 1회 + Pinecone 1회 + DB 2회를
        #    가장 많이 쓰는 경로("전기기능사 따고 싶어요")에서 매번 낭비했다.
        #    대안은 같은 중분류의 형제 직업으로 대체한다(DB 한 번, 의미도 더 자연스럽다).
        if forced:
            jobs = []
        else:
            #  ★ 질의 변형을 함께 넘긴다(RAG-Fusion) — match_jobs 가 각각 검색해 RRF 로 합친다.
            #    변형은 같은 턴 호출에서 이미 받아둔 것이라 LLM 추가 비용이 없다.
            qs = [q] + [a for a in (alts or []) if a and a.strip() and a.strip() != q]
            jobs = await m.match_jobs(db, qs, top_k=self.JOB_CAND_POOL) if q else []
        if not jobs and not forced:
            return None

        # ★ 직업 이름을 그대로 말했는가 — '없음' 판정보다 먼저 본다. (forced 면 이미 확정이라 스킵)
        named = self._named_job(q, jobs) if (direct and not forced) else None

        # ★ 지목도 아니고 1위 점수도 낮으면 → 우리에게 없다(지어내지 않는다). (forced 면 스킵)
        #   ★ 키워드 점수도 함께 본다(2026-07-30) — 예전엔 벡터 코사인만 봐서, FULLTEXT 가
        #     정확한 이름을 집었는데도 벡터가 낮으면 '우리에게 없다'가 나갈 수 있었다.
        if (direct and not forced and not named and jobs
                and jobs[0]['score'] < self.JOB_MIN_SCORE and not self._kw_winner(jobs)):
            return {'not_found': True, 'query': q,
                    'near': [{'job': j['job_name'], 'group': j['group']} for j in jobs[:3]]}

        # ★ 넓게 흩어졌나(narrowing) — 뚜렷한 1등이 없고 세부관심도 아직 없으면 한 번 좁힌다.
        #   "컴퓨터로 만드는 일" → 게임/웹/앱/응용SW 로 흩어질 때 바로 확정하지 않고 되묻는다.
        #   목표를 콕 집어 말했으면(named/forced) 넘어가고, 좁힌 뒤엔 세부관심이 차서 재검색 때 통과한다.
        #   ★ 단, **두 번은 좁히지 않는다**(2026-07-30) — 한 번 좁혔는데 사용자가 선택지를 집지 못하면
        #     예전엔 같은 질문이 계속 나갔다(무한 되물음). 이미 좁힌 적이 있으면 그냥 착지시킨다.
        if (not forced and not named and not (profile or {}).get('세부관심')
                and not (profile or {}).get('_narrowed') and self._is_spread(jobs)):
            #  설명을 함께 넘긴다(2026-07-30) — 'CO₂용접'·'내선공사' 같은 NCS 원문만 보여주면
            #  사용자가 뜻을 몰라 고를 수 없다. 프론트가 chip 아래 한 줄 캡션으로 쓴다.
            picks = jobs[:4]
            return {'narrow': True, 'query': q,
                    'options': [j['job_name'] for j in picks],
                    'option_notes': [re.sub(r'\s+', ' ', (j.get('description') or ''))[:60].strip()
                                     for j in picks]}

        # ★ SEARCH 경로에도 최소 점수 기준을 둔다(2026-07-30) — 예전엔 DIRECT 에만 있어서,
        #   착지 조건(슬롯 2개)만 차면 1위가 아무리 낮아도 카드가 나갔다. 실측 사고:
        #   "사람 돕는 일 + 몸 쓰는 것도 괜찮다" → [건강기능식품제조가공] (후보에 벡터 0.000 도 섞임).
        #   낮으면 카드 대신 **아직 안 채운 슬롯을 묻는다**(질문이 남아 있을 때만 — 무한루프 방지).
        if (not forced and not named and jobs and not self._kw_winner(jobs)
                and jobs[0]['score'] < self.JOB_MIN_SCORE and missing_slots(profile)):
            return {'low_score': True, 'query': q}

        # ② 직업 1개 선택 — 코드확정(forced)이면 코드, 지목이면 코드, 키워드 확정승자면 코드, 아니면 모델
        if forced:
            chosen, job_reason = forced, '말씀하신 걸 바로 찾아봤어요.'
        elif named:
            chosen, job_reason = named, '말씀하신 일이에요.'
        elif self._kw_winner(jobs):
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
                #  (2026-07-30) DB 에 있는데 화면에 안 쓰던 실데이터 — 자격증을 눌렀을 때 보여준다.
                'exam_method': c['exam_method'], 'outlook': c['outlook'],
                'qual_gb': c['qual_gb'], 'evidence': c['evidence'],
            })
        no_cert = not certs

        # ④ 강좌 — 자격증 대신 '직업 맛보기'. 직업명·분야·관심사로 던진다.
        cq = ' '.join(x for x in [chosen['job_name'], chosen['group'],
                                  (profile or {}).get('관심분야')] if x)
        courses, course_err = [], None
        try:
            #  ★ 강좌 선별을 '절대 임계'에서 '리랭커(상대 판정)'로 바꿈(2026-07-30).
            #    왜: 코사인 임계 0.70 은 직업마다 안 맞았다. 실측 —
            #      가구제작 최고 0.598 · 요양지원 0.696 · 내선공사 0.651 → **강좌 0개**(화면에 1단계가 사라짐),
            #      반대로 제빵은 0.713~0.737 로 「공업화학」·「식물공장」 같은 무관 강좌가 통과했다.
            #      K-MOOC 은 대학 강좌라 직업훈련 어휘와 달라 점수 분포가 직업마다 다르다 → 절대값 무의미.
            #    어떻게: 넓게(POOL) 받아 크로스인코더로 질의-강좌를 함께 읽혀 재정렬하고 상위 3개만 쓴다.
            #    리랭크가 실패하면 예전 임계 방식으로 안전하게 되돌아간다.
            #  커버리지 표가 '안 덮음'이라 하면 **검색 자체를 건너뛴다** — Pinecone 호출도 아낀다.
            #  화면은 이미 이 경우를 옳게 그린다: goal.has_courses 가 false 면 강좌 칸이 사라지고
            #  「2 · 국비 실전 훈련」만 남는다(LearnChat.jsx). 프론트는 고칠 게 없다.
            covered = await self._course_covered(db, chosen['job_code'])
            pool = (await m.match_courses(db, cq, top_k=self.COURSE_POOL, min_score=0.0)
                    if covered else [])
            ranked = []
            if pool:
                docs = [f"{c['title']} {c.get('classfy') or ''} {(c.get('summary') or '')[:160]}"
                        for c in pool]
                #  rerank() 는 실패해도 예외를 안 내고 [] 를 준다(실패 로그는 match.py 가 찍는다).
                order = await m.rerank(cq, docs, top_n=3)
                if order:
                    ranked = [pool[i] for i, _ in order[:3]]
                else:
                    #  ★ 폴백을 '절대임계'로 두면 안 된다(2026-07-30) — 실측상 COURSE_MIN_SCORE=0.70 은
                    #    가구제작·요양지원·내선공사에서 0개를 통과시킨다. 리랭커가 잠깐 죽었을 때
                    #    화면에서 '1단계 무료강의'가 통째로 사라지는 것이 더 나쁘다.
                    #    → 벡터 유사도 순서 상위 3개를 그대로 쓴다(리랭커 없던 시절과 동일한 품질).
                    ranked = pool[:3]
            courses = ranked
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
            #  forced 경로는 jobs 가 비어 있으므로 같은 중분류의 형제 직업을 대안으로 쓴다.
            'alternatives': ([j['job_name'] for j in jobs
                              if j['job_name'] != chosen['job_name']][:2] if jobs
                             else await self._siblings(db, chosen)),
        }

    async def _siblings(self, db, job, k=2):
        """같은 중분류의 다른 직업 이름 ≤k — forced 경로의 '다른 방향' 후보(2026-07-30)."""
        if not (job or {}).get('group'):
            return []
        #  같은 소분류(job_scls_name)를 먼저 — 중분류만 보면 '내선공사'에 '수력발전설비설계' 같은
        #  먼 형제가 무작위 순서로 잡혔다(LIMIT 에 ORDER BY 가 없어 순서도 비결정적이었다).
        rows = (await db.execute(text(
            "SELECT job_name FROM job_catalog "
            "WHERE job_mcls_name = :g AND job_code <> :c "
            "ORDER BY (job_scls_name = :s) DESC, job_name LIMIT :k"),
            {'g': job['group'], 'c': str(job['job_code']),
             's': job.get('scls') or '', 'k': k})).fetchall()
        return [r[0] for r in rows]

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
        #  자기 위해 신호 — 차단하지 않는다. 상담 연락처를 건네고 대화를 열어 둔다(kind='ask').
        #  LLM 을 부르지 않으므로 모델이 위험한 말을 생성할 여지도 없고 비용도 0이다.
        if pc == 'SELFHARM':
            return {'kind': 'ask', 'profile': profile, 'reply': CRISIS_REPLY,
                    'missing': missing_slots(profile), 'can_land': can_land(profile), 'card': None}
        if pc == 'UNSAFE':
            return {'kind': 'blocked', 'profile': profile,
                    'reply': '그런 이야기는 도와드리기 어려워요. 되고 싶은 모습이나 관심 있는 걸 들려주세요.',
                    'missing': missing_slots(profile), 'can_land': can_land(profile), 'card': None}

        # ★ 좁히기 답변 수신(2026-07-30) — 직전 턴에 선택지를 보여줬다면, 사용자가 이름으로든
        #   '첫 번째요'·'2번' 같은 순서로든 고른 걸 받아들인다. 예전엔 근거가 없어 슬롯이 버려지고
        #   같은 질문이 다시 나갔다(무한 되물음). LLM 을 부르지 않으므로 이 턴은 비용이 0이다.
        picked = pick_from_options(user_msg, profile.get('_narrow_opts'))
        if picked:
            profile = dict(profile)
            profile['세부관심'] = picked
            profile.pop('_narrow_opts', None)       # 같은 선택지를 다시 쓰지 않는다
            code = await self._named_entity(db, picked)
            card = None
            if code:
                try:
                    card = await self.search(db, profile, picked, direct=True, force_code=code)
                except Exception as e:
                    print(f'[itda] 좁히기 선택 후 검색 실패: {type(e).__name__}: {e}')
            if card and not card.get('narrow') and not card.get('not_found'):
                return {'kind': 'card', 'profile': profile, 'card': card,
                        'reply': f'‘{picked}’ 쪽으로 찾아봤어요.',
                        'missing': missing_slots(profile), 'can_land': can_land(profile)}
            #  카드를 못 만들면 선택은 반영한 채 대화를 이어간다(다음 턴에 다시 판단).
            return {'kind': 'ask', 'profile': profile, 'card': None,
                    'reply': f'‘{picked}’ 쪽으로 보고 있어요. 조금만 더 말씀해 주시면 길을 잡아볼게요 — '
                             '그 일에서 특히 어떤 부분이 끌리세요?',
                    'missing': missing_slots(profile), 'can_land': can_land(profile)}

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
        #   ★ 메타 발화도 건너뛴다(2026-07-31) — "뭐라고?"·"알아들었어?"는 진로 내용이 아니라서
        #     이탈 게이트가 "저는 진로·적성 상담을 도와드려요"로 되돌려버렸다(골든셋이 잡았다).
        #     대화에 대한 말은 이탈이 아니라 **대화의 일부**다. 아래 META 분기가 받아야 한다.
        if (not has_interest(profile) and not is_uncertain(user_msg)
                and not is_meta(user_msg) and not await self._on_topic(user_msg)):
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

        # ★ '그게 뭐예요?' 설명 응답(2026-07-30) — 좁히기 선택지에 뜬 이름의 뜻을 물으면
        #   카드가 아니라 **DB 의 직업 설명**으로 답한다. job_catalog.job_description 은 100% 채워져 있다.
        #   이전엔 이 발화가 카드 확정으로 이어졌고(사고), 막고 나니 모델이 사과만 하고 뜻은 안 알려줬다.
        #   LLM 호출 전에 처리하므로 이 턴은 Gemini 비용이 0이다.
        #   ★ 단, **짧은 순수 질문일 때만** 여기서 끝낸다(2026-07-30). 예전엔 길이를 안 봐서
        #     "제빵사는 어떤 일 해요? 저는 뭔가 만드는 게 좋아요" 처럼 질문 + 관심사가 섞인 발화에서
        #     '만들기'가 통째로 버려졌다(turn() 을 안 부르니 슬롯 추출이 아예 없다).
        #     긴 발화는 아래 정상 경로로 흘려보내 슬롯을 챙긴다.
        if asks_meaning(user_msg) and len(re.sub(r'\s+', '', user_msg or '')) <= 24:
            code = await self._named_entity(db, user_msg)
            job = await self._job_by_code(db, code) if code else None
            if job:
                nm = job['job_name']
                desc = re.sub(r'\s+', ' ', (job.get('description') or '')).strip()
                #  NCS 설명은 대개 '가구제작은 …이다' 처럼 직업명으로 시작한다. 앞머리를 떼지 않으면
                #  "‘가구제작’은 가구제작은 …" 으로 겹친다. 문말도 '~이다' → '~예요' 로 다듬는다.
                desc = re.sub(rf'^{re.escape(nm)}\s*(은|는|이란|이라 함은|이라는)\s*', '', desc)
                desc = re.sub(r'(하는 일|것)이다\.?$', r'\1이에요.', desc)
                desc = re.sub(r'이다\.?$', '이에요.', desc)
                if len(desc) > 220:
                    desc = desc[:220].rstrip() + '…'
                body = f"‘{nm}’{_eun_neun(nm)} {desc}" if desc else f"‘{nm}’ 쪽 일이에요."
                return {'kind': 'ask', 'profile': profile,
                        'reply': f"{body}\n\n이 쪽이 맞을까요? 아니면 다른 방향도 같이 볼까요?",
                        'missing': missing_slots(profile), 'can_land': can_land(profile),
                        'card': None}

        t = await self.turn(profile, user_msg)
        if not t:                                   # 안전필터 차단
            return {'kind': 'blocked', 'profile': profile,
                    'reply': '그 부분은 도와드리기 어려워요. 다른 관심사를 편하게 말씀해 주세요.',
                    'missing': missing_slots(profile), 'can_land': can_land(profile), 'card': None}

        # ★ 근거 검증 — 발화에 없는 근거를 댄 슬롯은 버린다 (프롬프트가 아니라 코드가 막는다)
        new_slots, dropped = verify_slots(t.get('profile'), user_msg)
        profile = merge(profile, new_slots)
        if new_slots:
            profile.pop('_unsure', None)        # 실제 정보를 주면 '모르겠다' 카운터 초기화
        act = t.get('action', 'ASK')

        # ★ 코드 DIRECT 탐지(2026-07-29) — 발화가 DB 실재 직업/자격증 이름을 통째로 담으면
        #   LLM 이 ASK/SEARCH 라 해도 코드가 그 직업으로 확정(DIRECT)한다. 저비용 모델(minimal·
        #   flashlite)이 "전기기능사 따고 싶어요"를 되묻던 것(NRM-direct-cert) 차단. '정확 포함'만
        #   신뢰하므로 이탈·인젝션·모호엔 안 걸린다(오탐 0, 20케이스 실측). 단, 모델이 명시적으로
        #   funnel 을 벗어난(REDIRECT/OFFRAMP) 건 존중한다(안전 우선 — 이름이 섞여도 뒤집지 않음).
        #   ★ 단, 사용자가 그 이름을 '거부·되물음'한 발화는 확정하지 않는다(2026-07-30 버그 수정).
        #     "가구제작은 무슨 소리야?" 를 [가구제작] 카드로 확정하던 사고. 자세한 근거는
        #     rejects_or_questions() 주석 참고.
        # ★ META(2026-07-30) — 대화 자체에 대한 말이면 검색하지 않는다. 코드 DIRECT 도 걸지 않는다.
        #   "알아들었어?" 가 진로 발화로 처리돼 [청각관리] 카드가 나갔던 사고를 구조적으로 막는다.
        #   '이해했나?' 류에는 **지금까지 이해한 슬롯을 그대로 되짚어** 준다(코드가 쓰므로 환각 없음).
        if act != 'META' and is_meta(user_msg) and act not in ('REDIRECT', 'OFFRAMP'):
            act = 'META'        # 코드 안전망 — 모델이 놓친 짧고 명백한 메타 발화를 코드가 확정
        if act == 'META':
            known = {k: v for k, v in profile.items() if v and not k.startswith('_')}
            if asks_understanding(user_msg) and known:
                lines = ' · '.join(f'{k} {v}' for k, v in known.items())
                reply = (f'네, 지금까지 이렇게 이해했어요 — {lines}\n'
                         '틀린 게 있으면 바로 고쳐 주세요. 맞으면 이대로 방향을 찾아볼게요.')
            elif asks_understanding(user_msg):
                reply = ('아직 들은 게 많지 않아요. 관심 있는 것이나 해봤던 일을 한 가지만 '
                         '말씀해 주시면 거기서부터 같이 찾아볼게요.')
            else:
                reply = t.get('reply') or '네, 편하게 말씀해 주세요.'
            return {'kind': 'ask', 'profile': profile, 'reply': reply, 'card': None,
                    'missing': missing_slots(profile), 'can_land': can_land(profile)}

        forced_code = None
        if act not in ('REDIRECT', 'OFFRAMP') and not rejects_or_questions(user_msg):
            forced_code = await self._named_entity(db, user_msg)
            if forced_code:
                act = 'DIRECT'

        # ★ 착지 가드(양방향) — 착지 여부는 코드가 판정한다. 모델의 SEARCH/ASK 자기판단을 안 믿는다.
        #   DIRECT 는 슬롯이 아니라 '목표를 말했는가'로 판단하므로 이 가드를 안 받는다(search 안 유사도로 검증).
        #   ↓ 미착지인데 SEARCH → 되묻기로 내림 (성급한 추천 방지)
        #   ↑ 착지 가능인데 ASK → 검색으로 올림. 프롬프트가 "채워지면 바로 SEARCH"라 부탁해도
        #     사고 적은 모델(minimal)이 흘려 한 턴 더 되묻는 게 실측됨(HAP-004·ADV-005: 슬롯은 dynamic과
        #     동일한데 ask). "충분한가"는 슬롯이 정하므로 코드가 강제한다. CLARIFY(모순확인)는 안 건드린다.
        #   ★ 승격 예외(2026-07-30) — 사용자가 방금 '거부·되물음'을 했으면 올리지 않는다.
        #     실측 사고: 좁히기 뒤 "가구제작은 무슨 소리야?" → 모델은 사과+되묻기(ASK)를 냈는데
        #     슬롯이 차 있다는 이유로 코드가 SEARCH 로 승격 → 벡터가 발화의 '가구제작'을 물어
        #     [가구제작] 카드를 확정했다. 뜻을 묻는 사람에게 그 직업을 확정해 주는 셈.
        #     ⇒ 거부·질문 턴은 모델의 ASK 를 그대로 존중한다(다음 턴에 다시 판단).
        if act == 'SEARCH' and not can_land(profile):
            act = 'ASK'
        elif act == 'ASK' and can_land(profile) and not rejects_or_questions(user_msg):
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
        elif (act == 'ASK' and is_uncertain(user_msg)
              #  ★ 사정을 이야기한 턴이나 긴 발화는 코드가 덮어쓰지 않는다(2026-07-30 사고 수정).
              #    "모르겠어 … 어머니가 아프셔서 돌봐드리느라" 같은 발화에서 모델의 공감 답변을
              #    통조림 슬롯 질문으로 갈아치우던 문제. 짧고 순수한 '모르겠다'에만 적용한다.
              and not tells_situation(user_msg)
              and len(re.sub(r'\s+', '', user_msg or '')) <= 20):
            #  ★ '모르겠다/생각 안 해봤다'에는 **열린 질문을 또 던지지 않는다**(2026-07-30).
            #    실사용 로그: 두 턴 연속 "생각 안 해봤다"인데 모델이 계속 열린 질문을 냈고,
            #    슬롯명(다루는대상='일의 주 재료')을 풀어쓰다 "어떤 대상을 만지거나 다루는" 같은
            #    어색한 문장이 나갔다. 코드가 쓴 **보기 있는 질문**으로 바꾼다.
            #    또 같은 질문을 글자 그대로 반복하지 않도록 횟수를 세서 각도를 바꾼다.
            n = int(profile.get('_unsure') or 0) + 1
            profile['_unsure'] = n
            out['profile'] = profile
            out['reply'] = unsure_reply(profile, n)
        elif act == 'ASK' and '?' not in (out['reply'] or ''):
            out['reply'] = ask_reply(profile)   # ASK인데 질문 없이 '찾아볼게요' 류로 끝냄 → 진짜 질문으로(막다른 답변 방지)

        if act in ('SEARCH', 'DIRECT'):
            #  검색어 앵커(2026-07-29) — 벡터가 '돌봄' 등 종류로 뭉쳐 드리프트하는 걸 사용자 원문 키워드로 고정.
            #  DIRECT(콕 집음)는 LLM 재작성이 '아이/청소년' 같은 엉뚱한 키워드를 섞어 오염시키므로 원문만 쓴다.
            #  SEARCH(누적·좁힘)는 슬롯 기반 query 가 필요하니 query + 원문.
            q = user_msg if act == 'DIRECT' else f"{t.get('query', '')} {user_msg}".strip()
            #  ★ 검색 실패를 흡수한다(2026-07-30) — 예전엔 여기서 예외가 그대로 올라가
            #    controllers 가 턴 전체를 blocked/error 로 만들었고, **병합된 슬롯도 버려졌다**.
            #    Pinecone 쿼터·네트워크가 한 번 흔들리면 착지 가능한 사용자는 매 턴 같은 오류만 보고
            #    영원히 진행하지 못했다(무한 루프). 이제 슬롯은 지키고 되묻기로 이어간다.
            try:
                #  ★ '결정론적 앵커' 시도는 **측정으로 기각**했다(2026-07-30).
                #    가설: 융합 목록 앞자리에 고정값(사용자 원문 · 슬롯 이어붙인 질의)을 넣으면
                #          LLM 질의가 흔들려도 결과가 고정될 것이다.
                #          (근거로 삼은 연구 결론: "LLM 출력으로 원문을 대체하면 회수율이 떨어진다.
                #           원문을 전부 포함하고 LLM 출력은 순위를 보태는 데만 써야 최적이다.")
                #    실측: 같은 입력 6회 반복에서 흔들림이 **1종 → 4종으로 악화**했다.
                #    이유: 슬롯 질의('사람 돕기 사람')가 너무 일반적이어서, 고정 앵커가 신호를
                #          고정하는 대신 '돕기' 계열(가사지원·공공복지·일상생활기능지원)을 잔뜩 끌어와
                #          후보 풀을 희석했다. 앵커가 약하면 안정화가 아니라 잡음이 된다.
                #    ⇒ 원문은 이미 q 에 이어붙여 들어간다(아래). 별도 앵커를 더하지 않는다.
                card = await self.search(db, profile, q, direct=(act == 'DIRECT'),
                                         force_code=forced_code,
                                         alts=t.get('query_alts'))
            except Exception as e:
                print(f'[itda] 검색 실패(대화는 계속): {type(e).__name__}: {e}')
                out['kind'] = 'ask'
                out['reply'] = ('지금 추천을 불러오는 데 문제가 있었어요. 조금 더 이야기해 주시면 '
                                '다시 찾아볼게요 — 어떤 일이 가장 마음에 걸리세요?')
                return out
            if card and card.get('narrow'):
                out['kind'] = 'ask'                           # 넓게 흩어짐 → 좁히는 되물음(코드가 문구 씀)
                out['reply'] = narrow_reply(card['options'])
                #  좁혔다는 사실과 보여준 선택지를 기억한다 → 다음 턴에 순서로 답해도 받고, 두 번 좁히지 않는다.
                profile['_narrowed'] = True
                profile['_narrow_opts'] = list(card['options'] or [])
                out['profile'] = profile
                out['options'] = list(card['options'] or [])          # 프론트 chip 용
                out['option_notes'] = list(card.get('option_notes') or [])
            elif card and card.get('low_score'):
                #  후보가 다 약하다 → 억지로 카드를 내지 않고 남은 슬롯을 묻는다(2026-07-30).
                out['kind'] = 'ask'
                out['reply'] = ask_reply(profile)
            elif card and card.get('not_found'):
                out['kind'] = 'notfound'
                out['near'] = card['near']
                out['reply'] = notfound_reply(card['near'])   # 모델 말 대신 코드가 쓴다
            elif card:
                out['kind'], out['card'] = 'card', card
                # 카드를 내놓으면 되물으면 안 된다 — ASK→SEARCH 승격 시 모델 답이 질문일 수 있다.
                #  (2026-07-30) endswith('?') 만 보면 "맞을까요? 아래에서 확인해 보세요." 처럼
                #  물음표가 문말이 아닌 답변이 카드와 함께 나갔다 → 문장 안에 물음표가 있으면 교체한다.
                if '?' in (out['reply'] or ''):
                    out['reply'] = '말씀해 주신 걸 바탕으로 이 길을 찾아봤어요.'
            else:
                out['kind'] = 'ask'
                #  (2026-07-30) '자격증' → '방향' — 직업-먼저 전환 뒤에도 남아 있던 옛 문구. 사용자에게 보인다.
                out['reply'] += '\n(아직 딱 맞는 방향을 못 찾았어요 — 조금 더 얘기해볼까요?)'
        return out
