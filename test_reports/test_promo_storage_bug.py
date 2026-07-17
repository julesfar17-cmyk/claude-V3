import asyncio
import json
import os
import time
import uuid

import requests
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


ROOT = os.environ.get("FRONTEND_URL", "https://pro-mailer-2.preview.emergentagent.com").rstrip("/")
API = f"{ROOT}/api"
ADMIN_EMAIL = "julesfar17@gmail.com"
ADMIN_PASSWORD = "Carnageproduction1704*"
USER_PASSWORD = "Testing1234!"
CODE = f"QAP{uuid.uuid4().hex[:8].upper()}"
USER_EMAIL = f"qa_promo_{uuid.uuid4().hex[:8]}@test.local"
OUT = "/app/test_reports/promo_bug_runtime_results.json"


results = {
    "root": ROOT,
    "api": API,
    "affiliate_code": CODE,
    "test_user": USER_EMAIL,
    "steps": [],
    "console_errors": [],
    "request_failures": [],
    "cleanup": {},
}


def record(name, ok, details=None):
    item = {"name": name, "ok": bool(ok), "details": details or {}}
    results["steps"].append(item)
    print(("PASS" if ok else "FAIL") + f" - {name}: {details or {}}")
    if not ok:
        raise AssertionError(f"{name} failed: {details}")


def api_json(method, url, session=None, **kwargs):
    sess = session or requests
    r = getattr(sess, method.lower())(url, timeout=60, **kwargs)
    try:
        body = r.json()
    except Exception:
        body = r.text[:500]
    return r, body


