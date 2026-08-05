# -*- coding: utf-8 -*-
"""세션 상태 저장 — profile(슬롯)·last_card·좁히기 이력을 session_id별로 보관.

지금은 메모리 dict(프로세스 재시작하면 사라짐, 단일 서버 전제).
운영에서는 Redis 또는 DB 테이블로 교체 → 여기만 바꾸면 됨(라우터/컨트롤러는 그대로).
"""

_SESSIONS: dict[str, dict] = {}
_MAX_SESSIONS = 5000    # 상한 — 넘으면 가장 오래된 세션부터 버린다(TTL/evict 없어 메모리 무한증가하던 것, 코드감사)


def get(session_id: str) -> dict:
    """세션은 profile(슬롯) 을 중심으로 담는다.

    ★ 2026-08-06 정정 — 예전 주석은 「대화 로그를 쌓지 않는다」·「턴이 길어져도 토큰이
      늘지 않는다」였다. **둘 다 지금은 사실이 아니다.**
      2026-08-04 에 HISTORY_MODE='full' 이 들어오면서 profile 안에 아래가 함께 담긴다:
        _history  최근 발화 원문(각 300자, 최대 16턴분 — 실측 4.8KB 수준)
        _summary  그보다 오래된 대화의 LLM 요약(최대 800자)
      turn() 이 매 턴 [앞선 대화 요약] + [최근 대화] 로 프롬프트에 넣으므로
      **토큰은 요약+최근 2턴만큼 늘어난다.**
      ⚠ 이 오해는 실제로 사고를 냈다 — _TURN_CACHE 개인정보 누출 버그가
        「'_' 접두 상태는 프롬프트에 안 들어간다」는 잘못된 전제에서 나왔다.
        여기 도크스트링이 그 전제의 출처였다.
    profile 은 itda_map.profile_json 과 같은 모양이라 그대로 저장·복원할 수 있다.
    (단 save_map 은 과정 상태를 pop 하고 결론만 남긴다 — controllers.save_map 참고)
    """
    s = _SESSIONS.get(session_id)
    if s is not None:
        #  ★ 최근 사용 순으로 끌어올린다(2026-07-30) — 예전엔 '만든 순서(FIFO)'로 축출해서
        #    한창 대화 중인(먼저 시작한) 세션이 먼저 잘리고, 방금 들어와 아무것도 안 한 세션이
        #    살아남았다. dict 는 삽입순을 지키므로 pop→재삽입이 곧 LRU 갱신이다.
        _SESSIONS[session_id] = _SESSIONS.pop(session_id)
        return s
    # 상한 초과 시 '가장 오래 안 쓴' 세션부터 축출(위 갱신 덕분에 LRU 가 된다).
    while len(_SESSIONS) >= _MAX_SESSIONS:
        _SESSIONS.pop(next(iter(_SESSIONS)), None)
    s = {"profile": {}}
    _SESSIONS[session_id] = s
    return s


def reset(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)

#  (2026-07-30) snapshot() 제거 — 호출부·엔드포인트가 없었다. 함께 쓰던 세션 "done" 키도 제거
#   (controllers 가 매 턴 쓰기만 하고 읽는 곳은 snapshot 뿐이었다).
