"""
BEATCUT iteration 9 — LOT protections perte de données
Tests:
- Backups versionnés côté serveur (POST /projects avec perte de clipRefs → backup 'perte-de-clips')
- Restore backup → state restauré
- Throttle : 2 saves sans perte de clips < 10 min → au max 1 backup 'auto' supplémentaire
- GET /media/mine (scoping user)
- Sécurité : /backups sans cookie → 401, restore backup inconnu → 404
Idempotent : remet le projet 'Morceau Série Test' dans son état d'origine à la fin.
"""
import copy
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"

DEMO_EMAIL = "demo@beatcut.fr"
DEMO_PASSWORD = "Demo1234!"
OTHER_EMAIL = "admin@beatcut.fr"
OTHER_PASSWORD = "Admin123!"
PROJECT_TITLE_MATCH = "Morceau Série Test"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def demo_session():
    return _login(DEMO_EMAIL, DEMO_PASSWORD)


@pytest.fixture(scope="module")
def other_session():
    return _login(OTHER_EMAIL, OTHER_PASSWORD)


@pytest.fixture(scope="module")
def demo_project(demo_session):
    """Find 'Morceau Série Test' project and preserve original state for restoration."""
    r = demo_session.get(f"{BASE_URL}/api/projects", timeout=15)
    assert r.status_code == 200
    projs = r.json().get("projects") or []
    target = None
    for p in projs:
        if PROJECT_TITLE_MATCH.lower() in (p.get("title") or "").lower():
            target = p
            break
    assert target, f"No project titled '{PROJECT_TITLE_MATCH}' for demo"
    pid = target["project_id"]
    r2 = demo_session.get(f"{BASE_URL}/api/projects/{pid}", timeout=15)
    assert r2.status_code == 200
    original = r2.json()
    yield {"project_id": pid, "original": original}
    # Teardown: restore original state (title+state)
    try:
        demo_session.post(
            f"{BASE_URL}/api/projects",
            json={"project_id": pid, "title": original.get("title") or PROJECT_TITLE_MATCH,
                  "state": original.get("state") or {}},
            timeout=20,
        )
    except Exception:
        pass


# ---------------- BACKUPS ----------------

def test_backup_created_on_clip_loss(demo_session, demo_project):
    pid = demo_project["project_id"]
    original_state = copy.deepcopy(demo_project["original"].get("state") or {})
    original_refs = [c for c in (original_state.get("clipRefs") or []) if c.get("mediaId") or c.get("pexelsUrl")]
    assert len(original_refs) >= 1, "Fixture requires clipRefs with mediaId in original state"

    # Save an empty clipRefs state (perte-de-clips)
    lossy_state = copy.deepcopy(original_state)
    lossy_state["clipRefs"] = []
    r = demo_session.post(
        f"{BASE_URL}/api/projects",
        json={"project_id": pid, "title": demo_project["original"].get("title"), "state": lossy_state},
        timeout=20,
    )
    assert r.status_code == 200, r.text

    # Check backup created with reason 'perte-de-clips'
    rb = demo_session.get(f"{BASE_URL}/api/projects/{pid}/backups", timeout=15)
    assert rb.status_code == 200
    backups = rb.json().get("backups") or []
    assert len(backups) >= 1
    latest = backups[0]
    assert latest.get("reason") == "perte-de-clips", f"expected perte-de-clips, got {latest.get('reason')}"
    assert latest["clips"] >= 1, "backup should contain the ORIGINAL clip count (before loss)"

    # Verify current state was persisted with empty clipRefs
    rg = demo_session.get(f"{BASE_URL}/api/projects/{pid}", timeout=15)
    assert rg.status_code == 200
    assert (rg.json().get("state") or {}).get("clipRefs") == []


