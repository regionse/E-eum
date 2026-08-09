# -*- coding: utf-8 -*-
"""「사실·제약 진술」이 「선호 슬롯」으로 기록되는지 재는 프로브 (2026-08-08 신설).

무엇을 재나
  발화 한 줄 → 슬롯 추출 결과. **채점하지 않는다. 기록만 한다.**

왜 채점을 안 하나
  「할머니를 5년 돌봤어요」의 정답이 무엇인지는 사람이 봐도 갈린다.
    · 설계 의도(_ASK_Q2 주석)로는 «무급 돌봄을 경력으로» 인정해야 한다 → 담는 게 맞다
    · 그런데 「돌보느라 못 해봤어요」는 좌절의 진술이지 선호가 아니다 → 담으면 안 된다
  둘의 경계는 문장 «형태»에 있고, 그 선을 코드가 먼저 그으면 그건 측정이 아니라 주장이다.
  ⇒ 무엇이 나오는지 찍고, 판단은 사람이 한다.

왜 이 프로브가 필요했나 (2026-08-08 실측)
  「할머니 돌보느라 아무것도 못 해봤어요」
    → 활동유형 = [돕기·돌봄]  **출처 user**
  「~하느라 못 했다」는 제약 진술인데 「~를 원한다」는 선호로, 그것도 사용자가 «말했다»고 기록됐다.
  verify_slots 는 통과시킨다 — 근거로 「할머니 돌보느라」를 대면 그 글자가 발화에 실제로 있어서다.
  **근거는 있는데 뜻이 뒤집혀 있다.** 이것이 우리 사용자군에게 가장 흔한 문장 형태다.

케이스 다섯 축
  A 명확한 선호   담아야 한다
  B 명확한 제약   담으면 안 된다
  C 애매(경험)    판단이 갈린다  ← 본 시험
  D 부정         담으면 안 된다
  E 혼합         한 문장에 둘 다  ← 본 시험

주의
  · 세션 DB 를 안 쓴다(step 에 프로필을 직접 넘긴다). 흔적이 남지 않는다.
  · LLM 을 부른다. 케이스당 1콜 + 착지하면 검색이 더 붙는다. 돌리기 전 콜 수를 찍는다.

쓰는 법
  python -m app.itda.scripts.checks.fact_pref_probe
  python -m app.itda.scripts.checks.fact_pref_probe --only C,E
"""
import asyncio
import io
import json
import sys
from pathlib import Path

#  ★ 2026-08-08 — LLM 을 쓴 실험은 **원시 기록을 통째로 남긴다.**
#    요약(정답 몇/몇)만 두면 「왜 그렇게 나왔나」를 되짚을 수 없다.
#    실제로 A/B 가 캐시 때문에 동일하게 나온 사고를 원시 기록으로 찾았다(실측기록 6-6).
OUT_PATH = Path(__file__).with_name('_fact_pref_probe_result.json')
RECORDS = []

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda.db import async_session              # noqa: E402
from app.itda.itda_core import ItdaEngine, ASK_ORDER   # noqa: E402

#  (축, 발화, 이 케이스가 무엇을 보려는지)
CASES = [
    # ── A 명확한 선호 — 담겨야 정상 ─────────────────────────────
    ('A', '사람 챙기는 게 좋아요', '선호 표현이 분명하다'),
    ('A', '빵 만드는 게 재밌어요', '관심분야+활동유형이 한 문장에'),
    ('A', '기계 만지는 거 좋아해요', '다루는대상까지 분명'),
    ('A', '어르신들이랑 얘기하는 게 편해요', '대상세부까지 선호로 분명'),

    # ── B 명확한 제약 — 담기면 오기록 ───────────────────────────
    ('B', '할머니 돌보느라 아무것도 못 해봤어요', '「~느라 못 했다」 · 실측된 오기록'),
    ('B', '돌봄 때문에 학원을 그만뒀어요', '「~때문에 그만뒀다」'),
    ('B', '동생 챙기느라 알바도 못 했어요', '돌봄 대상이 어르신이 아닌 경우'),
    ('B', '어머니 간병하느라 시간이 없어요', '제약(시간)과 사실(간병)이 함께'),

    # ── C 애매 — 경험 진술. 여기가 본 시험 ──────────────────────
    ('C', '할머니를 5년 돌봤어요', '경력인가 부담인가 — 태도가 없다'),
    ('C', '사람 돌보는 건 익숙해요', '익숙 = 잘한다? 좋아한다? 지쳤다?'),
    ('C', '돌보면서 약 챙기는 걸 배웠어요', '_ASK_Q2 가 «의도적으로» 끌어내는 답'),
    ('C', '어머니 병원 모시고 다녔어요', '순수 사실 진술 · 태도 없음'),

    # ── D 부정 — 담기면 안 된다 ─────────────────────────────────
    ('D', '돌봄 일은 이제 하기 싫어요', '명시적 거부'),
    ('D', '사람 상대하는 건 힘들어요', '_NEG_MARK 가 잡는 형태'),

    # ── E 혼합 — 한 문장에 긍정과 부정. 제일 어렵다 ─────────────
    ('E', '돌봄은 힘들었지만 보람은 있었어요', '부정+긍정이 같은 대상에'),
    ('E', '요양보호사 자격증은 있는데 그 일은 하기 싫어요', '보유 사실 + 거부'),
    ('E', '돌봄 말곤 해본 게 없어서요', '유일한 경험이자 유일한 제약'),

    # ── F 짧은·맥락 의존 답변 — «가드가 과잉 차단하는지»가 핵심 ──
    #    되묻기에 대한 답이라 한 문장만 보면 선호축이 안 잡힐 수 있다.
    #    그때 코드 보완마저 막으면 대화가 영영 안 나아간다.
    ('F', '어르신이요', '「어떤 분들이 편하세요?」의 답'),
    ('F', '사람이요', '「사람/기계/컴퓨터 중?」의 답'),
    ('F', '아이들이요', '대상만 말한 답'),
    ('F', '그쪽이 나을 것 같아요', '지시어만 있는 답'),
    ('F', '네', '최소 응답'),

    # ── G 선호인데 표현이 우회적 — LLM 이 놓치면 코드가 구해야 한다 ──
    ('G', '할머니 같은 분들이랑 있으면 마음이 편해요', '선호인데 「좋다」가 없다'),
    ('G', '애들이랑 있는 게 그나마 나아요', '「그나마」 — 소극적 선호'),
    ('G', '몸 쓰는 건 자신 있어요', '강점 표현이 선호를 함의'),
    ('G', '기계 쪽은 어릴 때부터 손댔어요', '경험 진술이 선호를 함의'),

    # ── H 제약과 선호가 «순서»로 붙음 — 앞말에 끌리나 뒷말에 끌리나 ──
    ('H', '돌봄은 힘든데 그래도 사람 만나는 건 좋아요', '제약 먼저 · 선호 나중'),
    ('H', '빵은 계속 좋아했는데 학원은 못 다녔어요', '선호 먼저 · 제약 나중'),
    ('H', '시간이 없긴 한데 그래도 뭔가 만들고 싶어요', '제약 먼저 · 희망 나중'),

    # ── I 부정형 선호 — 「A는 싫고 B는 좋다」 ────────────────────
    ('I', '사무직은 싫고 몸 쓰는 게 좋아요', '거부와 선호가 나란히'),
    ('I', '혼자 하는 것보다 같이 하는 게 나아요', '비교급 선호'),
    ('I', '사람 많은 데 말고 조용한 데서 일하고 싶어요', '「말고」 + 선호'),

    # ── J 양태·시제 — 한국어에서 선호/제약을 가르는 핵심 ────────
    #    같은 「돌보다」에 어미만 바꿔 넣는다. 여기가 제일 정밀한 시험이다.
    ('J', '할머니를 돌보고 있어요', '현재 진행 — 사실'),
    ('J', '할머니를 돌봤었어요', '과거 완료 — 사실'),
    ('J', '할머니를 돌봐야 해요', '의무 — 제약'),
    ('J', '할머니를 돌보고 싶어요', '희망 — 선호'),
    ('J', '할머니를 돌보는 게 좋아요', '선호 — 명시'),
    ('J', '할머니를 돌볼 수밖에 없었어요', '불가피 — 강한 제약'),
]

