"""
BEATCUT iteration 4 — LOT 4 : PROJETS & MÉDIAS (GridFS)
Tests:
- Media upload (dedup sha256, media_id return)
- Media download (streaming, size, isolation entre users → 404)
- Media quota (basic=2Go, free=200Mo)
- Projects CRUD (list, save-upsert, get, duplicate, delete)
- Project deletion purges orphan media (media_deleted count)
- Quota projets: free=1 (429), basic=10
- Régression: login, export/quota, separate (403 basic), admin
Clean up all TEST_ users/projects/media at end.
"""
import io
import os
import uuid

import pytest
import requests
from pymongo import MongoClient
from bson import ObjectId

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://pro-mailer-2.preview.emergentagent.com"
).rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

DEMO_EMAIL = "demo@beatcut.fr"
DEMO_PASSWORD = "Demo1234!"
VIP_EMAIL = "julesfar17@gmail.com"
VIP_PASSWORD = "Carnageproduction1704*"


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
    # Ensure demo is basic
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
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    yield s


@pytest.fixture(scope="module")
def vip_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": VIP_EMAIL, "password": VIP_PASSWORD})
    assert r.status_code == 200, f"VIP login failed: {r.status_code} {r.text}"
    yield s


@pytest.fixture(scope="module")
def free_session(mongo_db):
    """Free user — will be deleted at end of module."""
    email = f"TEST_free_{uuid.uuid4().hex[:6]}@example.com"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"name": "FreeLot4", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    s.email = email  # attach for cleanup
    yield s
    # Cleanup: delete user, their projects, their media
    u = mongo_db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
    if u:
        uid = u["user_id"]
        mongo_db.projects.delete_many({"user_id": uid})
        # Delete all media for this user
        for f in mongo_db["media.files"].find({"metadata.user_id": uid}, {"_id": 1}):
            mongo_db["media.chunks"].delete_many({"files_id": f["_id"]})
        mongo_db["media.files"].delete_many({"metadata.user_id": uid})
    mongo_db.users.delete_one({"email": email})


@pytest.fixture(scope="module")
def free_session_2(mongo_db):
    """Second free user for isolation test."""
    email = f"TEST_free2_{uuid.uuid4().hex[:6]}@example.com"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"name": "FreeLot4b", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    s.email = email
    yield s
    u = mongo_db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
    if u:
        uid = u["user_id"]
        mongo_db.projects.delete_many({"user_id": uid})
        for f in mongo_db["media.files"].find({"metadata.user_id": uid}, {"_id": 1}):
            mongo_db["media.chunks"].delete_many({"files_id": f["_id"]})
        mongo_db["media.files"].delete_many({"metadata.user_id": uid})
    mongo_db.users.delete_one({"email": email})


def _small_bytes(prefix: bytes = b"TESTFILE") -> bytes:
    """Random small binary payload (~1 KB)."""
    return prefix + uuid.uuid4().bytes * 60  # ~961 B


