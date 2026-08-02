"""Load the built loader in real Chromium against the live collector."""
import http.server, json, os, socketserver, subprocess, sys, threading, time, uuid

import sqlalchemy
from playwright.sync_api import sync_playwright

DB = "postgresql://postgres:testpw@127.0.0.1:5432/consent_db"
API_PORT, WEB_PORT = 8099, 8098
API = f"http://127.0.0.1:{API_PORT}"
SITE_ORIGIN = f"http://localhost:{WEB_PORT}"

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS  " if cond else "FAIL  ") + name + (f"  — {detail}" if detail else ""))

eng = sqlalchemy.create_engine(DB)
KEY = f"pk_site_browser_{uuid.uuid4().hex[:10]}"
SLUG = f"btest-{uuid.uuid4().hex[:8]}"

with eng.begin() as c:
    SITE_ID = c.execute(sqlalchemy.text("""
        INSERT INTO sites (name, slug, publishable_key, allowed_origins,
            data_fiduciary_name, data_fiduciary_address, grievance_officer_name,
            grievance_officer_email, grievance_officer_phone,
            default_language, available_languages, auto_block)
        VALUES ('Apollo Clinics', :slug, :key, ARRAY[:origin],
            'Apollo Clinics Pvt Ltd', '12 MG Road, Bengaluru 560001',
            'Priya Nair', 'grievance@apollo.example.in', '+91-80-4000-1234',
            'en', ARRAY['en','te','hi'], TRUE)
        RETURNING id"""), {"slug": SLUG, "key": KEY, "origin": SITE_ORIGIN}).scalar()

# ---------------------------------------------------------------- serve both
html = open("fixture/index.html").read().replace("PK_PLACEHOLDER", KEY).replace("API_PLACEHOLDER", API)
open("fixture/index.html.built", "w").write(html)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=os.path.abspath("fixture"), **kw)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = html.encode()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
web = socketserver.TCPServer(("127.0.0.1", WEB_PORT), Handler)
threading.Thread(target=web.serve_forever, daemon=True).start()

env = {**os.environ, "DATABASE_URL": DB, "REDIS_URL": "redis://localhost:6379/0",
       "PYTHONPATH": "/home/claude/b1"}
api = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "src.main:app", "--port", str(API_PORT), "--log-level", "error"],
    cwd="/home/claude/b1", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(4)

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        UA_REAL = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        # Playwright's default UA says HeadlessChrome, which the collector
        # correctly treats as a crawler. Present as a real browser instead.
        page = browser.new_page(user_agent=UA_REAL)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        blocked_requests = []
        page.on("request", lambda r: blocked_requests.append(r.url))

        page.goto(SITE_ORIGIN, wait_until="networkidle")
        page.wait_for_timeout(600)

        check("no page errors from the loader", not errors, "; ".join(errors[:2]))

        # The banner lives in a shadow root, so query through it.
        banner = page.locator('[data-sentinel-cmp]')
        check("banner element injected", banner.count() == 1)

        title = page.evaluate("""() => {
            const h = document.querySelector('[data-sentinel-cmp]');
            return h && h.shadowRoot ? h.shadowRoot.querySelector('h2')?.textContent : null;
        }""")
        check("banner renders inside shadow DOM", bool(title), str(title))

        fid = page.evaluate("""() => {
            const r = document.querySelector('[data-sentinel-cmp]').shadowRoot;
            return r.querySelector('.fid')?.textContent?.replace(/\\s+/g,' ').trim();
        }""")
        check("Data Fiduciary named in the notice (s.6(3))",
              "Apollo Clinics Pvt Ltd" in (fid or ""), (fid or "")[:80])
        check("grievance officer reachable from the notice (s.8(9), R.9)",
              "grievance@apollo.example.in" in (fid or "") and "Priya Nair" in (fid or ""))

        # Accept and reject must be equally reachable — no dark pattern.
        btns = page.evaluate("""() => {
            const r = document.querySelector('[data-sentinel-cmp]').shadowRoot;
            const m = el => { const c = getComputedStyle(el); const b = el.getBoundingClientRect();
              return {w: Math.round(b.width), h: Math.round(b.height), fs: c.fontSize,
                      display: c.display, visibility: c.visibility}; };
            return {a: m(r.getElementById('accept')), rj: m(r.getElementById('reject'))};
        }""")
        check("reject is the same size and weight as accept",
              btns["a"]["h"] == btns["rj"]["h"] and btns["a"]["fs"] == btns["rj"]["fs"]
              and btns["rj"]["visibility"] == "visible",
              f"accept={btns['a']} reject={btns['rj']}")

        # Cooperative tag must not have run before consent.
        check("cooperative tag inert before consent",
              page.evaluate("() => window.__analyticsRan === undefined"))

        # Auto-block: injected GA must not be fetched.
        page.click("#inject")
        page.wait_for_timeout(700)
        ga = [u for u in blocked_requests if "googletagmanager" in u]
        check("dynamically injected tracker blocked before consent",
              not ga, f"requests: {ga[:2]}")

        # Consent Mode v2 defaults must be denied before a choice.
        cm = page.evaluate("() => (window.dataLayer||[]).map(x => JSON.stringify(x))")
        check("Consent Mode pushed with denied defaults",
              any('"denied"' in s and "analytics_storage" in s for s in cm),
              str(cm[:1]))

        # ------------------------------------------------ language switching
        langs = page.evaluate("""() => {
            const r = document.querySelector('[data-sentinel-cmp]').shadowRoot;
            return Array.from(r.getElementById('lang').options).map(o => o.value);
        }""")
        check("language switcher offers the site's languages",
              set(langs) == {"en", "hi", "te"}, str(langs))

        page.evaluate("""() => {
            const r = document.querySelector('[data-sentinel-cmp]').shadowRoot;
            const s = r.getElementById('lang'); s.value = 'te';
            s.dispatchEvent(new Event('change'));
        }""")
        page.wait_for_timeout(900)
        lang_attr = page.evaluate("""() => {
            const r = document.querySelector('[data-sentinel-cmp]').shadowRoot;
            return r.querySelector('.card')?.getAttribute('lang');
        }""")
        check("switching language re-renders the notice in that language",
              lang_attr == "te", str(lang_attr))

        # ------------------------------------------------------ give consent
        page.evaluate("""() => {
            const r = document.querySelector('[data-sentinel-cmp]').shadowRoot;
            r.getElementById('accept').click();
        }""")
        page.wait_for_timeout(1200)

        check("cooperative tag released after consent",
              page.evaluate("() => window.__analyticsRan === true"))

        cm2 = page.evaluate("() => (window.dataLayer||[]).map(x => JSON.stringify(x))")
        check("Consent Mode updated to granted",
              any('"granted"' in s and "analytics_storage" in s for s in cm2))

        # The persistent way back in — DPDP s.6(4).
        fab = page.evaluate("""() => {
            const r = document.querySelector('[data-sentinel-cmp]').shadowRoot;
            const f = r.getElementById('fab');
            return f ? f.textContent.trim() : null;
        }""")
        check("persistent withdrawal affordance remains (s.6(4))", bool(fab), str(fab))

        pid = page.evaluate("() => window.sentinel('identify')")
        check("identify() returns the pseudonymous id, not an email",
              bool(pid) and "@" not in str(pid), str(pid))

        with eng.connect() as c:
            row = c.execute(sqlalchemy.text("""
                SELECT language_version, interaction_type, purposes, purposes_presented
                FROM consent_receipts WHERE site_id = :s ORDER BY collected_at DESC LIMIT 1
            """), {"s": SITE_ID}).mappings().first()
        check("consent reached the register", row is not None)
        if row:
            check("language served is stamped on the record (s.6(10))",
                  row["language_version"] == "te", str(row["language_version"]))
            check("interaction recorded as accept_all",
                  row["interaction_type"] == "accept_all", row["interaction_type"])
            check("purposes_presented captured what was on screen",
                  len(row["purposes_presented"]) > 0, str(row["purposes_presented"]))

        # ------------------------------------------------- returning visitor
        page2 = browser.new_page(user_agent=UA_REAL)
        page2.goto(SITE_ORIGIN, wait_until="networkidle")
        page2.wait_for_timeout(800)
        shown = page2.evaluate("""() => {
            const r = document.querySelector('[data-sentinel-cmp]')?.shadowRoot;
            return !!(r && r.querySelector('h2'));
        }""")
        check("a fresh browser is prompted", shown)

        page.reload(wait_until="networkidle")
        page.wait_for_timeout(900)
        reprompted = page.evaluate("""() => {
            const r = document.querySelector('[data-sentinel-cmp]')?.shadowRoot;
            return !!(r && r.querySelector('h2'));
        }""")
        check("someone who already answered is not asked again", not reprompted)

        released = page.evaluate("() => window.__analyticsRan === true")
        check("consent persists across reload and releases tags", released)

        browser.close()
finally:
    api.terminate()
    web.shutdown()
    with eng.begin() as c:
        c.execute(sqlalchemy.text("DELETE FROM consent_receipts WHERE site_id = :s"), {"s": SITE_ID})
        c.execute(sqlalchemy.text("DELETE FROM sites WHERE id = :s"), {"s": SITE_ID})

print("\n" + "=" * 60)
failed = [n for n, ok in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed")
for f in failed:
    print("  FAILED:", f)
sys.exit(1 if failed else 0)
