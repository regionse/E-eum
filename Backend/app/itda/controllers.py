# -*- coding: utf-8 -*-
"""
잇다 컨트롤러 — itda_core 를 프론트 계약에 맞춰 변환한다.

역할은 '번역'뿐. 판단 로직은 전부 itda_core 에 있다(CLI 와 같은 코드를 쓴다).
  itda_core.step()  →  {kind, reply, profile, missing, can_land, card}
  프론트가 기대      →  {type, reply, turn, max_turn, understanding, mode, goal, alternatives}

· 세션에는 slot(profile) 만 보관한다. 대화 로그를 쌓지 않는다.
· itda_core 는 async 다(2026-07-24). db 세션은 라우터가 Depends(get_db)로 주입한다.
"""
import asyncio
import json

from fastapi import HTTPException
from sqlalchemy import text

from app.itda import session
from app.itda.schemas import (Goal, CertStep, Course, Hire, Handoff, MessageResponse,
                              ItdaSyncStatus, SyncRun)

try:                                   # 서버(패키지) 경로
    from app.itda.itda_core import (ItdaEngine, missing_slots, ASK_ORDER, kst_today,
                                    kst_now, POLICY_HANDOFF)
except ImportError:                    # standalone 실행 경로
    from itda_core import (ItdaEngine, missing_slots, ASK_ORDER, kst_today,
                           kst_now, POLICY_HANDOFF)


# 엔진은 프로세스당 하나 — DB·직무분야 목록을 매 요청마다 다시 읽지 않는다.
_ENGINE = None

def get_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ItdaEngine()         # 지연 초기화(첫 요청 때 1회). think_level 미지정 → Gemini 기본(dynamic)
    return _ENGINE


#  ★ 프론트로 내보낼 profile — '_' 로 시작하는 내부 상태는 뺀다(2026-07-30).
#    좁히기 이력(_narrowed·_narrow_opts)·'모르겠다' 카운터(_unsure)가 브라우저로 새어나갔다.
#    사용자에게 의미도 없고, 내부 판단 로직을 그대로 노출하는 것이라 막는다.
def _public_profile(profile: dict) -> str:
    known = {k: v for k, v in (profile or {}).items() if v and not str(k).startswith("_")}
    return json.dumps(known, ensure_ascii=False)


# ── 카드 → 프론트 goal ──────────────────────────────────────────────
def _exam_text(exam):
    """exam(dict) → 사람이 읽는 한 줄. **접수 마감일을 맨 앞에** 둔다.

    사용자가 놓쳐서 1년을 기다리게 되는 날짜는 시험일이 아니라 접수 마감일이다.
    (2026-07-30: 위치 언패킹 → 키 접근으로 변경 — 컬럼 추가에 조용히 깨지지 않게.)
    """
    if not exam:
        return "다음 시험 일정이 아직 공고되지 않았어요"
    if not isinstance(exam, dict):             # 옛 튜플 형태 방어(저장된 카드 등)
        seq, doc, prac, pas = (list(exam) + [None] * 4)[:4]
        exam = {'seq': seq, 'doc': doc, 'prac': prac, 'pass': pas}
    #  ★ 올해 일정이 다 끝난 자격증 (2026-08-05, _next_exam 의 past 플래그)
    #    지난 날짜를 「접수 ~2026-05-04 (마감) · 필기 2026-05-09 …」로 늘어놓으면
    #    사용자가 그게 무슨 뜻인지 직접 읽어내야 한다. 그냥 그렇다고 말한다.
    #    ※ Q-Net API 가 당해년도만 주므로 「올해는 끝」이 우리가 아는 전부다 —
    #      내년 공고 시점을 지어내지 않는다(카드에 없는 사실은 안 쓴다는 원칙).
    if exam.get("past"):
        return "올해 시험 일정은 끝났어요 (내년 일정 공고 전)"
    bits = []
    if exam.get("reg_end"):
        #  ★ D-day(2026-07-30) — 사용자가 놓쳐서 1년을 기다리는 건 접수 마감일이다.
        #    날짜만 적어두면 남은 일수를 사용자가 손으로 세야 한다.
        tag = ""
        try:
            d = (exam["reg_end"] - kst_today()).days
            tag = f" (D-{d})" if 0 <= d <= 60 else (" (마감)" if d < 0 else "")
        except Exception:
            tag = ""
        bits.append(f"접수 ~{exam['reg_end']}{tag}")
    if exam.get("doc"):
        bits.append(f"필기 {exam['doc']}")
    if exam.get("prac"):
        bits.append(f"실기 {exam['prac']}")
    if exam.get("pass"):
        bits.append(f"발표 {exam['pass']}")
    seq = exam.get("seq")
    return f"제{seq}회 · " + " · ".join(bits) if bits else f"제{seq}회"


