import type { InteractionType, SiteConfig } from './types';

export interface CollectResult {
  receipt_id: string;
  pseudonymous_id: string;
  receipt: string;
  language: string;
  expires_at: string;
}

export function fetchConfig(base: string, key: string, lang?: string): Promise<SiteConfig> {
  const url = base + '/api/v1/cmp/config/' + encodeURIComponent(key) + (lang ? '?lang=' + encodeURIComponent(lang) : '');
  return fetch(url, { credentials: 'omit' }).then((r) => {
    if (!r.ok) throw new Error('config ' + r.status);
    return r.json() as Promise<SiteConfig>;
  });
}

export function collect(
  base: string,
  key: string,
  body: {
    pseudonymous_id?: string | null;
    purposes: Record<string, boolean>;
    purposes_presented: Record<string, boolean>;
    interaction_type: InteractionType;
    language?: string;
    page_url?: string;
  },
): Promise<CollectResult> {
  // The key rides in the path so the CORS preflight can resolve the site —
  // a preflight carries no custom headers, only their names.
  return fetch(base + '/api/v1/cmp/collect/' + encodeURIComponent(key), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    credentials: 'omit',
    body: JSON.stringify(body),
    // The record must survive the person navigating away the instant they
    // click. keepalive lets the request outlive the page.
    keepalive: true,
  }).then((r) => {
    if (!r.ok) throw new Error('collect ' + r.status);
    return r.json() as Promise<CollectResult>;
  });
}
