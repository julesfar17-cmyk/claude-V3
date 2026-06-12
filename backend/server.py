from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import bcrypt
import jwt
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="BEATCUT API")
api_router = APIRouter(prefix="/api")

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_DAYS = 7

PRO_PRICE = 9.99          # défini côté serveur uniquement — jamais depuis le front
PRO_CURRENCY = "eur"
SUBSCRIPTION_DAYS = 30

EMERGENT_SESSION_DATA_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("beatcut")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def parse_dt(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


# ---------------------------------------------------------------------------
# Passwords / tokens
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": now_utc() + timedelta(days=ACCESS_TOKEN_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def set_jwt_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="lax", max_age=ACCESS_TOKEN_DAYS * 86400, path="/",
    )


def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key="session_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=7 * 86400, path="/",
    )


# ---------------------------------------------------------------------------
# Subscription helpers
# ---------------------------------------------------------------------------
def sub_info(user: dict) -> dict:
    sub = user.get("subscription") or {}
    status = sub.get("status")
    end = parse_dt(sub.get("current_period_end"))
    active = status in ("active", "canceled") and end is not None and end > now_utc()
    return {
        "is_pro": bool(active),
        "status": status if active else None,
        "current_period_end": end.isoformat() if (active and end) else None,
        "cancel_at_period_end": (status == "canceled") if active else False,
    }


def public_user(user: dict) -> dict:
    info = sub_info(user)
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "picture": user.get("picture"),
        "auth_provider": user.get("auth_provider", "password"),
        "is_pro": info["is_pro"],
        "subscription": info,
    }


async def activate_subscription(user_id: str):
    end = now_utc() + timedelta(days=SUBSCRIPTION_DAYS)
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"subscription": {
            "status": "active",
            "started_at": iso(now_utc()),
            "current_period_end": iso(end),
        }}},
    )
    logger.info("Subscription PRO activated for %s until %s", user_id, end)


# ---------------------------------------------------------------------------
# Auth dependency (JWT cookie OR Emergent session token, header fallback)
# ---------------------------------------------------------------------------
async def _user_from_jwt(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
    except jwt.PyJWTError:
        return None


async def _user_from_session(token: str):
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        return None
    expires_at = parse_dt(sess.get("expires_at"))
    if expires_at is None or expires_at < now_utc():
        return None
    return await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})


async def get_current_user(request: Request) -> dict:
    jwt_token = request.cookies.get("access_token")
    if jwt_token:
        user = await _user_from_jwt(jwt_token)
        if user:
            return user
    session_token = request.cookies.get("session_token")
    if session_token:
        user = await _user_from_session(session_token)
        if user:
            return user
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        bearer = auth_header[7:]
        user = await _user_from_jwt(bearer) or await _user_from_session(bearer)
        if user:
            return user
    raise HTTPException(status_code=401, detail="Non authentifié")


# ---------------------------------------------------------------------------
# Brute force protection
# ---------------------------------------------------------------------------
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


async def check_lockout(identifier: str):
    cutoff = iso(now_utc() - timedelta(minutes=LOCKOUT_MINUTES))
    count = await db.login_attempts.count_documents({"identifier": identifier, "at": {"$gt": cutoff}})
    if count >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Trop de tentatives. Réessaie dans 15 minutes.")


async def record_failed_attempt(identifier: str):
    await db.login_attempts.insert_one({"identifier": identifier, "at": iso(now_utc())})


async def clear_attempts(identifier: str):
    await db.login_attempts.delete_many({"identifier": identifier})


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: str
    password: str


class GoogleSessionIn(BaseModel):
    session_id: str


class CheckoutIn(BaseModel):
    origin_url: str


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@api_router.post("/auth/register")
async def register(data: RegisterIn, response: Response):
    email = data.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Un compte existe déjà avec cet email")
    user = {
        "user_id": f"user_{uuid.uuid4().hex[:12]}",
        "email": email,
        "name": data.name.strip(),
        "password_hash": hash_password(data.password),
        "auth_provider": "password",
        "role": "user",
        "subscription": None,
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(user)
    set_jwt_cookie(response, create_access_token(user["user_id"], email))
    return public_user(user)


@api_router.post("/auth/login")
async def login(data: LoginIn, request: Request, response: Response):
    email = data.email.strip().lower()
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    identifier = f"{ip}:{email}"
    await check_lockout(identifier)
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_password(data.password, user["password_hash"]):
        await record_failed_attempt(identifier)
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    await clear_attempts(identifier)
    set_jwt_cookie(response, create_access_token(user["user_id"], email))
    return public_user(user)


@api_router.post("/auth/google/session")
async def google_session(data: GoogleSessionIn, response: Response):
    # Échange le session_id (fragment d'URL) contre les données utilisateur — appel serveur uniquement
    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.get(EMERGENT_SESSION_DATA_URL, headers={"X-Session-ID": data.session_id})
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Session Google invalide ou expirée")
    info = r.json()
    email = info["email"].strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user = {
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": email,
            "name": info.get("name") or email.split("@")[0],
            "picture": info.get("picture"),
            "auth_provider": "google",
            "role": "user",
            "subscription": None,
            "created_at": iso(now_utc()),
        }
        await db.users.insert_one({**user})
    else:
        updates = {}
        if info.get("picture") and not user.get("picture"):
            updates["picture"] = info["picture"]
        if updates:
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
            user.update(updates)
    session_token = info["session_token"]
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": iso(now_utc() + timedelta(days=7)),
        "created_at": iso(now_utc()),
    })
    set_session_cookie(response, session_token)
    return public_user(user)


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("session_token", path="/")
    return {"message": "Déconnecté"}


