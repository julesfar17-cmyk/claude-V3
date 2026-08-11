"""Tests backend — transcodage vidéo serveur (iteration 7)
Couvre : upload vidéo → transcodage async, upload audio (no transcode),
dedup, status scoping, admin migration."""
import os
import json
import time
import shutil
import subprocess
import tempfile
import pytest
import requests
import imageio_ffmpeg

def _read_base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except OSError:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL introuvable")


BASE_URL = _read_base_url()
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FFPROBE = shutil.which("ffprobe")  # peut être None → on utilisera ffmpeg -i à défaut

from creds import DEMO_EMAIL, DEMO_PASSWORD, ADMIN_EMAIL, ADMIN_PASSWORD


# ----------------------- Helpers -----------------------
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s


def _make_test_mp4(path, width=1280, height=720, duration=3, seed=None):
    """Créer un MP4 H.264/AAC de test avec testsrc2 + sine.
    Le seed rend le contenu unique pour éviter la dédup entre runs."""
    if seed is None:
        seed = int(time.time() * 1000) % 100000
    # frequency variable + duration+petit epsilon → SHA256 unique
    freq = 300 + (seed % 200)
    dur = duration + (seed % 7) * 0.1
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate=30:duration={dur:.2f}",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur:.2f}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _make_test_wav(path, duration=2):
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-ar", "44100", "-ac", "1",
        path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _probe(path):
    """Retourne (video_codec, width, height, audio_codec)."""
    if FFPROBE:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-show_streams", "-of", "json", path],
            capture_output=True, text=True, check=True,
        )
        streams = json.loads(r.stdout).get("streams", [])
        v = next((s for s in streams if s.get("codec_type") == "video"), {})
        a = next((s for s in streams if s.get("codec_type") == "audio"), {})
        return v.get("codec_name"), v.get("width"), v.get("height"), a.get("codec_name")
    # Fallback via ffmpeg -i (parse stderr)
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    txt = r.stderr
    v_codec = None
    a_codec = None
    w = h = None
    for line in txt.splitlines():
        if "Video:" in line:
            # ex: Stream #0:0 ... Video: h264 (High) ... , yuv420p, 1920x1080
            parts = line.split("Video:")[1]
            v_codec = parts.strip().split(" ")[0].rstrip(",")
            import re
            m = re.search(r"(\d{2,5})x(\d{2,5})", parts)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
        elif "Audio:" in line:
            parts = line.split("Audio:")[1]
            a_codec = parts.strip().split(" ")[0].rstrip(",")
    return v_codec, w, h, a_codec


def _poll_status(session, media_id, timeout=120):
    """Poll GET /media/{id}/status jusqu'à processing:false ou timeout."""
    start = time.time()
    last = None
    while time.time() - start < timeout:
        r = session.get(f"{BASE_URL}/api/media/{media_id}/status", timeout=15)
        assert r.status_code == 200, f"status HTTP {r.status_code}: {r.text}"
        last = r.json()
        if not last.get("processing"):
            return last
        time.sleep(2)
    raise AssertionError(f"Timeout polling status for {media_id}, last={last}")


# ----------------------- Fixtures -----------------------
@pytest.fixture(scope="module")
def demo_session():
    return _login(DEMO_EMAIL, DEMO_PASSWORD)


@pytest.fixture(scope="module")
def demo2_session():
    """Second compte user (non-admin, non-demo). On crée un compte éphémère."""
    email = f"TEST_media_scope_{int(time.time())}@test.fr"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"name": "Scope", "email": email, "password": "Passw0rd!", "cgv_accepted": True},
               timeout=15)
    assert r.status_code in (200, 201), f"register: {r.status_code} {r.text}"
    yield s
    # cleanup (best effort — pas d'endpoint delete-account exposé)


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def video_file():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name
    _make_test_mp4(path, width=1280, height=720, duration=3)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture(scope="module")
def audio_file():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    # freq random pour éviter dédup entre runs
    freq = 200 + (int(time.time()) % 300)
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=2",
        "-ar", "44100", "-ac", "1",
        path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


