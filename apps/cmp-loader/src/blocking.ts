/**
 * Tag blocking.
 *
 * Honest about what this can and cannot do, because the difference is a
 * compliance question rather than a technical nicety:
 *
 *   Cooperative blocking (reliable). The customer marks a tag
 *     <script type="text/plain" data-sentinel-purpose="analytics" src="...">
 *   The browser will not execute a script whose type it does not recognise, so
 *   the tag is inert no matter when it appears. On consent we clone it with the
 *   real type and it runs. This is the only form that is guaranteed.
 *
 *   Auto-blocking (best effort). A MutationObserver installed before anything
 *   else neutralises matching <script> nodes as they are added. This does catch
 *   the common case, because GTM, GA and the ad pixels all inject their tags
 *   dynamically. It does NOT reliably catch a plain <script src> sitting in the
 *   customer's served HTML: the parser executes those synchronously and an
 *   observer callback is a microtask that arrives afterwards.
 *
 * So auto_block reduces leakage; it does not make a site compliant on its own.
 * The console tells customers this rather than implying blanket coverage,
 * because a Data Fiduciary relying on it would be carrying a risk they did not
 * know they had.
 */

const BLOCKED_TYPE = 'text/sentinel-blocked';
const PURPOSE_ATTR = 'data-sentinel-purpose';
const SRC_ATTR = 'data-sentinel-src';

/** Known trackers, mapped to the purpose they belong to. */
const KNOWN: Array<[RegExp, string]> = [
  [/googletagmanager\.com|google-analytics\.com|\/gtag\/js/i, 'analytics'],
  [/connect\.facebook\.net|facebook\.com\/tr/i, 'marketing'],
  [/doubleclick\.net|googlesyndication\.com|googleadservices\.com/i, 'marketing'],
  [/hotjar\.com|clarity\.ms|fullstory\.com|mouseflow\.com/i, 'analytics'],
  [/linkedin\.com\/px|snap\.licdn\.com|analytics\.tiktok\.com/i, 'marketing'],
  [/hubspot\.com|hs-scripts\.com|hs-analytics\.net/i, 'marketing'],
];

function purposeForSrc(src: string): string | null {
  for (const [re, purpose] of KNOWN) if (re.test(src)) return purpose;
  return null;
}

let observer: MutationObserver | null = null;
let granted: Record<string, boolean> = {};

function neutralise(el: HTMLScriptElement, purpose: string): void {
  if (el.type === BLOCKED_TYPE) return;
  el.type = BLOCKED_TYPE;
  el.setAttribute(PURPOSE_ATTR, purpose);
  if (el.src) {
    el.setAttribute(SRC_ATTR, el.src);
    // Clearing src is what actually stops the fetch. Setting type alone leaves
    // an already-started request in flight in some browsers.
    el.removeAttribute('src');
  }
}

let srcPatched = false;

/**
 * Intercept `script.src = ...` before the node is ever inserted.
 *
 * A MutationObserver alone is not enough and it is worth being precise about
 * why: the browser begins fetching a dynamically-created script the moment its
 * src is set and it is connected to the document, whereas observer callbacks
 * are microtasks that run afterwards. By the time we saw the node the request
 * was already on the wire — measured, not assumed: the GA request went out with
 * the observer installed and working.
 *
 * Every real tag injector (GTM, GA, the Meta pixel) does
 * `el = createElement('script'); el.src = ...; head.appendChild(el)`, so
 * trapping the setter catches them before a single byte leaves the browser.
 * The observer stays as a second net for the `setAttribute('src', ...)` path.
 */
function patchSrcSetter(isGranted: (purpose: string) => boolean): void {
  if (srcPatched) return;
  const proto = HTMLScriptElement.prototype;
  const desc = Object.getOwnPropertyDescriptor(proto, 'src');
  if (!desc || !desc.set || !desc.get) return;
  srcPatched = true;

  Object.defineProperty(proto, 'src', {
    configurable: true,
    enumerable: desc.enumerable,
    get(this: HTMLScriptElement) {
      return this.getAttribute(SRC_ATTR) || desc.get!.call(this);
    },
    set(this: HTMLScriptElement, value: string) {
      const purpose = purposeForSrc(String(value || ''));
      if (purpose && !isGranted(purpose)) {
        // Park the URL where releaseTags can find it and never assign the real
        // property, so no request is made.
        this.setAttribute(SRC_ATTR, String(value));
        this.setAttribute(PURPOSE_ATTR, purpose);
        this.type = BLOCKED_TYPE;
        return;
      }
      desc.set!.call(this, value);
    },
  });
}

/**
 * Start auto-blocking. Must run before the customer's tags, which is why the
 * snippet goes in <head> and this is called synchronously at parse time.
 */
export function installAutoBlock(isGranted: (purpose: string) => boolean): void {
  patchSrcSetter(isGranted);
  if (observer) return;

  observer = new MutationObserver((records) => {
    for (const r of records) {
      r.addedNodes.forEach((n) => {
        if ((n as Element).nodeName !== 'SCRIPT') return;
        const el = n as HTMLScriptElement;
        const src = el.getAttribute('src') || '';
        if (!src) return;
        const purpose = purposeForSrc(src);
        if (purpose && !isGranted(purpose)) neutralise(el, purpose);
      });
    }
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });
}

export function stopAutoBlock(): void {
  observer?.disconnect();
  observer = null;
}

/**
 * Run the tags a person has now consented to.
 *
 * A blocked script cannot be un-blocked in place — changing `type` after the
 * browser has seen the node does not re-queue it — so each one is replaced by a
 * fresh element carrying the original attributes.
 */
export function releaseTags(isGranted: (purpose: string) => boolean): void {
  granted = {};
  const selector = 'script[type="text/plain"][' + PURPOSE_ATTR + '], script[type="' + BLOCKED_TYPE + '"]';
  document.querySelectorAll<HTMLScriptElement>(selector).forEach((el) => {
    const purpose = el.getAttribute(PURPOSE_ATTR) || '';
    if (!purpose || !isGranted(purpose) || granted[purpose + el.src]) return;

    const fresh = document.createElement('script');
    for (const attr of Array.from(el.attributes)) {
      if (attr.name === 'type' || attr.name === SRC_ATTR) continue;
      fresh.setAttribute(attr.name, attr.value);
    }
    const src = el.getAttribute(SRC_ATTR);
    if (src) fresh.src = src;
    else fresh.text = el.textContent || '';
    fresh.type = el.getAttribute('data-sentinel-type') || 'text/javascript';

    el.parentNode?.insertBefore(fresh, el.nextSibling);
    el.parentNode?.removeChild(el);
  });
}

/**
 * Google Consent Mode v2.
 *
 * Pushed whether or not gtag is present — Google's own snippet reads the
 * dataLayer queue on load, so ordering does not matter, and a site without
 * Google tags is simply left with an unread array.
 */
export function pushConsentMode(isGranted: (p: string) => boolean): void {
  const w = window as unknown as { dataLayer?: unknown[] };
  w.dataLayer = w.dataLayer || [];
  const v = (b: boolean) => (b ? 'granted' : 'denied');
  w.dataLayer.push([
    'consent',
    'update',
    {
      ad_storage: v(isGranted('marketing')),
      ad_user_data: v(isGranted('marketing')),
      ad_personalization: v(isGranted('marketing')),
      analytics_storage: v(isGranted('analytics')),
      functionality_storage: v(isGranted('functional')),
      personalization_storage: v(isGranted('functional')),
      security_storage: 'granted',
    },
  ]);
}