def _to_goal(card) -> Goal:
    """직업 먼저(2026-07-27) 카드 → 프론트 goal. 주인공은 '직업', 자격증은 그 직업의 수단(≤3)."""
    # 강좌 — 제목만 넘기던 걸 상세(교수·링크·유사도)까지. 유사도는 '관련도'라 UI에 그대로 노출.
    courses = [Course(title=c["title"], professor=c.get("professor") or "",
                      classfy=c.get("classfy") or "", url=c.get("url") or "",
                      score=float(c.get("score") or 0)) for c in (card.get("courses") or [])]
    #  이 직업의 자격증 ≤3 — 「지금 바로」 우선 정렬. entry_free 는 3값(True=제한없음 확인 /
    #  False=미확인). 미확인이면 우리가 해석하지 않고 공단 조건 원문(entry_note)을 그대로 넘긴다.
    certs = []
    for c in (card.get("certs") or []):
        free = bool(c.get("entry_free"))
        certs.append(CertStep(
            cert=c["cert"], grade=c.get("grade") or "", entry_free=free,
            entry="조건 없음" if free else "응시자격 확인 필요",
            entry_note="" if free else (c.get("entry_note") or ""),
            exam=_exam_text(c.get("exam")),
            verified=bool(c.get("verified")),
            #  ★ 2026-08-04 — 연 회차 수. 화면이 「자주 열려요」 배지로 쓸 수 있다.
            exam_n=int(c.get("exam_n") or 0),
            often=bool(c.get("often")),
            exam_method=c.get("exam_method") or "",
            outlook=c.get("outlook") or "",
            qual_gb=c.get("qual_gb") or "",
            evidence=c.get("evidence") or "",
        ))
    job = card.get("job") or {}
    hd = card.get("hire") or {}
    return Goal(
        job=job.get("name") or "",
        group=job.get("group") or "",
        description=job.get("description") or "",       # NCS 설명(2026-07-29)
        reason=card.get("job_reason", ""),
        certs=certs,
        no_cert_path=bool(card.get("no_cert_path")),
        guide=card.get("guide") or "",
        has_courses=bool(courses),
        courses=courses,
        hire=Hire(label=hd.get("label", ""), url=hd.get("url", ""),
                  note=hd.get("note", "")) if hd else None,          # 국비 딥링크
    )


def _progress(profile):
    """슬롯이 얼마나 찼는지를 진행도로 보여준다."""
    total = len(ASK_ORDER)
    return total - len(missing_slots(profile)), total


