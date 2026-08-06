# -*- coding: utf-8 -*-
"""세션 상태 저장 — profile(슬롯)·last_card·좁히기 이력을 session_id별로 보관.

기본은 메모리 dict 다. `ITDA_SESSION_DB=1` 이면 **DB 에도 함께 써서**
프로세스가 죽어도 대화가 살아남는다(아래 「왜 DB 인가」 참고).

★★ 2026-08-06 — 예전 이 파일 주석은 이렇게 적혀 있었다:
     「운영에서는 Redis 또는 DB 테이블로 교체 → **여기만 바꾸면 됨**(라우터/컨트롤러는 그대로)」
   **사실이 아니었다.** get() 이 돌려주는 dict 를 호출부가 «제자리에서» 고치고 있어서
   (controllers 7곳: st["profile"]·st["last_card"]·st["owner"]·복원 3줄·백그라운드 2곳)
   메모리 dict 일 때만 그게 곧 저장이었다. 다른 저장소로 바꾸면 전부 명시적 쓰기가 필요하다.
   ⇒ 그래서 «교체»하지 않고 **write-through** 로 했다. 메모리 dict 는 그대로 두고
     턴 시작에 load() · 턴 끝에 save() 두 줄만 더한다. 기존 7곳은 하나도 안 건드린다.

왜 DB 인가 (2026-08-06, 전제 변경)
  설계 전제가 「대화 3턴」에서 「20~100턴」으로 바뀌었다. 3턴이면 서버가 재시작해도
  「다시 해 주세요」로 넘길 수 있다. **40턴짜리 대화는 다시 못 한다.**
  메모리 dict 는 아래 네 경우에 통째로 사라진다:
    · 서버 재시작 / 배포        ← 코드 한 줄 고쳐 올려도 진행 중 대화 전원 소실
    · 프로세스 죽음
    · 세션 5000개 초과          ← LRU 축출. 대화 중인 세션도 대상이다
    · uvicorn 워커 2개 이상     ← 턴마다 다른 워커에 붙어 슬롯이 없다

  ⚠ 워커 여러 개는 **이걸로 완전히 해결되지 않는다.** load() 가 메모리를 먼저 보므로
    두 워커가 같은 세션을 동시에 들고 있으면 서로의 최신 상태를 모른다.
    완전히 하려면 매 턴 DB 를 읽어야 하고, 그러면 백그라운드 요약(_fold)이 메모리에만
    쓴 결과가 날아간다. 지금은 «재시작 생존»만 목표로 한다. 시연은 워커 1개 그대로.

  ⚠ 백그라운드 태스크(_fold·_rethink)는 메모리만 고친다. 그 결과는 **다음 턴의 save()**
    에 실려 저장된다. 그 사이에 서버가 죽으면 요약 한 사이클을 잃는다 — 요약은
    있으면 좋은 것이지 필수가 아니므로(itda_core.summarize 주석) 그 손실은 받아들인다.

테이블이 없으면 (2026-08-06)
  **조용히 메모리 전용으로 돈다.** 팀원마다 DB 가 다르고 이 저장소에는 마이그레이션
  체계가 없어서(alembic·create_all·.sql 전부 없음), 테이블을 안 만든 사람의 서버가
  이것 때문에 죽으면 안 된다. 첫 실패에서 한 번만 로그를 남기고 이후로는 시도하지 않는다.

  켜려면 아래를 한 번 실행하고 ITDA_SESSION_DB=1 을 .env 에 넣는다:

    CREATE TABLE IF NOT EXISTS itda_session (
      session_id     VARCHAR(64)  NOT NULL PRIMARY KEY,
      user_id        BIGINT       NULL,
      state_json     JSON         NOT NULL,
      updated_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_itda_session_updated (updated_at)
    ) DEFAULT CHARSET=utf8mb4;

주의: 값은 절대 로그로 찍지 않는다(대화 내용이 들어 있다).
"""
import json

from sqlalchemy import text

try:
    from .env import ENV
except ImportError:                     # CLI: path 에 app/itda 가 들어와 있을 때
    from env import ENV

_SESSIONS: dict[str, dict] = {}
_MAX_SESSIONS = 5000    # 상한 — 넘으면 가장 오래된 세션부터 버린다(TTL/evict 없어 메모리 무한증가하던 것, 코드감사)

#  기본은 꺼짐 — 테이블을 만든 사람만 켠다(위 도크스트링 참고).
SESSION_DB = (ENV.get('ITDA_SESSION_DB') or '0').lower() in ('1', 'true', 'on')
#  DB 쪽이 한 번이라도 실패하면 내려간다. 매 턴 실패를 반복하며 지연을 만들지 않으려고.
_DB_OK = True

#  한 세션이 DB 에 차지할 수 있는 최대 크기. 넘으면 저장을 건너뛴다(메모리로는 계속 돈다).
#  _history 8턴 + _summary + _facts 로 실측 10KB 안팎이라 넉넉히 잡는다.
_MAX_STATE_BYTES = 256 * 1024


