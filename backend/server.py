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
import asyncio
import secrets
import stripe
import resend
from fastapi import UploadFile, File, Form

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

PRO_PRICE = 12.99           # 12,99 € — défini côté serveur uniquement, jamais depuis le front
PRO_PRICE_CENTS = 1299
PRO_PRICE_YEAR = 99.00
PRO_PRICE_YEAR_CENTS = 9900
PRO_CURRENCY = "eur"
SUBSCRIPTION_DAYS = 30      # filet de sécurité si Stripe est injoignable
SUBSCRIPTION_DAYS_YEAR = 365
REFERRAL_BONUS_DAYS = 30    # +1 mois offert pour le parrain ET le parrainé après 1er paiement

stripe.api_key = os.environ['STRIPE_API_KEY']

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
PEXELS_API_KEY = os.environ.get('PEXELS_API_KEY', '')
REPLICATE_API_TOKEN = os.environ.get('REPLICATE_API_TOKEN', '')
if REPLICATE_API_TOKEN:
    os.environ['REPLICATE_API_TOKEN'] = REPLICATE_API_TOKEN
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

PRO_WHITELIST = {
    e.strip().lower()
    for e in os.environ.get('PRO_WHITELIST', '').split(',')
    if e.strip()
}

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
# Emails (Resend si clé configurée, sinon mode simulé : log serveur)
# ---------------------------------------------------------------------------
def _fmt_date_fr(iso_str) -> str:
    try:
        return parse_dt(iso_str).strftime("%d/%m/%Y")
    except Exception:
        return ""


def _email_html(title: str, body: str, cta_label: str = None, cta_url: str = None) -> str:
    button = (
        f'<tr><td style="padding:24px 0 8px"><a href="{cta_url}" '
        f'style="background:#ff3b30;color:#ffffff;text-decoration:none;font-weight:bold;'
        f'padding:14px 28px;display:inline-block">{cta_label}</a></td></tr>'
    ) if cta_url else ""
    return f"""<table width="100%" cellpadding="0" cellspacing="0" style="background:#121016;padding:32px 16px;font-family:Arial,Helvetica,sans-serif">
<tr><td align="center"><table width="520" cellpadding="0" cellspacing="0" style="background:#1a1720;border:1px solid #2a2631;padding:36px">
<tr><td style="font-size:20px;font-weight:bold;color:#ece6da;padding-bottom:6px">BEAT<span style="color:#ff3b30">CUT</span></td></tr>
<tr><td style="font-size:17px;font-weight:bold;color:#ece6da;padding:18px 0 8px">{title}</td></tr>
<tr><td style="font-size:14px;color:#9a93a6;line-height:1.6">{body}</td></tr>
{button}
<tr><td style="font-size:11px;color:#6b6478;padding-top:28px">BEATCUT — studio beat-sync. 12,99 €/mois, sans engagement.</td></tr>
</table></td></tr></table>"""


async def send_email(to: str, subject: str, html: str) -> bool:
    """Retourne True si réellement envoyé, False en mode simulé ou en cas d'échec."""
    if not RESEND_API_KEY:
        logger.info("[EMAIL simulé] to=%s | subject=%s", to, subject)
        return False
    try:
        params = {"from": SENDER_EMAIL, "to": [to], "subject": subject, "html": html}
        await asyncio.to_thread(resend.Emails.send, params)
        return True
    except Exception as e:
        logger.error("Envoi email échoué (%s): %s", to, e)
        return False


def reset_email_html(link: str) -> str:
    return _email_html(
        "Réinitialise ton mot de passe",
        "Tu as demandé à réinitialiser ton mot de passe BEATCUT. Clique sur le bouton ci-dessous — le lien est valable 1 heure. Si tu n'es pas à l'origine de cette demande, ignore cet email.",
        "Réinitialiser mon mot de passe", link,
    )


def sub_confirmed_email_html(period_end) -> str:
    return _email_html(
        "Bienvenue en PRO ✦",
        f"Ton abonnement BEATCUT PRO est actif : export vidéo sans watermark, sous-titres .srt et "
        f"extraction d'acapella (GPU) débloqués. Renouvellement automatique le {_fmt_date_fr(period_end)} "
        f"(12,99 €/mois). Tu peux te désabonner à tout moment en 1 clic depuis ton compte.",
    )