# ----------------------- Tests -----------------------
class TestVideoTranscode:
    """Upload vidéo → transcodage FFmpeg serveur (H.264 1080p / AAC / faststart)."""

    def test_video_upload_returns_processing_true(self, demo_session, video_file):
        with open(video_file, "rb") as fh:
            r = demo_session.post(f"{BASE_URL}/api/media/upload",
                                  files={"file": ("clip_test.mp4", fh, "video/mp4")},
                                  timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "media_id" in data and isinstance(data["media_id"], str)
        assert data.get("processing") == True, f"video should be processing: {data}"
        assert data.get("deduped") == False
        # stash pour tests suivants
        pytest.video_media_id = data["media_id"]

    def test_status_poll_until_done(self, demo_session):
        media_id = getattr(pytest, "video_media_id", None)
        assert media_id, "précédent test doit avoir défini video_media_id"
        s = _poll_status(demo_session, media_id, timeout=180)
        assert s.get("processing") == False
        assert s.get("transcoded") == True, f"transcodage doit avoir réussi: {s}"
        assert s.get("failed") == False
        assert isinstance(s.get("size"), int) and s["size"] > 0

    def test_download_and_verify_h264_aac_1080p_max(self, demo_session, tmp_path):
        media_id = getattr(pytest, "video_media_id", None)
        assert media_id
        r = demo_session.get(f"{BASE_URL}/api/media/{media_id}", timeout=60)
        assert r.status_code == 200, r.text
        content_type = r.headers.get("Content-Type", "")
        assert "video/mp4" in content_type, f"content_type doit être video/mp4: {content_type}"
        out = tmp_path / "downloaded.mp4"
        out.write_bytes(r.content)
        v_codec, w, h, a_codec = _probe(str(out))
        # H.264 (aussi noté avc1/h264)
        assert v_codec in ("h264", "avc1"), f"video codec doit être H.264, got {v_codec}"
        # dimensions max 1920 sur le grand côté
        big = max(w or 0, h or 0)
        assert big <= 1920, f"le grand côté doit être <=1920, got {w}x{h}"
        # audio AAC
        assert a_codec in ("aac",), f"audio codec doit être AAC, got {a_codec}"


class TestAudioUpload:
    """Upload audio → PAS de transcodage (fichier identique)."""

    def test_audio_upload_no_transcode(self, demo_session, audio_file):
        with open(audio_file, "rb") as fh:
            data_bytes = fh.read()
        with open(audio_file, "rb") as fh:
            r = demo_session.post(f"{BASE_URL}/api/media/upload",
                                  files={"file": ("test_audio.wav", fh, "audio/wav")},
                                  timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("processing") == False, f"audio ne doit PAS être en processing: {data}"
        media_id = data["media_id"]
        pytest.audio_media_id = media_id
        # Download → identique octet-pour-octet
        r2 = demo_session.get(f"{BASE_URL}/api/media/{media_id}", timeout=30)
        assert r2.status_code == 200
        assert r2.content == data_bytes, "audio doit être identique au fichier uploadé (pas de transcodage)"


class TestDedup:
    """Ré-upload du MÊME fichier → deduped:true."""

    def test_reupload_same_video_returns_deduped(self, demo_session, video_file):
        with open(video_file, "rb") as fh:
            r = demo_session.post(f"{BASE_URL}/api/media/upload",
                                  files={"file": ("clip_test.mp4", fh, "video/mp4")},
                                  timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("deduped") == True, f"re-upload doit être dedup: {data}"
        # media_id existant renvoyé
        assert data.get("media_id") == getattr(pytest, "video_media_id", None)
        # processing reflète l'état actuel (transcodage terminé donc False)
        assert data.get("processing") == False


class TestStatusScoping:
    """GET /media/{id}/status : 400 si id invalide, 404 pour un autre user."""

    def test_status_invalid_id_returns_400(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/media/notanid/status", timeout=15)
        assert r.status_code == 400, f"id invalide doit renvoyer 400, got {r.status_code} {r.text}"

    def test_status_other_user_returns_404(self, demo2_session):
        media_id = getattr(pytest, "video_media_id", None)
        assert media_id, "besoin du media_id de la démo"
        r = demo2_session.get(f"{BASE_URL}/api/media/{media_id}/status", timeout=15)
        assert r.status_code == 404, f"user scoping doit renvoyer 404, got {r.status_code} {r.text}"


class TestAdminMigration:
    """POST/GET /admin/media/migrate — admin uniquement."""

    def test_migrate_get_admin_ok(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/media/migrate", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("running", "total", "done", "failed"):
            assert k in data, f"clé manquante {k}"

    def test_migrate_post_admin_ok(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/media/migrate", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Migration déjà exécutée avec succès (7/7) → nouveau POST devrait retourner total:0 running:False
        # (sauf si des vidéos non transcodées existent — dans notre suite, on vient d'en uploader une
        # mais elle a été transcodée par _transcode_media dans le test précédent)
        for k in ("running", "total", "done", "failed"):
            assert k in data
        assert isinstance(data["total"], int)

    def test_migrate_non_admin_forbidden(self, demo_session):
        r_post = demo_session.post(f"{BASE_URL}/api/admin/media/migrate", timeout=15)
        assert r_post.status_code == 403, f"POST non-admin doit être 403, got {r_post.status_code}"
        r_get = demo_session.get(f"{BASE_URL}/api/admin/media/migrate", timeout=15)
        assert r_get.status_code == 403, f"GET non-admin doit être 403, got {r_get.status_code}"


# ----------------------- Cleanup -----------------------
@pytest.fixture(scope="module", autouse=True)
def _cleanup(demo_session):
    """Purge les média uploadés par la démo à la fin du module."""
    yield
    # best-effort delete via endpoint dédié si dispo — sinon laisser (GridFS quota reset via admin)
    for attr in ("video_media_id", "audio_media_id"):
        mid = getattr(pytest, attr, None)
        if not mid:
            continue
        try:
            demo_session.delete(f"{BASE_URL}/api/media/{mid}", timeout=10)
        except Exception:
            pass