# ── 한 턴 ───────────────────────────────────────────────────────────
#  db 는 라우터가 Depends(get_db) 로 요청마다 주입하는 async 세션.
#  예전엔 run_in_threadpool 로 동기 step 을 스레드에 던졌는데, 그 스레드들이
#  전역 pymysql 커넥션을 공유해 깨졌다(코드리뷰 HIGH). 이제 step 이 async 라 그냥 await.
async def handle_message(db, session_id: str, message: str,
                         user_id: int | None = None) -> MessageResponse:
    st = session.get(session_id)
    #  ★ 2026-08-06 — **대화 자체를 소유자 확인한다.**
    #    예전엔 저장(save_map)·이어서하기(resume_map)에만 검증이 있었다. 그런데 정작
    #    보호하려던 값(제약 슬롯 — 학력부담·체력부담·비용부담)은 이 엔드포인트가
    #    understanding=_public_profile(profile) 로 **매 턴 그대로 돌려주고** 있었다.
    #    남의 session_id 를 아는 사람이 /itda/message 한 번이면 슬롯을 받아갔다.
    if user_id is not None:
        _claim_session(st, user_id)
    profile = st.get("profile") or {}

    try:
        eng = get_engine()
        #  ★ 이번 턴 사용량 (2026-08-04) — 엔진은 프로세스당 하나라 total_usage 가 계속 쌓인다.
        #    호출 전후 차이를 떠서 **이 턴에 쓴 것만** 응답에 담는다.
        _u0 = dict(eng.total_usage)
        r = await eng.step(db, profile, message)
    except Exception as e:
        print(f"[itda] step 실패: {type(e).__name__}: {e}")   # 서버 로그에만 남긴다
        done, total = _progress(profile)
        return MessageResponse(
            type="blocked",
            reply="지금 잠시 연결이 원활하지 않아요. 잠시 후 다시 말씀해 주실래요?",
            turn=done, max_turn=total,
            understanding=_public_profile(profile),
            mode="error",
        )

    profile = r["profile"]
    #  ★ 2026-08-04 — 이번에 봇이 한 말을 다음 턴 프롬프트용으로 남긴다.
    #    '_' 로 시작하므로 모델에게 슬롯으로 보이지 않고(profile_text 가 걸러냄),
    #    화면에도 안 나간다(_public_profile 이 걸러냄). 오직 지시대명사 해석용이다.
    #    길면 자른다 — 필요한 건 '무엇을 물었나'지 문장 전체가 아니다.
    if r.get("reply"):
        profile["_last_ask"] = str(r["reply"])[:300]
    #  대화 이력 — HISTORY_MODE='full' 이 읽는다. 최근 것만 남겨 무한히 커지지 않게 한다.
    #  r={'r':'u'|'b','t':텍스트} 로 짧게 담는다(키 이름이 길면 그것만으로 토큰이 는다).
    hist = list(profile.get("_history") or [])
    hist.append({"r": "u", "t": str(message)[:300]})
    if r.get("reply"):
        hist.append({"r": "b", "t": str(r["reply"])[:300]})

    #  ★ 최근 창을 넘긴 앞부분은 버리지 않고 요약해 이어 붙인다(2026-08-04).
    #    요약은 **응답을 보낸 뒤 백그라운드로** 돌린다 — 다음 턴에나 필요한 값이라
    #    지금 기다릴 이유가 없다. 사용자는 답을 바로 받는다.
    keep = eng.HISTORY_TURNS * 2
    if len(hist) > eng.SUMMARIZE_AFTER * 2:
        overflow, hist = hist[:-keep], hist[-keep:]

        async def _fold(sid, old, chunk):
            new = await eng.summarize(old, chunk)
            s = session.get(sid)                     # 그 사이 바뀌었을 수 있어 다시 읽는다
            if s.get("profile") is not None:
                s["profile"]["_summary"] = new

        asyncio.create_task(_fold(session_id, profile.get("_summary") or "", overflow))

    #  ★ 분야(관심대분류) 갱신도 백그라운드로 (2026-08-04).
    #    step() 이 '_think_stale' 을 남기면 여기서 큰 모델을 돌려 **다음 턴**에 반영한다.
    #    이번 턴을 5.5초 붙잡지 않으려는 것 — 첫 착지(분야를 아예 모를 때)만 기다린다.
    stale_sig = profile.pop("_think_stale", None)
    if stale_sig:
        async def _rethink(sid, snap, last, sig):
            th = await eng.think(snap, last)
            if not th:
                return
            p = session.get(sid).get("profile")     # 그 사이 바뀌었을 수 있어 다시 읽는다
            if p is None:
                return
            if th.get("관심대분류") is not None:
                p["관심대분류"] = [x for x in th["관심대분류"] if x]
            p["_think_sig"] = sig                   # 같은 슬롯 상태로 또 부르지 않게

        asyncio.create_task(_rethink(session_id, dict(profile),
                                     str(message)[:300], stale_sig))

    profile["_history"] = hist
    st["profile"] = profile
    done, total = _progress(profile)

    kind = r["kind"]
    #  notfound = 사용자가 콕 집어 말한 목표가 우리 613종에 없는 경우.
    #  대화는 계속돼야 하므로 프론트에는 ask 로 내보낸다(문구는 코드가 이미 써 뒀다).
    msg_type = "result" if kind == "card" else ("blocked" if kind == "blocked" else "ask")

    reply = r["reply"]
    #  ★ OFFRAMP = 「어떤 일에도 이어주기 어렵다」 → 이건 정의상 **덜다로 건네야 하는** 경우다.
    #    예전엔 문장 한 줄만 덧붙이고 아무 데도 안 보냈다(2026-08-04 이전).
    handoff = r.get("handoff")
    if kind == "offramp":
        reply += "\n\n지금은 자격증보다 돌봄 지원이나 바로 해볼 수 있는 일부터 보는 것도 좋아요."
        handoff = handoff or dict(POLICY_HANDOFF)

    card = r.get("card")
    if card:
        st["last_card"] = card                 # 미래설계지도 '저장'용 — 마지막 카드를 세션에 캐시(2026-07-29)
    #  코드감사 #6 — 강좌 매칭 실패(Pinecone/임베딩 장애)를 조용히 삼키지 않고 서버 로그에 남긴다.
    if card and card.get("course_error"):
        print(f"[itda] 강좌 매칭 실패(카드는 나감): {card['course_error']}")
    # 카드가 있으면 다른 후보 직업을, 못 찾았으면 가까운 직업들을 alternatives 로 내보낸다
    alts = ([c["job"] for c in (r.get("near") or [])] if kind == "notfound"
            else (card or {}).get("alternatives", []))
    #  코드감사 — _to_goal 은 step() try 밖이라, 카드에 필수 키가 없으면 여기서 500이 난다.
    #  감싸서 변환 실패해도 대화가 죽지 않게(결과 대신 ask 로 유지) 한다.
    goal = None
    if card:
        try:
            goal = _to_goal(card)
        except Exception as e:
            print(f"[itda] 카드→goal 변환 실패: {type(e).__name__}: {e}")
            msg_type = "ask"
    return MessageResponse(
        type=msg_type,
        reply=reply,
        turn=done,
        max_turn=total,
        understanding=_public_profile(profile),
        mode="gemini",
        goal=goal,
        alternatives=alts,
        options=r.get("options") or [],
        option_notes=r.get("option_notes") or [],
        handoff=Handoff(**handoff) if handoff else None,
        usage={k: eng.total_usage.get(k, 0) - _u0.get(k, 0)
               for k in ("in", "out", "think", "cached", "calls")},
    )