def sub_canceled_email_html(period_end) -> str:
    return _email_html(
        "Abonnement annulé",
        f"Ton abonnement BEATCUT PRO a bien été annulé — aucun prélèvement futur. "
        f"Tu gardes l'accès PRO jusqu'au {_fmt_date_fr(period_end)}, puis ton compte repassera en gratuit. "
        f"Tu peux te réabonner quand tu veux depuis ton compte.",
    )


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
    # Comptes en liste blanche : PRO permanent, hors Stripe
    if (user.get("email") or "").lower() in PRO_WHITELIST:
        return {
            "is_pro": True,
            "status": "vip",
            "current_period_end": None,
            "cancel_at_period_end": False,
        }
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
        "role": user.get("role", "user"),
        "is_pro": info["is_pro"],
        "subscription": info,
        "ref_code": user.get("ref_code", ""),
    }


def _extract_period_end(sub_obj) -> datetime:
    """Stripe a déplacé current_period_end sur les items dans les versions récentes de l'API."""
    try:
        items = (sub_obj.get("items") or {}).get("data") or []
        ts = (items[0].get("current_period_end") if items else None) or sub_obj.get("current_period_end")
        if ts:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        pass
    return now_utc() + timedelta(days=SUBSCRIPTION_DAYS)


async def activate_subscription(user_id: str, customer_id: str = None, subscription_id: str = None, plan: str = "monthly"):
    days = SUBSCRIPTION_DAYS_YEAR if plan == "yearly" else SUBSCRIPTION_DAYS
    sub_doc = {
        "status": "active",
        "plan": plan,
        "started_at": iso(now_utc()),
        "current_period_end": iso(now_utc() + timedelta(days=days)),
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "synced_at": iso(now_utc()),
    }
    if subscription_id:
        try:
            s = await asyncio.to_thread(stripe.Subscription.retrieve, subscription_id)
            sub_doc["current_period_end"] = iso(_extract_period_end(s))
            if not customer_id:
                sub_doc["stripe_customer_id"] = s.get("customer")
        except Exception as e:
            logger.warning("Stripe subscription retrieve failed: %s", e)
    await db.users.update_one({"user_id": user_id}, {"$set": {"subscription": sub_doc}})
    await _apply_referral_bonus(user_id)
    logger.info("Subscription PRO activated for %s (plan=%s stripe sub: %s)", user_id, plan, subscription_id)


async def _apply_referral_bonus(referee_id: str):
    """Crédit +1 mois au parrain ET au parrainé lors du 1er paiement validé."""
    referee = await db.users.find_one({"user_id": referee_id}, {"_id": 0})
    if not referee:
        return
    ref_code = referee.get("referred_by")
    if not ref_code or referee.get("referral_credited"):
        return
    referrer = await db.users.find_one({"ref_code": ref_code}, {"_id": 0})
    if not referrer or referrer["user_id"] == referee_id:
        return
    # Bonus pour le parrain (+30j sur sa fin de période)
    rsub = referrer.get("subscription") or {}
    end_curr = parse_dt(rsub.get("current_period_end")) or now_utc()
    if end_curr < now_utc():
        end_curr = now_utc()
    new_end = end_curr + timedelta(days=REFERRAL_BONUS_DAYS)
    await db.users.update_one(
        {"user_id": referrer["user_id"]},
        {"$set": {
            "subscription.bonus_until": iso(new_end),
            "subscription.referral_count": (rsub.get("referral_count") or 0) + 1,
        }},
    )
    # Bonus pour le parrainé (+30j sur sa fin de période)
    sub = referee.get("subscription") or {}
    end_referee = parse_dt(sub.get("current_period_end")) or now_utc()
    new_end_referee = end_referee + timedelta(days=REFERRAL_BONUS_DAYS)
    await db.users.update_one(
        {"user_id": referee_id},
        {"$set": {
            "subscription.current_period_end": iso(new_end_referee),
            "referral_credited": True,
        }},
    )
    logger.info("Bonus parrainage : +30j à %s et %s", referrer["email"], referee["email"])


async def sync_stripe_subscription(user: dict) -> dict:
    """Synchronise l'abonnement avec Stripe : renouvellement auto, annulation, expiration."""
    if (user.get("email") or "").lower() in PRO_WHITELIST:
        return user        # comptes VIP : pas de Stripe à synchroniser
    sub = user.get("subscription") or {}
    sub_id = sub.get("stripe_subscription_id")
    if not sub_id:
        return user
    end = parse_dt(sub.get("current_period_end"))
    synced = parse_dt(sub.get("synced_at"))
    fresh = synced is not None and (now_utc() - synced) < timedelta(hours=12)
    if end is not None and end > now_utc() and fresh:
        return user
    try:
        s = await asyncio.to_thread(stripe.Subscription.retrieve, sub_id)
    except Exception as e:
        logger.warning("Stripe sync failed for %s: %s", sub_id, e)
        return user
    if s.get("status") in ("active", "trialing"):
        status = "canceled" if s.get("cancel_at_period_end") else "active"
    else:
        status = "expired"
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "subscription.status": status,
            "subscription.current_period_end": iso(_extract_period_end(s)),
            "subscription.synced_at": iso(now_utc()),
        }},
    )
    return await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})


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
    ref_code: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class GoogleSessionIn(BaseModel):
    session_id: str
    ref_code: str | None = None


