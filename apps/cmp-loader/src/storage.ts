import type { StoredConsent } from './types';

const KEY = '_sentinel_consent';

/**
 * localStorage with a cookie fallback.
 *
 * The cookie matters more than it looks: Safari caps script-written localStorage
 * on some configurations and clears it after seven days of no interaction. A
 * consent record that silently evaporates would re-prompt someone who already
 * answered, which reads to a regulator as though we never captured the choice.
 */
function readRaw(): string | null {
  try {
    const v = window.localStorage.getItem(KEY);
    if (v) return v;
  } catch {
    /* private mode, disabled storage — fall through to the cookie */
  }
  const m = document.cookie.match(new RegExp('(?:^|; )' + KEY + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : null;
}

function writeRaw(value: string, days: number): void {
  try {
    window.localStorage.setItem(KEY, value);
  } catch {
    /* ignore — the cookie below is the fallback */
  }
  const exp = new Date(Date.now() + days * 864e5).toUTCString();
  // Lax rather than None: the banner is only ever read first-party, and None
  // would require Secure plus a third-party cookie that browsers are removing.
  document.cookie =
    KEY + '=' + encodeURIComponent(value) + ';path=/;expires=' + exp + ';SameSite=Lax';
}

export function load(): StoredConsent | null {
  const raw = readRaw();
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredConsent;
    if (!parsed || typeof parsed !== 'object' || !parsed.pid) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function save(c: StoredConsent, days: number): void {
  writeRaw(JSON.stringify(c), days);
}

export function clear(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
  document.cookie = KEY + '=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT;SameSite=Lax';
}

/**
 * Whether a stored choice still stands.
 *
 * Re-prompt when the notice materially changed (banner version moved) or the
 * record aged out. Consent given against wording that no longer exists is not
 * consent to the current wording — that is the whole reason banner_versions is
 * immutable and the version travels with the record.
 */
export function isStale(c: StoredConsent, currentVersion: number | null, maxAgeDays: number): boolean {
  if (currentVersion != null && c.bv != null && currentVersion > c.bv) return true;
  return Date.now() / 1000 - c.ts > maxAgeDays * 86400;
}