# ─────────────────────────────────────────────────────────────────────
#  미래설계지도 (저장 · 목록 · 이어서하기 · 삭제) — 2026-07-29
#  itda_map(user·job_code·profile_json) + itda_map_cert + itda_map_course.
#  저장은 세션에 캐시된 '마지막 카드'(last_card)를 그대로 담는다 → 프론트가 id 를 되돌릴 필요 없음.
# ─────────────────────────────────────────────────────────────────────
def _hire(job_name: str) -> Hire:
    import urllib.parse
    url = ('https://m.work24.go.kr/hr/a/a/1100/trnnCrsInf.do?'
           f'keyword={urllib.parse.quote(job_name)}&searchYn=Y')
    return Hire(label=f"'{job_name}' 국비 훈련 찾기", url=url,
                note='국민내일배움카드로 훈련비 지원 · 고용24(HRD-Net)에서 검색')


async def _saved_goal(db, map_id: int) -> Goal:
    """저장된 지도(map_id) → Goal 재구성 (직무·설명·자격·강좌·국비링크)."""
    m = (await db.execute(text(
        "SELECT jc.job_name, jc.job_mcls_name, jc.job_description, im.profile_json "
        "FROM itda_map im JOIN job_catalog jc ON jc.job_code = im.job_code "
        "WHERE im.map_id = :mid"), {"mid": map_id})).fetchone()
    #  JOIN 이 안 맞으면(직업코드가 카탈로그에서 사라진 경우) m 이 None 이라 아래에서 500 이 났다.
    if not m:
        raise HTTPException(status_code=404, detail="지도의 직업 정보를 찾을 수 없어요.")
    cert_rows = (await db.execute(text(
        "SELECT c.jm_name, COALESCE(c.grade_std, c.grade), c.entry_free, c.entry_note "
        "FROM itda_map_cert mc JOIN certification c ON c.cert_id = mc.cert_id "
        "WHERE mc.map_id = :mid ORDER BY mc.`rank`"), {"mid": map_id})).fetchall()
    course_rows = (await db.execute(text(
        "SELECT co.title, co.professor, co.classfy_name, co.course_url, mco.similarity_score "
        "FROM itda_map_course mco JOIN course co ON co.course_id = mco.course_id "
        "WHERE mco.map_id = :mid ORDER BY mco.`rank`"), {"mid": map_id})).fetchall()
    certs = [CertStep(cert=r[0], grade=r[1] or "", entry_free=(r[2] == 1),
                      entry="조건 없음" if r[2] == 1 else "응시자격 확인 필요",
                      entry_note="" if r[2] == 1 else (r[3] or "")) for r in cert_rows]
    courses = [Course(title=r[0], professor=r[1] or "", classfy=r[2] or "",
                      url=r[3] or "", score=float(r[4] or 0)) for r in course_rows]
    #  저장할 때 profile_json 안에 담아둔 추천 이유를 되살린다(save_map 의 '_job_reason').
    reason = ""
    try:
        pj = m[3]
        pj = json.loads(pj) if isinstance(pj, str) else (pj or {})
        reason = (pj or {}).get("_job_reason") or ""
    except Exception:
        reason = ""
    return Goal(
        job=m[0], group=m[1] or "", description=m[2] or "", reason=reason,
        certs=certs, no_cert_path=(len(certs) == 0),
        guide=('이 방향은 국가기술자격으로 바로 이어지진 않아요. 국민내일배움카드로 '
               '훈련비를 지원받아 아래 강좌부터 시작할 수 있어요.') if not certs else "",
        has_courses=bool(courses), courses=courses, hire=_hire(m[0]),
    )


