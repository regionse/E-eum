# -*- coding: utf-8 -*-
"""대화 단위 회귀 — 한 마디가 아니라 **대화 전체**를 판정한다 (2026-08-04 신규)

왜 만들었나
  기존 골든셋(golden_check/golden_judge)은 **한 마디 + 한 응답**을 본다.
  그것으로는 안 잡히는 실패가 있다. 2026-08-04 에 대화를 눈으로 읽다가 나온 것들:
    · 「근데 계속 그것만 하긴 좀」 이라고 거부했는데 **같은 카드를 세 번** 줬다
    · 「할머니 간병하면서 학교를 못 다녔어요」(첫 마디)에 공감 없이 카드부터 던졌다
    · 카드를 준 뒤 「네」 한 마디에 **다시 되묻기**로 돌아갔다
  셋 다 각 턴만 보면 멀쩡하다. **턴 사이의 관계**가 문제다.

  10분 읽어서 버그 3개를 찾았다. 그걸 사람이 매번 하는 대신 판정관에게 맡긴다.

설계 원칙 (골든셋 판정관에서 그대로 가져온다)
  · **「최선인가」가 아니라 「타당한가」를 묻는다.**
    Rao & Daumé(ACL 2018) — 「best」 평가자 간 일치 κ=0.15, 「valid」 는 0.58,
    best 를 valid 로 완화하면 0.87. 정답이 하나가 아닌 과제에서 「최선」은 사람도 합의 못 한다.
  · **축을 나눠서 묻는다.** 한 덩어리로 「좋았나」를 물으면 판정이 뭉개진다.
  · **판정 근거를 반드시 받는다.** 사람이 뒤집어볼 수 있어야 한다.

실행 (Backend/ 에서)
    python -m app.itda.scripts.convo_judge
    python -m app.itda.scripts.convo_judge --tag 거부      # 특정 묶음만
    python -m app.itda.scripts.convo_judge --no-judge     # 대화만 출력(판정 안 함, 비용 0)
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.itda.db import async_session                    # noqa: E402
from app.itda import itda_core as IC                     # noqa: E402


# ─────────────────────────────────────────────────────────────────────
#  대화 케이스 — 전부 **실제로 겪은 실패**나 사용자상에서 나온 것이다.
#    note 는 판정관에게도 전달된다(이 대화가 무엇을 시험하는지 알려준다).
# ─────────────────────────────────────────────────────────────────────
#  ★ 2026-08-04 — 시나리오 6개를 **통째로 갈아엎었다.**
#    예전 것은 「빵 만드는 게 좋아요」·「기계 만지는 게 재밌어요」 같은 말투였다.
#    전부 **내가 상상해서 쓴 것**이고, 다시 보니 **여유가 있는 사람의 말투**였다.
#    실제 당사자 발화를 찾아서 대조하니 결이 완전히 달랐다 —
#      「돈이 많이 급해서 새벽까지 근무를 하거든요 … 17시간 주 7일 근무」        (사례 11)
#      「제 몸이 망가진 건가 이제 감정을 못 느끼겠더라고요」                     (사례 11)
#      「고고학자의 월급이 낮다고 … 갑작스럽게 진로를 바꾸게 되었고요」           (사례 2)
#      「바쁘다 보니까 어떤 지원 사업이 있는지 찾아보기도 힘들거든요」            (사례 2)
#      「정확히 해당되는지 몰라서.. 혜택을 받을 수 있는 상황인 것 같은데 아닌 것 같기도」(사례 14)
#      「엄마 입원하거나 … 중간에 조퇴해 나간 적도 많고요」                      (사례 4)
#    출처: 월드비전 「돌봄 청소년 맞춤형 지원 체계 수립을 위한 연구」 이슈브리프(2024) 심층면접.
#          같은 보고서가 인용한 일본 조사 — 「가족 이외의 사람과 이야기한 적이 없다」 54%.
#    ⇒ 시간이 없고 · 돈이 급하고 · 이미 꿈을 한 번 접었고 · 감정이 무디고 ·
#      자기가 대상인지도 모른다. **면접 답변을 채팅 말투로만 옮겨** 아래를 만들었다.
#    ※ 지어낸 대화인 건 여전하다. 다만 이제 **출처가 있는 목소리**를 흉내 낸다.
CONVS = [
    dict(tag='시간', title='시간이 없는 사람',
         msgs=['일하느라 뭐 준비할 시간이 없어요', '새벽까지 일해서요',
               '그냥 지금 하는 일 계속해야 되나 싶어요'],
         note='시간 제약을 세 번 말했다. 강좌 수강·자격증 공부를 당연한 전제로 밀면 실패다. '
              '제약을 받아주고, 시간을 덜 쓰는 길이나 다른 도움(돌봄 지원·정책)으로 '
              '이어주는 게 맞는 자리다.'),

    dict(tag='돈', title='돈 때문에 급한 사람',
         msgs=['돈 때문에 빨리 취업해야 돼요', '자격증은 오래 걸리잖아요',
               '지원 같은 거 받을 수 있나요'],
         note='마지막에 **지원 제도를 직접 물었다.** 진로 카드만 주고 그 질문을 지나치면 실패다. '
              '또 「오래 걸린다」고 했는데 장기 과정을 밀면 실패다.'),

    dict(tag='무딤', title='감정이 무딘 사람',
         msgs=['딱히 재밌는 게 없어요', '그냥 아무 생각이 안 들어요', '모르겠어요', '음...'],
         note='「재밌는 걸 말해보라」는 질문이 통하지 않는 사람이다. 같은 결의 질문을 반복하면 실패다. '
              '단계적으로 물러나며 부담을 덜어줘야 하고, **4턴째에 처음 질문으로 돌아가면 실패다.**'),

    dict(tag='자격', title='자격이 되는지 모르는 사람',
         msgs=['제가 딸 수 있는 자격증이 있을까요', '고등학교만 나왔는데요',
               '전기기능사는 아무나 볼 수 있나요'],
         note='2턴은 「내가 대상이 되나」, 3턴은 특정 자격의 응시요건 질문이다. '
              '★ 우리 DB에는 **응시제한 유무(entry_free)와 안내문(entry_note)까지만** 있다. '
              '「고졸이면 응시 가능합니다」처럼 학력·경력 요건을 지어내면 **실패**다(그 데이터가 없다).'),

    dict(tag='착지요청', title='그만 묻고 추천해달라고 할 때',
         msgs=['빨리 돈 벌 수 있는 일이면 좋겠어요', '사람 상대하는 건 좀 힘들고요',
               '그냥 추천해줘'],
         note='마지막이 **명시적 착지 요청**이다. 여기서 또 되물으면 실패다. '
              '그리고 2턴에서 「사람 상대는 힘들다」고 했으니 대인 업무를 주면 실패다.'),

    dict(tag='학업', title='학업이 끊긴 사람',
         msgs=['고등학교 때 학교를 많이 못 갔어요', '할머니 때문에요',
               '뭐부터 해야 될지 모르겠어요'],
         note='첫 마디가 무겁고 2턴에서 돌봄 사정을 처음 털어놨다. '
              '반응 없이 슬롯 질문이나 카드로 넘어가면 실패다. '
              '3턴의 「뭐부터」에는 **단계**로 답해야 한다 — 한 번에 결론을 던지면 실패다.'),
]

JUDGE_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        '놓친정보': {'type': 'STRING', 'enum': ['없음', '있음']},
        '놓친정보_근거': {'type': 'STRING'},
        '반복': {'type': 'STRING', 'enum': ['없음', '있음']},
        '반복_근거': {'type': 'STRING'},
        '거부무시': {'type': 'STRING', 'enum': ['없음', '있음', '해당없음']},
        '거부무시_근거': {'type': 'STRING'},
        '최종타당': {'type': 'STRING', 'enum': ['타당', '부당', '판단불가']},
        '최종타당_근거': {'type': 'STRING'},
        '진전': {'type': 'STRING', 'enum': ['나아감', '제자리']},
        '진전_근거': {'type': 'STRING'},
        '한줄평': {'type': 'STRING'},
    },
    'required': ['놓친정보', '반복', '거부무시', '최종타당', '진전', '한줄평'],
}

PROMPT = """너는 진로상담 챗봇의 **대화 품질 심사관**이다.
아래는 사용자와 챗봇이 나눈 대화 전체다. 이 대화가 **타당하게 굴러갔는지** 판정해라.

