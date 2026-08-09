# -*- coding: utf-8 -*-
"""「종류」(원함/해봤음/못함)를 **모델이 실제로 가를 수 있는가** — 능력·과부하 시험 (2026-08-08).

왜 이 시험을 먼저 하나
  fact_pref_probe 실측: 같은 「할머니를 돌보다」에 어미만 바꾼 6종이 **전부 동일하게**
  활동유형=돕기·돌봄 으로 기록됐다. 「돌봐야 해요」(의무)와 「돌보고 싶어요」(희망)가
  구분되지 않는다. 담을 «자리»가 없어서다.
  ⇒ 자리(종류 필드)를 만들자는 제안이 나왔는데, **모델이 못 가르면 칸만 늘고 쓰레기가 들어온다.**

두 조건으로 잰다 — 이게 이 파일의 핵심이다
  ① 가벼움  단일 활동 · {값·종류·근거} 3필드만. **능력 자체**를 본다.
  ② 실제부하 PROFILE_SCHEMA 를 그대로 쓰되 각 슬롯에 종류를 얹는다(6슬롯 × 3필드).
            프롬프트·이력·게이트까지 실제 경로 그대로 돈다. **과부하**를 본다.

  ①은 되는데 ②가 안 되면 → 능력은 있으나 부하가 문제. 슬롯을 줄이거나 호출을 나눠야 한다.
  ①부터 안 되면 → 이 설계 자체가 이 모델로는 무리다. 큰 모델을 쓰거나 접어야 한다.

생산 코드는 안 건드린다
  ②는 PROFILE_SCHEMA 를 **이 프로세스 안에서만** 갈아끼운다(monkeypatch). 파일은 그대로다.

정의를 반드시 붙인다 — tag_job_attr 에서 배운 것.
  「이름만 준 1차: 빵 → 자연·생물(오답). 정의를 준 2차: 빵 → 창작물(정답)」

쓰는 법
  python -m app.itda.scripts.checks.kind_capability_test            # ① 가벼움만
  python -m app.itda.scripts.checks.kind_capability_test --full     # ② 실제부하도
  python -m app.itda.scripts.checks.kind_capability_test --big      # 큰 모델과 비교
"""
import asyncio
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda import itda_core as C                # noqa: E402
from app.itda.db import async_session              # noqa: E402

BIG = 'gemini-3.6-flash'
KINDS = ['원함', '해봤음', '못함']

#  종류의 정의 — ①②가 같은 글을 쓴다. 스키마 description 에 그대로 실린다.
KIND_DESC = (
    '이 값에 대한 화자의 처지. '
    '원함=하고 싶다·좋다고 말했다(앞으로 하려는 의지가 있다). '
    '해봤음=해왔거나 하고 있다는 사실만 말했다(좋다고도 싫다고도 안 했다). '
    '못함=그것에 묶여 있거나 그것 때문에 다른 걸 못 했다(의무·불가피·좌절). '
    '어미를 보라 — 「~하고 싶어요」와 「~해야 해요」는 정반대다. '
    '애매하면 해봤음으로 둔다. 원함으로 짐작하지 마라.'
)

# ── ① 가벼움 ────────────────────────────────────────────────────
LIGHT_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        '값': {'type': 'STRING', 'description': '활동을 가리키는 한 낱말(돌봄·제빵·용접·컴퓨터 등)'},
        '종류': {'type': 'STRING', 'enum': KINDS, 'description': KIND_DESC},
        '근거': {'type': 'STRING', 'description': '그렇게 판단한 근거를 발화에서 그대로 인용'},
    },
    'required': ['값', '종류', '근거'],
}

LIGHT_PROMPT = """사용자가 어떤 활동을 말했다. 값·종류·근거 셋을 채운다.

[사용자 발화]
{msg}"""