def _claim_session(st: dict, user_id: int) -> None:
    """이 세션이 이 사용자의 것인지 확인하고, 처음이면 소유자로 표시한다 (2026-08-05).

    왜 필요한가 — `session_id` 는 **프론트가 만들어 보내는 값**이다.
    그래서 예전엔 로그인한 A 가 B 의 session_id 를 넘기면 **B 의 카드와 B 의 profile_json 이
    A 의 지도로 저장**됐고, 그대로 A 가 조회할 수 있었다.
    새어나가는 값이 가볍지 않다 — 제약 슬롯에는 학력부담·체력부담·비용부담이 들어 있다.
    ⚠ 실제 악용에는 B 의 session_id(무작위 11자)를 알아야 하므로 무차별 대입은 비현실적이다.
      그래도 **인증 경계에 검증이 없다는 것 자체가 문제**라 막는다.

    ★ 2026-08-06 — 「비로그인 대화도 허용해야 한다」는 옛 주석을 지웠다. **그런 경로는 없다.**
      덜다·잇다·나누다 모두 로그인이 필요하다(이음이 없는 것은 로그인이 아니라 *본인확인*이다).
      그래서 이제 /itda/message · /itda/reset 도 이 검증을 지난다.
      '처음 만지는 로그인 사용자'가 소유자가 되는 규칙은 그대로 둔다 —
      세션이 메모리라 서버가 재시작되면 소유자 표시도 함께 사라지기 때문이다.
    """
    owner = st.get("owner")
    if owner is not None and owner != user_id:
        raise HTTPException(status_code=403, detail="이 대화의 결과가 아니에요.")
    st["owner"] = user_id


def claim_session(session_id: str, user_id: int) -> None:
    """세션 소유자 확인만 한다 (2026-08-06). /itda/reset 처럼 st 를 안 만지는 자리에서 쓴다.

    reset 도 막아야 하는 이유 — 남의 session_id 를 알면 **진행 중인 대화를 지울 수 있다.**
    """
    _claim_session(session.get(session_id), user_id)


