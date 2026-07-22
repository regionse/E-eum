import { createContext, useContext, useState } from 'react'

// mock 로그인 상태. 새로고침에도 유지되도록 localStorage 사용.
const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('eum_user')) } catch { return null }
  })
  const [admin, setAdmin] = useState(() => {
    try { return JSON.parse(localStorage.getItem('eum_admin')) } catch { return null }
  })
  // 가족 연결 여부 (가족편지 기능) — 초대코드로 연결되면 true
  const [familyLinked, setFamilyLinked] = useState(() => localStorage.getItem('eum_family') === '1')

  const login = (u) => { setUser(u); localStorage.setItem('eum_user', JSON.stringify(u)) }
  const logout = () => { setUser(null); localStorage.removeItem('eum_user') }
  const adminLogin = (a) => { setAdmin(a); localStorage.setItem('eum_admin', JSON.stringify(a)) }
  const adminLogout = () => { setAdmin(null); localStorage.removeItem('eum_admin') }
  const linkFamily = () => { setFamilyLinked(true); localStorage.setItem('eum_family', '1') }
  const unlinkFamily = () => { setFamilyLinked(false); localStorage.removeItem('eum_family') }

  return (
    <AuthCtx.Provider value={{ user, admin, familyLinked, login, logout, adminLogin, adminLogout, linkFamily, unlinkFamily }}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
