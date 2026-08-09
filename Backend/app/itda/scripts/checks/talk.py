# -*- coding: utf-8 -*-
"""손으로 대화해 보는 도구 — 페르소나 시험용 (personas.md 참고).

왜 엔진이 아니라 controllers.handle_message 를 부르나
  골든셋(golden_check)은 eng.step() 을 직접 부른다. 그러면 **컨트롤러가 하는 일이
  전부 빠진다** — 세션 적재·이력 누적·요약 접기·지도 저장·응답 조립.
  실제 사용자가 겪는 건 그쪽이다. 여기서는 그 경로를 그대로 탄다.
  (라우터와 JWT 만 건너뛴다. 그 둘은 브라우저로 따로 확인한다)

왜 한 번에 한 턴인가
  페르소나는 **봇이 뭐라고 했는지 보고** 다음 말을 정한다. 미리 다 적어 두면
  그건 그냥 골든셋이고, 우리가 이미 통과할 줄 아는 문장만 던지는 꼴이다.

⚠ 프로세스가 매번 새로 뜨므로 메모리 세션은 비어 있다. 즉 **매 턴이 「서버 재시작」**이다.
  ITDA_SESSION_DB=1 이어야 대화가 이어진다(그 자체가 ⑥번 검증이 된다).
  그리고 요약·분야갱신은 응답 뒤 백그라운드로 도는데, 그냥 두면 프로세스가 먼저 죽어
  영영 안 돈다. 그래서 아래에서 **남은 태스크를 기다렸다가 한 번 더 저장**한다.

쓰는 법
  python talk.py --sid p01 --msg "뭐라도 해야 되는데 뭘 해야 될지 모르겠어요"
  python talk.py --sid p01 --save            # 지금 카드를 미래설계지도로 저장
  python talk.py --sid p01 --maps            # 저장된 지도 목록
  python talk.py --sid p01 --reset           # 세션 비우기
"""
import argparse
import asyncio
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\e-um-1\E-eum-team\Backend')

from app.itda import controllers, session          # noqa: E402
from app.itda.db import async_session              # noqa: E402

USER_ID = 6          # 브라우저에 로그인돼 있는 계정과 같은 것

BAR = '─' * 88


def _w(s):
    """한글 폭을 고려한 길이."""
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def show_profile(p):
    """사용자에게 보이지 않는 내부 상태까지 전부 보여준다 — 그게 이 도구의 목적이다."""
    p = p or {}
    slots = {k: v for k, v in p.items() if not k.startswith('_') and v}
    print(f'  슬롯   {json.dumps(slots, ensure_ascii=False)}' if slots else '  슬롯   (없음)')
    meta = []
    for k, label in (('_turns', '턴'), ('_abuse', '남용'), ('_ask_n', '질문횟수'),
                     ('_unsure', '모르겠다'), ('_landed', '착지함'),
                     ('_slot_src', '슬롯출처'), ('_narrowed', '좁힘'),
                     ('_exclude', '제외'), ('_demote', '강등')):
        if p.get(k):
            meta.append(f'{label}={json.dumps(p[k], ensure_ascii=False)}'
                        if isinstance(p[k], (dict, list)) else f'{label}={p[k]}')
    if meta:
        print(f'  내부   {" · ".join(meta)}')
    if p.get('_facts'):
        print(f'  누적사실 {p["_facts"]}')
    if p.get('_summary'):
        print(f'  요약   {p["_summary"][:120]}')
    h = p.get('_history') or []
    if h:
        print(f'  이력   {len(h)}개 (원문 유지)')


async def flush_background():
    """백그라운드 태스크(_fold·_rethink)를 끝까지 기다린다. 위 도크스트링 참고."""
    pend = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if not pend:
        return 0
    try:
        await asyncio.wait_for(asyncio.gather(*pend, return_exceptions=True), timeout=30)
    except asyncio.TimeoutError:
        print('  ⚠ 백그라운드 작업이 30초를 넘겨 기다리지 않는다')
    return len(pend)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sid', required=True, help='세션 id (페르소나마다 다르게)')
    ap.add_argument('--msg', help='사용자가 할 말')
    ap.add_argument('--save', action='store_true', help='지금 카드를 지도로 저장')
    ap.add_argument('--maps', action='store_true', help='저장된 지도 목록')
    ap.add_argument('--reset', action='store_true', help='세션 비우기')
    a = ap.parse_args()

    print(f'세션DB={session.SESSION_DB}  ·  sid={a.sid}')

    async with async_session() as db:
        if a.reset:
            await session.reset(db, a.sid)
            print('■ 세션을 비웠다')
            return
        if a.maps:
            rows = await controllers.list_maps(db, USER_ID)
            print(f'■ 미래설계지도 {len(rows)}개')
            for r in rows:
                print(f'   · {json.dumps(r, ensure_ascii=False, default=str)}')
            return
        if a.save:
            try:
                r = await controllers.save_map(db, USER_ID, a.sid)
                print(f'■ 지도 저장 → {json.dumps(r, ensure_ascii=False, default=str)}')
            except Exception as e:                      # noqa: BLE001
                print(f'🔴 지도 저장 실패: {type(e).__name__}: {e}')
            return

        if not a.msg:
            ap.error('--msg 가 필요하다')

        print(BAR)
        print(f'🧑 {a.msg}')
        print(BAR)
        #  ↓ 이 사이에 서버 쪽 [itda] 로그가 그대로 찍힌다. 그게 보려는 것이다.
        r = await controllers.handle_message(db, a.sid, a.msg, user_id=USER_ID)
        n = await flush_background()
        #  백그라운드가 고친 상태(요약·분야)를 한 번 더 저장한다 — 위 도크스트링 참고.
        if n:
            await session.save(db, a.sid, session.get(a.sid))

        print(BAR)
        print(f'🤖 [{r.type}] {r.reply}')
        if r.goal:
            g = r.goal.model_dump() if hasattr(r.goal, 'model_dump') else dict(r.goal)
            print(f'\n  🃏 카드 = {g.get("job_name") or g.get("name") or g}')
            for k in ('reason', 'why', 'summary'):
                if g.get(k):
                    print(f'     {k}: {str(g[k])[:160]}')
            if g.get('certs'):
                #  ★ 2026-08-08 — 키가 'name' 이 아니라 'cert' 다. 그동안 자격증이 멀쩡히
                #    들어있는데도 [None] 로 찍혀, 이 도구를 보는 사람이 「자격증이 안 나온다」고
                #    오해할 수 있었다. 프론트(LearnChat.jsx CertRow)는 s.cert 로 옳게 읽고 있다.
                print(f'     자격증: {[c.get("cert") if isinstance(c, dict) else c for c in g["certs"]][:4]}')
            if g.get('courses'):
                print(f'     강좌: {len(g["courses"])}개')
        if r.alternatives:
            print(f'  대안   {r.alternatives}')
        if r.options:
            print(f'  [칩]   {r.options}')
        if r.handoff:
            print(f'  인계   {r.handoff}')
        print(f'  이해   {r.understanding}')
        print(f'  사용량 {r.usage}')
        if n:
            print(f'  (백그라운드 {n}개 완료 후 재저장)')
        print(BAR)
        st = session.get(a.sid)
        show_profile(st.get('profile'))
        if st.get('last_card'):
            print(f'  마지막카드 {(st["last_card"].get("job") or {}).get("name")}')


asyncio.run(main())