async def save_map(db, user_id: int, session_id: str) -> dict:
    """세션에 캐시된 마지막 카드를 미래설계지도로 저장 (로그인 사용자 소유)."""
    st = session.get(session_id)
    _claim_session(st, user_id)
    card = st.get("last_card") or {}
    job_code = (card.get("job") or {}).get("code")

    #  ★ '이어서하기' 세션 대응(2026-07-30 · 사용자 신고) — resume 로 들어온 세션은 새 대화를 안 했으니
    #    last_card 가 비어 있다. 예전엔 그 상태에서 저장을 누르면 400("아직 저장할 결과가 없어요")만 떴다.
    #    이미 저장된 그 지도를 already=True 로 돌려준다(프론트가 안내하고 목록으로 보낼 수 있게).
    if not job_code:
        rid = st.get("resumed_map_id")
        if rid:
            row = (await db.execute(text(
                "SELECT im.map_id, jc.job_name FROM itda_map im "
                "JOIN job_catalog jc ON jc.job_code = im.job_code "
                "WHERE im.map_id = :mid AND im.user_id = :uid"),
                {"mid": rid, "uid": user_id})).fetchone()
            if row:
                return {"ok": True, "map_id": row[0], "job": row[1], "already": True}
        raise HTTPException(status_code=400,
                            detail="아직 저장할 결과가 없어요. 대화로 직업을 찾은 뒤 저장해 주세요.")

    profile = dict(st.get("profile") or {})
    #  ★ 2026-08-04 — 대화 이력은 저장하지 않는다.
    #    _history 는 다음 턴 프롬프트용 임시 상태다. 지도에 넣으면 한 장마다 최대 7천 자가
    #    붙고, '이어서하기'로 복원했을 때 남의 옛 대화가 프롬프트에 섞인다.
    #    지도가 담아야 하는 건 **결론(슬롯·직업·이유)**이지 과정이 아니다.
    profile.pop("_history", None)
    profile.pop("_last_ask", None)
    #  ★★ 2026-08-05 (코드감사) — **저장이 500 으로 죽고 있었다.**
    #    _last_certs(2026-08-04 추가)는 「시험이 언제예요?」에 DB 값 그대로 답하려고 남겨둔
    #    **다음 턴용 임시 상태**인데, 그 안의 exam 은 _next_exam() 이 DB 에서 꺼낸
    #    `datetime.date` 객체다. aiomysql 은 DATE 를 문자열이 아니라 date 로 준다.
    #    아래 json.dumps 에는 default= 가 없다 →
    #      TypeError: Object of type date is not JSON serializable → 라우터에 try 도 없어 HTTP 500.
    #    시험일정이 있는 자격증이 붙은 카드(=거의 모든 카드)를 받은 뒤 「저장」하면 터졌다.
    #    위 주석의 원칙 그대로다 — 지도는 **결론**을 담는다. 이건 과정이므로 뺀다.
    profile.pop("_last_certs", None)
    #  그리고 같은 사고가 다시 나지 않게 직렬화에 안전망을 둔다(날짜가 또 섞여 들어와도
    #  저장이 죽지는 않는다). 위 pop 이 1차 방어, 이것이 2차다.
    _dump = lambda p: json.dumps(p, ensure_ascii=False, default=str)   # noqa: E731
    #  ★ 추천 이유를 함께 저장한다(2026-07-30) — 대화 카드엔 나오는데 저장된 지도엔 없었다.
    #    itda_map 에 컬럼이 없어 profile_json 안에 '_' 키로 담는다('_' 는 노출 필터가 걸러낸다).
    if card.get("job_reason"):
        profile["_job_reason"] = card["job_reason"]

    #  ★ 중복 저장 방지 — 같은 직업 지도를 이미 갖고 있으면 새 행을 만들지 않는다.
    #    단, '그냥 옛 지도를 돌려주기'만 하면 대화를 더 해서 갱신된 카드(자격증·강좌·슬롯)가
    #    조용히 버려진다 → 사용자는 저장했다고 믿는데 내용이 옛것이다. 그래서 **덮어쓴다**.
    dup = (await db.execute(text(
        "SELECT map_id FROM itda_map WHERE user_id = :uid AND job_code = :jc "
        "ORDER BY created_at DESC LIMIT 1"), {"uid": user_id, "jc": job_code})).fetchone()
    if dup:
        map_id = dup[0]
        done, _ = _progress(profile)
        await db.execute(text(
            "UPDATE itda_map SET progress_step = :ps, profile_json = :pj WHERE map_id = :mid"),
            {"ps": done, "pj": _dump(profile), "mid": map_id})
        #  자격증·강좌는 통째로 다시 넣는다(카드가 바뀌었을 수 있다).
        await db.execute(text("DELETE FROM itda_map_cert WHERE map_id = :mid"), {"mid": map_id})
        await db.execute(text("DELETE FROM itda_map_course WHERE map_id = :mid"), {"mid": map_id})
        await _fill_map_children(db, map_id, card)
        await db.commit()
        return {"ok": True, "map_id": map_id,
                "job": (card.get("job") or {}).get("name") or "", "already": True}

    done, _ = _progress(profile)
    res = await db.execute(text(
        "INSERT INTO itda_map (user_id, job_code, status, progress_step, profile_json, created_at) "
        "VALUES (:uid, :jc, '진행중', :ps, :pj, :now)"),
        {"uid": user_id, "jc": job_code, "ps": done,
         "pj": _dump(profile),
         "now": kst_now()})
    map_id = res.lastrowid
    await _fill_map_children(db, map_id, card)
    await db.commit()
    return {"ok": True, "map_id": map_id,
            "job": (card.get("job") or {}).get("name") or "", "already": False}


