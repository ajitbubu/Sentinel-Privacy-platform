import type { SiteConfig } from './types';

export interface UIHandlers {
  onAcceptAll: () => void;
  onRejectAll: () => void;
  onSave: (choices: Record<string, boolean>) => void;
  onWithdraw: () => void;
  onLanguage: (code: string) => void;
}

const CSS = `
:host{all:initial}
*{box-sizing:border-box;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{position:fixed;z-index:2147483647;left:0;right:0;padding:16px;display:flex;justify-content:center}
.wrap[data-pos=bottom]{bottom:0}
.wrap[data-pos=top]{top:0}
.card{width:100%;max-width:920px;background:var(--bg);color:var(--fg);border-radius:12px;
  box-shadow:0 8px 32px rgba(0,0,0,.18),0 2px 8px rgba(0,0,0,.12);padding:20px 22px;
  max-height:85vh;overflow-y:auto}
h2{margin:0 0 8px;font-size:17px;font-weight:650;line-height:1.3}
p{margin:0 0 12px;font-size:14px;line-height:1.55;opacity:.92}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:14px}
button{font-size:14px;font-weight:560;padding:10px 18px;border-radius:8px;cursor:pointer;
  border:1.5px solid transparent;line-height:1.2;min-height:42px}
button:focus-visible{outline:3px solid var(--btn);outline-offset:2px}
/* Accept and reject carry identical weight. DPDP s.6(4) requires withdrawing
   consent to be as easy as giving it, and a reject styled as a faint link is
   the classic way of making it harder. */
.primary{background:var(--btn);color:#fff;border-color:var(--btn)}
.secondary{background:transparent;color:var(--fg);border-color:currentColor}
.link{background:none;border:none;text-decoration:underline;padding:8px 4px;font-weight:450;
  color:var(--fg);min-height:auto}
.grow{flex:1}
.purposes{margin:6px 0 0;border-top:1px solid rgba(128,128,128,.28);padding-top:6px}
.purpose{display:flex;gap:12px;align-items:flex-start;padding:12px 0;
  border-bottom:1px solid rgba(128,128,128,.18)}
.purpose:last-child{border-bottom:none}
.purpose .meta{flex:1;min-width:0}
.purpose .nm{font-size:14px;font-weight:600;display:block;margin-bottom:2px}
.purpose .ds{font-size:13px;opacity:.85;line-height:1.5}
.req{font-size:12px;opacity:.7;white-space:nowrap;padding-top:2px}
.sw{position:relative;width:44px;height:26px;flex:none;margin-top:2px}
.sw input{position:absolute;opacity:0;width:100%;height:100%;margin:0;cursor:pointer}
.sw span{position:absolute;inset:0;background:#9aa2ad;border-radius:99px;transition:background .15s;pointer-events:none}
.sw span:after{content:"";position:absolute;width:20px;height:20px;border-radius:50%;
  background:#fff;top:3px;left:3px;transition:transform .15s}
.sw input:checked+span{background:var(--btn)}
.sw input:checked+span:after{transform:translateX(18px)}
.sw input:focus-visible+span{outline:3px solid var(--btn);outline-offset:2px}
.sw input:disabled+span{opacity:.55}
.fid{margin-top:14px;padding-top:12px;border-top:1px solid rgba(128,128,128,.28);
  font-size:12.5px;line-height:1.6;opacity:.88}
.fid strong{font-weight:620}
.fid a{color:inherit}
.mt{font-size:12px;margin-top:10px;padding:7px 10px;border-radius:6px;
  background:rgba(180,120,0,.13);border:1px solid rgba(180,120,0,.35)}
select{font-size:13px;padding:7px 10px;border-radius:7px;border:1.5px solid currentColor;
  background:transparent;color:var(--fg);min-height:38px}
.fab{position:fixed;bottom:16px;inset-inline-start:16px;z-index:2147483646;background:var(--btn);
  color:#fff;border:none;border-radius:99px;padding:11px 16px;font-size:13px;font-weight:560;
  cursor:pointer;box-shadow:0 3px 14px rgba(0,0,0,.28);min-height:42px}
.hidden{display:none!important}
@media(max-width:560px){
  .card{padding:16px}
  .row button{flex:1 1 100%}
  .row .link{flex:1 1 auto}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
`;

export class BannerUI {
  private host: HTMLElement;
  private root: ShadowRoot;
  private cfg: SiteConfig;
  private h: UIHandlers;
  private lastFocus: Element | null = null;
  private detailsOpen = false;

  constructor(cfg: SiteConfig, handlers: UIHandlers) {
    this.cfg = cfg;
    this.h = handlers;
    this.host = document.createElement('div');
    this.host.setAttribute('data-sentinel-cmp', '');
    // Shadow DOM so the customer's stylesheet cannot restyle a legal notice,
    // deliberately or otherwise, and so ours cannot leak onto their page.
    this.root = this.host.attachShadow({ mode: 'open' });
    document.body.appendChild(this.host);
  }