class CheckoutIn(BaseModel):
    origin_url: str
    plan: str = "monthly"   # "monthly" ou "yearly"


class ForgotPasswordIn(BaseModel):
    email: str
    origin_url: str


class ResetPasswordIn(BaseModel):
    token: str
    password: str = Field(min_length=6, max_length=128)


class PexelsSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=120)
    orientation: str = "portrait"


class PromoApplyIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    style: dict


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
    referred_by = None
    if data.ref_code:
        rc = data.ref_code.strip().upper()
        sponsor = await db.users.find_one({"ref_code": rc}, {"_id": 0})
        if sponsor and sponsor["email"] != email:
            referred_by = rc
    user = {
        "user_id": f"user_{uuid.uuid4().hex[:12]}",
        "email": email,
        "name": data.name.strip(),
        "password_hash": hash_password(data.password),
        "auth_provider": "password",
        "role": "user",
        "subscription": None,
        "ref_code": f"REF{uuid.uuid4().hex[:6].upper()}",
        "referred_by": referred_by,
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
            "ref_code": f"REF{uuid.uuid4().hex[:6].upper()}",
            "referred_by": (data.ref_code or "").strip().upper() or None,
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
    user = await sync_stripe_subscription(user)
    return public_user(user)


@api_router.post("/auth/forgot-password")
async def forgot_password(data: ForgotPasswordIn):
    email = data.email.strip().lower()
    generic = {"message": "Si un compte existe avec cet email, un lien de réinitialisation a été envoyé."}
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash"):
        return generic
    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token": token,
        "user_id": user["user_id"],
        "expires_at": iso(now_utc() + timedelta(hours=1)),
        "used": False,
        "created_at": iso(now_utc()),
    })
    reset_link = f"{data.origin_url.rstrip('/')}/reset-password?token={token}"
    sent = await send_email(email, "Réinitialise ton mot de passe — BEATCUT", reset_email_html(reset_link))
    logger.info("Password reset link for %s: %s", email, reset_link)
    if not sent:
        # Mode simulé (pas encore de service email configuré) : le lien est renvoyé pour affichage à l'écran
        return {**generic, "dev_reset_link": reset_link}
    return generic


@api_router.post("/auth/reset-password")
async def reset_password(data: ResetPasswordIn):
    doc = await db.password_reset_tokens.find_one({"token": data.token}, {"_id": 0})
    if not doc or doc.get("used"):
        raise HTTPException(status_code=400, detail="Lien invalide ou déjà utilisé")
    if parse_dt(doc["expires_at"]) < now_utc():
        raise HTTPException(status_code=400, detail="Lien expiré — refais une demande")
    await db.users.update_one({"user_id": doc["user_id"]}, {"$set": {"password_hash": hash_password(data.password)}})
    await db.password_reset_tokens.update_one({"token": data.token}, {"$set": {"used": True}})
    return {"message": "Mot de passe mis à jour — tu peux te connecter."}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("session_token", path="/")
    return {"message": "Déconnecté"}


# ---------------------------------------------------------------------------
# Stripe — abonnement PRO récurrent (renouvellement automatique réel)
# ---------------------------------------------------------------------------
async def _claim_and_activate(session_id: str, customer_id: str = None, subscription_id: str = None):
    """Idempotent : active l'abonnement une seule fois par session payée."""
    res = await db.payment_transactions.update_one(
        {"session_id": session_id, "processed": {"$ne": True}},
        {"$set": {"processed": True, "payment_status": "paid", "status": "complete", "updated_at": iso(now_utc())}},
    )
    if res.modified_count:
        tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if tx and tx.get("user_id"):
            await activate_subscription(tx["user_id"], customer_id, subscription_id, plan=tx.get("plan", "monthly"))
            user = await db.users.find_one({"user_id": tx["user_id"]}, {"_id": 0})
            if user:
                end = (user.get("subscription") or {}).get("current_period_end")
                await send_email(user["email"], "Bienvenue en PRO ✦ BEATCUT", sub_confirmed_email_html(end))


