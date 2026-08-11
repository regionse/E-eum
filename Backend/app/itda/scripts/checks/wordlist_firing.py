# -*- coding: utf-8 -*-
r"""낱말표가 «실제로» 발동하나 — 세션 DB의 진짜 발화로 센다 (2026-08-11). **0원**

왜 만드나
  낱말표가 70개(낱말 1,175개)인데, 그중 «사용자 발화를 해석하는» 것이 약 650개다.
  전부 옮기려면 각각 채점표를 만들어야 하고 그건 오늘 할 수 있는 일이 아니다.
  ⇒ **먼저 어느 것이 «일하고 있는지»를 센다.**
     한 번도 안 걸리는 목록을 옮기는 건 시간 낭비고,
     매 턴 걸리는 목록은 틀리면 매 턴 아프다.

무엇을 쓰나
  `itda_session.state_json` 의 `_history` 에서 **사용자 발화만** 뽑는다.
  `itda-*` 세션은 브라우저에서 실제로 오간 대화다(내가 만든 페르소나가 아니다).
  ⚠ 발화는 300자에서 잘려 저장된다(_history 규칙). 긴 말의 뒷부분은 못 본다.

무엇을 세나
  목록마다 «몇 개의 발화에 걸리나». 걸린다고 «틀렸다»는 뜻이 아니다 —
  이 표는 **어디를 먼저 봐야 하는지**를 정하는 용도다.

⚠ 안전 낱말표(자해·폭력·성·불법·인젝션)는 여기서 **일부러 뺐다.**
  그건 이미 2층 구조(낱말표 → LLM)이고, 발동률이 낮은 게 정상이다.
⚠ 명부(NCS·조사·우리 enum)도 뺐다. 그건 닫힌 집합이라 옮길 대상이 아니다.

쓰는 법 (Backend/ 에서)
  python app/itda/scripts/checks/wordlist_firing.py
"""
import asyncio
import io
import json
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from sqlalchemy import text                            # noqa: E402
from app.itda.db import async_session                  # noqa: E402
from app.itda import itda_core as C                    # noqa: E402