#  프롬프트 «본문»에 붙일 종류 설명 — SYSTEM 뒤에 이어 붙인다.
KIND_BLOCK = """

[종류] — 슬롯의 값마다 «화자의 처지»를 함께 표시한다. 이게 없으면 사실과 소망이 섞인다.
  원함    하고 싶다·좋다고 말했다. 앞으로 하려는 의지가 있다.
          「빵 만들고 싶어요」 「사람 만나는 게 좋아요」 「배워보고 싶어요」
  해봤음  해왔거나 하고 있다는 «사실»만 말했다. 좋다고도 싫다고도 안 했다.
          「5년 돌봤어요」 「컴퓨터 만지고 있어요」 「익숙해요」
  못함    그것에 묶여 있거나, 그것 «때문에» 다른 걸 못 했다. 원해서 하는 게 아니다.
          「돌봐야 해요」 「그럴 수밖에 없었어요」 「그거 하느라 아무것도 못 해봤어요」
          「그것밖에 할 줄 아는 게 없어요」
★ 어미를 보라 — 「~하고 싶어요」와 「~해야 해요」는 **정반대**다. 값이 같아도 종류가 다르다.
★ 애매하면 «해봤음». 원함으로 짐작하지 마라.
★ 우리 사용자는 돌봄에 묶여 있는 경우가 많다. 「돌본다」는 사실을 「돌봄을 원한다」로 읽지 마라.
"""

ONLY3 = '--all-slots' not in sys.argv          # 기본: 선호 3축에만
PROMPT_HINT = '--no-hint' not in sys.argv      # 기본: 프롬프트 본문에도 설명

#  케이스마다 «전부» 남긴다 — 스키마 원시응답·verify 뒤 슬롯·봇 대답·질문문장·사용량.
#  요약(정답 몇/몇)만 보면 나중에 「왜 그렇게 나왔나」를 되짚을 수 없다.
RECORDS = []
OUT_PATH = Path(__file__).with_name('_kind_capability_result.json')


