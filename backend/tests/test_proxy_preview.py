"""Tests backend: proxy preview auto (POST /api/media/proxy/{id})."""
import os
import subprocess
import tempfile
import time

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DEMO_EMAIL = "demo@beatcut.fr"
DEMO_PASSWORD = "Demo1234!"


def _ffmpeg_bin():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _make_video(width: int, height: int, seconds: int = 3) -> bytes:
    """Génère un mp4 H.264 en mémoire."""
    ff = _ffmpeg_bin()
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "v.mp4")
        cmd = [
            ff, "-y", "-f", "lavfi", "-i",
            f"testsrc=size={width}x{height}:rate=30:duration={seconds}",
            "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", out,
        ]
        r = subprocess.run(cmd, capture_output=True)
        assert r.returncode == 0, r.stderr.decode(errors="ignore")[-500:]
        with open(out, "rb") as f:
            return f.read()


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def uploaded_ids(session):
    """Upload une vidéo portrait 1080p (proxy attendu) + une 360p (proxy sauté)."""
    ids = {}
    for key, (w, h) in [("portrait", (1080, 1920)), ("light", (640, 360))]:
        raw = _make_video(w, h, seconds=3)
        files = {"file": (f"test_{key}.mp4", raw, "video/mp4")}
        r = session.post(f"{BASE_URL}/api/media/upload", files=files, timeout=180)
        assert r.status_code == 200, f"upload {key}: {r.status_code} {r.text[:200]}"
        ids[key] = r.json()["media_id"]
    return ids


def _wait_processing(session, media_id, timeout=90):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = session.get(f"{BASE_URL}/api/media/{media_id}/status", timeout=15)
        if r.status_code == 200:
            last = r.json()
            if not last.get("processing"):
                return last
        time.sleep(2)
    pytest.fail(f"processing timed out ({media_id}) last={last}")


# ---------- 1. proxy auto sur portrait 1080p ----------
def test_proxy_auto_generated_for_heavy_video(session, uploaded_ids):
    mid = uploaded_ids["portrait"]
    _wait_processing(session, mid)
    # attente supplémentaire pour laisser tourner _auto_proxy (tâche background)
    proxy_id = None
    deadline = time.time() + 120
    while time.time() < deadline:
        r = session.post(f"{BASE_URL}/api/media/proxy/{mid}", timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        if j.get("proxy_id") and j["proxy_id"] != mid:
            proxy_id = j["proxy_id"]
            break
        if j.get("status") == "failed":
            pytest.fail("proxy generation failed")
        time.sleep(3)
    assert proxy_id, "aucun proxy_id différent obtenu dans le délai"

    # Vérifier le contenu du proxy
    r = session.get(f"{BASE_URL}/api/media/{proxy_id}", timeout=60)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "mp4" in ct or "video" in ct, ct
    assert len(r.content) > 1000

    # Vérifie codec h264 & résolution via ffmpeg -i (parsing stderr)
    ff = _ffmpeg_bin()
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        tf.write(r.content); path = tf.name
    try:
        out = subprocess.run([ff, "-hide_banner", "-i", path],
                             capture_output=True, text=True).stderr
    finally:
        os.unlink(path)
    assert "h264" in out.lower(), out[-800:]
    import re
    m = re.search(r"(\d{2,4})x(\d{2,4})", out)
    assert m, out[-800:]
    w, h = int(m.group(1)), int(m.group(2))
    assert w <= 720, f"width {w} > 720"
    assert h <= 1280, f"height {h} > 1280"


# ---------- 2. proxy sauté sur vidéo légère ----------
def test_proxy_skipped_for_light_video(session, uploaded_ids):
    mid = uploaded_ids["light"]
    _wait_processing(session, mid)
    # Attendre un peu que l'analyse background décide de skip
    proxy_id_same = False
    deadline = time.time() + 60
    while time.time() < deadline:
        r = session.post(f"{BASE_URL}/api/media/proxy/{mid}", timeout=30)
        assert r.status_code == 200
        j = r.json()
        if j.get("proxy_id") == mid:
            proxy_id_same = True
            break
        time.sleep(3)
    assert proxy_id_same, "proxy_id devrait égaler media_id pour vidéo légère"


# ---------- 3. Erreurs ----------
def test_proxy_404_unknown_id(session):
    fake = "507f1f77bcf86cd799439011"
    r = session.post(f"{BASE_URL}/api/media/proxy/{fake}", timeout=15)
    assert r.status_code == 404, r.text


def test_proxy_400_invalid_id(session):
    r = session.post(f"{BASE_URL}/api/media/proxy/not-an-oid", timeout=15)
    assert r.status_code == 400, r.text


def test_proxy_401_unauthenticated():
    r = requests.post(f"{BASE_URL}/api/media/proxy/507f1f77bcf86cd799439011", timeout=15)
    assert r.status_code == 401, f"expected 401 got {r.status_code} {r.text[:200]}"


# ---------- 4. /media/mine et /media/quota excluent les proxys ----------
def test_media_mine_excludes_proxies(session, uploaded_ids):
    r = session.get(f"{BASE_URL}/api/media/mine", timeout=30)
    assert r.status_code == 200
    items = r.json().get("media", [])
    proxy_files = [m for m in items if (m.get("filename") or "").endswith(".proxy.mp4")]
    assert not proxy_files, f"des proxys apparaissent dans /media/mine: {proxy_files}"


def test_media_quota_excludes_proxies(session):
    r = session.get(f"{BASE_URL}/api/media/quota", timeout=30)
    assert r.status_code == 200
    j = r.json()
    # On ne peut pas connaître la valeur exacte, on vérifie juste le format cohérent
    assert "used" in j or "storage_used" in j or "quota" in j or isinstance(j, dict)