★ 「최선이었나」를 묻는 게 아니다. 「타당했나」를 묻는 것이다.
  이 과제는 정답이 하나가 아니다 — 같은 사람에게 여러 직업이 다 맞을 수 있다.
  더 나은 답이 있었을 것 같다는 이유로 부당 판정을 하지 마라.
  **명백히 앞뒤가 안 맞거나, 사용자 말을 무시했거나, 제자리를 돌 때만** 문제로 본다.

[이 대화가 시험하는 것]
{note}

[대화]
{transcript}

[판정 축 — 각각 따로 본다]
1. 놓친정보 : 사용자가 말했는데 챗봇이 전혀 반영하지 않은 정보가 있나
2. 반복     : 같은 질문이나 같은 추천을 되풀이했나
3. 거부무시  : 사용자가 물리거나 다른 걸 원한다고 했는데 무시했나 (그런 발화가 없으면 '해당없음')
4. 최종타당  : 마지막에 나온 추천이나 응답이 **대화 전체**에 비춰 말이 되나
5. 진전     : 대화가 앞으로 나아갔나, 아니면 제자리였나

근거는 **대화에서 실제 문장을 인용해서** 써라. 짐작으로 쓰지 마라."""


def fmt(rec):
    out = []
    for r in rec:
        out.append(f"사용자: {r['msg']}")
        out.append(f"챗봇: {r['reply']}")
        meta = r['kind']
        if r.get('card'):
            meta += f" · 추천직업 「{r['card']}」"
        if r.get('options'):
            meta += f" · 선택지 [{' / '.join(r['options'])}]"
        out.append(f"   (시스템 상태: {meta} · 파악한 정보: {r['slots']})")
    return '\n'.join(out)


async def run_convo(db, c):
    eng = IC.ItdaEngine()
    eng.QUERY_CACHE = False
    prof, rec = {}, []
    for msg in c['msgs']:
        r = await eng.step(db, prof, msg)
        prof = r.get('profile') or prof
        h = list(prof.get('_history') or [])
        h.append({'r': 'u', 't': msg})
        if r.get('reply'):
            h.append({'r': 'b', 't': str(r['reply'])[:300]})
        prof['_history'] = h[-24:]
        card = r.get('card') or {}
        j = card.get('job') if isinstance(card, dict) else None
        rec.append({
            'msg': msg, 'reply': r.get('reply') or '',
            'kind': r.get('kind') or '?',
            'card': (j.get('name') if isinstance(j, dict) else None),
            'options': list(r.get('options') or []),
            'slots': {k: v for k, v in prof.items() if v and not k.startswith('_')},
        })
    return rec


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag')
    ap.add_argument('--no-judge', action='store_true')
    a = ap.parse_args()

    cases = [c for c in CONVS if not a.tag or c['tag'] == a.tag]
    bad = []
    async with async_session() as db:
        for c in cases:
            print(f'\n{"=" * 78}\n■ [{c["tag"]}] {c["title"]}\n{"=" * 78}')
            rec = await run_convo(db, c)
            for r in rec:
                tail = (f'  → 「{r["card"]}」' if r['card']
                        else (f'  → [{" / ".join(r["options"])}]' if r['options'] else ''))
                print(f'\n  🧑 {r["msg"]}')
                print(f'  🤖 {r["reply"]}')
                print(f'     [{r["kind"]}]{tail}')
            if a.no_judge:
                continue

            eng = IC.ItdaEngine()
            v = await eng.gemini(PROMPT.format(note=c['note'], transcript=fmt(rec)),
                                 JUDGE_SCHEMA, 0.1) or {}
            print('\n  ── 판정 ──')
            problems = []
            for ax, bad_val in (('놓친정보', '있음'), ('반복', '있음'), ('거부무시', '있음'),
                                ('최종타당', '부당'), ('진전', '제자리')):
                val = v.get(ax, '?')
                mark = '✗' if val == bad_val else '○'
                if val == bad_val:
                    problems.append(ax)
                print(f'     {mark} {ax:6s} {val:6s} {v.get(ax + "_근거", "")[:88]}')
            print(f'     한줄평: {v.get("한줄평", "")}')
            if problems:
                bad.append((c['title'], problems))

    if not a.no_judge:
        print(f'\n{"=" * 78}')
        print(f'■ 문제가 잡힌 대화 {len(bad)}/{len(cases)}')
        for t, p in bad:
            print(f'   · {t:24s} {", ".join(p)}')


if __name__ == '__main__':
    asyncio.run(main())
