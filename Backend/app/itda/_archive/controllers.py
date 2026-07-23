# -*- coding: utf-8 -*-
"""잇다 그래프 로직 — 안전게이트 → 상담루프 → 결정 → 착지(grounded).

라우터는 이 함수 하나만 부른다. Gemini 블로킹 호출은 스레드풀로 넘겨 async를 안 막는다.
"""
from fastapi.concurrency import run_in_threadpool

from app.itda import config, gemini, session
from app.itda.catalog import CATALOG
from app.itda.schemas import Goal, MessageResponse

# ── ① 안전 게이트 (코드, 최소 예시) ──
_BAD = ("죽이", "때리", "폭행", "야한", "성인물", "자살", "칼로")


def _unsafe(text: str) -> bool:
    return any(b in text for b in _BAD)


async def handle_message(session_id: str, message: str) -> MessageResponse:
    st = session.get(session_id)

    # ① 안전 게이트
    if _unsafe(message):
        return MessageResponse(
            type="blocked",
            reply="그런 쪽은 도와드리기 어려워요. 다른 이야기를 들려주실래요?",
            turn=st["turn"], max_turn=config.SAFETY_TURN_LIMIT,
        )

    # ② 상담 턴 (Gemini, 실패 시 스텁 폴백)
    out, mode = await run_in_threadpool(gemini.counsel_turn, st["history"], message, st["summary"])
    st["summary"] = out.get("summary", st["summary"])
    st["turn"] += 1

    # ③ 충분? or 턴캡 → 착지
    if out.get("enough") or st["turn"] >= config.SAFETY_TURN_LIMIT:
        cands = [c for c in out.get("candidates", []) if c in CATALOG]
        reason = ""
        if not cands:                                     # ②b 강제 결정 노드
            cands, reason, mode = await run_in_threadpool(gemini.decide_cert, st["history"], st["summary"])
        st["done"] = True

        cert = cands[0]
        c = CATALOG[cert]
        goal = Goal(
            cert=cert, field=c["field"], reason=reason,
            exam=c["exam"], has_courses=c["kmooc"],
            courses=c["courses"], guide=c.get("guide", ""),
        )
        return MessageResponse(
            type="result",
            reply=out.get("reply") or "이야기를 들어보니 이런 쪽이 어울릴 것 같아요.",
            turn=st["turn"], max_turn=config.SAFETY_TURN_LIMIT,
            understanding=st["summary"], mode=mode,
            goal=goal, alternatives=cands[1:],
        )

    # 반복: 더 묻기
    st["history"].append({"user": message, "reply": out.get("reply", "")})
    return MessageResponse(
        type="ask", reply=out.get("reply", ""),
        turn=st["turn"], max_turn=config.SAFETY_TURN_LIMIT,
        understanding=st["summary"], mode=mode,
    )
