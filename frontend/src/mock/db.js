// ============================================================================
//  이음 mock 데이터베이스
//  ⚠️ 이 파일 + src/api/* 가 "가짜 데이터"의 전부다.
//     나중에 진짜 FastAPI를 붙일 땐 src/api/*.js 안의 반환부만 fetch로 바꾸면 되고,
//     화면(pages/components)은 한 줄도 손대지 않는다. (mock → real 교체 지점)
// ============================================================================

// ---------- 덜다 · 맞춤 지원 정책 (rule 기반 추천 결과) ----------
// fit: best(매우 적합) / good(적합) / rec(추천) / ref(참고)
export const policies = [
  {
    id: 'P-001', name: '가족돌봄청년 자기돌봄비 지원', fit: 'best',
    summary: '아픈 가족을 돌보는 청년에게 연 200만원의 자기돌봄비를 현금으로 지원합니다.',
    reasons: ['만 13~34세 가족돌봄청년 조건 충족', '입력하신 돌봄 상황(부모 간병)과 정확히 일치'],
    provider: '보건복지부', amount: '연 200만원', applyUrl: 'https://www.bokjiro.go.kr',
    detail: '가족을 돌보느라 생계·학업에 어려움을 겪는 청년에게 자기 돌봄과 미래 준비를 위한 비용을 지원합니다. 신청은 거주지 관할 청년미래센터 또는 복지로에서 가능합니다. 소득 기준과 돌봄 사실 증빙이 필요합니다.',
    tags: ['현금지원', '돌봄'],
    category: '돌봄·현금', supportType: '현금 지원', cycle: '연 1회',
    target: '만 13~34세 가족돌봄청년(아픈 가족을 돌보는 청년)',
    criteria: '가구 소득 기준 이하 + 돌봄 사실 증빙',
    method: '거주지 관할 청년미래센터 또는 복지로에서 신청',
    contact: '보건복지상담센터 129', pdfUrl: '#',
    needs: ['생활비 지원', '돌봄 서비스'],
  },
  {
    id: 'P-002', name: '청년 월세 특별지원', fit: 'best',
    summary: '무주택 청년에게 월 최대 20만원의 임대료를 최대 12개월 지원합니다.',
    reasons: ['거주지역(서울) 및 연령 요건 충족', '독립 거주 중인 청년 대상'],
    provider: '국토교통부', amount: '월 20만원 (최대 12개월)', applyUrl: 'https://www.bokjiro.go.kr',
    detail: '부모와 따로 거주하는 무주택 청년의 주거비 부담을 덜기 위한 제도입니다. 본인 소득과 재산, 부모 소득 기준을 함께 봅니다. 복지로 또는 관할 주민센터에서 신청합니다.',
    tags: ['주거', '월세'],
    category: '주거', supportType: '현금 지원(임대료)', cycle: '월 · 최대 12개월',
    target: '부모와 따로 거주하는 무주택 청년',
    criteria: '본인·부모 소득 및 재산 기준 충족',
    method: '복지로 또는 관할 주민센터에서 신청',
    contact: '보건복지상담센터 129', pdfUrl: '#',
    needs: ['생활비 지원'],
  },
  {
    id: 'P-003', name: '재난적 의료비 지원', fit: 'good',
    summary: '가구의 부담이 큰 의료비의 일부를 국가가 지원합니다.',
    reasons: ['가족 의료비 부담이 높은 상황으로 판단', '소득 대비 의료비 비중 요건 확인 필요'],
    provider: '국민건강보험공단', amount: '연간 최대 5,000만원', applyUrl: 'https://www.nhis.or.kr',
    detail: '질병·부상 등으로 발생한 과도한 의료비로 경제적 어려움을 겪는 가구를 지원합니다. 입원 및 일부 외래 진료가 대상이며, 병원 퇴원 후 180일 이내 신청해야 합니다.',
    tags: ['의료비', '가족'],
    category: '의료', supportType: '현금 지원(의료비)', cycle: '건별 · 퇴원 후 180일 이내',
    target: '과도한 의료비로 경제적 어려움을 겪는 가구',
    criteria: '소득 대비 의료비 비중 요건 확인',
    method: '국민건강보험공단 지사에서 신청',
    contact: '국민건강보험공단 1577-1000', pdfUrl: null,
    needs: ['의료비 지원'],
  },
  {
    id: 'P-004', name: '청년내일저축계좌', fit: 'rec',
    summary: '일하는 청년이 매달 저축하면 정부가 매칭 적립해 목돈 마련을 돕습니다.',
    reasons: ['근로 중인 청년 대상', '소득 요건에 따라 매칭 비율 상이'],
    provider: '보건복지부', amount: '3년 만기 최대 1,440만원', applyUrl: 'https://www.bokjiro.go.kr',
    detail: '근로·사업소득이 있는 저소득 청년이 매월 저축하면 정부 지원금을 함께 적립해 주는 자산형성 제도입니다.',
    tags: ['자산형성', '저축'],
    category: '자산형성', supportType: '정부 매칭 적립', cycle: '월 · 3년 만기',
    target: '근로·사업소득이 있는 저소득 청년',
    criteria: '소득 요건에 따라 매칭 비율 상이',
    method: '복지로 또는 관할 주민센터에서 신청',
    contact: '보건복지상담센터 129', pdfUrl: '#',
    needs: ['생활비 지원'],
  },
  {
    id: 'P-005', name: '심리상담 바우처 (청년마음건강)', fit: 'rec',
    summary: '전문 심리상담 서비스를 저렴하게 이용할 수 있는 바우처를 제공합니다.',
    reasons: ['돌봄 부담으로 인한 정서적 소진 가능성', '별도 소득 기준 없이 신청 가능'],
    provider: '보건복지부', amount: '10회기 (본인부담 일부)', applyUrl: 'https://www.bokjiro.go.kr',
    detail: '청년의 심리·정서적 어려움 해소를 위해 전문 상담 서비스를 바우처 형태로 지원합니다. 주민센터에서 신청합니다.',
    tags: ['심리상담', '정서'],
    category: '심리·정서', supportType: '바우처(서비스)', cycle: '10회기 · 1회 지원',
    target: '심리·정서적 어려움을 겪는 청년',
    criteria: '별도 소득 기준 없이 신청 가능',
    method: '주민센터에서 신청',
    contact: '보건복지상담센터 129', pdfUrl: null,
    needs: ['심리 지원'],
  },
]

