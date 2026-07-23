# -*- coding: utf-8 -*-
"""
잇다 컨트롤러 — itda_core 를 프론트 계약에 맞춰 변환한다.

역할은 '번역'뿐. 판단 로직은 전부 itda_core 에 있다(CLI 와 같은 코드를 쓴다).
  itda_core.step()  →  {kind, reply, profile, missing, can_land, card}
  프론트가 기대      →  {type, reply, turn, max_turn, understanding, mode, goal, alternatives}

· 세션에는 slot(profile) 만 보관한다. 대화 로그를 쌓지 않는다.
· itda_core 는 동기(urllib·pymysql)라 run_in_threadpool 로 넘겨 이벤트 루프를 막지 않는다.
"""
import json

from fastapi.concurrency import run_in_threadpool

from app.itda import session
from app.itda.schemas import Goal, MessageResponse, NextStep

try:                                   # 서버(패키지) 경로
    from app.itda.itda_core import ItdaEngine, missing_slots, ASK_ORDER
except ImportError:                    # standalone 실행 경로
    from itda_core import ItdaEngine, missing_slots, ASK_ORDER


# 엔진은 프로세스당 하나 — DB·직무분야 목록을 매 요청마다 다시 읽지 않는다.
_ENGINE = None

def get_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ItdaEngine()         # allow_prompt=False → 서버가 입력을 기다리는 일 없음
    return _ENGINE


# ── 카드 → 프론트 goal ──────────────────────────────────────────────
def _exam_text(exam):
    """exam = (회차, 필기시작, 실기시작, 발표) → 사람이 읽는 한 줄"""
    if not exam:
        return "다음 시험 일정이 아직 공고되지 않았어요"
    seq, doc, prac, pas = exam
    bits = []
    if doc:
        bits.append(f"필기 {doc}")
    if prac:
        bits.append(f"실기 {prac}")
    if pas:
        bits.append(f"발표 {pas}")
    return f"제{seq}회 · " + " · ".join(bits) if bits else f"제{seq}회"


def _to_goal(card) -> Goal:
    titles = [c["title"] for c in (card.get("courses") or [])]
    nxt = card.get("next_step")
    #  entry_free 는 3값이다 — True 는 '제한 없음 확인', False 는 '조건 있음'이 아니라 '미확인'.
    #  미확인일 땐 우리가 해석하지 않고 공단이 쓴 조건 원문(entry_note)을 그대로 넘긴다.
    free = bool(card.get("entry_free"))
    return Goal(
        cert=card["cert"],
        field=card.get("oblig_fld") or "",
        reason=card.get("reason", ""),
        exam=_exam_text(card.get("exam")),
        has_courses=bool(titles),
        courses=titles,
        guide="" if titles else
              "아직 딱 맞는 무료강좌를 못 찾았어요. 국민내일배움카드 훈련과정으로 이어서 볼 수 있어요.",
        grade=card.get("grade") or "",
        entry="지금 바로 응시 가능" if free else "응시자격 확인 필요",
        entry_note="" if free else (card.get("entry_note") or ""),
        next_step=NextStep(cert=nxt["cert"], grade=nxt.get("grade") or "",
                           entry_note=nxt.get("entry_note") or "") if nxt else None,
    )


def _progress(profile):
    """슬롯이 얼마나 찼는지를 진행도로 보여준다."""
    total = len(ASK_ORDER)
    return total - len(missing_slots(profile)), total


# ── 한 턴 ───────────────────────────────────────────────────────────
async def handle_message(session_id: str, message: str) -> MessageResponse:
    st = session.get(session_id)
    profile = st.get("profile") or {}

    try:
        eng = await run_in_threadpool(get_engine)          # 최초 1회 DB 연결도 스레드풀에서
        r = await run_in_threadpool(eng.step, profile, message)
    except Exception as e:
        print(f"[itda] step 실패: {type(e).__name__}: {e}")   # 서버 로그에만 남긴다
        done, total = _progress(profile)
        return MessageResponse(
            type="blocked",
            reply="지금 잠시 연결이 원활하지 않아요. 잠시 후 다시 말씀해 주실래요?",
            turn=done, max_turn=total,
            understanding=json.dumps(profile, ensure_ascii=False),
            mode="error",
        )

    profile = r["profile"]
    st["profile"] = profile
    st["done"] = bool(r.get("card"))
    done, total = _progress(profile)

    kind = r["kind"]
    #  notfound = 사용자가 콕 집어 말한 목표가 우리 613종에 없는 경우.
    #  대화는 계속돼야 하므로 프론트에는 ask 로 내보낸다(문구는 코드가 이미 써 뒀다).
    msg_type = "result" if kind == "card" else ("blocked" if kind == "blocked" else "ask")

    reply = r["reply"]
    if kind == "offramp":
        reply += "\n\n지금은 자격증보다 돌봄 지원이나 바로 해볼 수 있는 일부터 보는 것도 좋아요."

    card = r.get("card")
    # 카드가 있으면 다른 후보를, 못 찾았으면 가까운 것들을 alternatives 로 내보낸다
    alts = ([c["cert"] for c in (r.get("near") or [])] if kind == "notfound"
            else (card or {}).get("alternatives", []))
    return MessageResponse(
        type=msg_type,
        reply=reply,
        turn=done,
        max_turn=total,
        understanding=json.dumps(profile, ensure_ascii=False),
        mode="gemini",
        goal=_to_goal(card) if card else None,
        alternatives=alts,
    )