@api_router.post("/payments/checkout")
async def create_checkout(data: CheckoutIn, request: Request, user: dict = Depends(get_current_user)):
    if (user.get("email") or "").lower() in PRO_WHITELIST:
        raise HTTPException(status_code=400, detail="Compte VIP — déjà PRO")
    origin = data.origin_url.rstrip("/")
    success_url = f"{origin}/dashboard?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/dashboard"
    sub = user.get("subscription") or {}
    plan = "yearly" if data.plan == "yearly" else "monthly"
    if plan == "yearly":
        amount_cents = PRO_PRICE_YEAR_CENTS
        interval = "year"
        product_name = "BEATCUT PRO — annuel"
        product_desc = "Export sans watermark + .srt + extraction acapella — 99 €/an (2 mois offerts)"
    else:
        amount_cents = PRO_PRICE_CENTS
        interval = "month"
        product_name = "BEATCUT PRO"
        product_desc = "Export vidéo sans watermark + sous-titres .srt + acapella — sans engagement"
    params = dict(
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": PRO_CURRENCY,
                "unit_amount": amount_cents,
                "recurring": {"interval": interval},
                "product_data": {"name": product_name, "description": product_desc},
            },
            "quantity": 1,
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user["user_id"], "email": user["email"], "product": f"beatcut_pro_{plan}"},
        subscription_data={"metadata": {"user_id": user["user_id"], "plan": plan}},
    )
    if sub.get("stripe_customer_id"):
        params["customer"] = sub["stripe_customer_id"]
    else:
        params["customer_email"] = user["email"]
    try:
        session = await asyncio.to_thread(lambda: stripe.checkout.Session.create(**params))
    except Exception as e:
        logger.error("Stripe checkout error: %s", e)
        raise HTTPException(status_code=502, detail="Erreur Stripe lors de la création du paiement — réessaie") from e
    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "user_id": user["user_id"],
        "email": user["email"],
        "amount": amount_cents / 100.0,
        "currency": PRO_CURRENCY,
        "product": f"beatcut_pro_{plan}",
        "plan": plan,
        "status": "open",
        "payment_status": "initiated",
        "processed": False,
        "created_at": iso(now_utc()),
    })
    return {"url": session.url, "session_id": session.id}


@api_router.get("/payments/status/{session_id}")
async def payment_status(session_id: str, user: dict = Depends(get_current_user)):
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction introuvable")
    if tx.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Transaction liée à un autre compte")
    try:
        session = await asyncio.to_thread(stripe.checkout.Session.retrieve, session_id)
    except Exception as e:
        logger.error("Stripe status error: %s", e)
        raise HTTPException(status_code=502, detail="Impossible de vérifier le paiement") from e
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {"status": session.status, "payment_status": session.payment_status, "updated_at": iso(now_utc())}},
    )
    if session.payment_status == "paid":
        await _claim_and_activate(session_id, session.get("customer"), session.get("subscription"))
    return {"status": session.status, "payment_status": session.payment_status}


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        # Pas de webhook configuré dans le dashboard Stripe : le renouvellement
        # est synchronisé par polling (sync_stripe_subscription) — rien à faire ici.
        return {"received": True}
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("Stripe-Signature", ""), secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Webhook invalide")
    if event["type"] == "checkout.session.completed":
        obj = event["data"]["object"]
        if obj.get("payment_status") == "paid":
            await _claim_and_activate(obj["id"], obj.get("customer"), obj.get("subscription"))
    return {"received": True}


# ---------------------------------------------------------------------------
# Subscription management — se désabonner / état
# ---------------------------------------------------------------------------
@api_router.get("/subscription")
async def get_subscription(user: dict = Depends(get_current_user)):
    user = await sync_stripe_subscription(user)
    return sub_info(user)


