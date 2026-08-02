# 잇다 · 배치 스크립트

웹 서버(`main.py`)는 이 폴더를 **import 하지 않는다.** 손으로 실행하거나 스케줄러가 돌린다.
(덜다의 `app/delda/scripts/` 와 같은 구조)

## 실행 방법
레포의 `Backend/` 폴더에서:
```bash
python -m app.itda.scripts.<파일명>
```

## 언제 쓰나

### DB를 새로 만들었을 때 (AWS 이전 등) — 이 순서로
| 순서 | 파일 | 하는 일 |
|---|---|---|
| 1 | `load_certification.py` | 자격증 613종 적재 (Q-Net) |
| 2 | `load_cert_detail.py` | 시험방법·전망 등 상세 채우기 |
| 3 | `set_entry_free.py` | 응시자격 '조건 없음' 판정 |
| 4 | `set_entry_note.py` | 응시자격 원문 채우기 |
| 5 | `load_exam_schedule.py` | 시험일정 2,655건 (Q-Net) |
| 6 | `load_course.py` | K-MOOC 강좌 8,371건 |

※ 직업(job_catalog 1,094종)은 NCS 원본에서 적재한다. 적재 스크립트는 아직 없다.

### 벡터 인덱스를 만들거나 복구할 때
| 파일 | 대상 | 네임스페이스 |
|---|---|---|
| `embed_jobs.py` | 직업 1,094 | `job` ← **검색의 핵심** |
| `embed_cert.py` | 자격증 613 | `cert` |
| `embed_course.py` | 강좌 8,371 | `course` |

`embed_jobs.py` 는 **인덱스가 날아갔을 때 유일한 복구 수단**이다.
새 네임스페이스로 만들어 두고 확인 후 교체하는 것을 권한다:
```bash
python -m app.itda.scripts.embed_jobs --namespace job2 --all
# 확인 후 app/itda/match.py 의 NS_JOB 을 'job2' 로 변경 (되돌리기도 한 줄)
```

### 데이터가 갱신됐을 때
Q-Net 시험일정은 **매년 바뀐다.** `load_exam_schedule.py` 를 다시 돌린다.
(자격증·강좌 내용이 바뀌면 해당 임베딩도 다시 돌려야 검색이 맞는다.)

## 검증
```bash
python -m app.itda.scripts.golden_check
```
34 케이스 회귀 테스트. **배포 후 이걸 돌려 34/34 가 나오면** DB·FULLTEXT 인덱스·
환경변수·Pinecone·Gemini 가 모두 정상이라는 뜻이다.

## 주의
- 임베딩 모델은 `match.py` 의 `MODEL` 과 **반드시 같아야 한다**. 다르면 검색이 전부 어긋난다.
- 이 스크립트들은 외부 API(Q-Net·K-MOOC·Gemini·Pinecone)를 호출한다. 키가 필요하다.
- 무료 티어는 분당 한도가 있어 배치 사이에 쉰다. 전체 임베딩은 수십 분 걸릴 수 있다.
