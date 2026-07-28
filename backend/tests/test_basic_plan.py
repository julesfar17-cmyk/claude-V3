"""
BEATCUT iteration 3 — Basic plan (6,99 €/mois, 10 videos/mois, no acapella)
Tests:
- Auth /me → subscription.tier ('basic' for demo, 'pro' for VIP julesfar17)
- Payments checkout with plan='basic' returns stripe URL
- Export quota (basic vs pro)
- Export register (free=403, basic increments to 10 then 429, VIP allowed)
- Separate acapella (free=403, basic=403 with PRO-only msg, VIP=200)
- Regression: register/login/subscription/promo/me still work
Preserves demo@beatcut.fr in Basic plan and cleans its export_logs at the end.
"""
import io
import os
import uuid
import wave
import struct

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pro-mailer-2.preview.emergentagent.com').rstrip('/')
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

from creds import DEMO_EMAIL, DEMO_PASSWORD, VIP_EMAIL, VIP_PASSWORD


# -------------------------- fixtures --------------------------
@pytest.fixture(scope="module")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def demo_user_id(mongo_db):
    u = mongo_db.users.find_one({"email": DEMO_EMAIL}, {"_id": 0, "user_id": 1})
    assert u, "demo user must exist"
    return u["user_id"]


@pytest.fixture(scope="module")
def demo_session(mongo_db, demo_user_id):
    # Ensure demo is basic and export_logs empty at the beginning
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    mongo_db.users.update_one({"email": DEMO_EMAIL}, {"$set": {
        "subscription": {
            "status": "active",
            "plan": "basic",
            "current_period_end": (now + timedelta(days=30)).isoformat(),
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "activated_at": now.isoformat(),
        }
    }})
    mongo_db.export_logs.delete_many({"user_id": demo_user_id})
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    yield s
    # Teardown — keep demo in basic, clean export_logs
    mongo_db.export_logs.delete_many({"user_id": demo_user_id})
    mongo_db.users.update_one({"email": DEMO_EMAIL}, {"$set": {
        "subscription": {
            "status": "active",
            "plan": "basic",
            "current_period_end": (now + timedelta(days=30)).isoformat(),
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "activated_at": now.isoformat(),
        }
    }})


@pytest.fixture(scope="module")
def vip_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": VIP_EMAIL, "password": VIP_PASSWORD})
    assert r.status_code == 200, f"VIP login failed: {r.status_code} {r.text}"
    yield s


@pytest.fixture(scope="module")
def free_session(mongo_db):
    email = f"TEST_free_{uuid.uuid4().hex[:6]}@example.com"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"name": "FreeU", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    yield s
    mongo_db.users.delete_one({"email": email})


