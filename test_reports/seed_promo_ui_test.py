import json
import os
import uuid
import requests

ROOT = os.environ.get("FRONTEND_URL", "https://pro-mailer-2.preview.emergentagent.com").rstrip("/")
API = f"{ROOT}/api"
ADMIN_EMAIL = "julesfar17@gmail.com"
ADMIN_PASSWORD = "Carnageproduction1704*"
USER_PASSWORD = "Testing1234!"

code = f"QAPUI{uuid.uuid4().hex[:6].upper()}"
email = f"qa_promo_ui_{uuid.uuid4().hex[:8]}@test.local"

admin = requests.Session()
r = admin.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
r.raise_for_status()

payload = {"code": code, "kind": "percent", "percent_off": 10, "plans": ["basic", "monthly", "yearly"], "commission_pct": 0}
r = admin.post(f"{API}/admin/affiliate", json=payload, timeout=60)
r.raise_for_status()

user = requests.Session()
r = user.post(f"{API}/auth/register", json={"name": "QA Promo UI", "email": email, "password": USER_PASSWORD}, timeout=30)
r.raise_for_status()

out = {"root": ROOT, "api": API, "code": code, "email": email, "password": USER_PASSWORD}
with open("/app/test_reports/promo_ui_seed.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False))