async def _fill_map_children(db, map_id: int, card: dict) -> None:
    """지도의 자격증·강좌 행을 넣는다 — 신규 저장과 덮어쓰기가 같은 코드를 쓰게(2026-07-30)."""
    for i, c in enumerate(card.get("certs") or []):
        if c.get("cert_id"):
            await db.execute(text(
                "INSERT INTO itda_map_cert (map_id, cert_id, `rank`, is_next_step) "
                "VALUES (:m, :c, :r, 0)"), {"m": map_id, "c": c["cert_id"], "r": i + 1})
    for i, c in enumerate(card.get("courses") or []):
        if c.get("course_id"):
            await db.execute(text(
                "INSERT INTO itda_map_course (map_id, course_id, `rank`, similarity_score) "
                "VALUES (:m, :c, :r, :s)"),
                {"m": map_id, "c": c["course_id"], "r": i + 1, "s": c.get("score")})


async def list_maps(db, user_id: int) -> list[dict]:
    """내 미래설계지도 목록 (최신순)."""
    rows = (await db.execute(text(
        "SELECT im.map_id, jc.job_name, jc.job_mcls_name, im.status, im.progress_step, im.created_at, "
        "  (SELECT COUNT(*) FROM itda_map_cert WHERE map_id = im.map_id), "
        "  (SELECT COUNT(*) FROM itda_map_course WHERE map_id = im.map_id) "
        "FROM itda_map im JOIN job_catalog jc ON jc.job_code = im.job_code "
        "WHERE im.user_id = :uid ORDER BY im.created_at DESC"), {"uid": user_id})).fetchall()
    return [{"map_id": r[0], "job": r[1], "group": r[2] or "", "status": r[3],
             "progress_step": r[4], "created_at": r[5].isoformat() if r[5] else None,
             "n_cert": r[6], "n_course": r[7]} for r in rows]


async def get_map(db, user_id: int, map_id: int) -> dict:
    """저장된 지도 상세 — 세션을 건드리지 않는 '읽기 전용' 조회(잇다 홈 팝업용, 2026-07-30).
    resume_map 은 세션 슬롯을 덮어써서 단순 열람에는 쓸 수 없었다."""
    own = (await db.execute(text(
        "SELECT 1 FROM itda_map WHERE map_id = :mid AND user_id = :uid"),
        {"mid": map_id, "uid": user_id})).fetchone()
    if not own:
        raise HTTPException(status_code=404, detail="지도를 찾을 수 없어요.")
    goal = await _saved_goal(db, map_id)
    return {"ok": True, "map_id": map_id, "goal": goal.model_dump()}


async def resume_map(db, user_id: int, map_id: int, session_id: str) -> dict:
    """저장된 지도를 이어서 — 슬롯(profile)을 세션에 복원 + goal 재구성해 돌려준다."""
    row = (await db.execute(text(
        "SELECT profile_json FROM itda_map WHERE map_id = :mid AND user_id = :uid"),
        {"mid": map_id, "uid": user_id})).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="지도를 찾을 수 없어요.")
    profile = {}
    if row[0]:
        try:
            profile = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except Exception as e:
            #  조용히 {} 로 밀어버리면 사용자는 슬롯이 왜 사라졌는지 알 수 없다 → 로그를 남긴다.
            print(f"[itda] 지도 {map_id} profile_json 파싱 실패 — 슬롯 복원 없이 진행: "
                  f"{type(e).__name__}: {e}")
            profile = {}
    st = session.get(session_id)
    #  ★ 여기도 남의 세션을 덮어쓸 수 있다 — 데이터가 새지는 않지만 남의 대화가 망가진다.
    _claim_session(st, user_id)
    st["profile"] = profile                       # 세션에 슬롯 복원 → 대화 이어감
    st["last_card"] = None
    st["resumed_map_id"] = map_id                 # 저장 버튼이 '이미 저장됨'을 알 수 있게(save_map 참고)
    goal = await _saved_goal(db, map_id)
    return {"ok": True, "session_id": session_id, "profile": profile,
            "goal": goal.model_dump()}


