"""Iter15 — POST /api/telemetry/webview + GET /api/admin/telemetry/webview + auth regressions."""
import os
import requests
from creds import DEMO_EMAIL, DEMO_PASSWORD, ADMIN_EMAIL, ADMIN_PASSWORD

BASE = os.environ.get("REACT_APP_BACKEND_URL") or "https://pro-mailer-2.preview.emergentagent.com"
BASE = BASE.rstrip("/")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


def test_telemetry_webview_no_auth_ok():
    r = requests.post(f"{BASE}/api/telemetry/webview", json={"ua": "test-webview-ua-iter15", "build": "iter15"}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True


def test_telemetry_webview_empty_body_ok():
    r = requests.post(f"{BASE}/api/telemetry/webview", json={}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_telemetry_webview_admin_ok():
    s = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    r = s.get(f"{BASE}/api/admin/telemetry/webview", timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "total" in d and "samples" in d
    assert isinstance(d["total"], int) and d["total"] >= 1
    assert isinstance(d["samples"], list)
    uas = [s.get("ua", "") for s in d["samples"]]
    # au moins l'entrée envoyée à ce run OU l'entrée test-webview-ua précédente
    assert any("test-webview-ua" in ua for ua in uas), f"expected test-webview-ua sample among {uas[:5]}"


def test_admin_telemetry_webview_non_admin_403():
    s = _login(DEMO_EMAIL, DEMO_PASSWORD)
    r = s.get(f"{BASE}/api/admin/telemetry/webview", timeout=15)
    assert r.status_code == 403, f"expected 403 got {r.status_code}"


def test_admin_telemetry_webview_no_auth_401():
    r = requests.get(f"{BASE}/api/admin/telemetry/webview", timeout=15)
    assert r.status_code in (401, 403), r.status_code


# ── Régression auth / pages ──
def test_login_demo_and_me():
    s = _login(DEMO_EMAIL, DEMO_PASSWORD)
    r = s.get(f"{BASE}/api/auth/me", timeout=15)
    assert r.status_code == 200
    assert r.json().get("email") == DEMO_EMAIL


def test_subscription_demo_basic():
    s = _login(DEMO_EMAIL, DEMO_PASSWORD)
    r = s.get(f"{BASE}/api/subscription", timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    # demo doit être BASIC actif
    plan = (d.get("plan") or d.get("tier") or "").lower()
    assert "basic" in plan or plan == "basic", f"expected basic plan, got: {d}"


def test_projects_list_demo():
    s = _login(DEMO_EMAIL, DEMO_PASSWORD)
    r = s.get(f"{BASE}/api/projects", timeout=15)
    assert r.status_code == 200
    d = r.json()
    projects = d.get("projects") if isinstance(d, dict) else d
    assert isinstance(projects, list)
    ids = [p.get("project_id") or p.get("id") for p in projects]
    assert "d51b835aa74548" in ids, f"expected fixture project, got: {ids[:5]}"
