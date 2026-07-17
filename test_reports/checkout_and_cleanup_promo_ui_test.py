import json
import os
import requests

ROOT = os.environ.get("FRONTEND_URL", "https://pro-mailer-2.preview.emergentagent.com").rstrip("/")
API = f"{ROOT}/api"
ADMIN_EMAIL = "julesfar17@gmail.com"
ADMIN_PASSWORD = "Carnageproduction1704*"

with open("/app/test_reports/promo_ui_seed.json", encoding="utf-8") as f:
    seed = json.load(f)

code = seed["code"]
email = seed["email"]
password = seed["password"]

out = {"code": code, "email": email, "steps": []}

def rec(name, status, body, ok):
    item = {"name": name, "status": status, "ok": ok}
    if isinstance(body, dict):
        item["body_summary"] = {k: body.get(k) for k in ("session_id", "url", "detail", "ok") if k in body}
        if item["body_summary"].get("url"):
            item["body_summary"]["url"] = item["body_summary"]["url"][:120]
    else:
        item["body_summary"] = str(body)[:250]
    out["steps"].append(item)
    print(json.dumps(item, ensure_ascii=False))

user = requests.Session()
r = user.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
try: body = r.json()
except Exception: body = r.text
rec("user login", r.status_code, body, r.status_code == 200)

r = user.post(f"{API}/payments/checkout", json={"origin_url": ROOT, "plan": "monthly", "promo_code": code}, timeout=60)
try: body = r.json()
except Exception: body = r.text
checkout_url = body.get("url") if isinstance(body, dict) else None
session_id = body.get("session_id") if isinstance(body, dict) else None
rec("checkout with promo_code returns Stripe LIVE checkout URL (not opened)", r.status_code, body, r.status_code == 200 and isinstance(checkout_url, str) and "checkout.stripe.com" in checkout_url and "cs_live" in checkout_url and isinstance(session_id, str) and session_id.startswith("cs_live"))

admin = requests.Session()
r = admin.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
try: body = r.json()
except Exception: body = r.text
rec("admin login for cleanup", r.status_code, body, r.status_code == 200)

r = admin.delete(f"{API}/admin/affiliate/{code}", timeout=60)
try: body = r.json()
except Exception: body = r.text
rec("cleanup temporary affiliate code", r.status_code, body, r.status_code in (200, 404))

out["all_passed"] = all(s["ok"] for s in out["steps"])
with open("/app/test_reports/checkout_cleanup_promo_ui_results.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
if not out["all_passed"]:
    raise SystemExit(1)