@api_router.post("/subscription/cancel")
async def cancel_subscription(user: dict = Depends(get_current_user)):
    if (user.get("email") or "").lower() in PRO_WHITELIST:
        raise HTTPException(status_code=400, detail="Compte VIP — pas d'abonnement à annuler")
    user = await sync_stripe_subscription(user)
    info = sub_info(user)
    sub = user.get("subscription") or {}
    if not info["is_pro"]:
        raise HTTPException(status_code=400, detail="Aucun abonnement actif à annuler")
    if info["cancel_at_period_end"]:
        raise HTTPException(status_code=400, detail="Ton abonnement est déjà annulé")
    if sub.get("stripe_subscription_id"):
        # Annulation RÉELLE côté Stripe : aucun prélèvement futur
        try:
            await asyncio.to_thread(
                lambda: stripe.Subscription.modify(sub["stripe_subscription_id"], cancel_at_period_end=True)
            )
        except Exception as e:
            logger.error("Stripe cancel error: %s", e)
            raise HTTPException(status_code=502, detail="Erreur Stripe lors de l'annulation — réessaie")
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"subscription.status": "canceled", "subscription.canceled_at": iso(now_utc())}},
    )
    await send_email(user["email"], "Abonnement annulé — BEATCUT", sub_canceled_email_html(info["current_period_end"]))
    return {
        "message": "Abonnement annulé — aucun prélèvement futur. Tu gardes l'accès PRO jusqu'à la fin de la période en cours.",
        "current_period_end": info["current_period_end"],
    }


@api_router.post("/subscription/reactivate")
async def reactivate_subscription(user: dict = Depends(get_current_user)):
    user = await sync_stripe_subscription(user)
    info = sub_info(user)
    sub = user.get("subscription") or {}
    if not (info["is_pro"] and info["cancel_at_period_end"] and sub.get("stripe_subscription_id")):
        raise HTTPException(status_code=400, detail="Abonnement non réactivable — souscris à nouveau")
    try:
        await asyncio.to_thread(
            lambda: stripe.Subscription.modify(sub["stripe_subscription_id"], cancel_at_period_end=False)
        )
    except Exception as e:
        logger.error("Stripe reactivate error: %s", e)
        raise HTTPException(status_code=502, detail="Erreur Stripe — réessaie")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"subscription.status": "active"}})
    return {"message": "Abonnement réactivé — le renouvellement automatique reprend."}


# ---------------------------------------------------------------------------
# Proxy clé-en-main pour le studio : les clés Pexels & Groq restent serveur
# ---------------------------------------------------------------------------
@api_router.post("/proxy/pexels")
async def proxy_pexels(data: PexelsSearchIn, user: dict = Depends(get_current_user)):
    if not PEXELS_API_KEY:
        raise HTTPException(status_code=503, detail="Banque de clips indisponible pour le moment")
    orientation = data.orientation if data.orientation in ("portrait", "landscape", "square") else "portrait"
    async with httpx.AsyncClient(timeout=20) as http:
        r = await http.get(
            "https://api.pexels.com/videos/search",
            params={"query": data.query, "per_page": 12, "orientation": orientation},
            headers={"Authorization": PEXELS_API_KEY},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Banque de clips : erreur {r.status_code}")
    return r.json()


@api_router.post("/proxy/transcribe")
async def proxy_transcribe(
    file: UploadFile = File(...),
    language: str = Form(None),
    user: dict = Depends(get_current_user),
):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="Transcription indisponible pour le moment")
    content = await file.read()
    if len(content) > 26_000_000:
        raise HTTPException(status_code=413, detail="Extrait trop long — raccourcis la sélection")
    form = {
        "model": "whisper-large-v3-turbo",
        "response_format": "verbose_json",
        "timestamp_granularities[]": ["word", "segment"],
    }
    if language:
        form["language"] = language
    async with httpx.AsyncClient(timeout=120) as http:
        r = await http.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            data=form,
            files={"file": ("extrait.wav", content, "audio/wav")},
        )
    if r.status_code != 200:
        detail = "Transcription échouée — réessaie"
        try:
            detail = r.json().get("error", {}).get("message", detail)
        except Exception:
            pass
        logger.error("Groq transcribe error %s: %s", r.status_code, detail)
        raise HTTPException(status_code=502, detail=detail)
    return r.json()


# ---------------------------------------------------------------------------
# Séparation voix/instru — GPU à la demande via Replicate (Demucs v4)
# Coût : payé à la seconde GPU (~0,01-0,02 € par séparation) — scale to zero.
# ---------------------------------------------------------------------------
import replicate
from fastapi.responses import FileResponse

SEP_DIR = Path("/tmp/beatcut_sep")
SEP_DIR.mkdir(parents=True, exist_ok=True)
SEP_JOBS: dict = {}  # job_id -> {status, user_id, error, result_path, created_at}

# Demucs v4 (htdemucs) sur Replicate — le standard pour séparer voix/instru
DEMUCS_MODEL = (
    "cjwbw/demucs:25a173108cff36ef9f80f854c162d01df9e6528be175794b81158fa03836d953"
)


