# FILEMAP — 프론트엔드 파일별 역할 · 쓰이는 곳

`frontend/src/` 기준. "이 파일 건드리면 어디 영향 가는지" 빠르게 보는 지도.
(백엔드 붙일 땐 `api/*.js`만 mock → 실제 fetch로 바꾸면 됨. `USE_MOCK` 스위치는 `api/client.js`.)

---

## 진입 (Entry)
| 파일 | 역할 | 쓰이는 곳 |
|---|---|---|
| `main.jsx` | React 시작점. `#root`에 App 렌더 + Provider(Auth/Family) 감쌈 | index.html이 로드 |
| `App.jsx` | **라우터** — 35개 화면 경로 정의 (PublicLayout / AdminLayout 하위) | 모든 페이지 진입 |

## 레이아웃 · 공용 컴포넌트 (components/)
| 파일 | 역할 | 쓰이는 곳 |
|---|---|---|
| `components/layout/PublicLayout.jsx` | 사용자 **헤더(GNB·마이드롭다운·알림벨)+푸터** | 모든 공개 화면 껍데기 |
| `components/layout/AdminLayout.jsx` | 관리자 **좌측 사이드바(8메뉴)+헤더** | 모든 `/admin/*` |
| `components/RequireLogin.jsx` | 비로그인 시 로그인 유도 표시 | 덜다·잇다·나누다·마이·알림 |
| `components/ui/index.jsx` | **공용 UI 세트**: useAsync·Async·Loading·Modal·useToast·FitBadge·PageHead·Empty | 거의 모든 페이지 |

## 전역 상태 (store/) — localStorage 기반
| 파일 | 역할 | 쓰이는 곳 |
|---|---|---|
| `store/auth.jsx` | 로그인 상태(user/admin) + login/logout/linkFamily | 헤더·RequireLogin·마이·인증 |
| `store/family.jsx` | 가족편지 공유상태(records·meds·초대코드) + addRecord | family/* (가족편지·돌봄일지) |
| `store/history.js` | 즐겨찾기·최근본·**추천이력**(reco) | 덜다/잇다 메인·결과 |

## API 시접 (api/) — 지금은 mock, 나중에 여기만 백엔드로
| 파일 | 역할(=백엔드 계약) | 쓰이는 화면 |
|---|---|---|
| `api/client.js` | **USE_MOCK 스위치** + mockResolve + request(`/api` fetch) | 모든 api/* |
| `api/welfare.js` | 덜다 정책추천 findPolicies·getPolicy | PolicyFind·PolicyResult·PolicyDetail |
| `api/learn.js` | 잇다 추천 recommend·saveMap·getResume | LearnChat·LearnHub |
| `api/content.js` | 공지·문의 listNotices·getNotice·listInquiries·submitInquiry | notice/*·inquiry/*·admin |
| `api/share.js` | 나누다 기관 listResources | ResourceMap |
| `api/auth.js` | 로그인·가입·찾기 login·signup·findId·resetPassword·adminLogin | auth/*·AdminLogin |
| `api/admin.js` | 관리자 getDashboard·listAdminUsers·listAdminAccounts | Dashboard·AdminUsers·AdminAccounts |

## 가짜 데이터 (mock/)
| 파일 | 역할 |
|---|---|
| `mock/db.js` | **모든 mock 데이터** (정책·강좌·공지·문의·회원·인기·임베딩현황 등) |

## 화면 (pages/)
### 공통
| 파일 | 화면 |
|---|---|
| `pages/Home.jsx` | 홈 (HOM-001) |
| `pages/About.jsx` | 소개 (CMN-001) |
| `pages/Alerts.jsx` | 알림 (ALA-001) |
| `pages/library/Library.jsx` | 자료실 |
### 인증 (auth/)
| 파일 | 화면 |
|---|---|
| `Login.jsx`·`FindId.jsx`·`FindPw.jsx`·`Signup.jsx` | 로그인·아이디찾기·비번재설정·회원가입 |
| `AuthShell.jsx` | 인증 화면 공용 껍데기 |
### 덜다 (welfare/)
| 파일 | 화면 |
|---|---|
| `WelfareHub.jsx` | 덜다 메인 (WEL-101, 즐겨찾기·추천이력·인기) |
| `PolicyFind.jsx` | 맞춤정책찾기 폼 (WEL-102) |
| `PolicyResult.jsx` | 결과·결과없음·재상담 (WEL-103) |
| `PolicyDetail.jsx` | 정책 상세 (WEL-104) |
### 잇다 (learn/)
| 파일 | 화면 |
|---|---|
| `LearnHub.jsx` | 잇다 홈 (ITD-100, 미래설계지도·즐겨찾기·최근본) |
| `LearnChat.jsx` | 대화·지도결과·강좌상세팝업 (ITD-101~106) |
### 나누다 (share/ · family/)
| 파일 | 화면 |
|---|---|
| `share/ShareHub.jsx` | 나누다 선택 + 위치동의 (SHA-001·100) |
| `share/ResourceMap.jsx` | 동네 자원 지도 (SHA-101) |
| `family/FamilyLetter.jsx` | 가족편지 (SHA-201) |
| `family/CareDiary.jsx` | 돌봄일지 목록 + AI분석 (SHA-202) |
| `family/CareDiaryDetail.jsx` | 돌봄일지 상세 |
| `family/FamilyConnect.jsx` | 가족방 초대코드 생성 (SHA-303) |
| `family/FamilyJoin.jsx` | 초대코드 입력 |
### 마이 (mypage/)
| 파일 | 화면 |
|---|---|
| `MyPage.jsx` | 내정보·알림설정·동의관리·회원탈퇴 (MYP-101·301·601) — 탭 하나로 |
### 공지·문의 (notice/ · inquiry/)
| 파일 | 화면 |
|---|---|
| `notice/NoticeList.jsx`·`NoticeDetail.jsx` | 공지 목록·상세 |
| `inquiry/Inquiry.jsx`·`InquiryList.jsx` | 문의하기·문의내역 |
### 관리자 (admin/)
| 파일 | 화면 |
|---|---|
| `AdminLogin.jsx` | 관리자 로그인 (ADM-01) |
| `Dashboard.jsx` | 대시보드 (ADDAS-001) |
| `AdminUsers.jsx` | 회원관리 |
| `AdminNotices.jsx` | 공지관리 |
| `AdminInquiries.jsx` | 문의관리 |
| `AdminWelfare.jsx` | 덜다 정책 임베딩 (ADDUL-001) |
| `AdminLearn.jsx` | 잇다 임베딩 (ADM-ITD-EMB) |
| `AdminShare.jsx` | 나누다 임베딩 (ADSHA-001) |
| `AdminAccounts.jsx` | 관리자 계정 관리 |

## 스타일 (styles/)
| 파일 | 역할 |
|---|---|
| `styles/tokens.css` | 디자인 토큰(색·간격 CSS 변수) — `--teal-500` 등 |
| `styles/global.css` | 전역 스타일 + 공용 클래스(`.card`·`.btn`·`.badge`·`.tbl` 등) |
