"""Iter17 §2-A: POST /api/telemetry/preview + GET /api/admin/telemetry/preview."""
import os
import uuid
import time
import requests
from creds import DEMO_EMAIL, DEMO_PASSWORD, ADMIN_EMAIL, ADMIN_PASSWORD

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pro-mailer-2.preview.emergentagent.com").rstrip("/")
POST = f"{BASE}/api/telemetry/preview"
GET_ADMIN = f"{BASE}/api/admin/telemetry/preview"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} failed {r.status_code} {r.text}"
    return s


# ── POST /api/telemetry/preview (public) ─────────────────────────────

def test_post_no_auth_batch_2_events_stored():
    sid = f"TEST_iter17_{uuid.uuid4().hex[:12]}"
    payload = {
        "session_id": sid,
        "ctx": {"ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604",
                "mobile": True, "clips": 2, "plans": 3, "build": "iter17"},
        "events": [
            {"type": "preview_stall", "plan": 0, "clip": 0, "codec": "avc1.640028", "stallMs": 600},
            {"type": "frame_miss", "plan": 0, "clip": 1},
        ],
    }
    r = requests.post(POST, json=payload, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True
    assert d.get("stored") == 2


def test_post_events_empty_returns_stored_0():
    r = requests.post(POST, json={"session_id": "TEST_iter17_empty", "events": []}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("stored") == 0


def test_post_invalid_body_400():
    # non-JSON body should raise 400
    r = requests.post(POST, data="not-json-at-all", headers={"Content-Type": "application/json"}, timeout=15)
    assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text}"


def test_post_events_truncated_to_100():
    sid = f"TEST_iter17_trunc_{uuid.uuid4().hex[:8]}"
    events = [{"type": "frame_miss", "plan": 0, "clip": i} for i in range(150)]
    r = requests.post(POST, json={"session_id": sid, "ctx": {"ua": "Chrome"}, "events": events}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("stored") == 100


def test_post_filters_whitelist_hack_field_not_stored():
    """A field 'hack' should not be persisted (whitelist filter)."""
    sid = f"TEST_iter17_wl_{uuid.uuid4().hex[:8]}"
    r = requests.post(POST, json={
        "session_id": sid,
        "ctx": {"ua": "Chrome"},
        "events": [{"type": "preview_stall", "plan": 0, "clip": 0, "codec": "avc1.640028",
                    "stallMs": 700, "hack": "x-should-not-persist"}],
    }, timeout=15)
    assert r.status_code == 200
    # Retrieve via admin
    s = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    r2 = s.get(GET_ADMIN, params={"days": 1}, timeout=15)
    assert r2.status_code == 200
    d = r2.json()
    # look for our session in samples (session prefix first 8 chars)
    sess_prefix = sid[:8]
    found = [s for s in d.get("samples") or [] if s.get("session") == sess_prefix]
    assert found, f"expected sample with session prefix {sess_prefix}, got sessions: {[s.get('session') for s in d.get('samples') or []][:10]}"
    for s2 in found:
        assert "hack" not in s2, f"'hack' should have been filtered out: {s2}"


# ── GET /api/admin/telemetry/preview ─────────────────────────────────

def test_admin_no_auth_401():
    r = requests.get(GET_ADMIN, timeout=15)
    assert r.status_code in (401, 403)


def test_admin_non_admin_403():
    s = _login(DEMO_EMAIL, DEMO_PASSWORD)
    r = s.get(GET_ADMIN, timeout=15)
    assert r.status_code == 403, f"expected 403, got {r.status_code}"


def test_admin_report_shape_and_aggregates():
    # Post 2 sessions: one iPhone with stall, one Chrome desktop without stall
    sid_ios = f"TEST_iter17_ios_{uuid.uuid4().hex[:8]}"
    sid_chr = f"TEST_iter17_chr_{uuid.uuid4().hex[:8]}"
    r1 = requests.post(POST, json={
        "session_id": sid_ios,
        "ctx": {"ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605 Version/17 Mobile/15E148 Safari/604",
                "mobile": True, "clips": 2},
        "events": [
            {"type": "preview_stall", "codec": "avc1.640028", "stallMs": 900, "plan": 0, "clip": 0},
            {"type": "frame_miss", "plan": 0, "clip": 0},
        ],
    }, timeout=15)
    assert r1.status_code == 200
    r2 = requests.post(POST, json={
        "session_id": sid_chr,
        "ctx": {"ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
                "mobile": False, "clips": 6},
        "events": [
            {"type": "clip_not_ready", "optimizing": 1, "notReady": 2},
        ],
    }, timeout=15)
    assert r2.status_code == 200

    # small delay
    time.sleep(0.5)
    s = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    r = s.get(GET_ADMIN, params={"days": 7}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("total_sessions", "sessions_with_stall", "pct_sessions_with_stall",
              "event_counts", "stall_codecs", "by_browser", "by_project_size", "samples"):
        assert k in d, f"missing key {k}"
    assert isinstance(d["total_sessions"], int) and d["total_sessions"] >= 2
    # our iOS session must be counted in preview_stall
    assert d["sessions_with_stall"] >= 1
    # event_counts must include preview_stall and clip_not_ready and frame_miss
    ec = d["event_counts"]
    assert ec.get("preview_stall", 0) >= 1
    assert ec.get("clip_not_ready", 0) >= 1
    assert ec.get("frame_miss", 0) >= 1
    # codec avc1.640028 must appear in stall_codecs
    assert d["stall_codecs"].get("avc1.640028", 0) >= 1
    # by_browser: iOS Safari family and Chrome desktop family
    bb = d["by_browser"]
    assert "iOS Safari" in bb, f"expected iOS Safari in by_browser {list(bb)}"
    assert "Chrome desktop" in bb, f"expected Chrome desktop in by_browser {list(bb)}"
    assert bb["iOS Safari"]["with_stall"] >= 1
    # by_project_size buckets
    bs = d["by_project_size"]
    assert "1-3 clips" in bs
    assert "4-10 clips" in bs
    # pct = with_stall/total*100
    assert 0.0 <= d["pct_sessions_with_stall"] <= 100.0
