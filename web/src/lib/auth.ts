// Per-client dashboard access token (see naib.dashboard_auth). Naib has no
// user-account system yet -- a client's whole "session" is this token,
// captured once from a magic link's `?token=` query param (or typed in on
// the Landing page) and remembered per-viewer via localStorage so a reload
// doesn't lose it. See naib.dashboard_auth's docstring for the backend side
// and its scope.

const PREFIX = "naib.token."

export function getStoredToken(clientId: string): string | null {
  try {
    return localStorage.getItem(PREFIX + clientId)
  } catch {
    return null
  }
}

export function setStoredToken(clientId: string, token: string): void {
  try {
    localStorage.setItem(PREFIX + clientId, token)
  } catch {
    // Private browsing / blocked storage -- the token just won't survive a
    // reload; the current session still works since it's held in memory.
  }
}
