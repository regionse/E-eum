# -*- coding: utf-8 -*-
"""세션 DB 저장 검사 — **LLM 을 부르지 않는다(0원).** DB 만 쓴다.

무엇을 확인하나
  ① 테이블이 «없을 때» 서버가 안 죽고 메모리로 도는가   ← 팀원 DB 를 안 깨는지
  ② 테이블을 만들면 저장/복원이 되는가
  ③ **메모리를 통째로 비운 뒤**(= 서버 재시작) 대화가 살아나는가   ← 본 목적
  ④ reset 이 DB 행까지 지우는가                        ← 만들면서 밟은 구멍
  ⑤ 너무 큰 세션을 조용히 넘기지 않는가

⚠⚠ **이 스크립트는 itda_session 을 DROP 했다가 다시 만든다.**
  ①(테이블 없을 때)을 재현하려면 없는 상태를 만들어야 해서다.
  ⇒ **운영/시연 DB 에서 돌리지 마라. 진행 중인 대화가 전부 사라진다.**
  다른 테이블은 건드리지 않고, 끝에 테스트용 행만 지운다.
"""
import asyncio
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from sqlalchemy import text                        # noqa: E402

from app.itda.db import async_session              # noqa: E402
import app.itda.session as S                       # noqa: E402

SID = '__test_session_db__'
DDL = """
CREATE TABLE IF NOT EXISTS itda_session (
  session_id  VARCHAR(64) NOT NULL PRIMARY KEY,
  user_id     BIGINT      NULL,
  state_json  JSON        NOT NULL,
  updated_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
                          ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_itda_session_updated (updated_at)
) DEFAULT CHARSET=utf8mb4
"""

#  40턴쯤 진행한 대화를 흉내낸다
STATE = {
    'owner': 999999,
    'profile': {
        '관심분야': ['제빵', '조리'], '활동유형': ['만들기'], '다루는대상': ['음식'],
        '제약': ['야간불가'], '_turns': 41,
        '_summary': '할머니를 돌보며 학교를 마치지 못했고, 손으로 만드는 일에 관심이 있다.',
        '_facts': ['할머니 간병 중', '고졸', '아침 일찍은 힘들다', '빵 만드는 것 좋아함'],
        '_history': [{'r': 'u', 't': '빵 만드는 게 좋아요'}, {'r': 'b', 't': '어떤 빵이요?'}],
        '_slot_src': {'관심분야': 'user', '다루는대상': 'code'},
    },
    'last_card': {'job': {'code': 'X1', 'name': '제빵'}},
}

bad = []


def chk(ok, name, detail=''):
    print(f'{"✅" if ok else "🔴"}  {name}' + (f'   {detail}' if detail else ''))
    if not ok:
        bad.append(name)


async def main():
    print(f'ITDA_SESSION_DB 설정값 → SESSION_DB={S.SESSION_DB}\n')

    async with async_session() as db:
        # ── ① 테이블이 없을 때 죽지 않는가 ──────────────────────────
        print('■ ① 테이블이 없을 때 (팀원 DB 를 안 깨는지)')
        await db.execute(text("DROP TABLE IF EXISTS itda_session"))
        await db.commit()
        S.SESSION_DB, S._DB_OK = True, True
        S._SESSIONS.clear()
        st = await S.load(db, SID)
        chk(isinstance(st, dict) and st.get('profile') == {},
            'load 가 예외 없이 빈 세션을 준다', f'_DB_OK={S._DB_OK}')
        st.update({k: v for k, v in STATE.items()})
        await S.save(db, SID, st)
        chk(S._DB_OK is False, 'save 가 실패를 «한 번만» 알리고 스스로 내려간다')

        # ── ② 테이블을 만들면 저장되는가 ────────────────────────────
        print('\n■ ② 테이블을 만든 뒤')
        await db.execute(text(DDL))
        await db.commit()
        S._DB_OK = True
        await S.save(db, SID, st)
        row = (await db.execute(
            text("SELECT session_id FROM itda_session WHERE session_id=:s"),
            {'s': SID})).fetchone()
        chk(bool(row), 'DB 에 행이 생겼다')

        # ── ③ 서버 재시작 흉내 ─────────────────────────────────────
        print('\n■ ③ 메모리를 통째로 비운다 (= 서버 재시작)')
        S._SESSIONS.clear()
        chk(SID not in S._SESSIONS, '메모리에서 사라졌다', f'세션 수 {len(S._SESSIONS)}')
        st2 = await S.load(db, SID)
        p = st2.get('profile') or {}
        chk(int(p.get('_turns') or 0) == 41, '41턴이 되살아났다', f"_turns={p.get('_turns')}")
        chk(p.get('_facts') == STATE['profile']['_facts'], '누적 사실이 그대로다',
            f"{p.get('_facts')}")
        chk(p.get('_slot_src') == STATE['profile']['_slot_src'], '슬롯 출처가 그대로다',
            f"{p.get('_slot_src')}")
        chk((st2.get('last_card') or {}).get('job', {}).get('name') == '제빵',
            '마지막 카드도 살아났다 (저장 버튼이 동작한다)')
        chk(st2.get('owner') == 999999, '소유자가 유지된다')

        # ── ④ reset 이 DB 까지 지우는가 ─────────────────────────────
        print('\n■ ④ reset')
        await S.reset(db, SID)
        S._SESSIONS.clear()
        st3 = await S.load(db, SID)
        chk((st3.get('profile') or {}) == {}, 'reset 뒤에는 되살아나지 않는다',
            f"profile={st3.get('profile')}")

        # ── ⑤ 너무 큰 세션 ─────────────────────────────────────────
        print('\n■ ⑤ 크기 상한')
        huge = {'profile': {'x': 'ㄱ' * 300000}}
        await S.save(db, SID, huge)
        row = (await db.execute(
            text("SELECT session_id FROM itda_session WHERE session_id=:s"),
            {'s': SID})).fetchone()
        chk(row is None, '상한 초과는 저장하지 않는다 (그리고 로그로 알린다)')
        chk(S._DB_OK is True, '그렇다고 DB 를 내리지는 않는다')

        # 뒷정리 — 테스트 행만 지운다
        await db.execute(text("DELETE FROM itda_session WHERE session_id=:s"), {'s': SID})
        await db.commit()

    print('\n' + '=' * 84)
    print(f'  통과 {6 + 5 - len(bad)} / 11   ·  LLM 0회 (0원)')
    for n in bad:
        print(f'    🔴 {n}')
    print('=' * 84)


asyncio.run(main())
