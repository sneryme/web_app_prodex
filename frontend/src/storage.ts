// Токен хранится у участника (ТЗ п.3): localStorage — основной способ, а не сервер.
const STORAGE_KEY = "pez_participant_token";

export function loadStoredToken(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function storeToken(token: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, token);
  } catch {
    // приватный режим или квота — участник всё равно может продолжить по коду, показанному на экране
  }
}

export function clearStoredToken(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
