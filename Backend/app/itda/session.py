# -*- coding: utf-8 -*-
"""세션 상태 저장 — 대화 이력/요약/턴을 session_id별로 보관.

지금은 메모리 dict(프로세스 재시작하면 사라짐, 단일 서버 전제).
운영에서는 Redis 또는 DB 테이블로 교체 → 여기만 바꾸면 됨(라우터/컨트롤러는 그대로).
"""

_SESSIONS: dict[str, dict] = {}


def get(session_id: str) -> dict:
    """세션에는 슬롯(profile) 만 담는다.

    대화 로그를 쌓지 않는 게 잇다의 설계다 — 매 턴 '압축된 이해(슬롯)'만 넘긴다.
    그래서 턴이 길어져도 토큰이 늘지 않고, 앞부분을 잊는 문제도 없다.
    profile 은 itda_map.profile_json 과 같은 모양이라 그대로 저장·복원할 수 있다.
    """
    return _SESSIONS.setdefault(
        session_id,
        {"profile": {}, "done": False},
    )


def reset(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)


def snapshot() -> dict:
    """디버깅용 — 지금 살아있는 세션 요약."""
    return {sid: {"slots": len([v for v in s.get("profile", {}).values() if v]),
                  "done": s.get("done", False)}
            for sid, s in _SESSIONS.items()}
