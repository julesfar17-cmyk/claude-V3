"""Iteration 10 — Backend regression test after WebCodecs frontend engine swap.
Only checks that backend endpoints listed in review request still respond 200 for demo user."""
import os
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

from creds import DEMO_EMAIL, DEMO_PASSWORD as DEMO_PWD


def _session_with_login():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PWD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert data.get("email") == DEMO_EMAIL, f"unexpected login body: {data}"
    return s, data


def test_auth_login():
    s, data = _session_with_login()
    assert data.get("email") == DEMO_EMAIL


def test_auth_me():
    s, _ = _session_with_login()
    r = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 200, f"/auth/me returned {r.status_code} {r.text[:200]}"
    body = r.json()
    assert body.get("email") == DEMO_EMAIL


def test_projects_list():
    s, _ = _session_with_login()
    r = s.get(f"{BASE_URL}/api/projects", timeout=15)
    assert r.status_code == 200, f"/projects returned {r.status_code} {r.text[:200]}"
    projects = r.json()
    if isinstance(projects, dict):
        projects = projects.get("projects", [])
    assert isinstance(projects, list)
    # Should contain 'Morceau Série Test' fixture
    titles = [p.get("title") or p.get("name") for p in projects]
    assert any("Morceau Série Test" in (t or "") for t in titles), f"fixture project missing: {titles}"


def test_media_mine():
    s, _ = _session_with_login()
    r = s.get(f"{BASE_URL}/api/media/mine", timeout=15)
    assert r.status_code == 200, f"/media/mine returned {r.status_code} {r.text[:200]}"
    body = r.json()
    assert isinstance(body, (list, dict))


def test_subscription():
    s, _ = _session_with_login()
    r = s.get(f"{BASE_URL}/api/subscription", timeout=15)
    assert r.status_code == 200, f"/subscription returned {r.status_code} {r.text[:200]}"
    body = r.json()
    # basic plan expected
    assert isinstance(body, dict)
