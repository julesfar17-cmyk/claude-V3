"""Iter18 — Import par lien (yt-dlp) : POST /api/media/import-link + polling /status."""
import os
import time
import pytest
import requests

def _read_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()).rstrip("/")
from creds import DEMO_EMAIL, DEMO_PASSWORD, VIP_EMAIL, VIP_PASSWORD  # noqa: E402
DEMO = {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
ADMIN = {"email": VIP_EMAIL, "password": VIP_PASSWORD}

TEST_MP4 = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/720/Big_Buck_Bunny_720_10s_1MB.mp4"


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login {creds['email']}: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def demo_session():
    return _login(DEMO)


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN)


# --- Validation d'URL ---
@pytest.mark.parametrize("bad_url", [
    "http://localhost/x",
    "ftp://example.com/foo.mp4",
    "not-a-url",
    "http://127.0.0.1/x.mp4",
    "",
])
def test_import_link_invalid_url_returns_400(demo_session, bad_url):
    r = demo_session.post(f"{BASE_URL}/api/media/import-link", json={"url": bad_url}, timeout=15)
    assert r.status_code == 400, f"URL '{bad_url}' devrait être 400, got {r.status_code} {r.text[:200]}"


# --- Job inconnu → 404 ---
def test_status_unknown_job_returns_404(demo_session):
    r = demo_session.get(f"{BASE_URL}/api/media/import-link/deadbeef00000000", timeout=15)
    assert r.status_code == 404


# --- Job d'un autre user → 404 ---
def test_status_other_user_job_returns_404(demo_session, admin_session):
    # demo crée un job, admin interroge → 404 (isolation)
    r = demo_session.post(f"{BASE_URL}/api/media/import-link", json={"url": TEST_MP4}, timeout=20)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    r2 = admin_session.get(f"{BASE_URL}/api/media/import-link/{job_id}", timeout=15)
    assert r2.status_code == 404


# --- Flow complet : .mp4 direct → done + media accessible ---
def test_import_link_full_flow_direct_mp4(demo_session):
    r = demo_session.post(f"{BASE_URL}/api/media/import-link", json={"url": TEST_MP4}, timeout=20)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    assert isinstance(job_id, str) and len(job_id) >= 8

    seen_statuses = set()
    media_id = None
    filename = None
    deadline = time.time() + 180
    while time.time() < deadline:
        s = demo_session.get(f"{BASE_URL}/api/media/import-link/{job_id}", timeout=15)
        assert s.status_code == 200, s.text
        data = s.json()
        seen_statuses.add(data.get("status"))
        if data.get("status") == "done":
            media_id = data.get("media_id")
            filename = data.get("filename")
            break
        if data.get("status") == "error":
            pytest.fail(f"job en erreur: {data}")
        time.sleep(2)

    assert media_id, f"pas de media_id après timeout. statuses vues: {seen_statuses}"
    assert filename
    # statuts progressifs attendus (au moins un intermédiaire)
    assert seen_statuses & {"queued", "downloading", "storing", "done"}, seen_statuses

    # Récupération des octets vidéo
    mr = demo_session.get(f"{BASE_URL}/api/media/{media_id}", timeout=30)
    assert mr.status_code == 200
    assert len(mr.content) > 10000, f"contenu vidéo trop petit: {len(mr.content)}"
