/**
 * Session state.
 *
 * Only EMPLOYEE role is supported.
 */
import { setToken } from '@/lib/apiClient'
import { ROLE, type Role } from '@/types/domain'

export const SESSION_KEY = 'vaic-session'

/** Fired after this tab writes or clears the session (storage events do not). */
export const SESSION_CHANGED_EVENT = 'vaic:session-changed'

export interface Session {
  username: string
  role: Role
}

/** Pure parse + validation, so useSession can memoise on the raw string. */
export function parseSession(raw: string | null): Session | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Session
    // reject anything carrying an unsupported role
    if (parsed.role !== ROLE.EMPLOYEE) return null
    return parsed
  } catch {
    return null
  }
}

export function readSession(): Session | null {
  if (typeof window === 'undefined') return null
  return parseSession(window.localStorage.getItem(SESSION_KEY))
}

function notifyChanged(): void {
  window.dispatchEvent(new CustomEvent(SESSION_CHANGED_EVENT))
}

export function writeSession(session: Session, token: string): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session))
  setToken(token)
  notifyChanged()
}

export function clearSession(): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(SESSION_KEY)
  setToken(null)
  notifyChanged()
}

/** All business routes require EMPLOYEE role. */
export function canUseBusinessRoutes(session: Session | null): boolean {
  return session?.role === ROLE.EMPLOYEE
}