#  (기대, 발화, 왜 어려운가)   기대=None 이면 «사람도 갈리는» 케이스 → 채점 제외
#
#  ★ 2026-08-08 — 20 → 100 케이스. n=14(채점분)로는 「가능하다」를 말할 수 없었다.
#    분포를 일부러 이렇게 짰다:
#      원함 25 — **선호를 죽이는 실패(원함→못함)가 진짜 0인지**가 제일 중요하다.
#                그게 나면 사용자가 영영 착지를 못 한다.
#      해봤음 25 · 못함 25 — 균형
#      갈림 21 — 채점 제외. «안전한 쪽(해봤음)»으로 기우는지만 본다.
#      돌봄 영역과 다른 영역을 섞었다 — 돌봄에만 잘 듣는 건지 확인해야 한다.
CASES = [
    # ══ 원함 25 ═══════════════════════════════════════════════
    ('원함', '빵 만드는 게 재밌어요', ''),
    ('원함', '용접을 배우고 싶어요', ''),
    ('원함', '사람 만나는 게 좋아요', ''),
    ('원함', '컴퓨터로 뭐 만드는 거 해보고 싶어요', ''),
    ('원함', '요리 쪽으로 가고 싶어요', ''),
    ('원함', '아이들 가르치는 일 하고 싶어요', ''),
    ('원함', '손으로 만드는 게 제일 좋아요', ''),
    ('원함', '미용 배워보고 싶어요', ''),
    ('원함', '운전하는 일 하면 좋겠어요', ''),
    ('원함', '카페에서 일해보고 싶어요', ''),
    ('원함', '꽃 다루는 일이 좋아요', ''),
    ('원함', '그림 그리는 게 제일 즐거워요', ''),
    ('원함', '동물 돌보는 일 해보고 싶어요', ''),
    ('원함', '사진 찍는 거 좋아해요', ''),
    ('원함', '목공 쪽에 관심이 가요', ''),
    ('원함', '자동차 정비 배우고 싶어요', ''),
    ('원함', '옷 만드는 거 해보고 싶어요', ''),
    ('원함', '회계 쪽으로 가고 싶어요', ''),
    ('원함', '간호 쪽에 마음이 있어요', ''),
    ('원함', '제과제빵 자격증 따고 싶어요', ''),
    ('원함', '어르신들이랑 얘기하는 게 편해요', '소극적 선호'),
    ('원함', '조용히 혼자 하는 일이 좋아요', ''),
    ('원함', '몸 쓰는 일이 재밌어요', ''),
    ('원함', '기계 만지는 거 좋아해요', ''),
    ('원함', '상담하는 일 해보고 싶어요', ''),

    # ══ 해봤음 25 ═════════════════════════════════════════════
    ('해봤음', '컴퓨터를 만지고 있어요', ''),
    ('해봤음', '할머니를 돌봤었어요', ''),
    ('해봤음', '편의점에서 일한 적 있어요', ''),
    ('해봤음', '카페 알바 해봤어요', ''),
    ('해봤음', '집에서 밥은 제가 해요', ''),
    ('해봤음', '동생 학교 데려다줬어요', ''),
    ('해봤음', '청소는 계속 제가 했어요', ''),
    ('해봤음', '엄마 약 챙기는 건 제 몫이었어요', '「제 몫」 — 못함에 가까울 수도'),
    ('해봤음', '공장에서 몇 달 일했어요', ''),
    ('해봤음', '배달 일 해본 적 있어요', ''),
    ('해봤음', '컴퓨터 조립은 해봤어요', ''),
    ('해봤음', '어릴 때 농사일 도왔어요', ''),
    ('해봤음', '서류 정리하는 일 했었어요', ''),
    ('해봤음', '손님 응대는 해봤어요', ''),
    ('해봤음', '엑셀은 좀 다뤄요', ''),
    ('해봤음', '할머니 병원 모시고 다녔어요', ''),
    ('해봤음', '요양보호사 자격증은 있어요', '보유 사실'),
    ('해봤음', '미용실에서 보조 했었어요', ''),
    ('해봤음', '용접은 학교에서 배웠어요', ''),
    ('해봤음', '사람 돌보는 건 익숙해요', ''),
    ('해봤음', '애들 봐준 적 있어요', ''),
    ('해봤음', '짐 나르는 일 했어요', ''),
    ('해봤음', '전단지 돌려봤어요', ''),
    ('해봤음', '빵집에서 일해봤어요', ''),
    ('해봤음', '텃밭은 계속 가꿔요', ''),

    # ══ 못함 25 ═══════════════════════════════════════════════
    ('못함', '할머니를 돌봐야 해요', '의무'),
    ('못함', '할머니를 돌볼 수밖에 없었어요', '불가피'),
    ('못함', '할머니 돌보느라 아무것도 못 해봤어요', '좌절 · 이 조사의 출발점'),
    ('못함', '돌봄 때문에 학원을 그만뒀어요', ''),
    ('못함', '동생 챙기느라 알바도 못 했어요', ''),
    ('못함', '어머니 간병하느라 시간이 없어요', ''),
    ('못함', '용접을 배워야 해요', '돌봄 아닌 영역의 의무'),
    ('못함', '빵을 만들 수밖에 없었어요', '돌봄 아닌 영역의 불가피'),
    ('못함', '집안일은 제가 다 해야 해요', ''),
    ('못함', '아버지 때문에 취업을 포기했어요', ''),
    ('못함', '학교는 중간에 그만둬야 했어요', ''),
    ('못함', '밤에 일하느라 공부를 못 했어요', ''),
    ('못함', '돈 벌어야 해서 진학을 못 했어요', ''),
    ('못함', '병원 다니느라 아무 데도 못 갔어요', ''),
    ('못함', '어쩔 수 없이 계속 하고 있어요', ''),
    ('못함', '그만두고 싶어도 못 그만둬요', ''),
    ('못함', '제가 안 하면 아무도 안 해요', '책임 · 우회 표현'),
    ('못함', '다른 걸 할 여유가 없었어요', ''),
    ('못함', '시간이 없어서 다 접었어요', ''),
    ('못함', '자격증 준비하다가 접었어요', ''),
    ('못함', '하기 싫어도 해야 하는 상황이에요', ''),
    ('못함', '그거 하느라 다른 건 손도 못 댔어요', ''),
    ('못함', '등록해놓고 못 나갔어요', ''),
    ('못함', '제가 할 줄 아는 게 그거밖에 없어요', '자조'),
    ('못함', '돌봄 말곤 해본 게 없어서요', ''),

    # ══ 복합 — 채점하되 어려움 4 ══════════════════════════════
    ('원함', '사무직은 싫고 몸 쓰는 게 좋아요', '거부+선호'),
    ('원함', '빵은 계속 좋아했는데 학원은 못 다녔어요', '선호+제약'),
    ('원함', '시간이 없긴 한데 그래도 뭔가 만들고 싶어요', '제약+희망'),
    ('원함', '힘들어도 이건 계속 하고 싶어요', '부정어+선호'),

    # ══ 갈림 21 — 채점 제외. «해봤음»으로 기우는지만 본다 ══════
    (None, '돌보는 게 싫지는 않아요', '이중부정'),
    (None, '돌봄이야 뭐, 제가 전문이죠', '자조 또는 반어'),
    (None, '돈만 되면 돌봄도 할 수 있죠', '조건부'),
    (None, '그냥 하다 보니까 계속 하게 됐어요', '태도 없음'),
    (None, '안 좋아하는 건 아닌데 계속하고 싶진 않아요', '복합 부정'),
    (None, '뭐 딱히 좋아서 한 건 아닌데 그래도 하다 보니 나름 보람은 있더라고요', '장문 부정+긍정'),
    (None, '돌봄이요? 뭐 그럭저럭이요', '얼버무림'),
    (None, '그럭저럭 할 만은 해요', ''),
    (None, '나쁘진 않았어요', ''),
    (None, '남들 다 하는 거니까요', ''),
    (None, '시켜주면 하죠 뭐', ''),
    (None, '잘하는진 모르겠는데 하긴 했어요', ''),
    (None, '좋다기보단 익숙한 거죠', '핵심 구분 — 익숙 ≠ 좋음'),
    (None, '딱히 다른 걸 생각해본 적이 없어요', ''),
    (None, '뭐든 상관없어요', ''),
    (None, '돌봄은 힘든데 그래도 사람 만나는 건 좋아요', '같은 대상 부정+다른 대상 긍정'),
    (None, '요양보호사 자격증은 있는데 그 일은 하기 싫어요', '보유+거부'),
    (None, '어릴 때부터 할머니가 아프셔서 제가 계속 챙겼는데 그러다 보니 이런 일이 '
           '익숙해지긴 했지만 솔직히 이걸 평생 할 자신은 없어요', '장문 익숙+거부'),
    (None, '네', '최소 응답 — 슬롯이 안 나와야 정상'),
    (None, '그쪽이요', '지시어만'),
    (None, '몰라요', '못정함'),
]

