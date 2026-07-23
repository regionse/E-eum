# -*- coding: utf-8 -*-
"""잇다의 '뇌' — Gemini 상담/결정 + 실패 시 규칙 스텁 폴백.

두 함수 모두 (결과, mode) 반환. mode = "gemini" | "stub".
Gemini가 쿼터초과·타임아웃·오류면 규칙 스텁으로 자동 강등 → 서비스가 절대 안 죽는다.
"""
import json
import urllib.request

from app.itda import config
from app.itda.catalog import CATALOG, CERT_NAMES

SYSTEM = (
    "너는 '잇다'의 따뜻한 진로 상담사다. 대상은 가족 돌봄으로 학업을 접은 13~34세 청년.\n"
    "목표: 대화로 이 '사람'을 이해해서 아래 자격증 목록 중 어울리는 걸 찾아준다.\n"
    "규칙: (1) 절대 '어느 자격증 원하세요?'라 묻지 마라 — 사용자는 모른다. "
    "(2) 관심·좋아하는 활동·가치·제약(집/야외, 몸/머리, 돌봄병행)을 부드럽게 물어라. "
    "(3) 먼저 공감·반영한 뒤 한 걸음 더 파고들어라. "
    "(4) 충분히 이해됐다 싶을 때 후보를 정하라 — 억지로 몇 턴 안에 끝내려 말고, 반대로 불필요하게 끌지도 마라. "
    "(5) 구체적인 시험 날짜나 강좌 이름은 네가 말하지 마라 — 그건 마지막 결과 카드가 보여준다.\n"
    f"자격증 목록(여기서만 골라라): {CERT_NAMES}\n"
    '매 턴 JSON만 출력: {"reply":"따뜻한 말","summary":"이 사람 이해 요약",'
    '"enough":true/false,"candidates":["목록 중 1~2개(enough=true일 때만)"]}'
)

# 규칙 스텁용 키워드 → 자격증
RULES = [
    (("나무", "식물", "조경", "꽃", "정원", "야외", "자연"), "조경기능사"),
    (("컴퓨터", "프로그", "코딩", "데이터", "앱", "소프트", "개발"), "프로그래밍기능사"),
    (("디자인", "그림", "포토샵", "웹디자인", "편집"), "웹디자인개발기능사"),
    (("사람", "돕", "복지", "상담", "돌봄", "봉사"), "사회복지사2급"),
    (("요리", "빵", "제과", "제빵", "베이킹", "디저트"), "제과기능사"),
    (("지게차", "운전", "현장", "기계", "중장비", "물류"), "지게차운전기능사"),
]


def _call(contents, temp):
    body = json.dumps({"contents": contents,
        "generationConfig": {"responseMimeType": "application/json", "temperature": temp}}).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.MODEL}:generateContent?key={config.GEMINI_KEY}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        j = json.loads(r.read().decode())
    return json.loads(j["candidates"][0]["content"]["parts"][0]["text"])


# ── ② 상담 턴 ──
def counsel_turn(history, user, summary):
    if config.GEMINI_KEY:
        try:
            msgs = [{"role": "user", "parts": [{"text": SYSTEM}]},
                    {"role": "model", "parts": [{"text": "네, 준비됐어요."}]}]
            for h in history:
                msgs.append({"role": "user", "parts": [{"text": h["user"]}]})
                msgs.append({"role": "model", "parts": [{"text": h.get("reply", "")}]})
            msgs.append({"role": "user", "parts": [{"text": f"(지금까지 요약: {summary})\n사용자: {user}"}]})
            return _call(msgs, 0.7), "gemini"
        except Exception:
            pass   # ↓ 폴백
    return _stub_counsel(history, user, summary), "stub"


def _stub_counsel(history, user, summary):
    blob = " ".join(h["user"] for h in history) + " " + user
    hits = [c for kws, c in RULES if any(k in blob for k in kws)]
    new_summary = (summary + " | " if summary else "") + user
    if hits and len(history) >= 2:
        return {"reply": "", "summary": new_summary, "enough": True, "candidates": hits[:1]}
    if any(k in blob for k in ("나무", "식물", "조경")):
        reply = "아, 나무 다루는 걸 좋아하시는군요. 만들고 다듬는 쪽이 끌리세요, 아니면 밖에서 심고 가꾸는 쪽이 좋으세요?"
    elif hits:
        reply = "오, 그쪽에 관심이 있으시군요. 그걸 할 때 집에서 혼자가 편하세요, 밖에서 몸 쓰는 게 좋으세요?"
    else:
        reply = "말씀 고마워요. 요즘 뭘 할 때 시간 가는 줄 모르세요? 사소한 것도 좋아요."
    return {"reply": reply, "summary": new_summary, "enough": False, "candidates": []}


# ── ②b 사람 → 자격증 '결정' (착지 시, 요약을 근거로 강제 선택) ──
def decide_cert(history, summary):
    if config.GEMINI_KEY:
        try:
            fields = ", ".join(f"{k}({v['field']})" for k, v in CATALOG.items())
            convo = " / ".join(h["user"] for h in history)
            prompt = (f"진로상담 요약: {summary}\n사용자 발화: {convo}\n\n"
                      f"이 사람에게 가장 어울리는 자격증을 아래 목록에서 1~2개만 골라라(목록 밖 금지).\n"
                      f"목록: {fields}\n"
                      '반드시 JSON만: {"candidates":["자격증명"],"reason":"이 사람에게 맞는 이유 한 줄"}')
            out = _call([{"role": "user", "parts": [{"text": prompt}]}], 0.3)
            cands = [c for c in out.get("candidates", []) if c in CATALOG]
            if cands:
                return cands[:2], out.get("reason", ""), "gemini"
        except Exception:
            pass
    blob = summary + " " + " ".join(h["user"] for h in history)
    for kws, c in RULES:
        if any(k in blob for k in kws):
            return [c], "(규칙 매칭)", "stub"
    return ["프로그래밍기능사"], "(기본 추천)", "stub"