#  «사용자 발화를 해석하는» 목록만 — (이름, 대조방식, 무엇을 판정하나)
#  (안전·명부·봇출력 검사는 뺐다 — 위 도크스트링 참고)
#
#  ★★ 2026-08-11 — **처음엔 전부 «부분일치»로 셌다. 틀렸다.**
#    `_THIN_ACK` 이 71% 로 나와서 자를 의심했고, 코드를 보니 이랬다:
#        557행  return m in _THIN_ACK       ← 통째 «일치»지 부분일치가 아니다
#    「전부 걸린다」가 나오면 대상이 아니라 계측이 틀린 것이다. 모드를 붙였다.
#  대조방식 — 각 줄 옆에 «확인한 행 번호»를 적었다. 주석이 아니라 코드를 봤다.
#    exact  발화 전체가 목록에 있나        sub    낱말이 발화 안에 있나
#    tail   문장 «끝부분»만 본다           short  짧은 발화(≤16자)에서만 본다
#    skip   발화 분류가 «아니다» — 조사 떼기·슬롯값 거르기용이라 셀 대상이 아니다
OPEN = [
    ('_OBJ_MARK', 'sub', '「할머니」→사람 : 다루는대상을 채운다 (2330)'),
    ('_OBJ_DETAIL_MARK', 'sub', '「치매」→어르신 : 대상세부를 채운다'),
    ('_META_SOLO', 'short', '대화 자체에 대한 말인가 — ≤16자에서만 (1871)'),
    ('_META_EXACT', 'exact', '「응」「네」 통째 일치 (1869)'),
    ('_META_GREET', 'sub', '인사인가'),
    ('_UNDERSTAND', 'sub', '「알아들었어?」인가'),
    ('_POLICY_MONEY', 'sub', '돈이 부담이라는 신호'),
    ('_POLICY_TIME', 'sub', '시간이 부담이라는 신호'),
    ('_POLICY_ASK', 'sub', '지원 제도를 묻나'),
    ('_POLICY_NO', 'sub', '정책 안내를 물렸나'),
    ('_THIN_ACK', 'exact', '알맹이 없는 맞장구 — 통째 일치 (557)'),
    ('_UNCERTAIN', 'sub', '모르겠다는 답인가 (1435)'),
    ('_UNCERTAIN_ONLY', 'exact', '모르겠다«만» 있는가 — 통째 일치 (1438)'),
    ('_REJECT_LAST', 'sub', '직전 추천을 물렸나 (823) ※오늘 폴백으로 내림'),
    ('_REJECT', 'sub', '거부·되물음인가 (3516) ※DIRECT 확정 차단용'),
    ('_NONE_OF_THESE', 'sub', '목록 전체가 아니라는 말인가'),
    ('_LAND_REQ', 'sub', '「그만 묻고 보여줘」인가 ※게이트 백업 있음'),
    ('_CARE_CTX', 'sub', '돌봄·질병 이야기인가 (1813)'),
    ('_NEG_MARK', 'sub', '부정 표지 (2253) ※오늘 폴백으로 내림'),
    ('_POS_MARK', 'sub', '긍정 표지 (2254)'),
    ('_PIVOT', 'sub', '방향 전환 표지 (2255)'),
    ('_WANT', 'sub', '원한다는 표현 (3565)'),
    ('_HAVE', 'sub', '가지고 있다는 표현'),
    ('_CRED', 'sub', '자격증 이야기인가'),
    ('_NOT_CRED', 'sub', '자격증이 아닌 말 (3569)'),
    ('_ASK_MEANING', 'sub', '「무슨 소리야」인가'),
    ('_ASK_EXIST', 'sub', '「뭐가 있어요」인가 (3567)'),
    ('_EXAM_WHEN', 'sub', '시험이 «언제»인지 묻나'),
    ('_EXAM_WHAT', 'sub', '시험 이야기인가'),
    ('_ATTRIB_MARK', 'sub', '「확신이 있다」류 귀속 표현'),
    ('_NOT_ASSERT_TAIL', 'tail', '단정이 아닌 어미 — 끝부분만 (1273)'),
    ('_ASK_KEEP_TAIL', 'tail', '되물음을 유지할 어미'),
    ('_IMPERATIVE_AT_BOT', 'sub', '봇에게 시키는 말인가 (2913)'),
    ('_ENTRY_CLAIM', 'sub', '응시자격을 단정하는 말'),
    ('_ENTRY_HARD', 'sub', '응시제한이 없다는 단정'),
    #  ↓ 발화 분류가 아니다 — 세면 안 되는 것들
    ('_ORD_AMBIG', 'skip', '«파싱된 키»에 대한 일치 (2464) — 발화 분류가 아님'),
    ('_PICK_HEDGE', 'skip', '조사·완충어 «떼어내기»용 (2495) — 발화 분류가 아님'),
    ('_SUB_STOP', 'skip', '조각에서 뺄 일반명사 (2196) — 발화 분류가 아님'),
    ('_NOT_INTEREST', 'skip', '슬롯 «값»을 거른다 (7724) — 발화 분류가 아님'),
    ('_UNG_ADV', 'skip', '_UNGROUNDED_CLAIM 의 재료 (1217) — 단독으로 안 쓰임'),
    ('_UNG_VERB', 'skip', '〃'),
]