_OLD_CASES = [
    # ── 양태 6종 — fact_pref_probe 축 J 그대로 ─────────────────
    ('해봤음', '할머니를 돌보고 있어요', '현재 진행'),
    ('해봤음', '할머니를 돌봤었어요', '과거'),
    ('못함',   '할머니를 돌봐야 해요', '의무'),
    ('원함',   '할머니를 돌보고 싶어요', '희망'),
    ('원함',   '할머니를 돌보는 게 좋아요', '명시적 선호'),
    ('못함',   '할머니를 돌볼 수밖에 없었어요', '불가피'),
    ('못함',   '할머니 돌보느라 아무것도 못 해봤어요', '좌절'),

    # ── 꼬아서 말하기 ───────────────────────────────────────────
    (None,    '돌보는 게 싫지는 않아요', '이중부정'),
    (None,    '돌봄이야 뭐, 제가 전문이죠', '자조 또는 반어'),
    (None,    '돈만 되면 돌봄도 할 수 있죠', '조건부'),
    ('못함',   '제가 할 줄 아는 게 그거밖에 없죠 뭐', '자조 · 유일한 선택지'),
    (None,    '그냥 하다 보니까 계속 하게 됐어요', '회피 · 태도 없음'),
    (None,    '안 좋아하는 건 아닌데 계속하고 싶진 않아요', '복합 부정'),
    ('해봤음', '돌봄이요? 뭐 그럭저럭이요', '얼버무림'),

    # ── 돌봄이 아닌 영역 — 돌봄 편향인지 확인 ────────────────────
    ('못함',   '용접을 배워야 해요', '의무 · 다른 영역'),
    ('해봤음', '컴퓨터를 만지고 있어요', '진행 · 다른 영역'),
    ('못함',   '빵을 만들 수밖에 없었어요', '불가피 · 다른 영역'),
    ('원함',   '용접을 배우고 싶어요', '희망 · 다른 영역'),

    # ── 긴 문장에 여러 태도가 섞임 ──────────────────────────────
    ('못함', '어릴 때부터 할머니가 아프셔서 제가 계속 챙겼는데 그러다 보니 이런 일이 '
             '익숙해지긴 했지만 솔직히 이걸 평생 할 자신은 없어요', '장문 · 익숙+거부'),
    (None,  '뭐 딱히 좋아서 한 건 아닌데 그래도 하다 보니 나름 보람은 있더라고요', '장문 · 부정+긍정'),
]


def _short(s, n=40):
    return s if len(s) <= n else s[:n - 1] + '…'


