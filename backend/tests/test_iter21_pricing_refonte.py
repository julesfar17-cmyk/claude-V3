"""Iter21 — Refonte tarifaire BeatCut (Essentiel/Pro/Studio + paywall FREE + sessions uniques + onboarding).
Toutes les requêtes utilisent REACT_APP_BACKEND_URL. Stripe LIVE → aucun paiement complété.
"""
import os
import uuid
import struct
import zlib
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fallback : frontend .env
    fe_env = Path(__file__).resolve().parents[2] / "frontend" / ".env"
    for line in fe_env.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

API = f"{BASE_URL}/api"

from creds import (DEMO_EMAIL, DEMO_PASSWORD, FREE_EMAIL, FREE_PASSWORD,
                   VIP_EMAIL, VIP_PASSWORD)  # noqa: E402 — jamais de secrets en dur


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} → {r.status_code} {r.text[:200]}"
    return s


# ---------------------------------------------------------------------------
# Checkout — accepte les 4 nouveaux plans + legacy, renvoie URL stripe
# ---------------------------------------------------------------------------
class TestCheckoutPlans:
    @pytest.fixture(scope="class")
    def s_free(self):
        return _login(FREE_EMAIL, FREE_PASSWORD)

    @pytest.mark.parametrize("plan", ["essentiel", "pro_monthly", "pro_yearly", "studio", "monthly", "yearly", "basic"])
    def test_checkout_plan(self, s_free, plan):
        r = s_free.post(f"{API}/payments/checkout", json={
            "plan": plan, "origin_url": BASE_URL,
        }, timeout=30)
        assert r.status_code == 200, f"{plan} → {r.status_code} {r.text[:200]}"
        data = r.json()
        assert "url" in data and "checkout.stripe.com" in data["url"], f"URL invalide: {data}"

    def test_checkout_return_path(self, s_free):
        r = s_free.post(f"{API}/payments/checkout", json={
            "plan": "pro_monthly",
            "origin_url": BASE_URL,
            "return_path": "/studio?project=x",
        }, timeout=30)
        assert r.status_code == 200
        assert "checkout.stripe.com" in r.json().get("url", "")