def _coerce_url(value) -> str:
    """Replicate renvoie soit une str, soit un FileOutput (avec .url)."""
    if value is None:
        return ""
    if hasattr(value, "url"):
        return value.url
    return str(value)


def _separate_with_replicate(input_path: str) -> str:
    if not REPLICATE_API_TOKEN:
        raise RuntimeError("séparation indisponible — clé Replicate manquante")
    with open(input_path, "rb") as audio:
        output = replicate.run(
            DEMUCS_MODEL,
            input={
                "audio": audio,
                "stem": "vocals",
                # Réglages qualité maximale (style UVR5) :
                "model_name": "htdemucs_ft",  # fine-tuned, bien supérieur à htdemucs
                "shifts": 2,                  # réduit les artefacts (2× plus long mais propre)
                "overlap": 0.5,               # plus de chevauchement = transitions plus douces
                "output_format": "wav",
            },
        )
    vocals_url = ""
    if isinstance(output, dict):
        for key in ("vocals", "vocals_only", "vocals_audio", "audio", "output"):
            if output.get(key):
                vocals_url = _coerce_url(output[key])
                break
        if not vocals_url:
            for v in output.values():
                if v:
                    vocals_url = _coerce_url(v)
                    break
    elif isinstance(output, list) and output:
        vocals_url = _coerce_url(output[0])
    else:
        vocals_url = _coerce_url(output)
    if not vocals_url:
        raise RuntimeError("sortie inattendue du modèle de séparation")
    out_path = str(SEP_DIR / f"{uuid.uuid4().hex}_vocals.wav")
    with httpx.Client(timeout=180, follow_redirects=True) as http:
        r = http.get(vocals_url)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)
    return out_path


async def _run_separation(job_id: str, input_path: str):
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _separate_with_replicate, input_path)
        SEP_JOBS[job_id].update(status="done", result_path=result)
    except Exception as e:
        msg = str(e)
        logger.error("Séparation %s échouée: %s", job_id, msg)
        if "Insufficient credit" in msg or "402" in msg:
            user_msg = "Service de séparation momentanément indisponible — réessaie plus tard."
        else:
            user_msg = "séparation échouée — réessaie"
        SEP_JOBS[job_id].update(status="error", error=user_msg)
    finally:
        try:
            os.remove(input_path)
        except OSError:
            pass
        cutoff = now_utc() - timedelta(hours=1)
        for jid in list(SEP_JOBS.keys()):
            job = SEP_JOBS[jid]
            if parse_dt(job["created_at"]) < cutoff:
                if job.get("result_path"):
                    try:
                        os.remove(job["result_path"])
                    except OSError:
                        pass
                SEP_JOBS.pop(jid, None)


async def require_pro(user: dict) -> dict:
    user = await sync_stripe_subscription(user)
    if not sub_info(user)["is_pro"]:
        raise HTTPException(status_code=403, detail="Fonction réservée aux abonnés PRO")
    return user


