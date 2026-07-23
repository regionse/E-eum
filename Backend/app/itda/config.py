# -*- coding: utf-8 -*-
"""잇다 백엔드 설정 — Gemini 키 로딩 + 상수."""
import os

MODEL = "gemini-2.5-flash"   # 2.0-flash는 무료 쿼터 429가 잦아 2.5-flash 사용
# 대화 길이는 AI가 '충분하다(enough)'고 판단할 때 동적으로 끝난다.
# 아래는 강제 종료가 아니라 무한루프 방지용 '안전 상한'일 뿐 — 실제로는 거의 안 걸린다.
SAFETY_TURN_LIMIT = 8


def _read_key_from(path: str) -> str:
    if not os.path.exists(path):
        return ""
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if s.startswith("GEMINI_API_KEY") and "=" in s:
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _load_gemini_key() -> str:
    # 1) 환경변수 우선 (운영 배포 시 권장)
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    # 2) 모듈 위치에서 위로 올라가며 etc/.env 또는 .env 탐색 (폴더 이동에 안전)
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        for cand in (os.path.join(d, "etc", ".env"), os.path.join(d, ".env")):
            v = _read_key_from(cand)
            if v:
                return v
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return ""


GEMINI_KEY = _load_gemini_key()
