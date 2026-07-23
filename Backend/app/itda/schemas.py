# -*- coding: utf-8 -*-
"""잇다 요청/응답 스키마 (Pydantic)."""
from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    session_id: str = Field(..., description="프론트가 생성·유지하는 대화 세션 id")
    message: str = Field(..., min_length=1, description="사용자 발화")


class ResetRequest(BaseModel):
    session_id: str


class NextStep(BaseModel):
    """지도의 '그 다음' — 같은 분야의 상위 등급."""
    cert: str                       # 다음 자격증
    grade: str = ""                 # 산업기사 / 기사 …
    entry_note: str = ""            # 그 등급의 응시자격 조건 (Q-Net 원문)


class Goal(BaseModel):
    cert: str                       # 목표 자격증
    field: str                      # 직무분야
    reason: str = ""                # 이 사람에게 맞는 이유(투명성)
    exam: str                       # 시험 일정 (카탈로그에서)
    has_courses: bool               # K-MOOC 무료강좌 존재?
    courses: list[str] = []         # 추천 강좌 (있을 때만)
    guide: str = ""                 # 강좌 없을 때 훈련 안내
    # ── 2026-07-23 추가 (프론트가 아직 안 그려도 무방) ──
    grade: str = ""                 # 기능사 / 산업기사 …
    entry: str = ""                 # 「지금 바로 응시 가능」 / 「응시자격 확인 필요」
    entry_note: str = ""            # 미확인일 때 보여줄 등급별 조건 원문
    next_step: NextStep | None = None


class MessageResponse(BaseModel):
    type: str                       # "ask" | "result" | "blocked"
    reply: str                      # 사용자에게 보여줄 말
    turn: int = 0
    max_turn: int = 3
    understanding: str = ""         # LLM이 이해한 요약 (디버깅·투명성용)
    mode: str = "gemini"            # "gemini" | "stub"  ← 폴백 발동 여부
    goal: Goal | None = None        # type=result일 때만
    alternatives: list[str] = []    # 다른 후보 자격증