@api_router.post("/separate")
async def start_separation(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    user = await require_pro(user)
    content = await file.read()
    if len(content) > 30_000_000:
        raise HTTPException(status_code=413, detail="Extrait trop long — raccourcis la sélection")
    job_id = uuid.uuid4().hex[:16]
    input_path = str(SEP_DIR / f"{job_id}.wav")
    with open(input_path, "wb") as f:
        f.write(content)
    SEP_JOBS[job_id] = {
        "status": "processing", "user_id": user["user_id"],
        "error": None, "result_path": None, "created_at": iso(now_utc()),
    }
    await db.separation_logs.insert_one({
        "user_id": user["user_id"], "job_id": job_id,
        "size": len(content), "created_at": iso(now_utc()),
    })
    asyncio.create_task(_run_separation(job_id, input_path))
    return {"id": job_id, "status": "processing"}


def _get_job(job_id: str, user: dict) -> dict:
    job = SEP_JOBS.get(job_id)
    if not job or job["user_id"] != user["user_id"]:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return job


@api_router.get("/separate/{job_id}")
async def separation_status(job_id: str, user: dict = Depends(get_current_user)):
    job = _get_job(job_id, user)
    return {"id": job_id, "status": job["status"], "error": job["error"]}


@api_router.get("/separate/{job_id}/result")
async def separation_result(job_id: str, user: dict = Depends(get_current_user)):
    job = _get_job(job_id, user)
    if job["status"] != "done" or not job.get("result_path") or not os.path.exists(job["result_path"]):
        raise HTTPException(status_code=404, detail="Résultat indisponible")
    return FileResponse(job["result_path"], media_type="audio/wav", filename="acapella.wav")


# ---------------------------------------------------------------------------
# Codes promo + parrainage + templates + admin
# ---------------------------------------------------------------------------
async def require_admin(user: dict) -> dict:
    if (user.get("role") or "") != "admin":
        raise HTTPException(status_code=403, detail="Réservé à l'administration")
    return user


def _normalize_promo(code: str) -> str:
    return code.strip().upper()


@api_router.get("/promo/me")
async def promo_me(user: dict = Depends(get_current_user)):
    """Code de parrainage de l'utilisateur + stats."""
    rsub = user.get("subscription") or {}
    return {
        "ref_code": user.get("ref_code") or "",
        "referral_count": rsub.get("referral_count") or 0,
        "bonus_until": rsub.get("bonus_until"),
    }


@api_router.post("/promo/apply")
async def promo_apply(data: PromoApplyIn, user: dict = Depends(get_current_user)):
    code = _normalize_promo(data.code)
    promo = await db.promo_codes.find_one({"code": code}, {"_id": 0})
    if not promo:
        raise HTTPException(status_code=404, detail="Code invalide")
    if promo.get("expires_at") and parse_dt(promo["expires_at"]) < now_utc():
        raise HTTPException(status_code=400, detail="Code expiré")
    max_uses = promo.get("max_uses")
    if max_uses and (promo.get("used_count") or 0) >= max_uses:
        raise HTTPException(status_code=400, detail="Code épuisé")
    if user["user_id"] in (promo.get("used_by") or []):
        raise HTTPException(status_code=400, detail="Code déjà utilisé sur ce compte")
    days = int(promo.get("bonus_days") or 30)
    sub = user.get("subscription") or {}
    end = parse_dt(sub.get("current_period_end")) or now_utc()
    if end < now_utc():
        end = now_utc()
    new_end = end + timedelta(days=days)
    new_sub = {
        **sub,
        "status": sub.get("status") or "active",
        "current_period_end": iso(new_end),
        "promo_applied": code,
    }
    if not sub.get("started_at"):
        new_sub["started_at"] = iso(now_utc())
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"subscription": new_sub}},
    )
    await db.promo_codes.update_one(
        {"code": code},
        {"$inc": {"used_count": 1}, "$push": {"used_by": user["user_id"]}},
    )
    return {"message": f"Code appliqué : +{days} jours offerts ✦", "current_period_end": iso(new_end)}


@api_router.get("/templates")
async def list_templates(user: dict = Depends(get_current_user)):
    docs = await db.templates.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return docs


@api_router.post("/templates")
async def save_template(data: TemplateIn, user: dict = Depends(get_current_user)):
    doc = {
        "template_id": uuid.uuid4().hex[:12],
        "user_id": user["user_id"],
        "name": data.name.strip()[:80],
        "style": data.style,
        "created_at": iso(now_utc()),
    }
    await db.templates.insert_one({**doc})
    return doc


@api_router.delete("/templates/{template_id}")
async def delete_template(template_id: str, user: dict = Depends(get_current_user)):
    res = await db.templates.delete_one({"template_id": template_id, "user_id": user["user_id"]})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Template introuvable")
    return {"message": "supprimé"}


