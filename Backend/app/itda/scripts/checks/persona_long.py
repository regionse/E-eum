# -*- coding: utf-8 -*-
"""동적 페르소나 «장기» 대화 시험 — 최대 200턴 (2026-08-09)

무엇을 하나
  대본을 미리 쓰지 않는다. **LLM 이 사용자를 연기**하고, 봇의 실제 응답에 반응한다.
  카드가 나온 뒤에도 페르소나가 스스로 「__끝__」이라 할 때까지 둔다.

왜 controllers.handle_message 가 아니라 eng.step 인가
  세션 DB·응답 조립을 빼고 «엔진만» 재기 위해서다. 대신 controllers 가 profile 에
  하는 일(_last_ask(s) · _history · 요약 접기 · 분야 재판단)은 **여기서 직접** 한다.
  안 하면 웹과 조건이 달라진다:
    · HISTORY_MODE='full' 이 _history/_facts/_summary 를 프롬프트에 넣는다
    · _last_asks 는 drop_echo 와 「이미 한 질문」 안내에 쓰인다
    · _think_stale 을 안 받아 주면 관심대분류가 영영 안 갱신된다
  ⚠ 다른 점 하나 — 웹은 요약·분야갱신을 **백그라운드**로 돌린다. 여기선 **동기**로 돈다.
    (결과는 같고 타이밍만 다르다. 턴 지연 측정용이 아니므로 이 편이 재현성이 높다)

봇에게 인생 배경은 **절대** 안 넘어간다. eng.step 에는 페르소나가 «친 말»만 들어간다.

쓰는 법 (Backend/ 에서)
  PYTHONIOENCODING=utf-8 python app/itda/scripts/checks/persona_long.py --who 1 --max 200
  PYTHONIOENCODING=utf-8 python app/itda/scripts/checks/persona_long.py --who 2 --max 200

남기는 것
  checks/_persona_long_<who>.json   턴마다 원문·kind·카드·칩·슬롯·사용량 전부
"""
import argparse
import asyncio
import io
import json
import os
import sys
import time
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from app.itda import itda_core as C                       # noqa: E402
from app.itda.itda_core import ItdaEngine                 # noqa: E402
from app.itda.db import async_session                     # noqa: E402

SIM_SCHEMA = {'type': 'OBJECT',
              'properties': {'말': {'type': 'STRING'}},
              'required': ['말']}

#  ── 페르소나 정의 ────────────────────────────────────────────────
#  ⚠ 이 글은 «시뮬레이터»에게만 간다. 봇은 첫 마디부터 사용자가 친 말만 본다.
PERSONAS = {
    '1': {
        'name': '서다인 · 33 · 여',
        'life': (
            '너는 서다인. 33세 여자.\n'
            '어머니가 조현병이다. 20대 내내 어머니를 돌봤다.\n'
            '스물다섯에 회사를 그만뒀다 — 어머니가 병원에서 나간 날 회사 전화를 못 받아서였다.\n'
            '그 뒤로는 단기 알바만 했고, 이력서에 8년 공백이 있다.\n'
            '작년 겨울 어머니가 요양병원에 들어갔다. 처음으로 혼자가 됐는데 뭘 해야 할지 모르겠다.\n'
            '요즘 아침에 일어나는 게 힘들다.'),
        'hide': ('· 회사를 그만둔 «이유»(어머니 때문에 전화를 못 받았다는 것)\n'
                 '· 아침에 못 일어난다는 것\n'
                 '이 둘은 봇이 뭘 물어도 «말하지 마라». 다른 말로 돌려라.'),
        'tone': '존댓말. 말이 느리고 문장이 짧다. 「그냥」을 자주 붙인다.',
        'first': '일을 다시 하긴 해야 하는데 요즘 아무것도 못 하겠어요',
    },
    '2': {
        'name': '조현우 · 25 · 남',
        'life': (
            '너는 조현우. 25세 남자.\n'
            '아버지가 당뇨 합병증으로 주 3회 투석을 받는다. 네가 모시고 다닌다.\n'
            '병원을 오래 다니다 보니 의료 쪽에 관심이 생겼다.\n'
            '인터넷 카페에서 정보를 모았는데 상당수가 틀렸다. 그런데 너는 그게 «맞다고 확신»한다:\n'
            '  · 간호조무사는 대학을 나와야 한다\n'
            '  · 요양보호사는 국가자격이 아니다\n'
            '  · 사회복지사 2급도 시험을 봐야 한다\n'
            '  · 자격증만 따면 바로 취업된다\n'
            '너는 고졸이라 「나는 안 되겠구나」라고 생각하고 있다.'),
        'hide': ('· 고졸이라서 포기하려 한다는 것 — 학력 이야기는 «먼저» 꺼내지 마라.\n'
                 '  대신 「그거 자격 요건이 어떻게 되죠?」처럼 자격 요건을 계속 캐물어라.\n'
                 '이건 봇이 뭘 물어도 말하지 마라.'),
        'tone': '존댓말. 자신 있게 말한다. 틀린 걸 확신해서 되묻지 않는다.',
        'first': '간호조무사는 대학 나와야 되는 거죠?',
    },
}

