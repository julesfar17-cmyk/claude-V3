"""Backend regression tests for AFFILIATE feature (iteration 11).

Covers:
- Admin creation of an affiliate code (QATEST5, amount off 1€, monthly+yearly)
- Public GET /api/affiliate/check/{code} (200 with correct after prices; 404 on unknown)
- POST /api/payments/checkout with promo_code (returns cs_live URL) — does NOT complete payment
- Checkout with a plan NOT covered by the code passes without discount (no error)
- Admin create/delete "days offered" promo code (DELME)
- Admin delete affiliate code and verify /api/affiliate/check/qatest5 → 404
- Regression: /api/promo/apply still works ; /api/admin/stats 200 ; /api/auth/login ok
"""

import os
import pytest
import requests

def _read_env():
    val = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not val:
        try:
            with open("/app/frontend/.env") as fh:
                for line in fh:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        val = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    return val.rstrip("/")

BASE_URL = _read_env()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

from creds import DEMO_EMAIL, DEMO_PASSWORD, VIP_EMAIL, VIP_PASSWORD

ADMIN = {"email": VIP_EMAIL, "password": VIP_PASSWORD}
DEMO = {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}

AFF_CODE = "QATEST5"
PROMO_TEST_CODE = "DELMEQA"


def _login(session, creds):
    r = session.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed {creds['email']}: {r.status_code} {r.text[:200]}"
    data = r.json()
    # BEATCUT uses httpOnly cookie access_token — session cookies are preserved automatically.
    # We still verify /api/auth/me to prove the session works.
    me = session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert me.status_code == 200, f"auth/me failed after login: {me.status_code} {me.text[:200]}"
    return data


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    _login(s, ADMIN)
    yield s
    # Ensure QATEST5 is removed even if a test fails
    try:
        s.delete(f"{BASE_URL}/api/admin/affiliate/{AFF_CODE}", timeout=15)
    except Exception:
        pass
    try:
        s.delete(f"{BASE_URL}/api/admin/promo/{PROMO_TEST_CODE}", timeout=15)
    except Exception:
        pass


@pytest.fixture(scope="module")
def demo_session():
    s = requests.Session()
    _login(s, DEMO)
    return s


# ----- Health -----