// ---------- 덜다 · 최근 인기 제도 (즐겨찾기 많이 받은 순 · mock) ----------
export const popularPolicies = [
  { id: 'P-001', name: '가족돌봄청년 자기돌봄비 지원', provider: '보건복지부', favCount: 1284, tags: ['현금지원', '돌봄'] },
  { id: 'P-002', name: '청년 월세 특별지원', provider: '국토교통부', favCount: 970, tags: ['주거'] },
  { id: 'P-004', name: '청년내일저축계좌', provider: '보건복지부', favCount: 612, tags: ['자산형성'] },
  { id: 'P-003', name: '재난적 의료비 지원', provider: '국민건강보험공단', favCount: 455, tags: ['의료비'] },
  { id: 'P-005', name: '심리상담 바우처 (청년마음건강)', provider: '보건복지부', favCount: 331, tags: ['심리상담'] },
]





// ---------- 나누다 · 동네 자원 (지도 mock) ----------
export const resources = [
  { id: 'R-001', name: '성북구보건소 방문건강관리', type: '보건소', dist: '0.4km', desc: '무료 · 09~18시', phone: '02-000-0000', x: 30, y: 42 },
  { id: 'R-002', name: '성북 정신건강복지센터', type: '정신건강', dist: '1.2km', desc: '무료 심리상담', phone: '02-000-1111', x: 62, y: 30 },
  { id: 'R-003', name: '한빛 재활의학과의원', type: '재활', dist: '1.8km', desc: '물리치료 · 재활', phone: '02-000-2222', x: 74, y: 63 },
  { id: 'R-004', name: '성북구 청년미래센터', type: '보건소', dist: '2.1km', desc: '가족돌봄청년 전담 상담', phone: '02-000-3333', x: 44, y: 74 },
]

// ---------- 가족편지 (나누다 · 마이 > 가족편지) ----------
// 가족이 함께 남기는 공유 돌봄 기록 = 그대로 '돌봄일지'로 축적된다.
// 연결된 가족만 열람, 운영진 조회 불가. (스토리보드 FAM-001·003 원칙)

// 오늘의 약 (아침/점심/저녁 체크만, 시간 설정 없이, 매일 자정 초기화)
export const todayMeds = [
  { id: 'M1', label: '아침 약', taken: true },
  { id: 'M2', label: '점심 약', taken: true },
  { id: 'M3', label: '저녁 약', taken: false },
]

