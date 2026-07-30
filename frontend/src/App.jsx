import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import PublicLayout from './components/layout/PublicLayout.jsx'
import AdminLayout from './components/layout/AdminLayout.jsx'

// 공개
import Home from './pages/Home.jsx'
import About from './pages/About.jsx'
import Alerts from './pages/Alerts.jsx'
import NoticeList from './pages/notice/NoticeList.jsx'
import NoticeDetail from './pages/notice/NoticeDetail.jsx'
import Inquiry from './pages/inquiry/Inquiry.jsx'
import InquiryList from './pages/inquiry/InquiryList.jsx'
// 인증
import Login from './pages/auth/Login.jsx'
import Signup from './pages/auth/Signup.jsx'
import FindId from './pages/auth/FindId.jsx'
import FindPw from './pages/auth/FindPw.jsx'
// 마이페이지
import MyPage from './pages/mypage/MyPage.jsx'
// 덜다
import WelfareHub from './pages/welfare/WelfareHub.jsx'
import PolicyFind from './pages/welfare/PolicyFind.jsx'
import PolicyResult from './pages/welfare/PolicyResult.jsx'
import PolicyDetail from './pages/welfare/PolicyDetail.jsx'
// 잇다
import LearnHub from './pages/learn/LearnHub.jsx'
import LearnChat from './pages/learn/LearnChat.jsx'
// 나누다
import ShareHub from './pages/share/ShareHub.jsx'
import ResourceMap from './pages/share/ResourceMap.jsx'
// 가족편지 (마이 > 가족편지)
import FamilyLetter from './pages/family/FamilyLetter.jsx'
import FamilyConnect from './pages/family/FamilyConnect.jsx'
import FamilyJoin from './pages/family/FamilyJoin.jsx'
import CareDiary from './pages/family/CareDiary.jsx'
import CareDiaryDetail from './pages/family/CareDiaryDetail.jsx'
// 관리자
import AdminLogin from './pages/admin/AdminLogin.jsx'
import Dashboard from './pages/admin/Dashboard.jsx'
import AdminUsers from './pages/admin/AdminUsers.jsx'
import AdminNotices from './pages/admin/AdminNotices.jsx'
import AdminNoticeEdit from './pages/admin/AdminNoticeEdit.jsx'
import AdminInquiries from './pages/admin/AdminInquiries.jsx'
import AdminInquiryDetail from './pages/admin/AdminInquiryDetail.jsx'
import AdminWelfare from './pages/admin/AdminWelfare.jsx'
import AdminLearn from './pages/admin/AdminLearn.jsx'
import AdminShare from './pages/admin/AdminShare.jsx'
import AdminAccounts from './pages/admin/AdminAccounts.jsx'

function ScrollTop() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <ScrollTop />
      <Routes>
        {/* 공개 + 사용자 */}
        <Route element={<PublicLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<About />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/notice" element={<NoticeList />} />
          <Route path="/notice/:id" element={<NoticeDetail />} />
          <Route path="/inquiry" element={<Inquiry />} />
          <Route path="/inquiry/list" element={<InquiryList />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/find-id" element={<FindId />} />
          <Route path="/find-pw" element={<FindPw />} />
          <Route path="/mypage/*" element={<MyPage />} />

          <Route path="/welfare" element={<WelfareHub />} />
          <Route path="/welfare/policy" element={<PolicyFind />} />
          <Route path="/welfare/policy/result" element={<PolicyResult />} />
          <Route path="/welfare/policy/:id" element={<PolicyDetail />} />

          <Route path="/learn" element={<LearnHub />} />
          <Route path="/learn/chat" element={<LearnChat />} />

          <Route path="/share" element={<ShareHub />} />
          <Route path="/share/map" element={<ResourceMap />} />

          <Route path="/family" element={<FamilyLetter />} />
          <Route path="/family/connect" element={<FamilyConnect />} />
          <Route path="/family/join" element={<FamilyJoin />} />
          <Route path="/family/diary" element={<CareDiary />} />
          <Route path="/family/diary/:id" element={<CareDiaryDetail />} />
        </Route>

        {/* 관리자 */}
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route element={<AdminLayout />}>
          {/* 첫 화면은 회원관리 — 대시보드는 아래 메뉴로 남긴다(2026-07-30) */}
          <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
          <Route path="/admin/users" element={<AdminUsers />} />
          <Route path="/admin/dashboard" element={<Dashboard />} />
          <Route path="/admin/notices" element={<AdminNotices />} />
          <Route path="/admin/notices/new" element={<AdminNoticeEdit />} />
          <Route path="/admin/notices/:id" element={<AdminNoticeEdit />} />
          <Route path="/admin/inquiries" element={<AdminInquiries />} />
          <Route path="/admin/inquiries/:id" element={<AdminInquiryDetail />} />
          <Route path="/admin/welfare" element={<AdminWelfare />} />
          <Route path="/admin/learn" element={<AdminLearn />} />
          <Route path="/admin/share" element={<AdminShare />} />
          <Route path="/admin/accounts" element={<AdminAccounts />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