  private esc(s: string | null | undefined): string {
    return String(s ?? '').replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string);
  }

  private styleVars(): string {
    const a = this.cfg.appearance;
    return `--bg:${a?.background || '#ffffff'};--fg:${a?.text || '#1a1d21'};--btn:${a?.button || '#2f62d8'}`;
  }

  /** The identity block. DPDP s.6(3) and R.3 require the notice to say who is
   *  processing; s.8(9)/R.9 require a reachable grievance contact. */
  private fiduciaryHTML(): string {
    const d = this.cfg.data_fiduciary;
    const bits: string[] = [`<strong>${this.esc(d.name)}</strong>`];
    if (d.address) bits.push(this.esc(d.address));
    const contact: string[] = [];
    if (d.grievance_officer) contact.push(this.esc(d.grievance_officer));
    if (d.grievance_email)
      contact.push(`<a href="mailto:${this.esc(d.grievance_email)}">${this.esc(d.grievance_email)}</a>`);
    if (d.grievance_phone) contact.push(this.esc(d.grievance_phone));
    const line = contact.length ? `<div>Grievance Officer: ${contact.join(' · ')}</div>` : '';
    return `<div class="fid"><div>${bits.join(' · ')}</div>${line}</div>`;
  }

  private languageHTML(): string {
    const av = this.cfg.language.available;
    if (av.length < 2) return '';
    const opts = av
      .map((l) => `<option value="${this.esc(l.code)}"${l.code === this.cfg.language.code ? ' selected' : ''}>${this.esc(l.name)}</option>`)
      .join('');
    return `<select id="lang" aria-label="Choose language">${opts}</select>`;
  }

  private machineTranslatedHTML(): string {
    if (!this.cfg.language.machine_translated) return '';
    // Saying so is the honest position: a machine translation of a legal notice
    // is not equivalent to a reviewed one, and hiding that would misrepresent
    // what the person actually agreed to.
    return `<div class="mt" role="note">This notice was machine-translated. The English version is the reviewed text.</div>`;
  }

  private purposesHTML(stored: Record<string, boolean>): string {
    return (
      '<div class="purposes" id="purposes">' +
      this.cfg.purposes
        .map((p) => {
          const on = p.required || stored[p.slug] === true;
          return `<div class="purpose">
            <div class="meta">
              <span class="nm" id="nm-${this.esc(p.slug)}">${this.esc(p.name)}</span>
              <span class="ds">${this.esc(p.description)}</span>
            </div>
            ${p.required
              ? `<span class="req">Always active</span>`
              : `<label class="sw"><input type="checkbox" data-purpose="${this.esc(p.slug)}"
                   ${on ? 'checked' : ''} aria-labelledby="nm-${this.esc(p.slug)}"><span></span></label>`}
          </div>`;
        })
        .join('') +
      '</div>'
    );
  }

  render(stored: Record<string, boolean>): void {
    const n = this.cfg.notice;
    const rtl = this.cfg.language.rtl;
    this.lastFocus = document.activeElement;

    this.root.innerHTML = `<style>${CSS}</style>
      <div class="wrap" data-pos="${this.esc(this.cfg.appearance?.position || 'bottom')}"
           style="${this.styleVars()}" dir="${rtl ? 'rtl' : 'ltr'}">
        <div class="card" role="dialog" aria-modal="false" aria-labelledby="t" aria-describedby="m"
             lang="${this.esc(this.cfg.language.code)}">
          <h2 id="t">${this.esc(n.title || 'Your privacy choices')}</h2>
          <p id="m">${this.esc(n.message || '')}</p>
          ${this.machineTranslatedHTML()}
          <div class="${this.detailsOpen ? '' : 'hidden'}" id="details">${this.purposesHTML(stored)}</div>
          <div class="row">
            <button class="primary" id="accept">${this.esc(n.accept)}</button>
            <button class="secondary" id="reject">${this.esc(n.reject)}</button>
            <button class="link" id="toggle" aria-expanded="${this.detailsOpen}" aria-controls="details">${this.esc(n.customise)}</button>
            <span class="grow"></span>
            ${this.languageHTML()}
            <button class="primary ${this.detailsOpen ? '' : 'hidden'}" id="save">Save preferences</button>
          </div>
          ${this.fiduciaryHTML()}
        </div>
      </div>`;

    this.wire();
    (this.root.getElementById('accept') as HTMLElement | null)?.focus();
  }

  private choices(): Record<string, boolean> {
    const out: Record<string, boolean> = {};
    for (const p of this.cfg.purposes) out[p.slug] = p.required;
    this.root.querySelectorAll<HTMLInputElement>('input[data-purpose]').forEach((i) => {
      out[i.dataset.purpose as string] = i.checked;
    });
    return out;
  }

  private wire(): void {
    const g = (id: string) => this.root.getElementById(id);
    g('accept')?.addEventListener('click', () => this.h.onAcceptAll());
    g('reject')?.addEventListener('click', () => this.h.onRejectAll());
    g('save')?.addEventListener('click', () => this.h.onSave(this.choices()));
    g('toggle')?.addEventListener('click', () => {
      this.detailsOpen = !this.detailsOpen;
      this.render(this.choices());
    });
    g('lang')?.addEventListener('change', (e) =>
      this.h.onLanguage((e.target as HTMLSelectElement).value));
  }

  /**
   * The standing way back in.
   *
   * DPDP s.6(4) requires withdrawal to be as easy as giving consent. A banner
   * that disappears for good once dismissed leaves no route back, so something
   * persistent has to remain on the page.
   */
  showWithdrawAffordance(): void {
    this.detailsOpen = false;
    this.root.innerHTML = `<style>${CSS}</style>
      <button class="fab" id="fab" style="${this.styleVars()}"
              dir="${this.cfg.language.rtl ? 'rtl' : 'ltr'}">
        ${this.esc(this.cfg.notice.withdraw || 'Privacy settings')}
      </button>`;
    this.root.getElementById('fab')?.addEventListener('click', () => this.h.onWithdraw());
  }

  destroy(): void {
    this.root.innerHTML = '';
    (this.lastFocus as HTMLElement | null)?.focus?.();
  }

  update(cfg: SiteConfig): void {
    this.cfg = cfg;
  }
}
