# -*- coding: utf-8 -*-
"""
잇다 코어 — CLI와 백엔드가 함께 쓰는 순수 로직
──────────────────────────────────────────────────────────
왜 분리했나
  engine.py 는 import 만 해도 getpass 로 비번을 묻고 DB에 붙었다.
  → FastAPI 에 넣으면 서버가 아예 못 뜬다.
  이 파일은 import 시 아무 부작용이 없다. 필요한 순간에만 연결한다.

쓰는 법
    from itda_core import ItdaEngine
    eng = ItdaEngine()                     # 아직 DB·API 안 붙음
    r = eng.step(profile, "컴퓨터 만지는 게 재밌어요")
    #  r = {kind, reply, profile, missing, can_land, card}

DB 비밀번호
    ① 환경변수 DB_PASSWORD  ② .env 의 DB_PASSWORD  ③ (CLI 한정) getpass
    서버에서는 ①②로 해결되므로 프롬프트가 뜨지 않는다.
"""
import os, re, json, getpass
import urllib.request, urllib.error
import pymysql

MODEL = 'gemini-3.6-flash'
GRADE = '기능사'          # 응시자격 제한이 없는 유일한 등급 → 대상자가 지금 당장 딸 수 있음


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

PROFILE_SCHEMA = {'type': 'OBJECT', 'properties': {
    '관심분야': _slot('좋아한다·재밌다·해봤다고 말한 활동이나 대상'),
    '환경선호': _slot('실내/야외 선호', ['실내', '야외', '상관없음']),
    '활동선호': _slot('몸/머리 선호', ['몸쓰는일', '머리쓰는일', '둘다']),
    '시간제약': _slot('시간·일정에 관한 사정'),
    '비용제약': _slot('돈·비용에 관한 사정'),
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
    names = ' · '.join(c['cert'] for c in (near or [])[:3])
    msg = '말씀하신 건 저희가 다루는 국가자격(613종) 안에서는 찾지 못했어요.'
    if names:
        msg += f'\n\n비슷한 분야로는 {names} 가 있어요. 이 중에 궁금한 게 있으세요?'
    msg += '\n아니면 어떤 일을 하고 싶은지 편하게 말씀해 주셔도 좋아요.'
    return msg


def _match_mod():
    """match 모듈 — 백엔드(패키지)와 CLI(스크립트) 양쪽에서 import 되게."""
    try:
        from . import match          # 패키지로 import 될 때(백엔드)
    except ImportError:
        import match                 # 스크립트로 실행될 때(CLI)
    return match


ASK_ORDER = ['관심분야', '환경선호', '활동선호', '시간제약', '비용제약']

def missing_slots(p):
    return [k for k in ASK_ORDER if not (p or {}).get(k)]

#  '상관없음'·'둘다' 는 값이 채워져 있어도 직무분야를 좁히는 데 기여가 0이다.
#  모델이 "모르겠다"를 이 값으로 바꿔 담는 일이 실측됨(2026-07-23) → 착지 판정에서 제외한다.
NEUTRAL = {'상관없음', '둘다'}

def can_land(p):
    """착지 조건은 코드가 판정한다 — 모델의 자기보고(confidence)를 믿지 않는다."""
    p = p or {}
    narrowing = (p.get('환경선호') not in NEUTRAL and p.get('환경선호')) or \
                (p.get('활동선호') not in NEUTRAL and p.get('활동선호'))
    return bool(p.get('관심분야')) and bool(narrowing)

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


SYSTEM = """너는 '잇다'의 진로 동반자다.

[대상]
가족 돌봄으로 학업을 놓은 청년. 시간과 돈이 부족하고, 무엇보다 자기 목표를 말로 표현하지 못한다.

[가장 중요한 원칙]
"어떤 자격증을 원하세요?"라고 묻지 않는다. 그 질문에 답할 수 있는 사람은 애초에 여기 오지 않는다.
일상의 언어로 묻고, 그 답을 직무분야로 번역하는 것이 네 일이다.

[하지 말 것]
· 사용자가 직접 말하지 않은 사정(돌봄 상황·가정형편·경제사정)을 단정하지 마라.
  짐작이 되더라도 아는 척하지 말고, 필요하면 질문으로 확인하라.
· 한 턴에 여러 개를 묻지 마라. 하나씩.
· 확실하지 않은 슬롯은 채우지 말고 생략하라. 추측으로 채우면 안 된다.

[매 턴 할 일 — 이 순서대로]
1) 먼저, 사용자가 방금 한 말에서 슬롯을 뽑는다.   ← 이게 최우선이다
2) 그 다음, 아직 빈 슬롯을 보고 행동을 고른다.

[슬롯 5개]
관심분야  좋아한다·재밌다·해봤다고 말한 활동이나 대상
환경선호  실내 / 야외 / 상관없음
활동선호  몸쓰는일 / 머리쓰는일 / 둘다
시간제약  시간·일정에 관한 사정
비용제약  돈·비용에 관한 사정

[슬롯 뽑기 — 값과 '근거'를 함께 낸다]
근거에는 사용자가 **실제로 한 말을 그대로** 옮긴다. 요약하거나 바꿔 쓰지 않는다.

  "컴퓨터 만지는 게 재밌어요"
      → 관심분야 = {값:"컴퓨터", 근거:"컴퓨터 만지는 게 재밌어요"}
  "고치는 것도 좋고 컴퓨터도 재밌어요"
      → 관심분야 = {값:"기계 고치기, 컴퓨터", 근거:"고치는 것도 좋고 컴퓨터도 재밌어요"}
  "화면 앞이 나아요"
      → 환경선호 = {값:"실내", 근거:"화면 앞이 나아요"}
  "할머니 보느라 시간이 없어요"
      → 시간제약 = {값:"돌봄으로 시간 부족", 근거:"할머니 보느라 시간이 없어요"}
  "잘 모르겠어요"
      → 아무 슬롯도 내지 않는다

★ 근거로 쓸 말이 발화에 없으면 그 슬롯을 아예 내지 마라.
  지어낸 근거는 시스템이 원문과 대조해서 걸러내므로, 채워도 버려진다.
  "모르겠다"는 "상관없다"가 아니다 — 내지 않는 쪽이다.

[관심분야를 직업으로 바꾸지 않는다]
관심은 목적지가 아니라 성향의 단서다.
  "게임을 좋아한다"  → 화면 앞·실내·컴퓨터를 편해한다는 신호로 읽는다.
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
OFFRAMP   어떤 자격증에도 연결되지 않는다
REDIRECT  가해·해악의 의도, 선정적 표현, 욕설/도발 → 차분히 되돌린다
          ※ '군인·경찰·소방관' 같은 직업으로서의 관심은 정상이다. 절대 REDIRECT 하지 마라.

[DIRECT — 이미 답을 가진 사람에게 되묻지 마라]
목표를 분명히 말한 사람에게 "실내가 좋으세요?"를 묻는 건 무례하고 시간 낭비다.
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
'관심분야'가 있고, '환경선호'나 '활동선호' 중 하나가 있으면 착지 가능이다.
★ 판단은 '이번 턴에 네가 새로 파악한 것까지 포함한 상태'로 하라.
   이번 턴에 마지막 조건이 채워졌다면 곧바로 SEARCH로 가라. 한 턴 더 묻지 마라.
조건이 충족되지 않으면 SEARCH를 고르지 마라. 예외 없다.

[검색 질의 — SEARCH일 때만 query를 쓴다]
query에는 이 사람이 '어떤 일을 하게 될지'를 풀어 쓴다.
자격증 이름을 짐작해서 쓰지 마라. 그건 시스템이 찾는다.
  관심분야=기계 고치기, 컴퓨터 / 환경선호=실내
      → query = "기계나 전자장비를 실내에서 점검하고 수리하는 일"
  관심분야=요리 / 환경선호=실내
      → query = "주방에서 재료를 손질하고 음식을 조리하는 일"
자격증 설명은 '무슨 일을 하는지'로 적혀 있다. 그 말투에 맞춰 쓸수록 잘 찾는다.

[말투]
따뜻하되 과장하지 않는다. 상대의 상황을 앞질러 규정하지 않는다.
'고생 많으셨겠어요' 같은 말은 사용자가 실제로 그 상황을 말했을 때만 쓴다."""


class ItdaEngine:
    """import 시점에는 아무것도 연결하지 않는다. 필요할 때 붙는다."""

    def __init__(self, gemini_key=None, db=None, model=MODEL, allow_prompt=False,
                 think_budget=None):
        self.model = model
        self.gemini_key = gemini_key or next(
            (v for k, v in ENV.items() if k.startswith('GEMINI_API_KEY') and v), None)
        self.allow_prompt = allow_prompt          # CLI 에서만 True → 비번 물어봄
        # 사고(thinking) 토큰 — 화면엔 안 보이는데 출력 단가로 과금된다(실측: 비용의 약 75%).
        #   None = 모델 기본 / 정수 = 상한.  128 이면 실측상 사고 0 → 턴당 9원 → 3.8원
        #   ※ 0 은 400 에러. 끄려면 작은 양수를 준다.
        if think_budget is None:
            v = ENV.get('ITDA_THINK_BUDGET')
            think_budget = int(v) if v and v.strip().isdigit() else None
        self.think_budget = think_budget
        self._db = db                             # 외부에서 커넥션 주입 가능
        self._oblig = None
        self._turn_schema = None
        self.last_usage = {'in': 0, 'out': 0, 'think': 0}
        self.total_usage = {'in': 0, 'out': 0, 'think': 0, 'calls': 0}

    # ── DB (지연 연결 + 끊기면 재연결) ──────────────────────────────
    def _password(self):
        pw = ENV.get('DB_PASSWORD') or os.environ.get('DB_PASSWORD')
        if not pw and self.allow_prompt:
            pw = getpass.getpass('user2604 DB 비밀번호: ')
        if not pw:
            raise RuntimeError('DB_PASSWORD 없음 — .env 에 넣거나 allow_prompt=True 로 실행')
        os.environ.setdefault('DB_PW', pw)        # match.py 가 이 키를 재사용
        return pw

    @property
    def db(self):
        if self._db is None:
            self._db = pymysql.connect(
                host=ENV.get('DB_HOST', 'localhost'),
                port=int(ENV.get('DB_PORT', 3306)),
                user=ENV.get('DB_USER', 'user2604'),
                password=self._password(),
                database=ENV.get('DB_NAME', 'eum'),
                charset='utf8mb4')
        else:
            try:
                self._db.ping(reconnect=True)      # 서버에서 오래 살면 끊긴다
            except Exception:
                pass
        return self._db

    # ── 직무분야 enum (DB 에서 1회 로드) ────────────────────────────
    @property
    def oblig_flds(self):
        if self._oblig is None:
            with self.db.cursor() as cur:
                cur.execute("SELECT DISTINCT oblig_fld FROM certification "
                            "WHERE grade=%s ORDER BY oblig_fld", (GRADE,))
                self._oblig = [r[0] for r in cur.fetchall()]
        return self._oblig

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
    def gemini(self, prompt, schema, temp=0.7):
        url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
               f'{self.model}:generateContent?key={self.gemini_key}')
        cfg = {'responseMimeType': 'application/json',
               'responseSchema': schema, 'temperature': temp}
        if self.think_budget is not None:
            cfg['thinkingConfig'] = {'thinkingBudget': self.think_budget}
        body = json.dumps({'contents': [{'parts': [{'text': prompt}]}],
                           'generationConfig': cfg}).encode()
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={'Content-Type': 'application/json'})
            j = json.loads(urllib.request.urlopen(req, timeout=90).read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', 'replace')[:200]
            raise RuntimeError(f'Gemini {e.code}: {detail}') from None
        # 과금 근거를 남긴다 — 사고 토큰은 화면에 안 보이므로 이걸로만 확인 가능
        um = j.get('usageMetadata') or {}
        self.last_usage = {
            'in': um.get('promptTokenCount', 0),
            'out': um.get('candidatesTokenCount', 0),
            'think': um.get('thoughtsTokenCount', 0),
        }
        self.total_usage['in'] += self.last_usage['in']
        self.total_usage['out'] += self.last_usage['out']
        self.total_usage['think'] += self.last_usage['think']
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

    def turn(self, profile, user_msg):
        miss = missing_slots(profile)
        prompt = (f"{SYSTEM}\n\n"
                  f"[지금까지 파악한 것]\n{profile_text(profile)}\n\n"
                  f"[아직 모르는 것]\n{', '.join(miss) if miss else '(없음)'}\n\n"
                  f"[이번 턴 입력 전 착지 조건]\n"
                  f"{'이미 충족 — SEARCH 가능' if can_land(profile) else '아직 미충족 (이번 턴에 채워지면 충족될 수 있다. 착지 규칙 참고)'}\n\n"
                  f"[사용자]\n{user_msg}")
        return self.gemini(prompt, self.turn_schema, self.TEMP_TURN)

    # ── 검색 : 후보는 벡터, 선택만 모델 ─────────────────────────────
    #  2026-07-23 전면 교체.
    #    예전 : 모델이 대직무분야 17개 중 1개 선택 → 그 분야 기능사만 조회 → 모델이 1개 선택
    #    지금 : query → 벡터 → 613종 중 후보 20 → 「지금 바로」/「다음 단계」로 가름 → 모델이 선택
    #
    #  왜 바꿨나 (실측 근거)
    #    · 기능사가 0개인 대직무분야가 7개다 — 사회복지·경영회계사무·보건의료 등.
    #      "사람 돌보는 일이 익숙해요" 라고 하면 옛 경로에선 추천할 게 아예 없었다.
    #    · 국가전문자격 100종은 oblig_fld 가 빈 문자열이라 17개 enum 에 들어가지도 못했다.
    #      (공인중개사·세무사·관세사·물류관리사가 통째로 도달 불가)
    #    · 자격증 임베딩에 '수행직무'가 들어가 있어 일상어로도 걸린다.
    #      "고치는 거 좋아해요" → 자동차정비기능사("고장부위를 진단하고 수리하는")
    CAND_POOL = 20        # 벡터에서 뽑을 후보 수
    N_NOW     = 6         # 모델에게 보여줄 「지금 바로」 후보 수

    # 목표를 콕 집어 말했을 때(DIRECT) 그 목표가 '우리에게 있는가'를 가르는 선.
    #  실측(2026-07-23, 26개 질의)으로 정했다:
    #      있음  최저 0.623 · 중앙 0.765 · 최고 0.885
    #      없음  최저 0.458 · 중앙 0.597 · 최고 0.693  (공무원 0.693 · 바리스타 0.688)
    #  0.70 이면 오탐 0 / 놓침 2 (미용사 0.623 · 전기산업기사 0.665).
    #  일부러 오탐 0 쪽으로 잡았다 —
    #    놓침은 "못 찾았어요, 대신 이런 게 있는데" 로 회복되지만,
    #    "AWS 자격증" 에 "공인중개사 어떠세요?" 를 내놓으면 신뢰가 회복되지 않는다.
    #  ※ cert_job 을 채워 얇은 25종의 벡터가 두꺼워지면 이 값을 다시 재야 한다.
    DIRECT_MIN_SCORE = 0.70

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

    def _search_query(self, profile, query=''):
        """모델이 query 를 안 줬을 때 쓸 대체 질의 — 슬롯을 이어붙인다."""
        if query:
            return query
        p = profile or {}
        bits = [p.get('관심분야')]
        for k in ('환경선호', '활동선호'):
            if p.get(k) and p[k] not in NEUTRAL:
                bits.append(p[k])
        return ' '.join(x for x in bits if x)

    def _next_exam(self, cert_id):
        """'다음' 시험 — 회차 번호가 아니라 '오늘 이후 날짜' 중 가장 가까운 것.

        회차순 정렬은 제0회(필기 없는 특별회차)나 이미 지난 회차를 뽑아버린다(실측).
        """
        SEL = ("SELECT impl_seq, doc_exam_start, prac_exam_start, prac_pass_dt "
               "FROM exam_schedule WHERE cert_id=%s ")
        with self.db.cursor() as cur:
            cur.execute(SEL + "  AND (doc_exam_start >= CURDATE() OR prac_exam_start >= CURDATE()) "
                              " ORDER BY COALESCE(doc_exam_start, prac_exam_start) LIMIT 1",
                        (cert_id,))
            exam = cur.fetchone()
            if not exam:                       # 남은 일정이 없으면 가장 최근 것이라도
                cur.execute(SEL + " ORDER BY COALESCE(doc_exam_start, prac_exam_start) DESC LIMIT 1",
                            (cert_id,))
                exam = cur.fetchone()
        return exam

    def search(self, profile, query='', direct=False):
        """착지 후 카드 만들기. 후보는 벡터가 찾고, 최종 선택만 모델이 한다.

        direct=True 는 사용자가 목표를 콕 집어 말한 경우다.
          · 유사도 1위가 DIRECT_MIN_SCORE 미만이면 '우리에게 없다'고 판정한다
          · 넘으면 1위를 그대로 쓴다 (모델에게 다시 안 물어봄 — 더 정확하고 8원 싸다)
        """
        q = self._search_query(profile, query)
        if not q:
            return None
        m = _match_mod()

        # ① 벡터 — 613종 전체. 대분류를 거치지 않는다
        cands = m.match_certs(q, top_k=self.CAND_POOL)
        if not cands:
            return None

        # ★ 목표를 콕 집어 말했는데 우리에게 없는 경우 — 지어내지 않고 없다고 한다
        if direct and cands[0]['score'] < self.DIRECT_MIN_SCORE:
            return {'not_found': True, 'query': q,
                    'near': [{'cert': c['jm_name'], 'grade': c['grade'],
                              'entry_free': c['entry_free'],
                              'score': c['score']} for c in cands[:3]]}

        now = [c for c in cands if c['entry_free']][:self.N_NOW]
        later = [c for c in cands if not c['entry_free']]

        # 자격증 '이름'을 그대로 말했는가. 이름이 발화 안에 통째로 들어 있으면 지목이다.
        #   "전기기능사 따고 싶어요"   → 지목  → 그 자격증을 그대로 보여준다(조건과 함께)
        #   "제빵사가 되고 싶어요"     → 아님  → 「지금 바로」 우선으로 간다
        #
        #   ★ 이 구분이 없으면 안 된다(실측 2026-07-23):
        #     "제빵사가 되고 싶어요" 의 벡터 1위는 '제과기능장'이었다.
        #     기능장은 산업기사 취득 후 5년 또는 기능대 기능장과정 이수가 필요하다.
        #     학업을 놓은 대상자에게 이건 최악의 추천이다 — 후보에 제빵기능사가 있는데도.
        #     이름을 지목한 게 아니라면 등급을 사용자가 고른 게 아니므로, 우리가 낮춰 잡아야 한다.
        named = None
        if direct:
            nq = _clean(q)
            named = next((c for c in cands if _clean(c['jm_name']) and _clean(c['jm_name']) in nq),
                         None)

        if named:
            chosen = named
            later = [c for c in cands if not c['entry_free'] and c is not named]
            names = [c['jm_name'] for c in cands[:self.N_NOW]]
            pick = {'reason': '말씀하신 자격증이에요.'}
        else:
            # 「지금 바로」가 하나도 없으면 기능사로 한정해 다시 찾는다.
            # 상위 등급만 내놓으면 학업을 놓은 대상자에게는 쓸모가 없다.
            if not now:
                now = m.match_certs(q, top_k=self.N_NOW, grade=GRADE)
            if not now:
                return None

            # ② 모델은 '고르기'만 한다 — 목록 밖은 스키마(enum)가 막는다
            names = [c['jm_name'] for c in now]
            listing = '\n'.join(f"- {c['jm_name']} ({c['oblig_fld'] or '분야 없음'})" for c in now)
            pick = self.gemini(
                f"이 사람에 대해 파악한 것: {profile_text(profile)}\n\n"
                f"지금 바로 응시할 수 있는 자격증 후보:\n{listing}\n\n"
                f"이 중 가장 어울리는 하나를 골라라(목록 밖 금지).\n"
                f"이유는 이 사람이 실제로 한 말에 근거해서 한 문장으로.",
                {'type': 'OBJECT',
                 'properties': {'cert': {'type': 'STRING', 'enum': names},
                                'reason': {'type': 'STRING'}},
                 'required': ['cert', 'reason']}, 0.3) or {'cert': names[0], 'reason': ''}
            chosen = next(c for c in now if c['jm_name'] == pick['cert'])

        # ③ 강좌 — 자격증명만으로는 벡터가 빈약하다. 분야와 관심사를 함께 던진다
        cq = ' '.join(x for x in [chosen['jm_name'], chosen['oblig_fld'],
                                  chosen['mdoblig_fld'], (profile or {}).get('관심분야')] if x)
        courses, course_err = [], None
        try:
            # 강좌를 못 찾아도 카드는 나가야 한다. 억지로 채우는 것보다 비는 게 낫다
            courses = m.match_courses(cq, top_k=3, min_score=self.COURSE_MIN_SCORE)
        except Exception as e:
            course_err = f'{type(e).__name__}: {str(e)[:80]}'

        # ④ 다음 단계 — 같은 분야의 상위 등급 하나. 지도에 '그 다음'이 있어야 지도다
        nxt = next((c for c in later if c['oblig_fld'] == chosen['oblig_fld']), None)

        return {
            'oblig_fld': chosen['oblig_fld'], 'cert_id': chosen['cert_id'],
            'cert': chosen['jm_name'], 'grade': chosen['grade'],
            'entry_free': chosen['entry_free'], 'entry_note': chosen['entry_note'],
            'reason': pick['reason'], 'courses': courses, 'course_error': course_err,
            'exam': self._next_exam(chosen['cert_id']),
            'next_step': ({'cert': nxt['jm_name'], 'grade': nxt['grade'],
                           'entry_note': nxt['entry_note']} if nxt else None),
            'alternatives': [n for n in names if n != chosen['jm_name']][:2],
        }

    # ── 백엔드가 부를 단일 진입점 ───────────────────────────────────
    def step(self, profile, user_msg):
        """한 턴을 통째로 처리. HTTP 응답으로 그대로 옮길 수 있는 모양으로 돌려준다."""
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

        t = self.turn(profile, user_msg)
        if not t:                                   # 안전필터 차단
            return {'kind': 'blocked', 'profile': profile,
                    'reply': '그 부분은 도와드리기 어려워요. 다른 관심사를 편하게 말씀해 주세요.',
                    'missing': missing_slots(profile), 'can_land': can_land(profile), 'card': None}

        # ★ 근거 검증 — 발화에 없는 근거를 댄 슬롯은 버린다 (프롬프트가 아니라 코드가 막는다)
        new_slots, dropped = verify_slots(t.get('profile'), user_msg)
        profile = merge(profile, new_slots)
        act = t.get('action', 'ASK')

        # ★ 착지 가드 — 조건은 코드가 판정한다.
        #   DIRECT 는 슬롯이 아니라 '목표를 말했는가'로 판단하므로 이 가드를 안 받는다.
        #   대신 search() 안에서 유사도 임계로 검증한다.
        if act == 'SEARCH' and not can_land(profile):
            act = 'ASK'

        out = {'kind': act.lower(), 'reply': t.get('reply', ''), 'profile': profile,
               'missing': missing_slots(profile), 'can_land': can_land(profile),
               'dropped': dropped, 'card': None, 'near': None}

        if act in ('SEARCH', 'DIRECT'):
            card = self.search(profile, t.get('query', ''), direct=(act == 'DIRECT'))
            if card and card.get('not_found'):
                out['kind'] = 'notfound'
                out['near'] = card['near']
                out['reply'] = notfound_reply(card['near'])   # 모델 말 대신 코드가 쓴다
            elif card:
                out['kind'], out['card'] = 'card', card
            else:
                out['kind'] = 'ask'
                out['reply'] += '\n(아직 딱 맞는 자격증을 못 찾았어요 — 조금 더 얘기해볼까요?)'
        return out