async def delete_map(db, user_id: int, map_id: int) -> dict:
    row = (await db.execute(text(
        "SELECT 1 FROM itda_map WHERE map_id = :mid AND user_id = :uid"),
        {"mid": map_id, "uid": user_id})).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="지도를 찾을 수 없어요.")
    await db.execute(text("DELETE FROM itda_map_cert WHERE map_id = :mid"), {"mid": map_id})
    await db.execute(text("DELETE FROM itda_map_course WHERE map_id = :mid"), {"mid": map_id})
    await db.execute(text("DELETE FROM itda_map WHERE map_id = :mid"), {"mid": map_id})
    await db.commit()
    return {"ok": True}


# ── 관리자 · 임베딩 관리 (2026-08-02) ───────────────────────────────
#  덜다(ADDUL-001)·나누다(ADSHA-001) 화면과 같은 항목을 한 번에 돌려준다.
#
#  값이 어디서 오나
#    시각·신규·변경·임베딩  →  itda_sync_log   (배치가 돌 때마다 한 줄씩 쌓인다)
#    총계                   →  각 테이블 COUNT
#    임베딩 완료            →  content_hash 가 채워진 행 수
#
#  ※ '신규/변경'은 배치가 content_hash 를 비교해 넣은 값이다(scripts/_common.diff_by_hash).
#    화면이 계산하는 게 아니라 **실행 당시의 사실**을 그대로 보여준다.
def _fmt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


async def get_sync_status(db) -> ItdaSyncStatus:
    #  ① 마지막 실행 시각 — 적재(load_*)와 임베딩(embed_*)을 나눠 본다
    row = (await db.execute(text(
        "SELECT (SELECT MAX(finished_at) FROM itda_sync_log "
        "          WHERE target LIKE 'load\\_%' AND status <> 'error') AS api_at, "
        "       (SELECT MAX(finished_at) FROM itda_sync_log "
        "          WHERE target LIKE 'embed\\_%' AND status <> 'error') AS emb_at"
    ))).fetchone()
    api_at, emb_at = (row[0], row[1]) if row else (None, None)

    #  ② 총계 + 임베딩 완료(해시가 찍힌 행)
    tot = (await db.execute(text(
        "SELECT (SELECT COUNT(*) FROM certification), "
        "       (SELECT COUNT(*) FROM job_catalog), "
        "       (SELECT COUNT(*) FROM course), "
        "       (SELECT COUNT(*) FROM certification WHERE content_hash <> ''), "
        "       (SELECT COUNT(*) FROM course        WHERE content_hash <> '')"
    ))).fetchone()

    #  ③ 최근 7일 실패 — 화면의 '실패한 N건'
    failed = (await db.execute(text(
        "SELECT COUNT(*) FROM itda_sync_log "
        "WHERE status <> 'ok' AND finished_at > NOW() - INTERVAL 7 DAY"
    ))).scalar() or 0

    #  ④ 대상별 '가장 최근 실행' 한 줄씩
    rows = (await db.execute(text(
        "SELECT target, finished_at, fetched, inserted, updated, embedded, status, message "
        "FROM itda_sync_log s "
        "WHERE id = (SELECT MAX(id) FROM itda_sync_log WHERE target = s.target) "
        "ORDER BY finished_at DESC"
    ))).fetchall()

    return ItdaSyncStatus(
        last_api_sync=_fmt(api_at),
        last_embedding=_fmt(emb_at),
        cert_total=tot[0] or 0, job_total=tot[1] or 0, course_total=tot[2] or 0,
        cert_embedded=tot[3] or 0, course_embedded=tot[4] or 0,
        failed_recent=int(failed),
        runs=[SyncRun(target=r[0], finished_at=_fmt(r[1]), fetched=r[2] or 0,
                      inserted=r[3] or 0, updated=r[4] or 0, embedded=r[5] or 0,
                      status=r[6] or "", message=r[7] or "") for r in rows],
    )