def _make_small_wav_bytes(seconds: float = 0.5, framerate: int = 8000) -> bytes:
    """Generate a small silent wav in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(framerate)
        nframes = int(seconds * framerate)
        w.writeframes(struct.pack("<" + "h" * nframes, *([0] * nframes)))
    return buf.getvalue()


# -------------------------- /auth/me tier --------------------------
class TestAuthMeTier:
    def test_demo_me_tier_basic(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == DEMO_EMAIL
        assert body["is_pro"] == True
        assert body["subscription"]["tier"] == "basic"
        assert body["subscription"]["plan"] == "basic"

    def test_vip_me_tier_pro(self, vip_session):
        r = vip_session.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == VIP_EMAIL
        assert body["is_pro"] == True
        assert body["subscription"]["tier"] == "pro"


# -------------------------- Payments checkout basic --------------------------
class TestCheckoutBasic:
    def test_free_user_checkout_basic_returns_stripe_url(self, mongo_db):
        """A free user asking for plan='basic' must get a Stripe URL back — NEVER pay!"""
        email = f"TEST_ck_{uuid.uuid4().hex[:6]}@example.com"
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/register",
                   json={"name": "ChkU", "email": email, "password": "Passw0rd!"})
        assert r.status_code == 200

        r = s.post(f"{BASE_URL}/api/payments/checkout",
                   json={"origin_url": BASE_URL, "plan": "basic"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "url" in data and "session_id" in data
        assert "checkout.stripe.com" in data["url"], data["url"]

        # Verify transaction was persisted with plan=basic and amount 6.99
        tx = mongo_db.payment_transactions.find_one({"session_id": data["session_id"]}, {"_id": 0})
        assert tx is not None
        assert tx["plan"] == "basic"
        assert tx["amount"] == 6.99
        assert tx["email"] == email.lower()

        # Cleanup
        mongo_db.users.delete_one({"email": email})
        mongo_db.payment_transactions.delete_many({"email": email.lower()})

    def test_vip_cannot_checkout(self, vip_session):
        r = vip_session.post(f"{BASE_URL}/api/payments/checkout",
                             json={"origin_url": BASE_URL, "plan": "basic"})
        assert r.status_code == 400, r.text


# -------------------------- Export quota --------------------------
class TestExportQuota:
    def test_quota_basic_shows_used_and_10(self, demo_session, mongo_db, demo_user_id):
        mongo_db.export_logs.delete_many({"user_id": demo_user_id})
        r = demo_session.get(f"{BASE_URL}/api/export/quota")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tier"] == "basic"
        assert data["used"] == 0
        assert data["quota"] == 10

    def test_quota_vip_returns_pro_none(self, vip_session):
        r = vip_session.get(f"{BASE_URL}/api/export/quota")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tier"] == "pro"
        assert data["used"] is None
        assert data["quota"] is None

    def test_quota_free_returns_paywall_0(self, free_session):
        """Nouvelle grille : free = 0 export (paywall essai Pro)."""
        r = free_session.get(f"{BASE_URL}/api/export/quota")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tier"] == "free"
        assert data["quota"] == 0
        assert data.get("paywall") == True


# -------------------------- Export register --------------------------
class TestExportRegister:
    def test_free_export_paywall_402(self, mongo_db):
        """Nouvelle grille : free = aucun export, 402 avec code paywall."""
        import uuid as _uuid
        email = f"TEST_freeexp_{_uuid.uuid4().hex[:6]}@example.com"
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/register",
                   json={"name": "FreeExp", "email": email, "password": "Passw0rd!"})
        assert r.status_code == 200
        try:
            q0 = s.get(f"{BASE_URL}/api/export/quota").json()
            assert q0["tier"] == "free" and q0["quota"] == 0
            r1 = s.post(f"{BASE_URL}/api/export/register")
            assert r1.status_code == 402, r1.text
            detail = r1.json().get("detail", {})
            assert isinstance(detail, dict) and detail.get("code") == "paywall"
        finally:
            u = mongo_db.users.find_one({"email": email}, {"user_id": 1, "_id": 0})
            if u:
                mongo_db.export_logs.delete_many({"user_id": u["user_id"]})
            mongo_db.users.delete_one({"email": email})

    def test_vip_export_allowed_unlimited(self, vip_session):
        r = vip_session.post(f"{BASE_URL}/api/export/register")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["allowed"] == True
        assert data["used"] is None
        assert data["quota"] is None

    def test_basic_export_10_then_429(self, demo_session, mongo_db, demo_user_id):
        # Ensure clean slate
        mongo_db.export_logs.delete_many({"user_id": demo_user_id})

        # Register exactly 10 exports
        for i in range(1, 11):
            r = demo_session.post(f"{BASE_URL}/api/export/register")
            assert r.status_code == 200, f"iter {i}: {r.status_code} {r.text}"
            data = r.json()
            assert data["allowed"] == True
            assert data["used"] == i
            assert data["quota"] == 10

        # Verify quota endpoint reports used=10
        q = demo_session.get(f"{BASE_URL}/api/export/quota").json()
        assert q["used"] == 10
        assert q["quota"] == 10

        # 11th call should be 429 with quota message
        r = demo_session.post(f"{BASE_URL}/api/export/register")
        assert r.status_code == 429, r.text
        detail = r.json().get("detail", "")
        assert "Quota" in detail or "quota" in detail
        assert "10" in detail
        assert "PRO" in detail

        # Cleanup as per instructions — leave demo quota at 0
        mongo_db.export_logs.delete_many({"user_id": demo_user_id})


# -------------------------- Separate acapella --------------------------
class TestSeparateAcapella:
    def test_free_separate_forbidden(self, free_session):
        wav_bytes = _make_small_wav_bytes()
        r = free_session.post(
            f"{BASE_URL}/api/separate",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
        )
        assert r.status_code == 403, r.text

    def test_basic_separate_forbidden_pro_only(self, demo_session):
        wav_bytes = _make_small_wav_bytes()
        r = demo_session.post(
            f"{BASE_URL}/api/separate",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
        )
        assert r.status_code == 403, r.text
        detail = r.json().get("detail", "")
        assert "acapella" in detail.lower() or "PRO" in detail

    def test_vip_separate_processing(self, vip_session, mongo_db):
        wav_bytes = _make_small_wav_bytes()
        r = vip_session.post(
            f"{BASE_URL}/api/separate",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "processing"
        assert "id" in data
        # Cleanup: mark the job as done to avoid burning replicate credits
        # (we don't wait for it to finish). Also delete the DB job.
        mongo_db.separation_jobs.delete_one({"job_id": data["id"]})


# -------------------------- Regression --------------------------
class TestRegression:
    def test_register_and_login(self, mongo_db):
        email = f"TEST_reg_{uuid.uuid4().hex[:6]}@example.com"
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/register",
                   json={"name": "RegU", "email": email, "password": "Passw0rd!"})
        assert r.status_code == 200
        # login again
        s2 = requests.Session()
        r = s2.post(f"{BASE_URL}/api/auth/login",
                    json={"email": email, "password": "Passw0rd!"})
        assert r.status_code == 200
        mongo_db.users.delete_one({"email": email})

    def test_get_subscription_demo_basic(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/subscription")
        assert r.status_code == 200, r.text
        body = r.json()
        # /api/subscription returns sub_info flat (no nested 'subscription')
        assert body["is_pro"] == True
        assert body["tier"] == "basic"
        assert body["plan"] == "basic"

    def test_promo_me_demo(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/promo/me")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ref_code" in data
        assert "referral_count" in data


# -------------------------- Cleanup --------------------------
def test_zzz_cleanup(mongo_db, demo_user_id):
    """Final cleanup — TEST_ users out, demo export_logs empty."""
    mongo_db.users.delete_many({"email": {"$regex": "^TEST_"}})
    mongo_db.export_logs.delete_many({"user_id": demo_user_id})