def get(session_id: str) -> dict:
    """세션은 profile(슬롯) 을 중심으로 담는다.

    ★ 2026-08-06 정정 — 예전 주석은 「대화 로그를 쌓지 않는다」·「턴이 길어져도 토큰이
      늘지 않는다」였다. **둘 다 지금은 사실이 아니다.**
      2026-08-04 에 HISTORY_MODE='full' 이 들어오면서 profile 안에 아래가 함께 담긴다:
        _history  최근 발화 원문(각 300자, HISTORY_TURNS*2 개)
        _summary  그보다 오래된 대화의 LLM 요약(최대 800자)
        _facts    재압축하지 않고 누적하는 사실 목록(2026-08-06)
      turn() 이 매 턴 [확인된 사실] + [앞선 대화 요약] + [최근 대화] 로 프롬프트에 넣으므로
      **토큰은 그만큼 늘어난다.**
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


def _down(where, exc):
    """DB 저장을 내린다 — **한 번만** 알리고 이후로는 조용히 메모리로 돈다."""
    global _DB_OK
    if _DB_OK:
        print(f'[itda] 세션 DB 사용 안 함({where}): {type(exc).__name__}: {str(exc)[:100]}')
        print('[itda]   → 메모리 전용으로 계속합니다. 재시작하면 진행 중 대화가 사라집니다.')
        print('[itda]   → 켜려면 session.py 도크스트링의 CREATE TABLE 을 실행하세요.')
    _DB_OK = False


async def load(db, session_id: str) -> dict:
    """세션을 가져온다. 메모리에 없으면 DB 에서 되살린다.

    ⚠ 메모리를 «먼저» 본다. 백그라운드 요약이 메모리에만 써 둔 결과를 DB 값으로
      덮어쓰지 않으려는 것이다(위 도크스트링의 워커 관련 한계와 같은 이유).
    """
    if session_id in _SESSIONS:
        return get(session_id)
    st = get(session_id)                      # 빈 세션을 만들어 LRU 에 올린다
    if not (SESSION_DB and _DB_OK and db is not None):
        return st
    try:
        row = (await db.execute(
            text("SELECT state_json FROM itda_session WHERE session_id = :sid"),
            {"sid": session_id})).fetchone()
    except Exception as e:                    # noqa: BLE001 — 테이블 없음 포함
        _down('읽기', e)
        return st
    if not row or not row[0]:
        return st
    try:
        saved = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    except (TypeError, ValueError) as e:
        print(f'[itda] 세션 복원 실패(무시하고 새로 시작): {type(e).__name__}: {e}')
        return st
    if isinstance(saved, dict):
        st.update(saved)
        st.setdefault('profile', {})
        print(f'[itda] 세션 DB 복원 — 턴 {int((st.get("profile") or {}).get("_turns") or 0)}')
    return st


async def save(db, session_id: str, st: dict) -> None:
    """턴이 끝날 때 한 번 부른다. **실패해도 절대 예외를 올리지 않는다.**

    이 저장은 «있으면 좋은 것»이다. 여기서 터져서 사용자 응답이 500 이 되면
    고치려던 것보다 큰 손해다(itda_core.summarize 의 실패 처리와 같은 원칙).
    """
    if not (SESSION_DB and _DB_OK and db is not None and st):
        return
    try:
        blob = json.dumps(st, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as e:
        print(f'[itda] 세션 직렬화 실패(저장 건너뜀): {type(e).__name__}: {e}')
        return
    if len(blob.encode('utf-8')) > _MAX_STATE_BYTES:
        #  ⚠ 조용히 넘기지 않는다 — 「저장되고 있다」고 믿는 게 제일 위험하다.
        print(f'[itda] 세션이 너무 큼({len(blob)}자) — 저장 건너뜀. 메모리로는 계속 돕니다.')
        return
    try:
        await db.execute(text(
            "INSERT INTO itda_session (session_id, user_id, state_json) "
            "VALUES (:sid, :uid, :js) "
            "ON DUPLICATE KEY UPDATE state_json = VALUES(state_json), "
            "                        user_id = VALUES(user_id)"),
            {"sid": session_id, "uid": st.get("owner"), "js": blob})
        await db.commit()
    except Exception as e:                    # noqa: BLE001 — 테이블 없음 포함
        try:
            await db.rollback()
        except Exception:                     # noqa: BLE001
            pass
        _down('쓰기', e)


async def reset(db, session_id: str) -> None:
    """메모리와 DB 양쪽에서 지운다.

    ⚠ 양쪽을 다 지워야 한다. 메모리만 지우면 다음 load() 가 **DB 에서 되살려서**
      초기화가 안 된 것처럼 보인다(2026-08-06 — 만들면서 바로 밟은 구멍).
      DB 삭제가 실패해도 예외를 올리지 않는다 — 그때는 메모리만 비고,
      다음 턴의 save() 가 빈 상태로 덮어쓴다.
    """
    _SESSIONS.pop(session_id, None)
    if not (SESSION_DB and _DB_OK and db is not None):
        return
    try:
        await db.execute(text("DELETE FROM itda_session WHERE session_id = :sid"),
                         {"sid": session_id})
        await db.commit()
    except Exception as e:                    # noqa: BLE001 — 테이블 없음 포함
        try:
            await db.rollback()
        except Exception:                     # noqa: BLE001
            pass
        _down('삭제', e)

#  (2026-07-30) snapshot() 제거 — 호출부·엔드포인트가 없었다. 함께 쓰던 세션 "done" 키도 제거
#   (controllers 가 매 턴 쓰기만 하고 읽는 곳은 snapshot 뿐이었다).
