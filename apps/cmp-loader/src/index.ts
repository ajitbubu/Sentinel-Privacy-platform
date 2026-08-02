/**
 * Sentinel CMP loader.
 *
 * Runs on the customer's site. Zero dependencies, no framework, shadow DOM, and
 * it must never break their page — every failure path leaves the host site
 * working, because a privacy banner that takes down a booking flow will simply
 * be removed and then nobody's consent is captured at all.
 */
import { collect, fetchConfig } from './api';
import { installAutoBlock, pushConsentMode, releaseTags, stopAutoBlock } from './blocking';
import * as storage from './storage';
import { BannerUI } from './ui';
import type { InteractionType, SiteConfig, StoredConsent } from './types';

const RECONSENT_DAYS = 365;

class Sentinel {
  private base = '';
  private key = '';
  private cfg: SiteConfig | null = null;
  private ui: BannerUI | null = null;
  private stored: StoredConsent | null = null;
  private listeners: Array<(p: Record<string, boolean>) => void> = [];
  private ready = false;

  private isGranted = (purpose: string): boolean => {
    if (!this.stored) return false;
    return this.stored.purposes[purpose] === true;
  };

  /** Purposes required by the notice are on regardless of what is stored. */
  private withRequired(choices: Record<string, boolean>): Record<string, boolean> {
    const out = { ...choices };
    for (const p of this.cfg?.purposes || []) if (p.required) out[p.slug] = true;
    return out;
  }

  /**
   * The purposes that were on screen, mapped to the state they were shown in.
   *
   * The keys are the evidence of what was offered; the values are the evidence
   * that nothing was pre-ticked. Only a required purpose may start switched on,
   * so a row of `false` is the compliant reading rather than an empty one — a
   * pre-ticked optional purpose is not freely given consent, and this is the
   * record that shows we did not do that.
   */
  private presented(): Record<string, boolean> {
    const out: Record<string, boolean> = {};
    for (const p of this.cfg?.purposes || []) out[p.slug] = p.required;
    return out;
  }

  init(opts: { key: string; api?: string; lang?: string }): void {
    this.key = opts.key;
    this.base = (opts.api || '').replace(/\/$/, '');
    this.stored = storage.load();

    // Blocking starts before the config request resolves. Waiting for a network
    // round trip would let a tracker fire in the gap, which is exactly the leak
    // the feature exists to close.
    installAutoBlock(this.isGranted);
    pushConsentMode(this.isGranted);

    fetchConfig(this.base, this.key, opts.lang || this.stored?.lang)
      .then((cfg) => this.onConfig(cfg))
      .catch((e) => {
        // Fail closed on tags, open on the page. Nothing is released without a
        // config to prove consent against, but the customer's site is untouched.
        // eslint-disable-next-line no-console
        console.warn('[sentinel] config unavailable, tags stay blocked:', e?.message || e);
      });
  }

  private onConfig(cfg: SiteConfig): void {
    this.cfg = cfg;
    this.ready = true;
    this.ui = new BannerUI(cfg, {
      onAcceptAll: () => this.decide(this.allPurposes(true), 'accept_all'),
      onRejectAll: () => this.decide(this.allPurposes(false), 'reject_all'),
      onSave: (c) => this.decide(c, 'save_preferences'),
      onWithdraw: () => this.reopen(),
      onLanguage: (code) => this.switchLanguage(code),
    });

    const stale = this.stored ? storage.isStale(this.stored, cfg.banner_version, RECONSENT_DAYS) : true;
    if (this.stored && !stale) {
      this.applyStored();
      this.ui.showWithdrawAffordance();
    } else {
      this.ui.render(this.stored?.purposes || {});
    }
  }

  private allPurposes(value: boolean): Record<string, boolean> {
    const out: Record<string, boolean> = {};
    for (const p of this.cfg?.purposes || []) out[p.slug] = p.required ? true : value;
    return out;
  }

  private applyStored(): void {
    releaseTags(this.isGranted);
    pushConsentMode(this.isGranted);
    this.emit();
  }