RULES = """[규칙 — 반드시 지켜라]
1. 처음부터 다 말하지 마라. 봇이 «구체적으로» 물으면 그때 조금씩만 연다.
2. 위 「말하지 않는 것」은 정말 말하지 마라.
3. 봇이 두루뭉술하게 물으면 짧게 회피해라. 같은 질문을 두 번 하면 「아까 말했는데요」라고 해라.
4. 카드(직업 추천)나 선택지를 봐도 바로 받아들이지 마라. «왜 아닌지»를 말하거나 의심해라.
5. 정말 마음에 드는 걸 찾았거나 더 할 말이 없으면 「__끝__」만 써라. 억지로 늘리지 마라.
6. 출력은 네가 «칠 한 마디»만. 설명·따옴표·지문 금지."""


def build_sim_prompt(per, hist, bot_last, turn):
    lines = []
    for h in hist[-16:]:                    # 최근 8턴 = 16줄
        lines.append(('나: ' if h['r'] == 'u' else '상담사: ') + h['t'])
    return (
        '너는 진로상담 챗봇과 대화하는 «사용자»를 연기한다.\n\n'
        f'[너의 인생 — 봇은 이걸 모른다]\n{per["life"]}\n\n'
        f'[말하지 않는 것]\n{per["hide"]}\n\n'
        f'[말투]\n{per["tone"]}\n\n'
        f'{RULES}\n\n'
        f'[최근 대화]\n{chr(10).join(lines) or "(없음)"}\n\n'
        f'[상담사가 방금 한 말]\n{bot_last}\n\n'
        f'(지금 {turn}번째 네 차례다) 네가 칠 한 마디만 써라.')


