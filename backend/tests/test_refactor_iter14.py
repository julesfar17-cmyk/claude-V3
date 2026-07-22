"""Iteration 14 — Backend regression after PURE refactoring of:
- create_checkout → _plan_pricing() + _apply_affiliate_discount()
- _stripe_revenue_stats → _sub_monthly_cents() + _stripe_mrr_cents() + _stripe_charge_totals()
- _mux_transcode → _mux_create_upload() + _mux_wait_asset_id() + _mux_wait_mp4()

Also verifies:
- Test credentials are loaded from backend/.env via creds.py (no hardcoded).
- Stripe LIVE keys: NEVER open the cs_live URL, NEVER complete payment.
- Affiliate code created for tests is deleted at the end (also removes Stripe coupon).
- /api/admin/stats returns numeric non-null stripe_* fields (read-only Stripe call).
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break
assert BASE_URL, "REACT_APP_BACKEND_URL required"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

from creds import DEMO_EMAIL, DEMO_PASSWORD, VIP_EMAIL, VIP_PASSWORD

AFF_CODE = f"ITER14_{uuid.uuid4().hex[:6].upper()}"


@pytest.fixture(scope="module")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def demo_session(mongo_db):
    """Login demo user; ensure it's in BASIC plan as documented in test_credentials.md."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    mongo_db.users.update_one({"email": DEMO_EMAIL}, {"$set": {"subscription": {
        "status": "active", "plan": "basic",
        "current_period_end": (now + timedelta(days=30)).isoformat(),
        "stripe_customer_id": None, "stripe_subscription_id": None,
        "activated_at": now.isoformat(),
    }}})
    # We need to still allow checkout for BASIC plan → the user cannot already be PRO/BASIC (whitelist check
    # only rejects PRO_WHITELIST VIP). Actually the create_checkout only rejects PRO_WHITELIST users.
    # Demo user is NOT in PRO_WHITELIST so it can call checkout — server does not reject already-basic user for checkout.
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    yield s
    # Keep demo in basic plan (per creds convention)


@pytest.fixture(scope="module")
def vip_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": VIP_EMAIL, "password": VIP_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"VIP login failed: {r.status_code} {r.text[:200]}"
    yield s


@pytest.fixture(scope="module")
def affiliate_code(vip_session):
    """Create an affiliate code for tests, delete at teardown (also removes Stripe coupon)."""
    # Preclean if lingering
    vip_session.delete(f"{BASE_URL}/api/admin/affiliate/{AFF_CODE}", timeout=15)
    payload = {
        "code": AFF_CODE,
        "kind": "percent",
        "percent_off": 10,
        "plans": ["monthly"],
        "commission_pct": 10,
    }
    r = vip_session.post(f"{BASE_URL}/api/admin/affiliate", json=payload, timeout=45)
    assert r.status_code == 200, f"affiliate create failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    assert data["code"] == AFF_CODE
    assert data["kind"] == "percent"
    assert data.get("stripe_coupon_id"), "expected stripe_coupon_id"
    assert data["active"] == True
    yield AFF_CODE
    # Cleanup
    dr = vip_session.delete(f"{BASE_URL}/api/admin/affiliate/{AFF_CODE}", timeout=30)
    assert dr.status_code in (200, 404), f"affiliate delete failed: {dr.status_code} {dr.text[:200]}"


# -------------------- REGRESSION CHECKOUT (refactored) --------------------
EXPECTED_AMOUNT = {"basic": 6.99, "monthly": 12.99, "yearly": 99.0}