def w(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def pad(s, n):
    return str(s) + ' ' * max(1, n - w(s))


def _flat(v):
    """튜플 안에 튜플이 든 것(_OBJ_MARK 꼴)도 평평하게."""
    out = []
    for x in (v or ()):
        if isinstance(x, (tuple, list, frozenset, set)):
            out += _flat(x)
        elif isinstance(x, str):
            out.append(x)
    return out


async def main():
    utts, per_sess = [], {}
    async with async_session() as db:
        rows = (await db.execute(
            text('SELECT session_id, state_json FROM itda_session'))).fetchall()
    for sid, sj in rows:
        try:
            st = json.loads(sj) if isinstance(sj, str) else sj
        except Exception:                                # noqa: BLE001
            continue
        h = ((st or {}).get('profile') or {}).get('_history') or []
        got = [x.get('t') for x in h
               if isinstance(x, dict) and x.get('r') == 'u' and x.get('t')]
        if got:
            per_sess[sid] = len(got)
            utts += got

    real = sum(n for s, n in per_sess.items() if s.startswith('itda-'))
    mine = sum(n for s, n in per_sess.items() if not s.startswith('itda-'))
    print('=' * 116)
    print(f'  낱말표 발동률 — 세션 {len(per_sess)}개 · 사용자 발화 {len(utts)}개 · **0원**')
    print(f'  (브라우저 실사용 {real}개 · 내가 만든 페르소나 {mine}개)')
    print('=' * 116)
    print()
    print(f'  {pad("이름", 22)} {pad("방식", 6)} {pad("낱말", 5)} {pad("걸림", 7)} '
          f'{pad("발동률", 8)} 무엇을 판정하나')
    print('  ' + '-' * 112)

    norm = [re.sub(r'\s+', '', u) for u in utts]
    rows2, skipped = [], []
    for name, mode, what in OPEN:
        words = _flat(getattr(C, name, ()))
        if not words:
            continue
        if mode == 'skip':
            skipped.append((name, what))
            continue
        if mode == 'exact':
            hit = sum(1 for m in norm if m in words)
        elif mode == 'tail':
            hit = sum(1 for m in norm if any(t in m[-12:] for t in words))
        elif mode == 'short':
            hit = sum(1 for m in norm if len(m) <= 16 and any(t in m for t in words))
        else:
            hit = sum(1 for m in norm if any(t in m for t in words))
        rows2.append((name, mode, len(words), hit,
                      hit / max(1, len(norm)) * 100, what))
    rows2.sort(key=lambda r: -r[3])
    for name, mode, nw, hit, pct, what in rows2:
        bar = '█' * int(pct / 4)
        print(f'  {pad(name, 22)} {pad(mode, 6)} {pad(nw, 5)} {pad(hit, 7)} '
              f'{pad(f"{pct:.0f}%", 7)} {bar} {what}')
    if skipped:
        print()
        print('  ── 발화 분류가 «아닌» 것 (셀 대상이 아님) ──')
        for name, what in skipped:
            print(f'  {pad(name, 22)} {what}')
    print('  ' + '-' * 112)
    dead = [r[0] for r in rows2 if r[3] == 0]
    rare = [r[0] for r in rows2 if 0 < r[3] <= 2]
    hot = [r[0] for r in rows2 if r[4] >= 20]
    print(f'  한 번도 안 걸린 목록 {len(dead)}개: {" · ".join(dead) or "없음"}')
    print(f'  2건 이하 {len(rare)}개: {" · ".join(rare) or "없음"}')
    print(f'  **발동률 20% 이상 {len(hot)}개**: {" · ".join(hot) or "없음"}')
    print('=' * 116)
    print('  ※ 「걸린다」가 「틀렸다」는 뜻이 아니다. 어디를 먼저 볼지 정하는 표다.')
    print('  ⚠ 발화는 300자에서 잘려 저장된다 — 긴 말의 뒷부분은 못 본다.')
    Path(__file__).with_name('_wordlist_firing.json').write_text(
        json.dumps({'잰날': '2026-08-11', '발화수': len(norm), '실사용': real,
                    '세션': per_sess,
                    '표': [{'이름': n, '낱말': nw, '걸림': h, '발동률': round(p, 1),
                            '방식': md, '무엇': wt} for n, md, nw, h, p, wt in rows2]},
                   ensure_ascii=False, indent=1), encoding='utf-8')
    print('  원값 저장: _wordlist_firing.json')


asyncio.run(main())

