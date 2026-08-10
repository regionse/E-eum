# -*- coding: utf-8 -*-
"""잇다 요청/응답 스키마 (Pydantic)."""
from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    #  session_id min_length=1 — 빈 문자열이면 여러 클라이언트가 한 세션을 공유해 프로필이 섞인다(코드감사)
    session_id: str = Field(..., min_length=1, description="프론트가 생성·유지하는 대화 세션 id")
    #  max_length — 상한이 없으면 대용량 발화가 그대로 LLM 프롬프트로 들어가 토큰비용이 폭증한다
    #  ★ 2026-08-10 — 2000 → 200 (사용자 지시). 프론트도 같은 값으로 막는다.
    #    ⚠ 알고 감수하는 대가: 실측한 사정 발화가 249자였다("어머니가 뇌졸중으로 쓰러지신 지
    #      4년…"). 이 서비스가 받으려고 만든 종류의 말이 200자를 넘는다. 잘리면 사용자는
    #      «다 못 쓰고» 보내게 된다. 되돌리려면 이 숫자와 LearnChat.jsx 의 MAX_LEN 을 같이 올린다.
    #    ⚠ 프론트가 먼저 막으므로 여기 422 는 «직접 API를 부른 경우»의 최후 방어선이다.
    message: str = Field(..., min_length=1, max_length=200, description="사용자 발화")


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
    exam: str = ""                  # 다음 시험일(접수 마감일 포함)
    verified: bool = False          # cert_job 검증된 연결인지
    #  (2026-07-30) DB 에 있으나 화면에 안 쓰던 실데이터를 노출 — 자격증 상세에서 보여준다.
    #  ★ 2026-08-04 — 연 시험 회차. 20 이상이면 상시시험급(제빵기능사 42 · 조리류 41)이고
    #    일반 기능사는 4~5 다. 시간이 없는 사용자에게 「놓쳐도 곧 다음이 있다」가 제일 크다.
    exam_n: int = 0                 # 연 회차 수
    often: bool = False             # 자주 열리는 시험인가 (exam_n >= 20)
    exam_method: str = ""           # 시험 방법(무엇을 공부하나) — certification.exam_method
    outlook: str = ""               # 이 자격의 전망 — certification.career_outlook
    qual_gb: str = ""               # 국가기술자격 / 국가전문자격
    evidence: str = ""              # 이 자격증을 이 직업에 이은 근거(cert_job.evidence) — '데이터가 골랐다'의 증거


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


#  ── 덜다(정책) 갈림길 (2026-08-04) ──
#  진로만으로 안 풀리는 문제(시간·비용)에 **다른 축으로 건네주는** 딱지.
#  잇다는 덜다 코드를 부르지 않는다 — 화면 경로만 알려준다(팀 경계를 넘지 않는다).
class Handoff(BaseModel):
    to: str = "welfare"             # 어느 축으로 (welfare=덜다)
    path: str = "/welfare/policy"   # 프론트 라우트
    label: str = ""                 # 버튼에 쓸 말


class MessageResponse(BaseModel):
    type: str                       # "ask" | "result" | "blocked"
    reply: str                      # 사용자에게 보여줄 말
    #  ★★ 2026-08-06 — `turn` · `max_turn` 을 **지웠다.**
    #    초기 설계(CRS 논의 이전)의 잔재다. max_turn=3 은 「3턴이면 끝난다」는 전제인데,
    #    그 전제는 이미 폐기됐고 프론트도 이 필드를 **한 번도 쓴 적이 없다**
    #    (LearnChat.jsx 가 쓰는 것: reply·type·goal·options·option_notes·alternatives·handoff).
    #    ⚠ 다시 넣지 말 것 — 우리 사용자는 자기가 뭘 원하는지 모르는 상태로 시작한다.
    #      대화가 20~30턴, 길면 100턴까지 갈 수 있다고 «전제하고» 설계해야 한다.
    #      「3/3」 진행도는 그 사용자에게 «너는 늦었다»고 말하는 것과 같다.
    understanding: str = ""         # LLM이 이해한 요약 (디버깅·투명성용)
    mode: str = "gemini"            # "gemini" | "error"  ← 턴 실패 여부(stub 폴백은 없다)
    goal: Goal | None = None        # type=result일 때만
    alternatives: list[str] = []    # 다른 후보 직업
    options: list[str] = []         # 좁히기 선택지 — 프론트가 클릭 chip 으로 그린다(2026-07-30)
    option_notes: list[str] = []    # 각 선택지의 한 줄 설명(같은 순서) — NCS 원문만 보여주면 못 고른다
    handoff: Handoff | None = None  # 덜다로 건네줄 때만 (2026-08-04)
    #  ★ 이번 턴에 실제로 쓴 토큰 (2026-08-04) — 비용을 눈으로 보려고 넣었다.
    #    {in, out, think, cached, calls}. cached 가 0이면 프롬프트 캐싱이 안 걸린 것이다.
    #    프론트는 안 써도 된다(모르는 필드는 무시된다). 데모·계측용.
    usage: dict | None = None