def test_health_admin_stats(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/stats", timeout=30)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "promo_codes" in body
    assert isinstance(body["promo_codes"], list)


# ----- Affiliate creation + check -----

def test_precleanup_affiliate(admin_session):
    # If QATEST5 lingers from a previous run, remove it
    admin_session.delete(f"{BASE_URL}/api/admin/affiliate/{AFF_CODE}", timeout=15)


def test_create_affiliate_qatest5(admin_session):
    payload = {
        "code": AFF_CODE,
        "kind": "amount",
        "amount_off_cents": 100,   # 1€
        "plans": ["monthly", "yearly"],
        "commission_pct": 15,
    }
    r = admin_session.post(f"{BASE_URL}/api/admin/affiliate", json=payload, timeout=45)
    assert r.status_code == 200, f"create failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    assert data["code"] == AFF_CODE
    assert data["kind"] == "amount"
    assert data["amount_off_cents"] == 100
    assert set(data["plans"]) == {"monthly", "yearly"}
    assert data["commission_pct"] == 15
    assert data.get("stripe_coupon_id"), "no stripe_coupon_id returned"
    assert data.get("active") == True


def test_affiliate_check_public_ok():
    # No auth required
    r = requests.get(f"{BASE_URL}/api/affiliate/check/{AFF_CODE.lower()}", timeout=15)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data["code"] == AFF_CODE
    assert data["kind"] == "amount"
    prices = data["prices"]
    assert prices["monthly"]["base_cents"] == 1299
    assert prices["monthly"]["after_cents"] == 1199, prices
    assert prices["yearly"]["base_cents"] == 9900
    assert prices["yearly"]["after_cents"] == 9800, prices
    # basic should NOT be in prices since not in plans
    assert "basic" not in prices


def test_affiliate_check_unknown_404():
    r = requests.get(f"{BASE_URL}/api/affiliate/check/DOESNOTEXISTZZ", timeout=15)
    assert r.status_code == 404


# ----- Checkout with promo_code (Stripe LIVE, do NOT open URL) -----

def test_checkout_with_affiliate_discount(demo_session):
    payload = {"origin_url": "https://pro-mailer-2.preview.emergentagent.com", "plan": "monthly", "promo_code": AFF_CODE}
    r = demo_session.post(f"{BASE_URL}/api/payments/checkout", json=payload, timeout=45)
    assert r.status_code == 200, f"checkout failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    assert "url" in data and data["url"].startswith("https://"), data
    assert "session_id" in data


def test_checkout_basic_plan_not_covered_still_ok(demo_session):
    # Plan basic is not in affiliate.plans → checkout MUST fail with an explicit 400
    payload = {"origin_url": "https://pro-mailer-2.preview.emergentagent.com", "plan": "basic", "promo_code": AFF_CODE}
    r = demo_session.post(f"{BASE_URL}/api/payments/checkout", json=payload, timeout=45)
    assert r.status_code == 400, f"expected 400 for uncovered plan: {r.status_code} {r.text[:400]}"
    assert "couvre pas" in (r.json().get("detail") or "")


# ----- Days-offered promo (regression) create + delete -----

def test_create_and_delete_days_promo(admin_session):
    # cleanup
    admin_session.delete(f"{BASE_URL}/api/admin/promo/{PROMO_TEST_CODE}", timeout=15)

    r = admin_session.post(
        f"{BASE_URL}/api/admin/promo",
        json={"code": PROMO_TEST_CODE, "bonus_days": 7, "max_uses": 1},
        timeout=15,
    )
    assert r.status_code == 200, r.text[:300]
    doc = r.json()
    assert doc["code"] == PROMO_TEST_CODE
    assert doc["bonus_days"] == 7

    # Verify it appears in admin stats
    stats = admin_session.get(f"{BASE_URL}/api/admin/stats", timeout=15).json()
    codes_now = {p["code"] for p in stats.get("promo_codes", [])}
    assert PROMO_TEST_CODE in codes_now

    # Delete
    r = admin_session.delete(f"{BASE_URL}/api/admin/promo/{PROMO_TEST_CODE}", timeout=15)
    assert r.status_code == 200

    # Re-delete should 404
    r = admin_session.delete(f"{BASE_URL}/api/admin/promo/{PROMO_TEST_CODE}", timeout=15)
    assert r.status_code == 404


# ----- Regression: /api/promo/apply still works with an existing days-offered code -----

def test_promo_apply_regression(admin_session, demo_session):
    # Create a fresh single-use "days offered" code
    code = "REGRESSDAY"
    admin_session.delete(f"{BASE_URL}/api/admin/promo/{code}", timeout=15)
    r = admin_session.post(
        f"{BASE_URL}/api/admin/promo",
        json={"code": code, "bonus_days": 1, "max_uses": 1},
        timeout=15,
    )
    assert r.status_code == 200

    try:
        r = demo_session.post(f"{BASE_URL}/api/promo/apply", json={"code": code}, timeout=15)
        # Either 200 (first use) or 400 (already used by this account) — both prove endpoint alive
        assert r.status_code in (200, 400), r.text[:200]
        if r.status_code == 200:
            body = r.json()
            assert "current_period_end" in body
    finally:
        admin_session.delete(f"{BASE_URL}/api/admin/promo/{code}", timeout=15)


# ----- Affiliate deletion at the end (mandatory cleanup) -----

def test_delete_affiliate_and_verify_404(admin_session):
    r = admin_session.delete(f"{BASE_URL}/api/admin/affiliate/{AFF_CODE}", timeout=30)
    assert r.status_code == 200, r.text[:300]
    # Check that public lookup now returns 404
    r = requests.get(f"{BASE_URL}/api/affiliate/check/{AFF_CODE.lower()}", timeout=15)
    assert r.status_code == 404
    # Deleting again → 404
    r = admin_session.delete(f"{BASE_URL}/api/admin/affiliate/{AFF_CODE}", timeout=15)
    assert r.status_code == 404


def test_cleanup_leftover_testaff(admin_session):
    # Optional cleanup: previous main-agent test code
    r = admin_session.delete(f"{BASE_URL}/api/admin/affiliate/TESTAFF", timeout=15)
    assert r.status_code in (200, 404)