  private decide(rawChoices: Record<string, boolean>, interaction: InteractionType): void {
    if (!this.cfg) return;
    const purposes = this.withRequired(rawChoices);

    // The local state moves first. The person clicked; the page should respond
    // now rather than after a round trip, and the record is reconciled behind it.
    const optimistic: StoredConsent = {
      pid: this.stored?.pid || '',
      purposes,
      lang: this.cfg.language.code,
      bv: this.cfg.banner_version,
      rid: this.stored?.rid || '',
      ts: Math.floor(Date.now() / 1000),
    };
    this.stored = optimistic;
    this.applyStored();
    this.ui?.showWithdrawAffordance();

    collect(this.base, this.key, {
      pseudonymous_id: this.stored.pid || null,
      purposes,
      purposes_presented: this.presented(),
      interaction_type: interaction,
      language: this.cfg.language.code,
      page_url: location.href.slice(0, 2000),
    })
      .then((res) => {
        this.stored = { ...optimistic, pid: res.pseudonymous_id, rid: res.receipt_id };
        storage.save(this.stored, RECONSENT_DAYS);
      })
      .catch((e) => {
        // Persist anyway. Losing the choice locally would re-prompt someone who
        // has already answered; the server record is retried on the next visit.
        storage.save(optimistic, RECONSENT_DAYS);
        // eslint-disable-next-line no-console
        console.warn('[sentinel] consent not recorded server-side:', e?.message || e);
      });
  }

  private reopen(): void {
    this.ui?.render(this.stored?.purposes || {});
  }

  private switchLanguage(code: string): void {
    fetchConfig(this.base, this.key, code)
      .then((cfg) => {
        this.cfg = cfg;
        this.ui?.update(cfg);
        this.ui?.render(this.stored?.purposes || {});
      })
      .catch(() => {
        /* keep the current language rather than blanking the notice */
      });
  }

  /**
   * Link this browser's pseudonymous id to a known person.
   *
   * Called by the customer after their own login. It does not send an email
   * address to the collector — that endpoint is public and unauthenticated, so
   * accepting identifiers there would let anyone write into another person's
   * consent record. The customer's backend performs the link against the
   * authenticated API using the pseudonymous id we hand back here.
   */
  identify(): string | null {
    return this.stored?.pid || null;
  }

  getConsent(): Record<string, boolean> {
    return this.stored ? { ...this.stored.purposes } : {};
  }

  onChange(fn: (p: Record<string, boolean>) => void): void {
    this.listeners.push(fn);
    if (this.stored) fn(this.getConsent());
  }

  showPreferences(): void {
    if (this.ready) this.reopen();
  }

  withdrawAll(): void {
    this.decide(this.allPurposes(false), 'withdraw');
  }

  private emit(): void {
    const snapshot = this.getConsent();
    for (const fn of this.listeners) {
      try {
        fn(snapshot);
      } catch {
        /* a customer callback throwing must not stop the others */
      }
    }
  }

  reset(): void {
    storage.clear();
    stopAutoBlock();
    this.stored = null;
  }
}

// --------------------------------------------------------------- public glue

const instance = new Sentinel();

type Cmd = [string, ...unknown[]];

function exec(cmd: Cmd): unknown {
  const [name, ...args] = cmd;
  const fn = (instance as unknown as Record<string, (...a: unknown[]) => unknown>)[name];
  if (typeof fn !== 'function') return undefined;
  return fn.apply(instance, args);
}

// The snippet creates a stub array so calls made before this file lands are not
// lost. Drain it, then replace the stub with a real dispatcher.
const w = window as unknown as { sentinel?: { q?: Cmd[] } & ((...a: unknown[]) => unknown) };
const pending: Cmd[] = (w.sentinel && w.sentinel.q) || [];

const api = ((...args: unknown[]) => exec(args as Cmd)) as typeof w.sentinel;
w.sentinel = api;

for (const cmd of pending) {
  try {
    exec(cmd);
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('[sentinel]', e);
  }
}

export {};