def seed_data():
    admin = requests.Session()
    r, body = api_json("post", f"{API}/auth/login", admin, json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    record("admin login for affiliate seed", r.status_code == 200, {"status": r.status_code, "body": body if r.status_code != 200 else {"email": body.get("email"), "role": body.get("role")}})

    payload = {"code": CODE, "kind": "percent", "percent_off": 10, "plans": ["basic", "monthly", "yearly"], "commission_pct": 0}
    r, body = api_json("post", f"{API}/admin/affiliate", admin, json=payload)
    record("create temporary affiliate code", r.status_code == 200, {"status": r.status_code, "body": body if r.status_code != 200 else {"code": body.get("code"), "plans": body.get("plans")}})

    r, body = api_json("get", f"{API}/affiliate/check/{CODE}")
    record("public affiliate check returns 10 percent discounted prices", r.status_code == 200 and body.get("prices", {}).get("monthly", {}).get("after_cents") == 1169, {"status": r.status_code, "body": body})

    user = requests.Session()
    r, body = api_json("post", f"{API}/auth/register", user, json={"name": "QA Promo", "email": USER_EMAIL, "password": USER_PASSWORD})
    record("create fresh free user", r.status_code == 200 and body.get("email") == USER_EMAIL, {"status": r.status_code, "body": body if r.status_code != 200 else {"email": body.get("email"), "is_pro": body.get("is_pro")}})
    return admin, user


async def login_ui(page, email=USER_EMAIL, password=USER_PASSWORD):
    await page.goto(f"{ROOT}/login", wait_until="domcontentloaded")
    await page.get_by_test_id("auth-email-input").fill(email)
    await page.get_by_test_id("auth-password-input").fill(password)
    await page.get_by_test_id("auth-submit-button").click()
    await page.wait_for_url("**/dashboard", timeout=20000)
    await page.get_by_test_id("dashboard-greeting").wait_for(timeout=20000)


async def read_dashboard_state(page):
    await page.get_by_test_id("subscription-card").wait_for(timeout=15000)
    # Give any affiliate/check request a short chance to alter visible prices.
    await page.wait_for_timeout(800)
    state = await page.evaluate(
        """() => ({
            priceBasic: document.querySelector('[data-testid="price-basic"]')?.innerText || null,
            priceMonthly: document.querySelector('[data-testid="price-monthly"]')?.innerText || document.querySelector('[data-testid="price-upgrade-monthly"]')?.innerText || null,
            priceYearly: document.querySelector('[data-testid="price-yearly"]')?.innerText || null,
            badges: Array.from(document.querySelectorAll('[data-testid^="promo-badge-"]')).map(e => ({testid: e.getAttribute('data-testid'), text: e.innerText})),
            legacy: localStorage.getItem('bc_affiliate'),
            manual: localStorage.getItem('bc_affiliate_manual'),
            link: sessionStorage.getItem('bc_affiliate_link'),
            url: window.location.href
        })"""
    )
    print("DASHBOARD_STATE", json.dumps(state, ensure_ascii=False))
    return state


def assert_no_promo_state(state, label):
    ok = (
        state["badges"] == []
        and state["priceBasic"] == "6,99 €/mois"
        and state["priceMonthly"] == "12,99 €/mois"
        and state["priceYearly"] == "99 €/an"
    )
    record(label, ok, state)


def assert_discount_state(state, label, storage_expectation=None):
    badge_texts = [b["text"] for b in state["badges"]]
    ok = (
        any(f"🎁 {CODE}" in txt for txt in badge_texts)
        and "6,99 €" in (state["priceBasic"] or "") and "6,29 €/mois" in (state["priceBasic"] or "")
        and "12,99 €" in (state["priceMonthly"] or "") and "11,69 €/mois" in (state["priceMonthly"] or "")
        and "99 €" in (state["priceYearly"] or "") and "89,10 €/an" in (state["priceYearly"] or "")
    )
    if storage_expectation:
        for key, expected in storage_expectation.items():
            ok = ok and state.get(key) == expected
    record(label, ok, state)


async def run_browser_tests():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])

        async def new_context(name, init_script=None):
            ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
            if init_script:
                await ctx.add_init_script(init_script)
            page = await ctx.new_page()
            page.on("console", lambda msg: results["console_errors"].append({"context": name, "type": msg.type, "text": msg.text}) if msg.type in ("error", "warning") else None)
            page.on("requestfailed", lambda req: results["request_failures"].append({"context": name, "url": req.url, "failure": req.failure}) )
            return ctx, page

        # 1) No promo flow: never passed through ?promo and never typed code.
        ctx, page = await new_context("no_promo")
        await login_ui(page)
        state = await read_dashboard_state(page)
        assert_no_promo_state(state, "no promo: normal prices and no promo badges")
        await ctx.close()

        # 2) Legacy purge: old permanent key present before app loads must be removed and ignored.
        ctx, page = await new_context("legacy_purge", f"localStorage.setItem('bc_affiliate', '{CODE}');")
        await login_ui(page)
        state = await read_dashboard_state(page)
        assert_no_promo_state(state, "legacy bc_affiliate is purged and ignored")
        record("legacy localStorage key removed", state["legacy"] is None, state)
        await ctx.close()

        # 3) Affiliate link: only sessionStorage and discount during same browser session.
        ctx, page = await new_context("affiliate_link")
        await page.goto(f"{ROOT}/?promo={CODE}", wait_until="domcontentloaded")
        stored = await page.evaluate("""() => ({link: sessionStorage.getItem('bc_affiliate_link'), manual: localStorage.getItem('bc_affiliate_manual'), legacy: localStorage.getItem('bc_affiliate'), url: window.location.href})""")
        record("affiliate link stored in sessionStorage only and URL cleaned", stored["link"] == CODE and stored["manual"] is None and stored["legacy"] is None and "promo=" not in stored["url"], stored)
        await login_ui(page)
        await page.get_by_test_id("promo-badge-monthly").wait_for(timeout=15000)
        state = await read_dashboard_state(page)
        assert_discount_state(state, "affiliate link discount visible during same session", {"link": CODE, "manual": None, "legacy": None})
        await ctx.close()

        # 4) New browser context/new session, same user, no link: no discount should carry over.
        ctx, page = await new_context("new_session_no_link")
        await login_ui(page)
        state = await read_dashboard_state(page)
        assert_no_promo_state(state, "new browser session without link has no discount")
        record("new browser session has no affiliate storage", state["link"] is None and state["manual"] is None and state["legacy"] is None, state)
        await ctx.close()

        # 5) Manual code: persists in localStorage across reload.
        ctx, page = await new_context("manual_promo")
        await login_ui(page)
        await page.get_by_test_id("promo-input").fill(CODE)
        await page.get_by_test_id("promo-submit").click()
        await page.get_by_test_id("promo-badge-monthly").wait_for(timeout=20000)
        state = await read_dashboard_state(page)
        assert_discount_state(state, "manual promo shows discounts and stores bc_affiliate_manual", {"manual": CODE, "legacy": None})
        await page.reload(wait_until="domcontentloaded")
        await page.get_by_test_id("dashboard-greeting").wait_for(timeout=15000)
        await page.get_by_test_id("promo-badge-monthly").wait_for(timeout=15000)
        state = await read_dashboard_state(page)
        assert_discount_state(state, "manual promo persists after reload", {"manual": CODE, "legacy": None})
        await ctx.close()

        await browser.close()


def checkout_regression(user_session):
    r, body = api_json("post", f"{API}/payments/checkout", user_session, json={"origin_url": ROOT, "plan": "monthly", "promo_code": CODE})
    url = body.get("url") if isinstance(body, dict) else None
    session_id = body.get("session_id") if isinstance(body, dict) else None
    ok = r.status_code == 200 and isinstance(url, str) and "checkout.stripe.com" in url and "cs_live" in url and isinstance(session_id, str) and session_id.startswith("cs_live")
    record("checkout regression with promo_code returns Stripe LIVE checkout URL (not opened)", ok, {"status": r.status_code, "session_id": session_id, "url_prefix": url[:80] if url else None, "body": body if r.status_code != 200 else None})


async def main():
    admin = None
    created = False
    try:
        admin, user = seed_data()
        created = True
        await run_browser_tests()
        checkout_regression(user)
    finally:
        if admin and created:
            try:
                r, body = api_json("delete", f"{API}/admin/affiliate/{CODE}", admin)
                results["cleanup"] = {"status": r.status_code, "body": body}
                print("CLEANUP", results["cleanup"])
            except Exception as e:
                results["cleanup"] = {"error": repr(e)}
        results["all_passed"] = all(step["ok"] for step in results["steps"])
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"WROTE {OUT}")


if __name__ == "__main__":
    asyncio.run(main())