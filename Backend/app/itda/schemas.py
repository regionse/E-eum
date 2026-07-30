# -*- coding: utf-8 -*-
"""잇다 요청/응답 스키마 (Pydantic)."""
from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    #  session_id min_length=1 — 빈 문자열이면 여러 클라이언트가 한 세션을 공유해 프로필이 섞인다(코드감사)
    session_id: str = Field(..., min_length=1, description="프론트가 생성·유지하는 대화 세션 id")
    #  max_length — 상한이 없으면 대용량 발화가 그대로 LLM 프롬프트로 들어가 토큰비용이 폭증한다
    message: str = Field(..., min_length=1, max_length=2000, description="사용자 발화")


class ResetRequest(BaseModel):
    session_id: str


class Course(BaseModel):
    """추천 강좌 (K-MOOC). 상세팝업·링크용 정보 포함."""
    title: str                      # 강좌 제목
    professor: str = ""             # 교수/기관
    classfy: str = ""               # 분류
    url: str = ""                   # K-MOOC 수강 링크 (외부)
    score: float = 0.0              # 유사도 = '관련도'(보장 아님). UI에 그대로 노출


class CertStep(BaseModel):
    """직업으로 가는 자격증 한 개 (cert_job 역방향). 「지금 바로」 우선 정렬."""
    cert: str                       # 종목명
    grade: str = ""                 # 기능사 / 산업기사 / 기사 …
    entry_free: bool = False        # 제한없음(지금 바로 응시 가능) 확인?
    entry: str = ""                 # 「지금 바로 응시 가능」 / 「응시자격 확인 필요」
    entry_note: str = ""            # 미확인일 때 등급별 조건 원문 (hover)
    exam: str = ""                  # 다음 시험일
    verified: bool = False          # cert_job 검증된 연결인지


class Hire(BaseModel):
    """국비 실전훈련 핸드오프 — 고용24(HRD-Net) 훈련검색 딥링크 (2026-07-29).
    카탈로그 API 는 게이트라 '이 직무로 검색된 화면' 링크로 넘긴다(모바일판만 딥링크 됨)."""
    label: str = ""                 # 버튼 라벨 ('○○ 국비 훈련 찾기')
    url: str = ""                   # m.work24 훈련검색 딥링크(직무 키워드 프리필)
    note: str = ""                  # 내일배움카드 안내 문구


class Goal(BaseModel):
    # ── NCS 원툴(2026-07-29) : 카드 주인공은 '직업(=방향)'. 선고 아닌 안내 — 설명으로 방향을 보여준다 ──
    job: str                        # 목표 직업 (주인공)
    group: str = ""                 # 직업군 (중분류)
    description: str = ""           # NCS 직무 설명(DUTY_DEF) — '이 방향이 뭔지'
    reason: str = ""                # 이 직업이 맞는 이유 (투명성)
    certs: list[CertStep] = []      # 이 직업의 자격증 ≤3 (「지금 바로」 우선). 없으면 빈 리스트
    no_cert_path: bool = False      # 자격증 없음 → 내일배움카드 안내
    guide: str = ""                 # 자격증 없을 때 안내 (국민내일배움카드)
    has_courses: bool = False       # K-MOOC 무료강좌 존재?
    courses: list[Course] = []      # 추천 강좌 (상세·링크 포함) — 직업 '맛보기'
    hire: Hire | None = None        # 국비 실전훈련 딥링크(핸드오프, 2026-07-29)


class MessageResponse(BaseModel):
    type: str                       # "ask" | "result" | "blocked"
    reply: str                      # 사용자에게 보여줄 말
    turn: int = 0
    max_turn: int = 3
    understanding: str = ""         # LLM이 이해한 요약 (디버깅·투명성용)
    mode: str = "gemini"            # "gemini" | "stub"  ← 폴백 발동 여부
    goal: Goal | None = None        # type=result일 때만
    alternatives: list[str] = []    # 다른 후보 직업


# ── 미래설계지도 (저장·이어서하기) 요청 (2026-07-29) ──
class SaveMapRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="저장할 대화 세션 id (마지막 카드를 담는다)")


class ResumeMapRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="이어갈 새 세션 id (여기에 슬롯을 복원)")
