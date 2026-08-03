# 알림 기능 적용 방법

## 1. 백엔드 파일 배치

`backend/app/notifications` 안의 파일을 프로젝트 `Backend/app/notifications`에 넣습니다.
수정된 `models(23).py`는 `Backend/app/notifications/models.py`,
`create_tables(11).py`는 `Backend/app/notifications/create_tables.py`로 사용합니다.

DB 테이블은 `backend/001_create_notifications.sql`을 MySQL에서 한 번 실행해 생성합니다.
이미 미완성 `notifications` 테이블이 있다면 바로 실행하지 말고 기존 테이블 구조를 먼저 확인해야 합니다.

## 2. FastAPI 라우터 등록

`app/main.py`에 추가합니다.

```python
from app.notifications.router import router as notification_router

app.include_router(notification_router, prefix="/api")
```

최종 주소는 다음과 같습니다.

- `GET /api/notifications`
- `GET /api/notifications/unread-count`
- `PATCH /api/notifications/{notification_id}/read`
- `PATCH /api/notifications/read-all`

## 3. 가족편지를 저장할 때 알림 생성

`app/nanuda/controllers.py` 상단에 추가합니다.

```python
from app.notifications.service import create_family_letter_notifications
```

기존 `create_family_letter()`에서 편지를 `db.add()`한 다음 ID를 얻고,
같은 트랜잭션에서 알림을 추가합니다.

```python
db.add(letter)
await db.flush()

await create_family_letter_notifications(
    db=db,
    letter_id=letter.letter_id,
    care_group_id=data.care_group_id,
    author_user_id=data.user_id,
)

await db.commit()
await db.refresh(letter)
```

기존의 `await db.commit()` 앞에 `flush()`와 알림 생성 호출을 넣어야 합니다.
작성자에게는 알림을 보내지 않고 같은 가족방의 다른 구성원에게만 생성됩니다.

## 4. 공지를 저장할 때 알림 생성

공지 생성 컨트롤러 상단에 추가합니다.

```python
from app.notifications.service import create_notice_notifications
```

공지 객체를 추가한 뒤 다음 순서로 실행합니다.

```python
db.add(notice)
await db.flush()

await create_notice_notifications(
    db=db,
    notice_id=notice.notice_id,
    notice_title=notice.title,
)

await db.commit()
await db.refresh(notice)
```

## 5. 프론트 파일 배치

- `frontend/src/api/notifications.js` → `src/api/notifications.js`
- `frontend/src/components/NotificationBell.jsx` → `src/components/NotificationBell.jsx`
- `frontend/src/pages/Notifications.jsx` → 실제 페이지 폴더

헤더에서 기존 종 아이콘을 다음 컴포넌트로 교체합니다.

```jsx
import NotificationBell from './NotificationBell.jsx'

<NotificationBell />
```

라우터에 알림 목록 화면을 추가합니다.

```jsx
import Notifications from './pages/Notifications.jsx'

<Route path="/notifications" element={<Notifications />} />
```

## 6. 이동 주소 확인

현재 생성되는 이동 경로는 다음과 같습니다.

- 공지: `/notices/{notice_id}`
- 가족편지: `/family/diary/{letter_id}`

프로젝트의 실제 공지 상세 주소가 다르면 `service.py`의 `target_url`만 변경합니다.

## 7. 동작 확인

1. 사용자 43과 44가 같은 가족방에 로그인되어 있는지 확인합니다.
2. 사용자 43이 가족편지를 작성합니다.
3. 사용자 44의 헤더 종 아이콘에 숫자가 나타나는지 확인합니다.
4. 알림 목록에서 가족편지 알림을 누르면 해당 편지 상세로 이동하는지 확인합니다.
5. 새 공지를 작성한 뒤 모든 회원에게 공지 알림이 생성되는지 확인합니다.