# ---------------------------------------------------------------------------
# Quota + register_export : FREE vs Basic legacy (grandfathering)
# ---------------------------------------------------------------------------
class TestQuotaAndPaywall:
    def test_free_quota_paywall(self):
        s = _login(FREE_EMAIL, FREE_PASSWORD)
        r = s.get(f"{API}/export/quota", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["tier"] == "free"
        assert d["quota"] == 0
        assert d.get("paywall") is True

    def test_free_register_export_402(self):
        s = _login(FREE_EMAIL, FREE_PASSWORD)
        r = s.post(f"{API}/export/register", timeout=15)
        assert r.status_code == 402
        detail = r.json().get("detail")
        # detail can be dict {code,message}
        assert isinstance(detail, dict) and detail.get("code") == "paywall", f"detail={detail}"

    def test_demo_basic_quota_grandfathering(self):
        s = _login(DEMO_EMAIL, DEMO_PASSWORD)
        r = s.get(f"{API}/export/quota", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["tier"] == "basic", f"tier={d}"
        assert d["quota"] == 10

    def test_demo_basic_register_export_ok(self):
        # Ne pas polluer le quota : compte utilisé, on ne vérifie que 200 + used/quota
        s = _login(DEMO_EMAIL, DEMO_PASSWORD)
        r = s.post(f"{API}/export/register", timeout=15)
        # peut retourner 200 (autorisé) ou 429 (déjà atteint). L'important : PAS 402.
        assert r.status_code in (200, 429), f"{r.status_code} {r.text[:200]}"
        if r.status_code == 200:
            d = r.json()
            assert d.get("allowed") is True
            assert d.get("quota") == 10
            assert isinstance(d.get("used"), int)


# ---------------------------------------------------------------------------
# Sessions uniques : 2e login invalide le 1er (sauf admin/VIP)
# ---------------------------------------------------------------------------
class TestSingleSession:
    def test_demo_second_login_invalidates_first(self):
        s1 = _login(DEMO_EMAIL, DEMO_PASSWORD)
        # sanity : s1 fonctionne
        r = s1.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        s2 = _login(DEMO_EMAIL, DEMO_PASSWORD)
        r2 = s2.get(f"{API}/auth/me", timeout=15)
        assert r2.status_code == 200, "2e session doit fonctionner"
        r1 = s1.get(f"{API}/auth/me", timeout=15)
        assert r1.status_code == 401, f"1re session doit être invalidée : got {r1.status_code}"
        assert "autre appareil" in (r1.text or "").lower() or "autre appareil" in str(r1.json().get("detail", "")).lower()

    def test_vip_admin_exempt_from_single_session(self):
        s1 = _login(VIP_EMAIL, VIP_PASSWORD)
        r1a = s1.get(f"{API}/auth/me", timeout=15)
        assert r1a.status_code == 200
        s2 = _login(VIP_EMAIL, VIP_PASSWORD)
        r2 = s2.get(f"{API}/auth/me", timeout=15)
        r1b = s1.get(f"{API}/auth/me", timeout=15)
        assert r2.status_code == 200
        assert r1b.status_code == 200, "VIP julesfar17 doit être exempté (1re session toujours OK)"


# ---------------------------------------------------------------------------
# Limite 5 clips vidéo FREE
# ---------------------------------------------------------------------------
def _fake_mp4(marker: bytes) -> bytes:
    # entête ftyp isom + payload unique pour éviter la dédup sha256
    ftyp = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    return ftyp + b"\x00" * 16 + marker + os.urandom(64)


class TestFreeClipsLimit:
    def test_free_5_clips_max(self):
        # Direct Mongo cleanup (pas d'endpoint DELETE /api/media/{id})
        from pymongo import MongoClient
        from bson import ObjectId
        MONGO_URL = os.environ["MONGO_URL"]
        DB_NAME = os.environ["DB_NAME"]
        mcli = MongoClient(MONGO_URL)
        mdb = mcli[DB_NAME]

        s = _login(FREE_EMAIL, FREE_PASSWORD)
        # Récupérer user_id pour cleanup
        me = s.get(f"{API}/auth/me", timeout=15).json()
        uid = me["user_id"]

        def _cleanup_videos():
            vids = list(mdb["media.files"].find({
                "metadata.user_id": uid,
                "metadata.content_type": {"$regex": "^video"},
            }, {"_id": 1}))
            for v in vids:
                oid = v["_id"]
                mdb["media.files"].delete_one({"_id": oid})
                mdb["media.chunks"].delete_many({"files_id": oid})

        uploaded_ids = []
        try:
            _cleanup_videos()
            statuses = []
            for i in range(6):
                marker = f"clip{i}-{uuid.uuid4().hex}".encode()
                files = {"file": (f"clip{i}.mp4", _fake_mp4(marker), "video/mp4")}
                r = s.post(f"{API}/media/upload", files=files, timeout=30)
                statuses.append(r.status_code)
                if r.status_code == 200:
                    mid = r.json().get("media_id")
                    if mid:
                        uploaded_ids.append(mid)
                elif r.status_code == 403:
                    assert "5 clips" in r.text or "clips maximum" in r.text.lower(), f"msg inattendu: {r.text[:200]}"
            # 5 premiers 200, 6e = 403
            assert statuses[:5].count(200) >= 5, f"statuses={statuses}"
            assert statuses[5] == 403, f"statuses={statuses}"
        finally:
            _cleanup_videos()
            mcli.close()


# ---------------------------------------------------------------------------
# Studio watermark : gating
# ---------------------------------------------------------------------------
class TestStudioWatermark:
    def test_non_studio_post_watermark_403(self):
        s = _login(DEMO_EMAIL, DEMO_PASSWORD)
        # PNG minimal valide (8 bytes signature + IHDR chunk)
        png_sig = b"\x89PNG\r\n\x1a\n"
        ihdr = b"\x00\x00\x00\x0dIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + b"\x1f\x15\xc4\x89"
        png = png_sig + ihdr
        files = {"file": ("logo.png", png, "image/png")}
        r = s.post(f"{API}/studio/watermark", files=files, timeout=15)
        assert r.status_code == 403, f"got {r.status_code} {r.text[:200]}"

    def test_get_watermark_404(self):
        s = _login(DEMO_EMAIL, DEMO_PASSWORD)
        r = s.get(f"{API}/studio/watermark", timeout=15)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Onboarding : sauvegarde + telemetry + nouveau compte a onboarding_done=false
# ---------------------------------------------------------------------------
class TestOnboarding:
    def test_new_user_onboarding_flow(self):
        email = f"TEST_onb_{uuid.uuid4().hex[:10]}@example.com"
        password = "Onboarding1234!"
        s = requests.Session()
        r = s.post(f"{API}/auth/register", json={
            "name": "Test Onboarding", "email": email, "password": password,
        }, timeout=20)
        assert r.status_code == 200, f"register: {r.status_code} {r.text[:200]}"
        # /auth/me → onboarding_done False
        rm = s.get(f"{API}/auth/me", timeout=15)
        assert rm.status_code == 200
        me = rm.json()
        assert me.get("onboarding_done") in (False, None), f"new user onboarding_done={me.get('onboarding_done')}"

        # POST /api/onboarding
        r_ob = s.post(f"{API}/onboarding", json={
            "persona": "artiste", "genre": "plugg_hyperpop",
            "skipped_at": 3, "done": True,
        }, timeout=15)
        assert r_ob.status_code == 200

        # Verify
        rm2 = s.get(f"{API}/auth/me", timeout=15)
        me2 = rm2.json()
        assert me2.get("onboarding_done") is True
        ob = me2.get("onboarding") or {}
        assert ob.get("genre") == "plugg_hyperpop"
        assert ob.get("persona") == "artiste"

    def test_telemetry_onboarding(self):
        s = _login(DEMO_EMAIL, DEMO_PASSWORD)
        r = s.post(f"{API}/telemetry/onboarding", json={
            "event": "onboarding_step_1", "step": 1,
        }, timeout=15)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Activate-now sans essai
# ---------------------------------------------------------------------------
class TestActivateNow:
    def test_activate_now_400_without_trial(self):
        s = _login(DEMO_EMAIL, DEMO_PASSWORD)
        r = s.post(f"{API}/payments/activate-now", timeout=15)
        assert r.status_code == 400
        assert "essai" in (r.text or "").lower()