@api_router.get("/admin/stats")
async def admin_stats(user: dict = Depends(get_current_user)):
    await require_admin(user)
    total_users = await db.users.count_documents({})
    google_users = await db.users.count_documents({"auth_provider": "google"})
    pwd_users = await db.users.count_documents({"auth_provider": "password"})
    paid_users = await db.users.count_documents({
        "subscription.status": {"$in": ["active", "canceled"]},
        "subscription.current_period_end": {"$gt": iso(now_utc())},
    })
    canceled = await db.users.count_documents({"subscription.status": "canceled"})
    yearly = await db.users.count_documents({"subscription.plan": "yearly"})
    monthly = max(0, paid_users - yearly)
    # MRR : annuels comptés au prorata mensuel
    mrr = round(monthly * PRO_PRICE + yearly * (PRO_PRICE_YEAR / 12), 2)
    # Séparations du mois
    start_month = iso(now_utc().replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    sep_count = await db.separation_logs.count_documents({"created_at": {"$gt": start_month}})
    est_sep_cost = round(sep_count * 0.015, 2)
    last_users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(10).to_list(10)
    promos = await db.promo_codes.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {
        "total_users": total_users,
        "paid_users": paid_users,
        "canceled": canceled,
        "google_users": google_users,
        "password_users": pwd_users,
        "monthly_subscribers": monthly,
        "yearly_subscribers": yearly,
        "mrr": mrr,
        "separations_this_month": sep_count,
        "estimated_separation_cost_eur": est_sep_cost,
        "recent_users": last_users,
        "promo_codes": promos,
    }


@api_router.post("/admin/promo")
async def admin_create_promo(payload: dict, user: dict = Depends(get_current_user)):
    await require_admin(user)
    code = _normalize_promo(payload.get("code") or "")
    if len(code) < 3:
        raise HTTPException(status_code=400, detail="Code trop court (3 min)")
    days = int(payload.get("bonus_days") or 30)
    max_uses = payload.get("max_uses") or None
    if max_uses is not None:
        max_uses = int(max_uses)
    expires_at = None
    if payload.get("expires_at"):
        expires_at = payload["expires_at"]
    existing = await db.promo_codes.find_one({"code": code})
    if existing:
        raise HTTPException(status_code=400, detail="Code déjà existant")
    doc = {
        "code": code, "bonus_days": days, "max_uses": max_uses,
        "expires_at": expires_at, "used_count": 0, "used_by": [],
        "created_at": iso(now_utc()),
    }
    await db.promo_codes.insert_one({**doc})
    return doc


# ---------------------------------------------------------------------------
# Emails de relance automatique pour les comptes gratuits (J+3, J+7)
# ---------------------------------------------------------------------------
def reengage_email_html(days_since: int) -> str:
    title = "Toujours là ?" if days_since >= 7 else "Tu as essayé BEATCUT ?"
    body = (
        "Une vidéo postée sur TikTok cette semaine vaut 100 fois celle du mois prochain. "
        "On t'offre 50 % sur ton premier mois avec le code <b>BIENVENUE50</b> — direct dans ton compte."
    )
    return _email_html(title, body, "Activer mon code", "https://pro-mailer-2.preview.emergentagent.com/dashboard")


async def _reengage_loop():
    """Toutes les 6 h, envoie un email aux comptes gratuits inscrits il y a 3 et 7 jours."""
    while True:
        try:
            for days in (3, 7):
                lo = now_utc() - timedelta(days=days, hours=6)
                hi = now_utc() - timedelta(days=days)
                async for u in db.users.find({
                    "created_at": {"$gt": iso(lo), "$lt": iso(hi)},
                    f"reengage_d{days}_sent": {"$ne": True},
                }, {"_id": 0}):
                    if (u.get("email") or "").lower() in PRO_WHITELIST:
                        continue
                    if (u.get("subscription") or {}).get("status") == "active":
                        continue
                    await send_email(u["email"], "BEATCUT — un coup de pouce ?", reengage_email_html(days))
                    await db.users.update_one({"user_id": u["user_id"]}, {"$set": {f"reengage_d{days}_sent": True}})
        except Exception as e:
            logger.error("Relance loop error: %s", e)
        await asyncio.sleep(6 * 3600)


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
            "ref_code": f"REF{uuid.uuid4().hex[:6].upper()}",
            "created_at": iso(now_utc()),
        })
        logger.info("Seeded %s account: %s", role, email)
    else:
        updates = {"role": role}
        if not verify_password(password, existing.get("password_hash") or ""):
            updates["password_hash"] = hash_password(password)
        if not existing.get("ref_code"):
            updates["ref_code"] = f"REF{uuid.uuid4().hex[:6].upper()}"
        await db.users.update_one({"email": email}, {"$set": updates})
        logger.info("Updated %s account: %s", role, email)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id")
    await db.users.create_index("ref_code")
    await db.user_sessions.create_index("session_token")
    await db.login_attempts.create_index("identifier")
    await db.payment_transactions.create_index("session_id")
    await db.password_reset_tokens.create_index("token")
    await db.promo_codes.create_index("code", unique=True)
    await db.templates.create_index([("user_id", 1), ("created_at", -1)])
    await seed_user(os.environ['ADMIN_EMAIL'], os.environ['ADMIN_PASSWORD'], "Admin", "admin")
    await seed_user("demo@beatcut.fr", "Demo1234!", "Démo", "user")
    # Codes promo par défaut
    for code, days in (("BIENVENUE50", 15), ("LAUNCH30", 30), ("BEATCUTSTART", 30)):
        existing = await db.promo_codes.find_one({"code": code})
        if not existing:
            await db.promo_codes.insert_one({
                "code": code, "bonus_days": days, "max_uses": None,
                "expires_at": None, "used_count": 0, "used_by": [],
                "created_at": iso(now_utc()),
            })
    asyncio.create_task(_reengage_loop())


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