# ---------------------------------------------------------------------------
# Stripe payments — abonnement PRO
# ---------------------------------------------------------------------------
def _stripe(request: Request) -> StripeCheckout:
    host_url = str(request.base_url).rstrip("/")
    return StripeCheckout(api_key=os.environ['STRIPE_API_KEY'], webhook_url=f"{host_url}/api/webhook/stripe")


async def _claim_and_activate(session_id: str):
    """Idempotent : active l'abonnement une seule fois par session payée."""
    res = await db.payment_transactions.update_one(
        {"session_id": session_id, "processed": {"$ne": True}},
        {"$set": {"processed": True, "payment_status": "paid", "status": "complete", "updated_at": iso(now_utc())}},
    )
    if res.modified_count:
        tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if tx and tx.get("user_id"):
            await activate_subscription(tx["user_id"])


@api_router.post("/payments/checkout")
async def create_checkout(data: CheckoutIn, request: Request, user: dict = Depends(get_current_user)):
    origin = data.origin_url.rstrip("/")
    success_url = f"{origin}/dashboard?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/dashboard"
    stripe = _stripe(request)
    checkout_req = CheckoutSessionRequest(
        amount=PRO_PRICE,
        currency=PRO_CURRENCY,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user["user_id"], "email": user["email"], "product": "beatcut_pro_monthly"},
    )
    session = await stripe.create_checkout_session(checkout_req)
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "user_id": user["user_id"],
        "email": user["email"],
        "amount": PRO_PRICE,
        "currency": PRO_CURRENCY,
        "product": "beatcut_pro_monthly",
        "status": "open",
        "payment_status": "initiated",
        "processed": False,
        "created_at": iso(now_utc()),
    })
    return {"url": session.url, "session_id": session.session_id}


@api_router.get("/payments/status/{session_id}")
async def payment_status(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction introuvable")
    stripe = _stripe(request)
    checkout = await stripe.get_checkout_status(session_id)
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {"status": checkout.status, "payment_status": checkout.payment_status, "updated_at": iso(now_utc())}},
    )
    if checkout.payment_status == "paid":
        await _claim_and_activate(session_id)
    return {"status": checkout.status, "payment_status": checkout.payment_status}


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    stripe = _stripe(request)
    try:
        event = await stripe.handle_webhook(body, request.headers.get("Stripe-Signature"))
    except Exception as e:
        logger.warning("Webhook Stripe invalide: %s", e)
        raise HTTPException(status_code=400, detail="Webhook invalide")
    if event.payment_status == "paid" and event.session_id:
        await _claim_and_activate(event.session_id)
    return {"received": True}


# ---------------------------------------------------------------------------
# Subscription management — se désabonner / état
# ---------------------------------------------------------------------------
@api_router.get("/subscription")
async def get_subscription(user: dict = Depends(get_current_user)):
    return sub_info(user)


@api_router.post("/subscription/cancel")
async def cancel_subscription(user: dict = Depends(get_current_user)):
    info = sub_info(user)
    if not info["is_pro"]:
        raise HTTPException(status_code=400, detail="Aucun abonnement actif à annuler")
    if info["cancel_at_period_end"]:
        raise HTTPException(status_code=400, detail="Ton abonnement est déjà annulé")
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"subscription.status": "canceled", "subscription.canceled_at": iso(now_utc())}},
    )
    return {
        "message": "Abonnement annulé. Tu gardes l'accès PRO jusqu'à la fin de la période en cours.",
        "current_period_end": info["current_period_end"],
    }


@api_router.get("/")
async def root():
    return {"message": "BEATCUT API", "status": "ok"}


# ---------------------------------------------------------------------------
# Startup : indexes + seed admin & demo
# ---------------------------------------------------------------------------
async def seed_user(email: str, password: str, name: str, role: str):
    existing = await db.users.find_one({"email": email})
    if existing is None:
        await db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": email,
            "name": name,
            "password_hash": hash_password(password),
            "auth_provider": "password",
            "role": role,
            "subscription": None,
            "created_at": iso(now_utc()),
        })
        logger.info("Seeded %s account: %s", role, email)
    elif not verify_password(password, existing.get("password_hash") or ""):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})
        logger.info("Updated password for %s", email)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id")
    await db.user_sessions.create_index("session_token")
    await db.login_attempts.create_index("identifier")
    await db.payment_transactions.create_index("session_id")
    await seed_user(os.environ['ADMIN_EMAIL'], os.environ['ADMIN_PASSWORD'], "Admin", "admin")
    await seed_user("demo@beatcut.fr", "Demo1234!", "Démo", "user")


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