async def light(model):
    """① 능력 자체 — 단일 활동 · 3필드."""
    eng = C.ItdaEngine(model=model)
    ok = 0
    scored = len([c for c in CASES if c[0] is not None])
    print(f'\n══ ① 가벼움 (단일 활동 · 값·종류·근거) · {model} ══')
    print(f"{'':2}{'발화':<44}{'기대':<9}{'종류':<9}{'값':<10}근거")
    print('─' * 118)
    for want, msg, why in CASES:
        try:
            r = await eng.gemini(LIGHT_PROMPT.format(msg=msg), LIGHT_SCHEMA, 0.1)
        except Exception as e:                            # noqa: BLE001
            print(f'🔴 {_short(msg,42):<44}{(want or "-"):<9}실패 {type(e).__name__}')
            continue
        got, val, ev = ((r or {}).get('종류', '?'), (r or {}).get('값', ''),
                        (r or {}).get('근거', ''))
        if want is None:
            mark = ' ·'
        else:
            hit = got == want
            ok += hit
            mark = '✅' if hit else '❌'
        print(f'{mark} {_short(msg,42):<44}{(want or "(갈림)"):<9}{got:<9}{_short(val,8):<10}{_short(ev,34)}')
    print(f'\n   정답 {ok}/{scored}   ·   사용량 {eng.total_usage}')
    return ok, scored


