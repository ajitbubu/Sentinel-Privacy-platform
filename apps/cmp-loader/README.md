# @sentinel/cmp-loader

The script a customer embeds in their site. Renders the consent notice,
blocks tags until a choice is made, and posts the result to the collector.

## Installing on a customer site

```html
<script>
!function(w,d,s,u){w.sentinel=w.sentinel||function(){(w.sentinel.q=w.sentinel.q||[]).push(arguments)};
var e=d.createElement(s);e.async=1;e.src=u;d.head.appendChild(e)}
(window,document,'script','https://cdn.sentinel.example/sentinel.js');
sentinel('init',{key:'pk_site_xxxxx', api:'https://api.sentinel.example'});
</script>
```

Put it in `<head>`, above every other tag. The stub queues calls made before
the script finishes loading, so nothing is lost, but auto-blocking can only
protect tags that appear after it runs.

## Public API

| Call | Purpose |
|---|---|
| `sentinel('init', {key, api, lang})` | Start. `lang` overrides negotiation. |
| `sentinel('getConsent')` | Current `{purpose: boolean}`. |
| `sentinel('onChange', fn)` | Fires on every change, and once immediately if a choice already exists. |
| `sentinel('showPreferences')` | Reopen the notice. |
| `sentinel('withdrawAll')` | Withdraw everything. |
| `sentinel('identify')` | Returns this browser's pseudonymous id. |
| `sentinel('reset')` | Clear local state (testing). |

### Linking a consent to a known person

`identify()` returns the pseudonymous id and nothing else. It deliberately does
not send an email address to the collector: that endpoint is public and
unauthenticated, so accepting identifiers there would let anyone write into
another person's consent record. Take the id and link it from your own backend
over the authenticated API.

## Tag blocking — what it does and does not cover

**Cooperative (guaranteed).** Mark a tag and it stays inert until consent:

```html
<script type="text/plain" data-sentinel-purpose="analytics" src="https://..."></script>
```

The browser will not execute a script whose type it does not recognise, so this
holds regardless of when the tag appears.

**Automatic (best effort).** With `auto_block` on, the loader traps
`script.src` assignment and watches the DOM for known tracker domains. This
catches how GTM, GA and the ad pixels actually load — create element, set src,
append — before any request is made.

It does **not** reliably catch a plain `<script src>` sitting in the HTML you
serve. The parser executes those synchronously, before any of our code can
intervene. Auto-blocking reduces leakage; it does not by itself make a site
compliant. Anything in your served HTML needs the cooperative markup above.

## Google Consent Mode v2

Pushed to `dataLayer` on load with everything denied, then updated on consent.
Safe to run whether or not Google tags are present.

## Size

5.6 KB gzipped against a 15 KB budget, enforced by `build.mjs` — the build
fails rather than quietly regressing, because this sits on the customer's
critical rendering path.

## Tests

`browser_test.py` drives the built bundle in real Chromium against a live
collector: shadow DOM rendering, the Data Fiduciary and grievance block,
accept/reject parity, blocking before and release after consent, language
switching, the persistent withdrawal affordance, and the row that lands in
`consent_receipts`.

```bash
npm run build && python3 browser_test.py
```