def test_restore_backup_brings_back_clips(demo_session, demo_project):
    pid = demo_project["project_id"]
    original_state = demo_project["original"].get("state") or {}
    original_refs_count = len([c for c in (original_state.get("clipRefs") or []) if c.get("mediaId") or c.get("pexelsUrl")])

    rb = demo_session.get(f"{BASE_URL}/api/projects/{pid}/backups", timeout=15)
    backups = rb.json().get("backups") or []
    # Find the 'perte-de-clips' backup that has clips count > 0 (i.e. the pre-loss snapshot)
    target = None
    for b in backups:
        if b.get("reason") == "perte-de-clips" and (b.get("clips") or 0) >= 1:
            target = b
            break
    assert target, f"No perte-de-clips backup with clips>=1 in {backups}"

    rr = demo_session.post(
        f"{BASE_URL}/api/projects/{pid}/backups/{target['backup_id']}/restore",
        timeout=20,
    )
    assert rr.status_code == 200
    assert rr.json().get("restored") is True

    # Verify clipRefs restored
    rg = demo_session.get(f"{BASE_URL}/api/projects/{pid}", timeout=15)
    assert rg.status_code == 200
    st = rg.json().get("state") or {}
    restored_refs = [c for c in (st.get("clipRefs") or []) if c.get("mediaId") or c.get("pexelsUrl")]
    assert len(restored_refs) == original_refs_count, \
        f"expected {original_refs_count} clipRefs after restore, got {len(restored_refs)}"


def test_backup_throttle_within_10_minutes(demo_session, demo_project):
    """Deux saves SANS perte de clips en <10 min → au max 1 backup 'auto' supplémentaire."""
    pid = demo_project["project_id"]
    # Current state (after prior restore) has clips
    rg = demo_session.get(f"{BASE_URL}/api/projects/{pid}", timeout=15)
    state = rg.json().get("state") or {}
    title = demo_project["original"].get("title") or PROJECT_TITLE_MATCH

    rb0 = demo_session.get(f"{BASE_URL}/api/projects/{pid}/backups", timeout=15)
    b0 = rb0.json().get("backups") or []
    count_before = len(b0)

    # 1st save (no clip loss)
    r1 = demo_session.post(
        f"{BASE_URL}/api/projects",
        json={"project_id": pid, "title": title, "state": state}, timeout=20)
    assert r1.status_code == 200
    time.sleep(1.0)
    # 2nd save (no clip loss) — should NOT create another backup (throttle window ~10 min)
    r2 = demo_session.post(
        f"{BASE_URL}/api/projects",
        json={"project_id": pid, "title": title, "state": state}, timeout=20)
    assert r2.status_code == 200

    rb1 = demo_session.get(f"{BASE_URL}/api/projects/{pid}/backups", timeout=15)
    b1 = rb1.json().get("backups") or []
    delta = len(b1) - count_before
    # Depending on whether the last backup >10 min ago, 0 or 1 backup created is OK; NEVER 2.
    assert delta <= 1, f"Throttle broken: {delta} backups created for 2 saves without clip loss"


# ---------------- MEDIA /mine ----------------

def test_media_mine_returns_list(demo_session):
    r = demo_session.get(f"{BASE_URL}/api/media/mine", timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert "media" in data
    media = data["media"]
    assert isinstance(media, list)
    # demo should have at least one media (fixture has GridFS audio)
    assert len(media) >= 1, "expected at least 1 media for demo"
    m0 = media[0]
    for k in ["media_id", "filename", "size", "content_type"]:
        assert k in m0, f"missing key {k} in media item"
    assert "transcoded" in m0


def test_media_mine_scoping_between_users(demo_session, other_session):
    demo_ids = {m["media_id"] for m in demo_session.get(
        f"{BASE_URL}/api/media/mine", timeout=20).json().get("media", [])}
    other_ids = {m["media_id"] for m in other_session.get(
        f"{BASE_URL}/api/media/mine", timeout=20).json().get("media", [])}
    # Sets must be disjoint (each user only sees their own media)
    assert demo_ids.isdisjoint(other_ids), "media leaked between users!"


# ---------------- SECURITY ----------------

def test_backups_endpoint_requires_auth(demo_project):
    # No cookies
    r = requests.get(f"{BASE_URL}/api/projects/{demo_project['project_id']}/backups", timeout=15)
    assert r.status_code == 401, f"expected 401, got {r.status_code}"


def test_restore_unknown_backup_id_returns_404(demo_session, demo_project):
    fake = uuid.uuid4().hex[:10]
    r = demo_session.post(
        f"{BASE_URL}/api/projects/{demo_project['project_id']}/backups/{fake}/restore",
        timeout=15)
    assert r.status_code == 404