async def full(model):
    """② 실제 부하 — PROFILE_SCHEMA 6슬롯에 종류를 얹고 step() 전체 경로로."""
    #  이 프로세스 안에서만 스키마·프롬프트를 갈아끼운다. 파일은 그대로다.
    orig = json.loads(json.dumps(C.PROFILE_SCHEMA))
    patched = json.loads(json.dumps(C.PROFILE_SCHEMA))
    n_slot = 0
    #  ★ (가) 종류를 «선호 3축»에만 얹는다 — 부하를 절반으로.
    #    세부관심·강점성향은 「원함/못함」이 성립하지 않고, 제약은 이미 제약이다.
    for _k in (C.ASK_ORDER if ONLY3 else list(patched['properties'])):
        v = patched['properties'].get(_k)
        if not v:
            continue
        items = v.get('items') or v          # ARRAY 면 items, 스칼라면 자기 자신
        props = items.get('properties')
        if props and '값' in props:
            props['종류'] = {'type': 'STRING', 'enum': KINDS, 'description': KIND_DESC}
            req = items.get('required') or []
            if '종류' not in req:
                items['required'] = req + ['종류']
            n_slot += 1
    C.PROFILE_SCHEMA = patched

    #  ★ (나) 프롬프트 «본문»에도 종류를 설명한다.
    #    지금까지는 스키마 description 에만 있었다. 4,500토큰짜리 지시를 읽는 모델이
    #    스키마 구석의 한 줄을 챙기길 기대한 셈이다. job_attr 교훈: 정의를 주면 달라진다.
    orig_system = C.SYSTEM
    if PROMPT_HINT:
        C.SYSTEM = C.SYSTEM + KIND_BLOCK

    #  ★ verify_slots 가 종류를 모르고 버리므로, 그 «앞»에서 원시 응답을 가로챈다.
    #    step() 이 모듈 전역으로 부르기 때문에 여기 갈아끼우면 걸린다.
    orig_verify = C.verify_slots
    seen = {}

    def spy(raw, user_msg):
        seen['raw'] = raw
        return orig_verify(raw, user_msg)

    C.verify_slots = spy

    print(f'\n══ ② 실제 부하 · {model} ══')
    print(f'   종류를 얹은 슬롯 {n_slot}개'
          f'{" (선호 3축만)" if ONLY3 else " (전체)"}'
          f'   ·   프롬프트 본문 설명 {"있음" if PROMPT_HINT else "없음"}')
    eng = C.ItdaEngine(model=model)
    ok = miss = broke = 0
    scored = len([c for c in CASES if c[0] is not None])
    try:
        async with async_session() as db:
            print(f"{'':2}{'발화':<42}{'기대':<8}{'활동유형의 종류':<16}원시 슬롯")
            print('─' * 118)
            for want, msg, why in CASES:
                seen.clear()
                _u0 = dict(eng.total_usage)
                try:
                    res = await eng.step(db, {}, msg)
                except Exception as e:                    # noqa: BLE001
                    broke += 1
                    RECORDS.append({'발화': msg, '기대': want, '메모': why,
                                    '실패': f'{type(e).__name__}: {str(e)[:200]}'})
                    print(f'🔴 {_short(msg,40):<42}실패 {type(e).__name__}: {str(e)[:46]}')
                    continue
                raw = seen.get('raw') or {}
                #  종류가 «어느 슬롯에든» 실려 왔는지 — 없으면 모델이 필드를 흘린 것이다.
                kinds = []
                for k, v in raw.items():
                    for it in (v if isinstance(v, list) else [v]):
                        if isinstance(it, dict) and it.get('종류'):
                            kinds.append(f"{k}={it['값']}:{it['종류']}")
                #  ★ 채점 — 예전엔 «활동유형»만 봤다. 그래서 「용접을 배워야 해요」가
                #    관심분야=용접:못함 으로 «맞았는데» 오답 처리됐다(2026-08-08 실측).
                #    ⇒ ASK_ORDER 우선순위로 대표 종류를 고른다.
                by_slot = {}
                for x in kinds:
                    slot, kind = x.split('=', 1)[0], x.rsplit(':', 1)[1]
                    by_slot.setdefault(slot, kind)
                act = next((by_slot[s] for s in C.ASK_ORDER if s in by_slot),
                           next(iter(by_slot.values()), ''))
                if not kinds:
                    miss += 1
                if want is not None and act:
                    ok += (act == want)
                mark = ('❌' if want and act and act != want
                        else '✅' if want and act == want
                        else '⚠' if not kinds else ' ·')

                #  ★ 전부 남긴다 — 요약만 보면 나중에 못 되짚는다.
                #    스키마 원시응답 · verify 뒤 슬롯 · 봇 대답 · 그중 질문문장까지.
                p = res.get('profile') or {}
                reply = res.get('reply') or ''
                RECORDS.append({
                    '발화': msg,
                    '기대': want,
                    '메모': why,
                    '판정': {'✅': '맞음', '❌': '틀림', '⚠': '종류없음'}.get(mark.strip(), '갈림'),
                    '대표종류': act or None,
                    '슬롯별종류': by_slot,
                    '스키마_원시응답': raw,
                    'verify뒤_슬롯': {k: p[k] for k in
                                     ('관심분야', '활동유형', '다루는대상',
                                      '세부관심', '강점성향', '제약', '대상세부')
                                     if p.get(k)},
                    '슬롯출처': p.get('_slot_src') or {},
                    '응답종류': res.get('kind'),
                    '착지가능': res.get('can_land'),
                    '대답': reply,
                    '질문문장': [s.strip() + '?' for s in reply.split('?')[:-1] if s.strip()],
                    '사용량': {k: eng.total_usage.get(k, 0) - _u0.get(k, 0)
                               for k in ('in', 'out', 'cached', 'calls')},
                })
                print(f'{mark} {_short(msg,40):<42}{(want or "(갈림)"):<8}'
                      f'{(act or "(없음)"):<16}{_short(", ".join(kinds), 52)}')
            print(f'\n   활동유형 종류 정답 {ok}/{scored}   ·   종류를 아예 못 낸 턴 {miss}건'
                  f'   ·   호출 실패 {broke}건')
            print(f'   사용량 {eng.total_usage}')
    finally:
        C.PROFILE_SCHEMA = orig               # 반드시 되돌린다
        C.verify_slots = orig_verify
        C.SYSTEM = orig_system
        if RECORDS:
            OUT_PATH.write_text(json.dumps(
                {'모델': model,
                 '조건': {'종류를_얹은_슬롯': (C.ASK_ORDER if ONLY3 else '전체'),
                          '프롬프트_본문_설명': PROMPT_HINT},
                 '요약': {'채점대상': scored, '맞음': ok,
                          '종류없음': miss, '호출실패': broke},
                 '케이스': RECORDS},
                ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'   ▸ 전체 기록 저장: {OUT_PATH}')


async def main():
    models = [C.MODEL] + ([BIG] if '--big' in sys.argv else [])
    skip_light = '--skip-light' in sys.argv
    per = (0 if skip_light else 1) + (1 if '--full' in sys.argv else 0)
    print(f'\n케이스 {len(CASES)}개 · 모델 {len(models)}개 → LLM 약 {len(CASES)*len(models)*per}콜'
          f'  (착지하는 케이스는 검색이 더 붙는다)')
    for mdl in models:
        if not skip_light:
            await light(mdl)
        if '--full' in sys.argv:
            await full(mdl)


asyncio.run(main())