async def run(who, maxturn, outpath):
    per = PERSONAS[who]
    eng = ItdaEngine()                      # 봇 — 웹과 같은 기본 설정
    sim = ItdaEngine()                      # 페르소나 연기 — 비용을 «따로» 센다
    sim.total_usage = {'in': 0, 'out': 0, 'think': 0, 'cached': 0, 'calls': 0}

    print(f'== 페르소나 {who} · {per["name"]} · 최대 {maxturn}턴 ==', flush=True)
    print(f'   봇 모델 {eng.model} · think_level={eng.think_level!r} '
          f'· HISTORY_MODE={eng.HISTORY_MODE} · HISTORY_TURNS={eng.HISTORY_TURNS} '
          f'· SUMMARIZE_AFTER={eng.SUMMARIZE_AFTER}', flush=True)

    p = {}
    rows = []
    msg = per['first']
    seen_replies = []                       # 지금까지 나온 봇 응답 전부(완전동일 판정용)
    t_start = time.time()

    for turn in range(1, maxturn + 1):
        C._TURN_CACHE.clear()               # 턴 캐시가 답을 재사용하지 않게
        u0 = dict(eng.total_usage)
        err = None
        t0 = time.time()
        try:
            async with async_session() as db:
                r = await eng.step(db, p, msg)
        except Exception as e:              # noqa: BLE001
            err = f'{type(e).__name__}: {e}'
            print(f'  ⚠ {turn}턴 step 예외: {err}', flush=True)
            traceback.print_exc()
            r = {'kind': 'error', 'profile': p, 'reply': '', 'card': None}
        dt = time.time() - t0

        p = r.get('profile') or p
        reply = str(r.get('reply') or '')
        kind = r.get('kind')
        card = r.get('card') or {}
        job = ((card.get('job') or {}).get('name')
               if isinstance(card.get('job'), dict) else None)
        chips = list(r.get('options') or []) or list(card.get('options') or [])

        # ── controllers 가 profile 에 하는 일을 그대로 (파일 상단 도크스트링 참고)
        if reply:
            p['_last_ask'] = reply[:300]
            _la = list(p.get('_last_asks') or [])
            _la.append(reply[:300])
            p['_last_asks'] = _la[-3:]
        hist = list(p.get('_history') or [])
        hist.append({'r': 'u', 't': str(msg)[:300]})
        if reply:
            hist.append({'r': 'b', 't': reply[:300]})
        keep = max(2, eng.HISTORY_TURNS * 2)
        folded = 0
        if len(hist) > max(eng.SUMMARIZE_AFTER, eng.HISTORY_TURNS + 2) * 2:
            overflow, hist = hist[:-keep], hist[-keep:]
            if overflow:
                try:
                    new, facts = await eng.summarize(p.get('_summary') or '', overflow,
                                                     list(p.get('_facts') or []))
                    p['_summary'], p['_facts'] = new, facts
                    folded = len(overflow)
                except Exception as e:      # noqa: BLE001
                    print(f'  ⚠ {turn}턴 요약 예외: {type(e).__name__}: {e}', flush=True)
        p['_history'] = hist
        rethought = None
        sig = p.pop('_think_stale', None)
        if sig:
            try:
                th = await eng.think(dict(p), str(msg)[:300])
                if th and th.get('관심대분류') is not None:
                    p['관심대분류'] = [x for x in th['관심대분류'] if x]
                    rethought = p['관심대분류']
                if th:
                    p['_think_sig'] = sig
            except Exception as e:          # noqa: BLE001
                print(f'  ⚠ {turn}턴 think 예외: {type(e).__name__}: {e}', flush=True)

        used = {k: eng.total_usage.get(k, 0) - u0.get(k, 0)
                for k in ('in', 'out', 'think', 'cached', 'calls')}

        dup_prev = bool(seen_replies) and reply == seen_replies[-1] and reply != ''
        dup_any = reply != '' and reply in seen_replies
        seen_replies.append(reply)

        flags = []
        if '109' in reply:
            flags.append('109')
        if kind == 'redirect':
            flags.append('차단')
        if dup_prev:
            flags.append('완전동일(직전)')
        elif dup_any:
            flags.append('완전동일(이전어딘가)')
        if err:
            flags.append('예외')

        rows.append({'turn': turn, 'user': msg, 'kind': kind, 'job': job,
                     'chips': chips, 'reply': reply, 'flags': flags,
                     'used': used, 'sec': round(dt, 2), 'err': err,
                     'folded': folded, 'rethought': rethought,
                     'slots': {k: v for k, v in p.items()
                               if v and not str(k).startswith('_')},
                     'stall': p.get('_stall'), 'landed': p.get('_landed')})

        print(f'{turn:>3} | {kind:<8} | {(job or "-"):<16} | '
              f'chips={len(chips)} | {" ".join(flags) or "":<22} | '
              f'🧑 {msg[:44]!r} → 🤖 {reply[:60]!r}', flush=True)

        if turn >= maxturn:
            print('  (최대 턴 도달)', flush=True)
            break

        # ── 페르소나가 다음 말을 정한다
        try:
            sr = await sim.gemini(build_sim_prompt(per, hist, reply, turn + 1),
                                  SIM_SCHEMA, 1.0, think='minimal')
            nxt = str((sr or {}).get('말') or '').strip()
        except Exception as e:              # noqa: BLE001
            print(f'  ⚠ {turn}턴 시뮬레이터 예외: {type(e).__name__}: {e}', flush=True)
            nxt = ''
        if not nxt:
            print('  (시뮬레이터가 빈 말을 냄 — 종료)', flush=True)
            break
        if nxt.replace(' ', '') == '__끝__' or nxt.startswith('__끝__'):
            print(f'  ★ 페르소나가 스스로 끝냈다 ({turn}턴에서)', flush=True)
            rows.append({'turn': turn + 1, 'user': '__끝__', 'kind': None, 'job': None,
                         'chips': [], 'reply': '', 'flags': ['종료'], 'used': {},
                         'sec': 0, 'err': None, 'folded': 0, 'rethought': None,
                         'slots': {}, 'stall': None, 'landed': None})
            break
        msg = nxt

    out = {
        'who': who, 'name': per['name'],
        'model_bot': eng.model, 'model_sim': sim.model,
        'think_level': eng.think_level, 'think_budget': eng.think_budget,
        'history_mode': eng.HISTORY_MODE, 'history_turns': eng.HISTORY_TURNS,
        'summarize_after': eng.SUMMARIZE_AFTER,
        'llm_timeout': eng.LLM_TIMEOUT, 'llm_deadline': eng.LLM_DEADLINE,
        'turns': len(rows), 'wall_sec': round(time.time() - t_start, 1),
        'bot_usage': dict(eng.total_usage), 'sim_usage': dict(sim.total_usage),
        'final_slots': {k: v for k, v in p.items() if v and not str(k).startswith('_')},
        'slot_kind': p.get('_slot_kind'),
        'facts': p.get('_facts'), 'summary': p.get('_summary'),
        'rows': rows,
    }
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    def krw(u):
        return ((u['in'] - u['cached']) * 0.25 + u['cached'] * 0.025
                + u['out'] * 1.50) / 1e6 * 1380

    print('\n── 집계 ──────────────────────────────────', flush=True)
    print(f'턴 {len(rows)} · 벽시계 {out["wall_sec"]}초', flush=True)
    print(f'봇   {eng.total_usage}  →  {krw(eng.total_usage):.1f}원', flush=True)
    print(f'시뮬 {sim.total_usage}  →  {krw(sim.total_usage):.1f}원', flush=True)
    print(f'저장 {outpath}', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--who', default='1', choices=list(PERSONAS))
    ap.add_argument('--max', type=int, default=200)
    a = ap.parse_args()
    _out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f'_persona_long_{a.who}.json')
    asyncio.run(run(a.who, a.max, _out))
