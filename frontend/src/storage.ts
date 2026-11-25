const TOKEN_COOKIE_NAME = "pez_participant_token";
const TOKEN_NOTICE_PENDING_KEY = "pez_participant_token_notice_pending";
const TOKEN_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

function readTokenCookie(): string | null {
  try {
    const prefix = `${TOKEN_COOKIE_NAME}=`;
    const cookie = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
  } catch {
    return null;
  }
}

export function loadStoredToken(): string | null {
  const cookieToken = readTokenCookie();
  if (cookieToken) {
    try {
      window.localStorage.removeItem(TOKEN_COOKIE_NAME);
    } catch {
      // Ignore unavailable local storage.
    }
    return cookieToken;
  }

  // Migrate tokens saved by older versions from localStorage to the cookie.
  try {
    const legacyToken = window.localStorage.getItem(TOKEN_COOKIE_NAME);
    if (legacyToken) storeToken(legacyToken);
    return legacyToken;
  } catch {
    return null;
  }
}

export function storeToken(token: string): void {
  try {
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${TOKEN_COOKIE_NAME}=${encodeURIComponent(token)}; Path=/; Max-Age=${TOKEN_COOKIE_MAX_AGE}; SameSite=Lax${secure}`;
  } catch {
    return;
  }

  if (readTokenCookie() === token) {
    try {
      window.localStorage.removeItem(TOKEN_COOKIE_NAME);
    } catch {
      // Ignore unavailable local storage.
    }
  }
}

export function markTokenNoticePending(): void {
  try {
    window.localStorage.setItem(TOKEN_NOTICE_PENDING_KEY, "true");
  } catch {
    // The token page still works for the current visit if storage is unavailable.
  }
}

export function isTokenNoticePending(): boolean {
  try {
    return window.localStorage.getItem(TOKEN_NOTICE_PENDING_KEY) === "true";
  } catch {
    return false;
  }
}

export function clearTokenNoticePending(): void {
  try {
    window.localStorage.removeItem(TOKEN_NOTICE_PENDING_KEY);
  } catch {
    // Ignore unavailable local storage.
  }
}

export function clearStoredToken(): void {
  try {
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${TOKEN_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
    window.localStorage.removeItem(TOKEN_COOKIE_NAME);
    window.localStorage.removeItem(TOKEN_NOTICE_PENDING_KEY);
  } catch {
    // Ignore unavailable browser storage.
  }
}
