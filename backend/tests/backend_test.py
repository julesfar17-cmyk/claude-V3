"""
BEATCUT backend API tests — auth, payments, subscription, brute force, Google session.
Run: pytest /app/backend/tests/backend_test.py -v --tb=short \
     --junitxml=/app/test_reports/pytest/pytest_results.xml
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if os.environ.get('REACT_APP_BACKEND_URL') else "https://pro-mailer-2.preview.emergentagent.com"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

from creds import DEMO_EMAIL, DEMO_PASSWORD, ADMIN_EMAIL


@pytest.fixture(scope="module")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def demo_session(mongo_db):
    """Login as demo user, return a requests.Session with cookies."""
    # Make sure demo user is in free state before tests
    mongo_db.users.update_one({"email": DEMO_EMAIL}, {"$set": {"subscription": None}})
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, f"Demo login failed: {r.status_code} {r.text}"
    yield s
    # Teardown — reset demo subscription
    mongo_db.users.update_one({"email": DEMO_EMAIL}, {"$set": {"subscription": None}})


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
def test_api_root():
    r = requests.get(f"{BASE_URL}/api/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# ---------------------------------------------------------------------------
# Auth — register / login / me / logout
# ---------------------------------------------------------------------------
class TestAuth:
    def test_register_new_user(self):
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/register",
                   json={"name": "Test U", "email": email, "password": "Passw0rd!", "cgv_accepted": True})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email.lower()
        assert data["is_pro"] == False
        assert "access_token" in s.cookies.get_dict()
        # Verify /me works
        me = s.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == email

    def test_register_duplicate_rejected(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/register",
                   json={"name": "Dup", "email": DEMO_EMAIL, "password": "whatever", "cgv_accepted": True})
        assert r.status_code == 400

    def test_demo_login_and_me(self, demo_session):
        me = demo_session.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 200
        body = me.json()
        assert body["email"] == DEMO_EMAIL
        assert body["is_pro"] in (False, True)  # depends on state — should be False initially

    def test_login_invalid_password(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "wrongpass!"})
        assert r.status_code == 401

    def test_me_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 401

    def test_logout_clears_session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login",
               json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        # Logout
        r = s.post(f"{BASE_URL}/api/auth/logout")
        assert r.status_code == 200
        # Clear cookies the server told us to
        s.cookies.clear()
        me = s.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 401


# ---------------------------------------------------------------------------
# Brute force lockout
# ---------------------------------------------------------------------------
class TestBruteForce:
    def test_lockout_after_5_failures(self, mongo_db):
        email = f"TEST_brute_{uuid.uuid4().hex[:6]}@example.com"
        # Clear any prior attempts
        mongo_db.login_attempts.delete_many({"identifier": {"$regex": email}})
        codes = []
        for _ in range(6):
            r = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"email": email, "password": "nope"})
            codes.append(r.status_code)
        # First 5 should be 401, 6th should be 429
        assert codes[:5] == [401] * 5, f"Expected 5x 401, got {codes}"
        assert codes[5] == 429, f"Expected 429 on 6th, got {codes[5]}"
        # Cleanup
        mongo_db.login_attempts.delete_many({"identifier": {"$regex": email}})


# ---------------------------------------------------------------------------
# Google session (Step 3 playbook) — fake session in Mongo
# ---------------------------------------------------------------------------
class TestGoogleSession:
    def test_bearer_session_token_returns_user(self, mongo_db):
        uid = f"TEST_user_{uuid.uuid4().hex[:8]}"
        email = f"TEST_g_{uuid.uuid4().hex[:6]}@example.com"
        token = f"test_session_{uuid.uuid4().hex}"
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        mongo_db.users.insert_one({
            "user_id": uid, "email": email, "name": "Test Google",
            "auth_provider": "google", "subscription": None,
            "created_at": now.isoformat(),
        })
        mongo_db.user_sessions.insert_one({
            "user_id": uid, "session_token": token,
            "expires_at": (now + timedelta(days=7)).isoformat(),
            "created_at": now.isoformat(),
        })
        try:
            r = requests.get(f"{BASE_URL}/api/auth/me",
                             headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["email"] == email
            assert data["auth_provider"] == "google"
        finally:
            mongo_db.users.delete_one({"user_id": uid})
            mongo_db.user_sessions.delete_one({"session_token": token})


# ---------------------------------------------------------------------------
# Payments — Stripe checkout + status
# ---------------------------------------------------------------------------
class TestPayments:
    def test_checkout_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/payments/checkout",
                          json={"origin_url": BASE_URL})
        assert r.status_code == 401

    def test_create_checkout_returns_stripe_url(self, demo_session):
        r = demo_session.post(f"{BASE_URL}/api/payments/checkout",
                              json={"origin_url": BASE_URL})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "url" in data and "session_id" in data
        assert "checkout.stripe.com" in data["url"], f"Expected stripe URL, got {data['url']}"
        # Status endpoint
        sid = data["session_id"]
        st = demo_session.get(f"{BASE_URL}/api/payments/status/{sid}")
        assert st.status_code == 200, st.text
        body = st.json()
        assert "status" in body and "payment_status" in body
        # Newly created session should not be paid yet
        assert body["payment_status"] in ("unpaid", "initiated", "no_payment_required")


# ---------------------------------------------------------------------------
# Subscription — force PRO, get, cancel
# ---------------------------------------------------------------------------
class TestSubscription:
    def test_force_pro_then_me_is_pro(self, demo_session, mongo_db):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        mongo_db.users.update_one({"email": DEMO_EMAIL}, {"$set": {
            "subscription": {
                "status": "active",
                "started_at": now.isoformat(),
                "current_period_end": (now + timedelta(days=30)).isoformat(),
            }
        }})
        me = demo_session.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 200
        body = me.json()
        assert body["is_pro"] == True
        assert body["subscription"]["status"] == "active"
        assert body["subscription"]["cancel_at_period_end"] == False

    def test_get_subscription(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/subscription")
        assert r.status_code == 200
        body = r.json()
        assert body["is_pro"] == True

    def test_cancel_subscription_keeps_access(self, demo_session):
        r = demo_session.post(f"{BASE_URL}/api/subscription/cancel")
        assert r.status_code == 200, r.text
        assert "current_period_end" in r.json()
        # /me should now show canceled but still pro
        me = demo_session.get(f"{BASE_URL}/api/auth/me").json()
        assert me["is_pro"] == True
        assert me["subscription"]["cancel_at_period_end"] == True
        assert me["subscription"]["status"] == "canceled"

    def test_cancel_again_rejected(self, demo_session):
        r = demo_session.post(f"{BASE_URL}/api/subscription/cancel")
        assert r.status_code == 400  # already canceled

    def test_cancel_without_subscription_rejected(self, mongo_db):
        # New TEST_ user with no subscription
        email = f"TEST_nosub_{uuid.uuid4().hex[:6]}@example.com"
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/register",
               json={"name": "NoSub", "email": email, "password": "Passw0rd!", "cgv_accepted": True})
        r = s.post(f"{BASE_URL}/api/subscription/cancel")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Forgot / Reset password (iteration 2)
# ---------------------------------------------------------------------------
class TestForgotReset:
    def test_forgot_unknown_email_generic(self):
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password",
                          json={"email": "nobody_xyz@example.com", "origin_url": BASE_URL})
        assert r.status_code == 200
        data = r.json()
        assert "message" in data
        # Unknown email: no dev_reset_link
        assert "dev_reset_link" not in data

    def test_forgot_reset_full_cycle(self, mongo_db):
        # Register a fresh TEST_ user
        email = f"TEST_reset_{uuid.uuid4().hex[:6]}@example.com"
        old_password = "OldPass123!"
        new_password = "NewPass456!"
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/register",
                   json={"name": "Reset U", "email": email, "password": old_password, "cgv_accepted": True})
        assert r.status_code == 200

        # Request reset
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password",
                          json={"email": email, "origin_url": BASE_URL})
        assert r.status_code == 200
        data = r.json()
        # Simulated email mode: dev_reset_link must be present
        assert "dev_reset_link" in data, f"Expected dev_reset_link in simulated mode, got {data}"
        link = data["dev_reset_link"]
        assert "/reset-password?token=" in link
        token = link.split("token=")[1]

        # Reset password
        r = requests.post(f"{BASE_URL}/api/auth/reset-password",
                          json={"token": token, "password": new_password})
        assert r.status_code == 200, r.text

        # Login with NEW password
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": email, "password": new_password})
        assert r.status_code == 200

        # Old password rejected
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": email, "password": old_password})
        assert r.status_code == 401

        # Token reuse rejected
        r = requests.post(f"{BASE_URL}/api/auth/reset-password",
                          json={"token": token, "password": "AnotherPass789!"})
        assert r.status_code == 400, r.text

    def test_reset_invalid_token(self):
        r = requests.post(f"{BASE_URL}/api/auth/reset-password",
                          json={"token": "totally-invalid-token", "password": "Whatever1!"})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Proxy endpoints — Pexels & Transcribe (iteration 2)
# ---------------------------------------------------------------------------
class TestProxy:
    def test_pexels_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/proxy/pexels",
                          json={"query": "neon city", "orientation": "portrait"})
        assert r.status_code == 401

    def test_transcribe_requires_auth(self):
        # Don't actually send a file — auth must be checked first
        r = requests.post(f"{BASE_URL}/api/proxy/transcribe",
                          files={"file": ("test.wav", b"RIFF", "audio/wav")})
        assert r.status_code == 401

    def test_pexels_authenticated_returns_videos(self, demo_session):
        r = demo_session.post(f"{BASE_URL}/api/proxy/pexels",
                              json={"query": "neon city", "orientation": "portrait"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "videos" in data
        assert isinstance(data["videos"], list)


# ---------------------------------------------------------------------------
# Subscription reactivate (iteration 2)
# ---------------------------------------------------------------------------
class TestReactivate:
    def test_reactivate_400_when_no_stripe_id(self, mongo_db):
        # Register a TEST_ user and force a canceled local sub without stripe id
        email = f"TEST_react_{uuid.uuid4().hex[:6]}@example.com"
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/register",
               json={"name": "ReactU", "email": email, "password": "Passw0rd!", "cgv_accepted": True})
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        mongo_db.users.update_one({"email": email}, {"$set": {"subscription": {
            "status": "canceled",
            "started_at": now.isoformat(),
            "current_period_end": (now + timedelta(days=30)).isoformat(),
        }}})
        r = s.post(f"{BASE_URL}/api/subscription/reactivate")
        assert r.status_code == 400, r.text


# Module-level cleanup
def test_zz_cleanup_demo(mongo_db):
    """Reset demo subscription to None so account stays in free state."""
    mongo_db.users.update_one({"email": DEMO_EMAIL}, {"$set": {"subscription": None}})
    # Delete TEST_ users created during testing
    mongo_db.users.delete_many({"email": {"$regex": "^TEST_"}})
    mongo_db.login_attempts.delete_many({"identifier": {"$regex": "TEST_"}})
