import {
  useCallback,
  createContext,
  useContext,
  useMemo,
  useState,
} from 'react'
import { clearToken } from '../api/client.js'

// 로그인 상태(user·admin). 새로고침에도 유지되도록 localStorage 사용.
//  JWT 토큰은 client.js(eum_token)가 소유하고, 여기선 로그아웃 때 같이 비운다.
const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('eum_user')) } catch { return null }
  })
  const [admin, setAdmin] = useState(() => {
    try { return JSON.parse(localStorage.getItem('eum_admin')) } catch { return null }
  })
  // 가족 연결 여부 (가족편지 기능) — 초대코드로 연결되면 true
  const login = (nextUser) => {
    setUser(nextUser)
    localStorage.setItem(
      'eum_user',
      JSON.stringify(nextUser),
    )
  }

  const unlinkFamily = useCallback(() => {
    setFamilyLinked(false)
    localStorage.removeItem('eum_family')
  }, [])

  const [
    familyLinked,
    setFamilyLinked,
  ] = useState(
    () =>
      localStorage.getItem('eum_family') === '1',
  )

  const userId =
    user?.user_id ??
    user?.id ??
    null

  const logout = () => {
    setUser(null)
    localStorage.removeItem('eum_user')
    unlinkFamily()
    clearToken()

    try {
      Object.keys(localStorage)
        .filter((key) =>
          key.startsWith('eum_itda_chat'),
        )
        .forEach((key) =>
          localStorage.removeItem(key),
        )
    } catch {
      // localStorage 접근이 제한된 환경
    }
  }

  const adminLogin = (nextAdmin) => {
    setAdmin(nextAdmin)
    localStorage.setItem(
      'eum_admin',
      JSON.stringify(nextAdmin),
    )
  }

  const adminLogout = () => {
    setAdmin(null)
    localStorage.removeItem('eum_admin')
    clearToken()
  }

  const linkFamily = useCallback(() => {
    setFamilyLinked(true)
    localStorage.setItem('eum_family', '1')
  }, [])

  const value = useMemo(
    () => ({
      user,
      userId,
      admin,
      familyLinked,
      login,
      logout,
      adminLogin,
      adminLogout,
      linkFamily,
      unlinkFamily,
    }),
    [
      user,
      userId,
      admin,
      familyLinked,
      linkFamily,
      unlinkFamily,
    ],
  )

  return (
    <AuthCtx.Provider value={value}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