// 공유 타임라인 = 돌봄일지 원본 (최신 위). author = '나' | '어머니'
// meds: 그날의 복약 스냅샷(상세 '그날의 약'에 표시)
export let familyRecords = [
  { id: 'FR-13', author: '나', date: '2026-07-06', time: '20:10', meds: { m: true, l: true, d: true },
    body: '저녁 약 챙겨드리고 무릎 스트레칭 도와드렸어요. 오늘은 계단도 한결 수월하게 오르셨어요.' },
  { id: 'FR-12', author: '어머니', date: '2026-07-06', time: '08:30', meds: { m: true, l: false, d: false },
    body: '아침 잘 먹었다. 혈압도 괜찮아.' },
  { id: 'FR-5', author: '나', date: '2026-07-05', time: '14:20', meds: { m: true, l: true, d: true },
    body: '점심 약까지 챙겨드렸어요. 오후에 정형외과 예약이 있어서 함께 다녀왔고, 무릎 통증은 어제보다 나아졌다고 하세요.\n다만 계단을 오르내릴 때는 아직 조심스러워하셔서, 저녁엔 무리하지 않으시게 했어요. 진통제는 처방대로 하루 두 번, 식후에 드시는 걸로 확인했어요.\n저녁 약은 어머니가 챙기기로 했어요. 내일 아침엔 제가 다시 봐드릴게요.' },
  { id: 'FR-3', author: '나', date: '2026-07-05', time: '09:10', meds: { m: true, l: false, d: false },
    body: '아침 식사·약 완료. 혈압 정상이에요.' },
  { id: 'FR-4', author: '어머니', date: '2026-07-05', time: '08:50', meds: { m: true, l: false, d: false },
    body: '밤새 뒤척이셨어요. 저녁 약은 내가 챙길게.' },
  { id: 'FR-2', author: '어머니', date: '2026-07-04', time: '21:10', meds: { m: true, l: true, d: true },
    body: '저녁 약 챙겨드리고 산책 15분. 표정 좋아지심.' },
  { id: 'FR-1', author: '나', date: '2026-07-04', time: '12:30', meds: { m: true, l: true, d: false },
    body: '점심 후 약. 무릎 통증 있다고 하셔서 온찜질 해드렸어요.' },
  { id: 'FR-11', author: '나', date: '2026-07-03', time: '19:40', meds: { m: true, l: true, d: true },
    body: '저녁 식사 후 약 챙겨드렸어요. 오늘은 무릎 통증이 덜하다고 하세요.' },
  { id: 'FR-10', author: '어머니', date: '2026-07-03', time: '08:20', meds: { m: true, l: false, d: false },
    body: '아침 약 먹었다. 동네 한 바퀴 산책 다녀올게.' },
  { id: 'FR-9', author: '나', date: '2026-07-02', time: '13:15', meds: { m: true, l: true, d: false },
    body: '점심 약. 오후에 복지관 프로그램 함께 다녀왔어요. 사람들과 어울리니 표정이 밝으셨어요.' },
  { id: 'FR-8', author: '어머니', date: '2026-07-02', time: '09:00', meds: { m: true, l: false, d: false },
    body: '아침 잘 챙겨 먹었어. 오늘 컨디션 좋아.' },
  { id: 'FR-7', author: '나', date: '2026-07-01', time: '20:30', meds: { m: true, l: true, d: true },
    body: '저녁 약 완료. 혈압 130/80으로 안정적이에요.' },
  { id: 'FR-6', author: '어머니', date: '2026-07-01', time: '12:00', meds: { m: true, l: true, d: false },
    body: '점심 먹고 약 먹었다.' },
  { id: 'FR-0', author: '나', date: '2026-07-01', time: '08:40', meds: { m: true, l: false, d: false },
    body: '아침 약·식사 완료. 오늘 정형외과 예약 있어요. 오전에 함께 다녀올게요.' },
]

// 연결된 가족 (초대 코드로 연결되면 표시) — 나 외 구성원
export const familyMembers = [
  { id: 'mom', name: '어머니', relation: '어머니', emoji: '👩' },
]

// 데모: 이 코드로 연결하면 성공. 그 외 특정 코드는 사유별 오류 흐름(FAM-000b)
export const demoInviteCode = '382910'