# -------------------------- MEDIA UPLOAD / DEDUP / DOWNLOAD --------------------------
class TestMediaUpload:
    def test_upload_returns_media_id(self, demo_session):
        payload = _small_bytes(b"UP1")
        r = demo_session.post(
            f"{BASE_URL}/api/media/upload",
            files={"file": ("song.wav", payload, "audio/wav")},
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert "media_id" in j
        assert j["size"] == len(payload)
        assert j["deduped"] is False
        demo_session._m1 = j["media_id"]  # remember for other tests
        demo_session._m1_size = len(payload)
        demo_session._m1_bytes = payload

    def test_upload_same_content_returns_deduped(self, demo_session):
        # Re-upload the exact same bytes
        r = demo_session.post(
            f"{BASE_URL}/api/media/upload",
            files={"file": ("song_bis.wav", demo_session._m1_bytes, "audio/wav")},
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["deduped"] is True
        assert j["media_id"] == demo_session._m1

    def test_download_streams_same_bytes(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/media/{demo_session._m1}")
        assert r.status_code == 200
        assert len(r.content) == demo_session._m1_size
        assert r.content == demo_session._m1_bytes

    def test_download_other_user_media_returns_404(self, demo_session, free_session):
        """SECURITY: free user cannot download demo's media."""
        r = free_session.get(f"{BASE_URL}/api/media/{demo_session._m1}")
        assert r.status_code == 404, r.text

    def test_download_invalid_id_returns_400(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/media/not_an_object_id")
        assert r.status_code == 400

    def test_download_missing_id_returns_404(self, demo_session):
        fake = str(ObjectId())
        r = demo_session.get(f"{BASE_URL}/api/media/{fake}")
        assert r.status_code == 404


# -------------------------- MEDIA QUOTA --------------------------
class TestMediaQuota:
    def test_quota_basic_is_2go(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/media/quota")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["tier"] == "basic"
        assert j["quota"] == 2_000_000_000
        assert isinstance(j["used"], int)
        assert j["used"] >= 0

    def test_quota_free_is_200mo(self, free_session):
        r = free_session.get(f"{BASE_URL}/api/media/quota")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["tier"] == "free"
        assert j["quota"] == 200_000_000

    def test_quota_pro_is_10go(self, vip_session):
        r = vip_session.get(f"{BASE_URL}/api/media/quota")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["tier"] == "pro"
        assert j["quota"] == 10_000_000_000


# -------------------------- PROJECTS CRUD --------------------------
class TestProjectsCRUD:
    def test_create_project_and_get(self, demo_session, mongo_db, demo_user_id):
        # Clean demo projects to have a fresh baseline
        mongo_db.projects.delete_many({"user_id": demo_user_id})
        state = {"bpm": 120, "clips": [], "audio": None, "subs": {"raw": "yo"}}
        r = demo_session.post(f"{BASE_URL}/api/projects",
                              json={"title": "TEST_Proj_1", "state": state})
        assert r.status_code == 200, r.text
        pid = r.json()["project_id"]
        demo_session._pid = pid

        # GET returns full state
        r = demo_session.get(f"{BASE_URL}/api/projects/{pid}")
        assert r.status_code == 200
        doc = r.json()
        assert doc["title"] == "TEST_Proj_1"
        assert doc["state"]["bpm"] == 120
        assert doc["state"]["subs"]["raw"] == "yo"

    def test_list_projects_excludes_state(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/projects")
        assert r.status_code == 200
        j = r.json()
        assert "projects" in j and "count" in j
        assert j["count"] >= 1
        # Every listed project must NOT contain state
        for p in j["projects"]:
            assert "state" not in p, p
            assert "project_id" in p
            assert "title" in p
            assert "_id" not in p  # no mongo _id leak
        assert j["quota"] == 10  # Basic

    def test_upsert_updates_existing(self, demo_session):
        pid = demo_session._pid
        r = demo_session.post(f"{BASE_URL}/api/projects", json={
            "project_id": pid,
            "title": "TEST_Proj_1_renamed",
            "state": {"bpm": 90, "clips": [], "audio": None},
        })
        assert r.status_code == 200, r.text
        assert r.json()["project_id"] == pid
        # Verify persisted
        r = demo_session.get(f"{BASE_URL}/api/projects/{pid}")
        assert r.json()["title"] == "TEST_Proj_1_renamed"
        assert r.json()["state"]["bpm"] == 90

    def test_upsert_nonexistent_project_id_returns_404(self, demo_session):
        r = demo_session.post(f"{BASE_URL}/api/projects", json={
            "project_id": "doesnotexist123",
            "title": "x", "state": {}
        })
        assert r.status_code == 404

    def test_get_other_user_project_returns_404(self, demo_session, free_session):
        r = free_session.get(f"{BASE_URL}/api/projects/{demo_session._pid}")
        assert r.status_code == 404

    def test_duplicate_project(self, demo_session, mongo_db, demo_user_id):
        pid = demo_session._pid
        r = demo_session.post(f"{BASE_URL}/api/projects/{pid}/duplicate")
        assert r.status_code == 200, r.text
        new_pid = r.json()["project_id"]
        # Verify presence with "(copie)" suffix
        r = demo_session.get(f"{BASE_URL}/api/projects/{new_pid}")
        assert r.status_code == 200
        assert "(copie)" in r.json()["title"]
        demo_session._pid_dup = new_pid


# -------------------------- DELETE + ORPHAN MEDIA PURGE --------------------------
class TestProjectDelete:
    def test_delete_project_purges_orphan_media(self, demo_session, mongo_db, demo_user_id):
        # Clean slate
        mongo_db.projects.delete_many({"user_id": demo_user_id})
        # Upload TWO distinct media
        payload_a = _small_bytes(b"DEL_A")
        payload_b = _small_bytes(b"DEL_B")
        rA = demo_session.post(f"{BASE_URL}/api/media/upload",
                               files={"file": ("a.mp4", payload_a, "video/mp4")})
        rB = demo_session.post(f"{BASE_URL}/api/media/upload",
                               files={"file": ("b.mp4", payload_b, "video/mp4")})
        mid_a = rA.json()["media_id"]
        mid_b = rB.json()["media_id"]
        # Project 1 references A + B
        r1 = demo_session.post(f"{BASE_URL}/api/projects", json={
            "title": "TEST_P1", "state": {
                "audio": {"mediaId": mid_a, "name": "a.mp4"},
                "clips": [{"mediaId": mid_b, "name": "b.mp4"}],
            }
        })
        pid1 = r1.json()["project_id"]
        # Project 2 also references A (shared)
        r2 = demo_session.post(f"{BASE_URL}/api/projects", json={
            "title": "TEST_P2", "state": {
                "audio": {"mediaId": mid_a, "name": "a.mp4"},
                "clips": [],
            }
        })
        pid2 = r2.json()["project_id"]

        # Delete project 1 → B should be purged (orphan), A remains (still in P2)
        r = demo_session.delete(f"{BASE_URL}/api/projects/{pid1}")
        assert r.status_code == 200, r.text
        assert r.json()["media_deleted"] == 1

        # Verify B is gone in GridFS
        assert mongo_db["media.files"].find_one({"_id": ObjectId(mid_b)}) is None
        # Verify A still exists
        assert mongo_db["media.files"].find_one({"_id": ObjectId(mid_a)}) is not None

        # Delete project 2 → A should be purged now
        r = demo_session.delete(f"{BASE_URL}/api/projects/{pid2}")
        assert r.status_code == 200
        assert r.json()["media_deleted"] == 1
        assert mongo_db["media.files"].find_one({"_id": ObjectId(mid_a)}) is None

    def test_delete_nonexistent_returns_404(self, demo_session):
        r = demo_session.delete(f"{BASE_URL}/api/projects/nosuchid")
        assert r.status_code == 404


# -------------------------- PROJECT QUOTAS --------------------------
class TestProjectQuotas:
    def test_free_user_limited_to_1_project(self, free_session):
        # 1st project OK
        r = free_session.post(f"{BASE_URL}/api/projects",
                              json={"title": "TEST_free1", "state": {"bpm": 100}})
        assert r.status_code == 200, r.text
        # 2nd project → 429
        r = free_session.post(f"{BASE_URL}/api/projects",
                              json={"title": "TEST_free2", "state": {"bpm": 100}})
        assert r.status_code == 429, r.text
        detail = r.json().get("detail", "")
        assert "1 projet" in detail or "1 projets" in detail
        assert "plan" in detail.lower()

    def test_free_duplicate_also_blocked_by_quota(self, free_session):
        # Get existing project id
        r = free_session.get(f"{BASE_URL}/api/projects")
        assert r.status_code == 200
        pid = r.json()["projects"][0]["project_id"]
        r = free_session.post(f"{BASE_URL}/api/projects/{pid}/duplicate")
        assert r.status_code == 429

    def test_basic_quota_is_10(self, demo_session, mongo_db, demo_user_id):
        # List should report quota 10
        r = demo_session.get(f"{BASE_URL}/api/projects")
        assert r.status_code == 200
        assert r.json()["quota"] == 10


# -------------------------- Régression --------------------------
class TestRegression:
    def test_login_still_works(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login",
                   json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert r.status_code == 200

    def test_export_quota_still_works(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/export/quota")
        assert r.status_code == 200
        j = r.json()
        assert j["tier"] == "basic"
        assert j["quota"] == 10

    def test_separate_basic_still_403(self, demo_session):
        # Send a tiny dummy WAV
        import wave
        import struct
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(struct.pack("<" + "h" * 400, *([0] * 400)))
        r = demo_session.post(
            f"{BASE_URL}/api/separate",
            files={"file": ("t.wav", buf.getvalue(), "audio/wav")},
        )
        assert r.status_code == 403

    def test_admin_stats_and_users(self, vip_session):
        r = vip_session.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 200, r.text
        r = vip_session.get(f"{BASE_URL}/api/admin/users")
        assert r.status_code == 200


# -------------------------- CLEANUP --------------------------
def test_zzz_cleanup(mongo_db, demo_user_id):
    """Wipe all TEST_ users, demo projects, orphan media."""
    # Delete demo's TEST_ projects & media
    demo_projects = list(mongo_db.projects.find({"user_id": demo_user_id}))
    referenced = set()
    for p in demo_projects:
        st = p.get("state") or {}
        a = (st.get("audio") or {}).get("mediaId")
        if a:
            referenced.add(a)
        for c in st.get("clips") or []:
            if c.get("mediaId"):
                referenced.add(c["mediaId"])
    # Delete all TEST_ projects
    mongo_db.projects.delete_many({"user_id": demo_user_id, "title": {"$regex": "^TEST_"}})
    # Delete orphan media for demo (anything referenced above, since we just deleted those projects)
    for mid in referenced:
        try:
            oid = ObjectId(mid)
        except Exception:
            continue
        # Check if still referenced
        still = False
        for p in mongo_db.projects.find({"user_id": demo_user_id}, {"state": 1}):
            st = p.get("state") or {}
            if (st.get("audio") or {}).get("mediaId") == mid:
                still = True
                break
            if any(c.get("mediaId") == mid for c in st.get("clips") or []):
                still = True
                break
        if not still:
            mongo_db["media.chunks"].delete_many({"files_id": oid})
            mongo_db["media.files"].delete_one({"_id": oid})

    # Also delete any lingering TEST_ users
    for u in mongo_db.users.find({"email": {"$regex": "^TEST_"}}, {"user_id": 1}):
        uid = u["user_id"]
        mongo_db.projects.delete_many({"user_id": uid})
        for f in mongo_db["media.files"].find({"metadata.user_id": uid}, {"_id": 1}):
            mongo_db["media.chunks"].delete_many({"files_id": f["_id"]})
        mongo_db["media.files"].delete_many({"metadata.user_id": uid})
    mongo_db.users.delete_many({"email": {"$regex": "^TEST_"}})