SLOTS = ('관심분야', '활동유형', '다루는대상', '세부관심', '강점성향', '제약', '대상세부')


async def main():
    only = None
    for i, a in enumerate(sys.argv):
        if a == '--only' and i + 1 < len(sys.argv):
            only = {x.strip().upper() for x in sys.argv[i + 1].split(',')}
    cases = [c for c in CASES if not only or c[0] in only]

    print(f'\n케이스 {len(cases)}개 · LLM 최소 {len(cases)}콜 '
          f'(착지하는 케이스는 검색이 더 붙는다)\n')

    eng = ItdaEngine()
    async with async_session() as db:
        for axis, msg, why in cases:
            profile = {}
            try:
                r = await eng.step(db, profile, msg)
            except Exception as e:                       # noqa: BLE001
                print(f'[{axis}] {msg}\n     🔴 실패 {type(e).__name__}: {str(e)[:90]}\n')
                continue
            p = r.get('profile') or {}
            got = {k: p[k] for k in SLOTS if p.get(k)}
            src = p.get('_slot_src') or {}
            #  ★ 제안 가드를 «적용하지 않고» 결과만 시뮬레이션한다.
            #    가드: LLM 이 이번 턴에 선호 3축을 하나도 안 담았으면 코드 보완을 건너뛴다.
            #    LLM 이 담은 축은 _slot_src 가 'user' 인 것(merge 가 그렇게 표시한다).
            llm_pref = [k for k in ASK_ORDER if src.get(k) == 'user']
            blocked = not llm_pref
            after = {k: v for k, v in got.items()
                     if not (blocked and (src.get(k) == 'code' or k == '대상세부'))}

            print(f'[{axis}] {msg}')
            print(f'     ({why})')
            print(f'     슬롯 {json.dumps(got, ensure_ascii=False) if got else "(없음)"}')
            if src:
                print(f'     출처 {json.dumps(src, ensure_ascii=False)}')
            if blocked and after != got:
                print(f'     가드후 {json.dumps(after, ensure_ascii=False) if after else "(없음)"}'
                      f'   ← 코드보완 차단됨')
            elif blocked:
                print('     가드후 (변화 없음 — 코드보완이 원래 없었다)')
            print(f'     종류 {r.get("kind")} · 착지가능 {r.get("can_land")}')
            print()

            reply = r.get('reply') or ''
            RECORDS.append({
                '축': axis, '발화': msg, '메모': why,
                '슬롯': got, '출처': src,
                '종류': p.get('_slot_kind') or {},
                '가드적용시': after, '가드발동': blocked,
                '응답종류': r.get('kind'), '착지가능': r.get('can_land'),
                '대답': reply,
                '질문문장': [s.strip() + '?' for s in reply.split('?')[:-1] if s.strip()],
            })

    print(f'누적 사용량: {eng.total_usage}')
    if RECORDS:
        OUT_PATH.write_text(json.dumps(
            {'케이스수': len(RECORDS), '사용량': eng.total_usage, '케이스': RECORDS},
            ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'▸ 전체 기록 저장: {OUT_PATH}')


asyncio.run(main())
