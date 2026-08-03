import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { useAuth } from './auth.jsx'
import {
  createCareGroup,
  createFamilyLetter,
  createInviteCode,
  getCareGroupMembers,
  getFamilyLetters,
  getMyCareGroups,
  joinCareGroup,
} from '../api/share.js'


export const TODAY = new Date()
  .toISOString()
  .slice(0, 10)
// 내가 남에게 주는 초대 코드(가족 연결 화면에 표시). 받은 코드(demoInviteCode)와는 별개.
// const MY_INVITE_CODE = '501537'

// ============================================================================
//  가족편지 공유 스토어
//  가족편지에 남긴 '돌봄 기록'이 곧 '돌봄일지'다. 한 곳(records)에 담아
//  가족편지 타임라인 · 돌봄일지 게시판 · 상세가 같은 데이터를 본다.
//  (mock: 앱 세션 동안만 유지 / 나중에 api/family.js 로 교체)
// ============================================================================


const WEEKDAYS = [
  '일',
  '월',
  '화',
  '수',
  '목',
  '금',
  '토',
]

export function fmtDateWithWeekday(dateStr) {
  const date = new Date(`${dateStr}T00:00:00`)
  return `${dateStr} (${WEEKDAYS[date.getDay()]})`
}

export function fmtBoardTime(record) {
  return `${record.date.slice(5)} ${record.time}`
}

export function fmtTimelineTime(record) {
  const dateLabel =
    record.date === TODAY
      ? '오늘'
      : record.date.slice(5)

  return `${dateLabel} ${record.time}`
}

function toRecord(letter, currentUserId) {
  const createdAt = letter.created_at ?? ''
  const date = createdAt.slice(0, 10)
  const time = createdAt.slice(11, 16)

  return {
    id: String(letter.letter_id),
    letterId: letter.letter_id,
    authorId: letter.user_id,
    author:
      Number(letter.user_id) === Number(currentUserId)
        ? '나'
        : '가족',
    date,
    time,
    body: letter.content,
  }
}

const FamilyCtx = createContext(null)

export function FamilyProvider({ children }) {
  const {
    userId,
    linkFamily,
    unlinkFamily,
  } = useAuth()

  const [careGroup, setCareGroup] = useState(null)
  const [members, setMembers] = useState([])
  const [records, setRecords] = useState([])
  const [inviteCode, setInviteCode] = useState('')
  const [inviteExpiresAt, setInviteExpiresAt] =
    useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const careGroupId =
    careGroup?.care_group_id ??
    careGroup?.care_groups_id ??
    null

  // care_groups.user_id는 가족방을 처음 만든 사용자의 ID다.
  // API 응답 필드명이 달라질 가능성을 고려해 호환 필드도 함께 확인한다.
  const careGroupOwnerId =
    careGroup?.user_id ??
    careGroup?.owner_user_id ??
    careGroup?.owner_id ??
    null

  const resetFamily = useCallback(() => {
    setCareGroup(null)
    setMembers([])
    setRecords([])
    setInviteCode('')
    setInviteExpiresAt(null)
    unlinkFamily()
  }, [unlinkFamily])

  const refreshFamily = useCallback(async () => {
    if (!userId) {
      resetFamily()
      return null
    }

    setLoading(true)
    setError('')

    try {
      const groups = await getMyCareGroups(userId)
      const group = groups[0] ?? null

      if (!group) {
        resetFamily()
        return null
      }

      const groupId =
        group.care_group_id ??
        group.care_groups_id

      setCareGroup(group)
      linkFamily()

      const [nextMembers, letters] =
        await Promise.all([
          getCareGroupMembers({
            careGroupId: groupId,
            userId,
          }),
          getFamilyLetters({
            careGroupId: groupId,
            userId,
            page: 1,
            size: 100,
          }),
        ])

      setMembers(nextMembers)

      if (nextMembers.length >= 2) {
        linkFamily()
      } else {
        unlinkFamily()
      }

      setRecords(
        letters.map((letter) =>
          toRecord(letter, userId),
        ),
      )
      

      return group
    } catch (requestError) {
      setError(requestError.message)
      throw requestError
    } finally {
      setLoading(false)
    }
  }, [
    userId,
    linkFamily,
    resetFamily,
  ])

  useEffect(() => {
    refreshFamily().catch(() => {
      // 오류 문구는 error 상태를 통해 화면에서 표시한다.
    })
  }, [refreshFamily])

  const createFamilyRoom = async (
    relationships = '본인',
  ) => {
    if (!userId) {
      throw new Error('로그인이 필요합니다.')
    }

    await createCareGroup({
      userId,
      relationships,
    })

    return refreshFamily()
  }

  const regenerateCode = async () => {
    if (!userId) {
      throw new Error('로그인이 필요합니다.')
    }

    let groupId = careGroupId

    if (!groupId) {
      const group =
        await createFamilyRoom('본인')

      groupId =
        group?.care_group_id ??
        group?.care_groups_id
    }

    const invite = await createInviteCode({
      userId,
      careGroupId: groupId,
    })

    setInviteCode(invite.invite_code)
    setInviteExpiresAt(invite.expires_at)

    return invite
  }

  const joinWithCode = async ({
    code,
    relationships,
  }) => {
    if (!userId) {
      throw new Error('로그인이 필요합니다.')
    }

    const result = await joinCareGroup({
      userId,
      inviteCode: code,
      relationships,
    })

    await refreshFamily()
    return result
  }

  const addRecord = async (rawBody) => {
    const content = rawBody.trim()

    if (!content) {
      return null
    }

    if (!userId || !careGroupId) {
      throw new Error(
        '가족방에 연결한 후 기록할 수 있습니다.',
      )
    }

    const letter = await createFamilyLetter({
      userId,
      careGroupId,
      content,
    })

    const record = toRecord(letter, userId)
    setRecords((previous) => [
      record,
      ...previous,
    ])

    return record
  }

  const getRecord = (recordId) =>
    records.find(
      (record) =>
        String(record.id) === String(recordId),
    )

  const value = useMemo(
    () => ({
      careGroup,
      careGroupId,
      careGroupOwnerId,
      members,
      records,
      inviteCode,
      inviteExpiresAt,
      loading,
      error,
      refreshFamily,
      createFamilyRoom,
      regenerateCode,
      joinWithCode,
      addRecord,
      getRecord,
    }),
    [
      careGroup,
      careGroupId,
      careGroupOwnerId,
      members,
      records,
      inviteCode,
      inviteExpiresAt,
      loading,
      error,
      refreshFamily,
    ],
  )

  return (
    <FamilyCtx.Provider value={value}>
      {children}
    </FamilyCtx.Provider>
  )
}

export function useFamily() {
  const context = useContext(FamilyCtx)

  if (!context) {
    throw new Error(
      'useFamily must be used within FamilyProvider',
    )
  }

  return context
}