// ---------- 공지사항 ----------
export const notices = [
  { id: 'N-5', type: '공지사항', title: '시스템 점검 안내 (7/10 새벽)', date: '2026-06-20', views: 63, status: '활성',
    body: '더 안정적인 서비스를 위해 7월 10일 새벽 2~4시 시스템 점검이 진행됩니다. 해당 시간 서비스 이용이 일시 중단될 수 있습니다.' },
  { id: 'N-4', type: '공지사항', title: '개인정보 처리방침 변경 안내', date: '2026-06-18', views: 310, status: '비활성',
    body: '개인정보 처리방침이 일부 개정되었습니다. 자세한 내용은 하단 개인정보처리방침을 확인해주세요.' },
  { id: 'N-3', type: '업데이트', title: '맞춤 지원 정책 찾기 기능 오픈', date: '2026-06-15', views: 522, status: '활성',
    body: '덜다에 AI 기반 맞춤 지원 정책 찾기 기능이 새롭게 추가되었습니다.' },
  { id: 'N-2', type: '이벤트', title: '가족돌봄청년 응원 캠페인 안내', date: '2026-06-15', views: 257, status: '활성',
    body: '함께 응원하는 캠페인을 진행합니다. 많은 관심 부탁드립니다.' },
  { id: 'N-1', type: '공지사항', title: '서비스 기능 개선 안내', date: '2026-06-01', views: 52, status: '활성',
    body: '사용성 개선을 위한 UI 업데이트가 적용되었습니다.' },
]

// ---------- 문의 ----------
export let inquiries = [
  { id: 5, title: '비밀번호 재설정 문의', type: '계정문의', date: '2026-07-05', status: '답변완료',
    body: '비밀번호를 까먹었는데 전화번호가 바뀌어서 로그인이 안돼요.', answer: '안녕하세요, 이음입니다. 계정 비밀번호 초기화를 완료했습니다. 재설정 후 이용해주세요.' },
  { id: 4, title: 'AI 추천 오류 문의', type: '덜다', date: '2026-07-04', status: '처리중', body: '정책 추천 결과가 안 떠요.', answer: '' },
  { id: 3, title: '회원가입 관련 문의', type: '기타', date: '2026-07-03', status: '접수', body: '가입 연령 제한이 왜 있나요?', answer: '' },
  { id: 2, title: '로그인 안돼요', type: '계정문의', date: '2026-07-02', status: '답변완료', body: '로그인이 안됩니다.', answer: '확인 결과 정상 처리되었습니다.' },
  { id: 1, title: '서비스 이용 문의', type: '서비스문의', date: '2026-07-01', status: '처리중', body: '나누다 지도가 안 보여요.', answer: '' },
]

// ---------- 관리자 · 회원 목록 ----------
export const adminUsers = [
  { id: 'U-10293', age: 27, joined: '2026-05-12', status: '활성', role: '뷰어' },
  { id: 'U-10288', age: 23, joined: '2026-05-10', status: '활성', role: '뷰어' },
  { id: 'U-10277', age: 31, joined: '2026-04-28', status: '휴면', role: '뷰어' },
  { id: 'U-10261', age: 16, joined: '2026-04-20', status: '정지', role: '뷰어' },
  { id: 'U-10255', age: 22, joined: '2026-04-15', status: '활성', role: '뷰어' },
]
export const adminAccounts = [
  { id: 'ADM-10293', age: 27, joined: '2026-05-12', status: '활성', role: '관리자', perms: '열람·수정·작성·삭제' },
  { id: 'ADM-10288', age: 23, joined: '2026-05-10', status: '활성', role: '관리자', perms: '열람·수정·작성·삭제' },
]


// ---------- 관리자 · 덜다 정책 임베딩 (ADDUL-001) ----------
export const policyEmbed = {
  lastApiSync: '2026-07-13 03:00', lastCrawl: '2026-07-13 03:00', lastEmbed: '2026-07-13 03:00',
  total: 3152, api: 3140, seoul: 12, added: 5, changed: 7, embedded: 3147,
}

// ---------- 관리자 · 잇다 임베딩 (ADM-ITD-EMB · K-MOOC → FAISS) ----------
export const learnIndex = {
  lastRebuild: '2026-07-11 04:00', total: 11600, embedded: 11600, pending: 0, status: '최신',
  model: 'gemini-embedding-001', dim: '1536차원(MRL)', vector: 'FAISS',
  categories: [
    { name: 'IT·디지털', courses: 4060, embedded: 4060, status: '완료' },
    { name: '보건·의료', courses: 1740, embedded: 1740, status: '완료' },
    { name: '취업·자격', courses: 1624, embedded: 1624, status: '완료' },
    { name: '상담·심리', courses: 1160, embedded: 1160, status: '완료' },
    { name: '돌봄·복지', courses: 812, embedded: 812, status: '완료' },
    { name: '인문·교양 외', courses: 2204, embedded: 2204, status: '완료' },
  ],
}

// ---------- 관리자 · 나누다 임베딩 (ADSHA-001 · 지원서비스/기관 데이터) ----------
export const shareEmbed = {
  lastApiSync: '2026-07-13 03:00', lastEmbed: '2026-07-13 03:00',
  api: 3140, added: 5, changed: 7, embedded: 3147,
}