# ── 미래설계지도 (저장·이어서하기) 요청 (2026-07-29) ──
class SaveMapRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="저장할 대화 세션 id (마지막 카드를 담는다)")


class ResumeMapRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="이어갈 새 세션 id (여기에 슬롯을 복원)")


# ── 관리자 · 임베딩 관리 화면 (2026-08-02) ──────────────────────────
#  덜다(ADDUL-001)·나누다(ADSHA-001) 화면과 같은 항목을 채운다.
#  값의 출처: itda_sync_log(배치 실행 기록) + content_hash(무엇이 바뀌었나)
class SyncRun(BaseModel):
    """대상별 '가장 최근 실행' 한 줄."""
    target: str                     # load_certification / load_cert_detail / embed_cert / embed_course …
    finished_at: str = ""           # "2026-08-02 20:53"
    fetched: int = 0                # 읽은 건수
    inserted: int = 0               # 신규 — content_hash 가 없던 것
    updated: int = 0                # 변경 — content_hash 가 달랐던 것
    embedded: int = 0               # 실제로 임베딩한 건수
    status: str = "ok"              # ok | partial | error
    message: str = ""


class ItdaSyncStatus(BaseModel):
    """관리자 임베딩 관리 화면이 한 번에 받아가는 현황."""
    last_api_sync: str = ""         # 마지막 API 동기화 (load_* 중 최신)
    last_embedding: str = ""        # 마지막 임베딩 (embed_* 중 최신)

    cert_total: int = 0             # 총 자격증
    job_total: int = 0              # 총 직업
    course_total: int = 0           # 총 강좌

    #  '임베딩 완료' = content_hash 가 채워진 행 수.
    #  ⚠️ job_catalog 에는 content_hash 컬럼이 없어 직업은 세지 않는다(NCS 원본이라 거의 안 바뀜).
    cert_embedded: int = 0
    course_embedded: int = 0

    failed_recent: int = 0          # 최근 7일 안에 ok 가 아니었던 실행 수
    runs: list[SyncRun] = []        # 대상별 최근 실행 (최신순)


# ── 최신화 실행 현황 (2026-08-04) ──────────────────────────────────
#  위 ItdaSyncStatus 는 '지금 데이터가 어떤 상태인가'(결과)를 말하고,
#  아래 둘은 '지금 최신화가 어디까지 돌고 있나'(진행)를 말한다. 출처가 다르다 —
#  결과는 DB(itda_sync_log·content_hash), 진행은 sync_runner 의 메모리 상태다.
class ItdaSyncStep(BaseModel):
    """최신화 한 단계."""
    key: str = ""
    title: str = ""
    desc: str = ""
    status: str = "waiting"         # waiting | running | ok | failed
    percent: int = 0                # 배치가 찍는 «300/613 (48%)» 에서 뽑은 값
    done: int = 0                   # 같은 줄의 앞 숫자 — 몇 개까지 처리했나
    total: int = 0                  # 같은 줄의 뒤 숫자 — 전체 몇 개인가
    elapsed: int = 0                # 그 단계가 시작된 뒤 흐른 초
    log: str = ""                   # 그 단계의 마지막 출력 한 줄


class ItdaSyncRun(BaseModel):
    """최신화 실행 하나의 진행 상황. 한 번도 안 돌렸으면 status='idle'."""
    run_id: str = ""
    status: str = "idle"            # idle | running | done | failed
    started_at: str = ""
    finished_at: str | None = None
    current: str = ""               # 지금 돌고 있는 단계의 key
    message: str = ""
    steps: list[ItdaSyncStep] = []