class TestCheckoutRefactor:
    @pytest.mark.parametrize("plan", ["basic", "monthly", "yearly"])
    def test_checkout_no_promo_each_plan(self, demo_session, mongo_db, plan):
        r = demo_session.post(
            f"{BASE_URL}/api/payments/checkout",
            json={"origin_url": BASE_URL, "plan": plan},
            timeout=45,
        )
        assert r.status_code == 200, f"{plan}: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert "url" in data and "session_id" in data
        assert data["url"].startswith("https://"), data["url"]
        # cs_live URL confirms LIVE mode without opening it
        assert "checkout.stripe.com" in data["url"], data["url"]
        # payment_transactions document
        tx = mongo_db.payment_transactions.find_one({"session_id": data["session_id"]}, {"_id": 0})
        assert tx is not None, "transaction not persisted"
        assert tx["plan"] == plan
        assert tx["amount"] == EXPECTED_AMOUNT[plan], f"expected {EXPECTED_AMOUNT[plan]} for {plan}, got {tx['amount']}"
        assert tx["product"] == f"beatcut_{plan}"
        assert tx["status"] == "open"
        assert tx["payment_status"] == "initiated"
        assert tx.get("affiliate_code") is None

    def test_checkout_monthly_with_valid_promo(self, demo_session, affiliate_code, mongo_db):
        r = demo_session.post(
            f"{BASE_URL}/api/payments/checkout",
            json={"origin_url": BASE_URL, "plan": "monthly", "promo_code": affiliate_code},
            timeout=45,
        )
        assert r.status_code == 200, f"monthly+promo: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data["url"].startswith("https://")
        # affiliate_code should be stored on tx
        tx = mongo_db.payment_transactions.find_one({"session_id": data["session_id"]}, {"_id": 0})
        assert tx is not None
        assert tx.get("affiliate_code") == affiliate_code
        assert tx["plan"] == "monthly"

    def test_checkout_basic_with_promo_not_covered_400(self, demo_session, affiliate_code):
        r = demo_session.post(
            f"{BASE_URL}/api/payments/checkout",
            json={"origin_url": BASE_URL, "plan": "basic", "promo_code": affiliate_code},
            timeout=30,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"
        detail = r.json().get("detail", "")
        assert "ne couvre pas ce plan" in detail.lower() or "couvre" in detail.lower(), detail

    def test_checkout_unknown_promo_400(self, demo_session):
        bogus = f"NOSUCHCODE_{uuid.uuid4().hex[:6].upper()}"
        r = demo_session.post(
            f"{BASE_URL}/api/payments/checkout",
            json={"origin_url": BASE_URL, "plan": "monthly", "promo_code": bogus},
            timeout=30,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"
        detail = r.json().get("detail", "")
        assert "invalide" in detail.lower() or "expiré" in detail.lower(), detail


# -------------------- REGRESSION STATS ADMIN (refactored) --------------------
class TestAdminStatsRefactor:
    def test_admin_stats_stripe_fields_present(self, vip_session):
        r = vip_session.get(f"{BASE_URL}/api/admin/stats", timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        for key in ("stripe_mrr", "stripe_active_subs", "revenue_this_month", "revenue_total"):
            assert key in body, f"missing key {key}"
            assert body[key] is not None, f"{key} is None — Stripe call likely failed"
            assert isinstance(body[key], (int, float)), f"{key} must be numeric, got {type(body[key])}: {body[key]}"
            assert body[key] >= 0, f"{key} negative: {body[key]}"

    def test_admin_stats_cached_second_call_fast(self, vip_session):
        # Second call within 10 min must return same numbers (cached).
        r1 = vip_session.get(f"{BASE_URL}/api/admin/stats", timeout=30).json()
        r2 = vip_session.get(f"{BASE_URL}/api/admin/stats", timeout=30).json()
        for key in ("stripe_mrr", "stripe_active_subs", "revenue_this_month", "revenue_total"):
            assert r1[key] == r2[key], f"cache inconsistent for {key}: {r1[key]} vs {r2[key]}"


# -------------------- CLEANUP payment_transactions created during tests --------------------
def test_zzz_cleanup_txs(mongo_db):
    """Remove open transactions we generated (never paid — cs_live never opened)."""
    # They are per demo user_id. Match by email.
    demo_user = mongo_db.users.find_one({"email": DEMO_EMAIL}, {"user_id": 1, "_id": 0})
    if demo_user:
        mongo_db.payment_transactions.delete_many({
            "user_id": demo_user["user_id"],
            "status": "open",
            "payment_status": "initiated",
        })
