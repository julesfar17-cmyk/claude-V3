from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import shutil
import sys
import tempfile
import uuid
import logging
import bcrypt
import jwt
import httpx
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pymongo.errors import DuplicateKeyError
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
media_fs = AsyncIOMotorGridFSBucket(db, bucket_name="media")

app = FastAPI(title="BEATCUT API")
api_router = APIRouter(prefix="/api")

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_DAYS = 7

PRO_PRICE = 12.99           # 12,99 € — défini côté serveur uniquement, jamais depuis le front
PRO_PRICE_CENTS = 1299
PRO_PRICE_YEAR = 99.00
PRO_PRICE_YEAR_CENTS = 9900
BASIC_PRICE = 6.99          # plan Basic — 10 vidéos/mois, sans acapella
BASIC_PRICE_CENTS = 699
BASIC_MONTHLY_EXPORTS = 10
# --- Nouvelle grille tarifaire (juin 2026) ---
ESSENTIEL_PRICE_CENTS = 999      # Essentiel — 9,99 €/mois, 15 exports/mois
PRO2_PRICE_CENTS = 1999          # Pro — 19,99 €/mois, essai 7 jours
PRO2_YEAR_CENTS = 14900          # Pro annuel — 149 €/an
STUDIO_YEAR_CENTS = 49900        # Studio — 499 €/an
ESSENTIEL_MONTHLY_EXPORTS = 15
TRIAL_DAYS = 7
TRIAL_EXPORT_CAP = 15            # plafond anti-abus pendant l'essai (invisible marketing)
NEW_PLANS = ("essentiel", "pro_monthly", "pro_yearly", "studio")
ANNUAL_PLANS = ("yearly", "pro_yearly", "studio")
PLAN_TIERS = {"basic": "basic", "essentiel": "essentiel", "studio": "studio"}  # défaut : pro
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
<tr><td style="font-size:11px;color:#6b6478;padding-top:28px">BEATCUT — studio beat-sync. Sans engagement sur les plans mensuels.</td></tr>
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
        "Bienvenue ✦",
        f"Ton abonnement BEATCUT est actif : exports sans watermark, tous les styles et effets débloqués. "
        f"Renouvellement automatique le {_fmt_date_fr(period_end)}. "
        f"Tu peux te désabonner à tout moment en 2 clics depuis ton compte.",
    )


def trial_started_email_html(trial_end) -> str:
    return _email_html(
        "Ton essai Pro a commencé 🎉",
        f"Tu as 7 jours d'accès Pro complet : exports illimités, séries de vidéos, tous les styles. "
        f"Ton abonnement Pro (19,99 €/mois) démarre automatiquement le {_fmt_date_fr(trial_end)}. "
        f"Tu peux annuler à tout moment avant cette date, en 2 clics, depuis ton compte — rien ne sera débité.",
        "Gérer mon abonnement", "https://beat-cut.com/dashboard",
    )


def trial_reminder_email_html(trial_end) -> str:
    return _email_html(
        "Ton essai se termine bientôt",
        f"Ton essai Pro se termine le {_fmt_date_fr(trial_end)}. "
        f"Ton abonnement Pro (19,99 €/mois) démarre automatiquement à cette date. "
        f"Si tu veux continuer, tu n'as rien à faire. Sinon, annule en 2 clics avant le débit — rien ne sera prélevé.",
        "Gérer ou annuler", "https://beat-cut.com/dashboard",
    )


def trial_canceled_email_html() -> str:
    return _email_html(
        "Essai annulé — rien ne sera débité",
        "Ton essai Pro a bien été annulé : aucun prélèvement. "
        "Ton montage et tes morceaux restent sauvegardés sur ton compte — tu peux reprendre un abonnement quand tu veux.",
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


def create_access_token(user_id: str, email: str, sid: str = "") -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "sid": sid,
        "type": "access",
        "exp": now_utc() + timedelta(days=ACCESS_TOKEN_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _session_limit(user: dict) -> int:
    """Anti-partage : 1 session active (3 pour Studio). Admin/VIP : illimité."""
    if user.get("role") == "admin" or (user.get("email") or "").lower() in PRO_WHITELIST:
        return 99
    return 3 if ((user.get("subscription") or {}).get("plan") == "studio") else 1


async def register_sid(user: dict, sid: str):
    sids = list(user.get("sids") or []) + [sid]
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"sids": sids[-_session_limit(user):]}})


def _check_sid(user: dict, sid: str):
    sids = user.get("sids")
    if not sids:
        return  # sessions créées avant le mécanisme : tolérées jusqu'au prochain login
    if sid not in sids:
        raise HTTPException(status_code=401, detail="Ton compte a été connecté sur un autre appareil.")


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
            "tier": "pro",
            "plan": "vip",
            "status": "vip",
            "current_period_end": None,
            "cancel_at_period_end": False,
        }
    sub = user.get("subscription") or {}
    status = sub.get("status")
    end = parse_dt(sub.get("current_period_end"))
    active = status in ("active", "canceled", "trialing") and end is not None and end > now_utc()
    plan = sub.get("plan") or "monthly"
    tier = PLAN_TIERS.get(plan, "pro") if active else "free"
    trialing = bool(active and status == "trialing")
    return {
        "is_pro": bool(active),
        "tier": tier,
        "plan": plan if active else None,
        "status": status if active else None,
        "current_period_end": end.isoformat() if (active and end) else None,
        "cancel_at_period_end": (status == "canceled") if active else False,
        "trial": trialing,
        "trial_end": end.isoformat() if trialing else None,
        "trial_start": sub.get("started_at") if trialing else None,
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
        "onboarding_done": bool(user.get("onboarding_done", True)),
        "onboarding": user.get("onboarding") or {},
        "has_watermark": bool(user.get("watermark_media_id")),
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


def _stripe_sub_status(s) -> str:
    st = s.get("status")
    if st == "trialing":
        return "canceled" if s.get("cancel_at_period_end") else "trialing"
    if st == "active":
        return "canceled" if s.get("cancel_at_period_end") else "active"
    return "expired"


async def _apply_stripe_sub_state(user_id: str, s):
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "subscription.status": _stripe_sub_status(s),
            "subscription.current_period_end": iso(_extract_period_end(s)),
            "subscription.synced_at": iso(now_utc()),
        }},
    )


async def activate_subscription(user_id: str, customer_id: str = None, subscription_id: str = None, plan: str = "monthly"):
    days = SUBSCRIPTION_DAYS_YEAR if plan in ANNUAL_PLANS else SUBSCRIPTION_DAYS
    # Changement de plan (ex: Basic → PRO) : annule l'ancien abonnement Stripe
    # pour éviter la double facturation.
    existing = await db.users.find_one({"user_id": user_id}, {"_id": 0, "subscription": 1})
    old_sub_id = ((existing or {}).get("subscription") or {}).get("stripe_subscription_id")
    if old_sub_id and subscription_id and old_sub_id != subscription_id:
        try:
            await asyncio.to_thread(stripe.Subscription.cancel, old_sub_id)
            logger.info("Ancien abonnement Stripe %s annulé (changement de plan)", old_sub_id)
        except Exception as e:
            logger.warning("Annulation ancien abonnement %s impossible: %s", old_sub_id, e)
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
    await _apply_stripe_sub_state(user["user_id"], s)
    return await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})


# ---------------------------------------------------------------------------
# Auth dependency (JWT cookie OR Emergent session token, header fallback)
# ---------------------------------------------------------------------------
async def _user_from_jwt(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None, ""
        return await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0}), (payload.get("sid") or "")
    except jwt.PyJWTError:
        return None, ""


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
        user, sid = await _user_from_jwt(jwt_token)
        if user:
            _check_sid(user, sid)
            return user
    session_token = request.cookies.get("session_token")
    if session_token:
        user = await _user_from_session(session_token)
        if user:
            _check_sid(user, session_token)
            return user
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        bearer = auth_header[7:]
        user, sid = await _user_from_jwt(bearer)
        if user:
            _check_sid(user, sid)
            return user
        user = await _user_from_session(bearer)
        if user:
            _check_sid(user, bearer)
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
    plan: str = "pro_monthly"   # essentiel | pro_monthly | pro_yearly | studio (+ legacy monthly/yearly/basic)
    promo_code: str | None = None   # code affilié (remise Stripe à vie)
    return_path: str | None = None  # chemin de retour après paiement (ex: /studio?project=ID)


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
        "onboarding_done": False,
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(user)
    sid = uuid.uuid4().hex
    await register_sid(user, sid)
    set_jwt_cookie(response, create_access_token(user["user_id"], email, sid))
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
    sid = uuid.uuid4().hex
    await register_sid(user, sid)
    set_jwt_cookie(response, create_access_token(user["user_id"], email, sid))
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
# Télémétrie — navigateurs incompatibles WebCodecs (écran bloquant de l'éditeur)
# ---------------------------------------------------------------------------
@api_router.post("/telemetry/unsupported-browser")
async def log_unsupported_browser(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    ua = str(body.get("ua") or request.headers.get("User-Agent") or "")[:500]
    user_id = None
    try:
        user = await get_current_user(request)
        user_id = user.get("user_id")
    except HTTPException:
        pass
    await db.browser_unsupported_logs.insert_one({
        "user_id": user_id,
        "ua": ua,
        "created_at": iso(now_utc()),
    })
    return {"ok": True}


@api_router.get("/admin/telemetry/unsupported-browser")
async def admin_unsupported_browsers(user: dict = Depends(get_current_user)):
    await require_admin(user)
    total = await db.browser_unsupported_logs.count_documents({})
    cutoff = iso(now_utc() - timedelta(days=30))
    last_30d = await db.browser_unsupported_logs.count_documents({"created_at": {"$gt": cutoff}})
    samples = await db.browser_unsupported_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    return {"total": total, "last_30d": last_30d, "samples": samples}


@api_router.post("/telemetry/webview")
async def log_webview_detected(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    ua = str(body.get("ua") or request.headers.get("User-Agent") or "")[:500]
    user_id = None
    try:
        user = await get_current_user(request)
        user_id = user.get("user_id")
    except HTTPException:
        pass
    await db.webview_logs.insert_one({
        "user_id": user_id,
        "ua": ua,
        "build": str(body.get("build") or "")[:50],
        "created_at": iso(now_utc()),
    })
    return {"ok": True}


@api_router.get("/admin/telemetry/webview")
async def admin_webview_logs(user: dict = Depends(get_current_user)):
    await require_admin(user)
    total = await db.webview_logs.count_documents({})
    cutoff = iso(now_utc() - timedelta(days=30))
    last_30d = await db.webview_logs.count_documents({"created_at": {"$gt": cutoff}})
    samples = await db.webview_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    return {"total": total, "last_30d": last_30d, "samples": samples}


_PREVIEW_EVENT_KEYS = ("type", "t", "plan", "clip", "codec", "wcReady", "wcAReady",
                       "queue", "buffered", "stallMs", "msg", "w", "h", "dur",
                       "optimizing", "notReady")


@api_router.post("/telemetry/preview")
async def log_preview_telemetry(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalide")
    events = body.get("events") or []
    if not isinstance(events, list) or not events:
        return {"ok": True, "stored": 0}
    user_id = None
    try:
        user = await get_current_user(request)
        user_id = user.get("user_id")
    except HTTPException:
        pass
    ctx = body.get("ctx") or {}
    doc = {
        "session_id": str(body.get("session_id") or "")[:64],
        "user_id": user_id,
        "ctx": {
            "ua": str(ctx.get("ua") or "")[:300],
            "mobile": bool(ctx.get("mobile")),
            "clips": int(ctx.get("clips") or 0),
            "plans": int(ctx.get("plans") or 0),
            "mem": ctx.get("mem") if isinstance(ctx.get("mem"), dict) else None,
            "build": str(ctx.get("build") or "")[:50],
        },
        "events": [{k: e.get(k) for k in _PREVIEW_EVENT_KEYS if k in e}
                   for e in events[:100] if isinstance(e, dict)],
        "created_at": iso(now_utc()),
    }
    await db.preview_logs.insert_one(doc)
    return {"ok": True, "stored": len(doc["events"])}


def _browser_family(ua: str) -> str:
    ua = ua or ""
    if "iPhone" in ua or "iPad" in ua:
        return "iOS Safari" if "Safari" in ua and "CriOS" not in ua else "iOS (app/Chrome)"
    if "Android" in ua:
        return "Android Chrome" if "Chrome" in ua else "Android autre"
    if "Firefox" in ua:
        return "Firefox"
    if "Edg/" in ua:
        return "Edge"
    if "Chrome" in ua:
        return "Chrome desktop"
    if "Safari" in ua:
        return "Safari macOS"
    return "Autre"


def _size_bucket(n: int) -> str:
    if n <= 3:
        return "1-3 clips"
    if n <= 10:
        return "4-10 clips"
    return ">10 clips"


@api_router.get("/admin/telemetry/preview")
async def admin_preview_report(days: int = 7, user: dict = Depends(get_current_user)):
    await require_admin(user)
    cutoff = iso(now_utc() - timedelta(days=min(max(days, 1), 90)))
    batches = await db.preview_logs.find({"created_at": {"$gt": cutoff}}, {"_id": 0}).to_list(10000)
    sessions, event_counts, stall_codecs, by_browser, by_size = {}, {}, {}, {}, {}
    samples = []
    for b in batches:
        ctx = b.get("ctx") or {}
        s = sessions.setdefault(b.get("session_id"), {"types": set(), "browser": _browser_family(ctx.get("ua")), "clips": 0})
        s["clips"] = max(s["clips"], ctx.get("clips") or 0)
        for e in b.get("events") or []:
            et = e.get("type") or "?"
            s["types"].add(et)
            event_counts[et] = event_counts.get(et, 0) + 1
            if et in ("preview_stall", "decoder_error") and e.get("codec"):
                stall_codecs[e["codec"]] = stall_codecs.get(e["codec"], 0) + 1
            if len(samples) < 40:
                samples.append({**e, "session": (b.get("session_id") or "")[:8], "browser": s["browser"]})
    for s in sessions.values():
        bb = by_browser.setdefault(s["browser"], {"sessions": 0, "with_stall": 0})
        bb["sessions"] += 1
        if "preview_stall" in s["types"]:
            bb["with_stall"] += 1
        sb = by_size.setdefault(_size_bucket(s["clips"]), {"sessions": 0, "with_stall": 0})
        sb["sessions"] += 1
        if "preview_stall" in s["types"]:
            sb["with_stall"] += 1
    total = len(sessions)
    with_stall = sum(1 for s in sessions.values() if "preview_stall" in s["types"])
    return {
        "days": days,
        "total_sessions": total,
        "sessions_with_stall": with_stall,
        "pct_sessions_with_stall": round(100.0 * with_stall / total, 1) if total else 0.0,
        "event_counts": event_counts,
        "stall_codecs": stall_codecs,
        "by_browser": by_browser,
        "by_project_size": by_size,
        "samples": samples,
    }


@api_router.post("/telemetry/export")
async def log_export_telemetry(request: Request, user: dict = Depends(get_current_user)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    await db.export_logs.insert_one({
        "user_id": user.get("user_id"),
        "mode": str(body.get("mode"))[:20],
        "server_audio": bool(body.get("server_audio")),
        "audio_chunks": int(body.get("audio_chunks") or 0),
        "aenc_err": (str(body.get("aenc_err"))[:200] if body.get("aenc_err") else None),
        "build": str(body.get("build") or "")[:40],
        "src_peak": body.get("src_peak"),
        "size": int(body.get("size") or 0),
        "ua": str(body.get("ua") or "")[:300],
        "created_at": iso(now_utc()),
    })
    return {"ok": True}


@api_router.get("/admin/telemetry/exports")
async def admin_export_telemetry(user: dict = Depends(get_current_user)):
    await require_admin(user)
    total = await db.export_logs.count_documents({})
    samples = await db.export_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    return {"total": total, "samples": samples}


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
            plan = tx.get("plan", "monthly")
            await activate_subscription(tx["user_id"], customer_id, subscription_id, plan=plan)
            trial_started = False
            if subscription_id:
                try:
                    s = await asyncio.to_thread(
                        lambda: stripe.Subscription.retrieve(subscription_id, expand=["default_payment_method"]))
                    if s.get("status") == "trialing":
                        if await _guard_trial_fingerprint(tx["user_id"], tx.get("email"), s):
                            return
                        trial_started = True
                    await _apply_stripe_sub_state(tx["user_id"], s)
                except Exception:
                    logger.exception("Sync post-activation impossible pour %s", subscription_id)
            if tx.get("affiliate_code"):
                await db.affiliate_codes.update_one(
                    {"code": tx["affiliate_code"]},
                    {"$inc": {"use_count": 1},
                     "$push": {"uses": {"user_id": tx["user_id"], "email": tx.get("email"),
                                        "plan": plan, "date": iso(now_utc())}}})
            user = await db.users.find_one({"user_id": tx["user_id"]}, {"_id": 0})
            if user:
                end = (user.get("subscription") or {}).get("current_period_end")
                if trial_started:
                    await send_email(user["email"], "Ton essai Pro a commencé ✦ BEATCUT", trial_started_email_html(end))
                else:
                    label = PLAN_LABELS.get(plan, "PRO")
                    await send_email(user["email"], f"Bienvenue en {label} ✦ BEATCUT", sub_confirmed_email_html(end))


async def _guard_trial_fingerprint(user_id: str, email: str, s) -> bool:
    """Anti-abus : un seul essai par carte (empreinte Stripe). Retourne True si l'essai est refusé."""
    fp = None
    try:
        pm = s.get("default_payment_method")
        if pm and pm.get("card"):
            fp = pm["card"].get("fingerprint")
    except Exception:
        pass
    if fp:
        dup = await db.trial_fingerprints.find_one({"fingerprint": fp, "user_id": {"$ne": user_id}})
        if dup:
            try:
                await asyncio.to_thread(stripe.Subscription.cancel, s["id"])
            except Exception:
                logger.exception("Annulation de l'essai dupliqué impossible (%s)", s["id"])
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"subscription.status": "expired", "trial_refused_at": iso(now_utc())}})
            logger.warning("Essai refusé (carte déjà utilisée pour un essai) : %s", email)
            return True
        await db.trial_fingerprints.update_one(
            {"fingerprint": fp},
            {"$setOnInsert": {"fingerprint": fp, "user_id": user_id, "email": email, "used_at": iso(now_utc())}},
            upsert=True)
    await db.users.update_one({"user_id": user_id}, {"$set": {"trial_used": True}})
    return False


def _plan_pricing(plan: str) -> dict:
    if plan == "essentiel":
        return {"amount_cents": ESSENTIEL_PRICE_CENTS, "interval": "month",
                "name": "BEATCUT ESSENTIEL",
                "desc": f"{ESSENTIEL_MONTHLY_EXPORTS} exports/mois — tous les styles et effets, banque de clips — sans engagement"}
    if plan == "pro_monthly":
        return {"amount_cents": PRO2_PRICE_CENTS, "interval": "month",
                "name": "BEATCUT PRO",
                "desc": "Exports illimités + séries de vidéos + tous styles/effets/polices — sans engagement"}
    if plan == "pro_yearly":
        return {"amount_cents": PRO2_YEAR_CENTS, "interval": "year",
                "name": "BEATCUT PRO — annuel",
                "desc": "Tout le plan Pro — 149 € facturés une fois par an (≈ 12,42 €/mois)"}
    if plan == "studio":
        return {"amount_cents": STUDIO_YEAR_CENTS, "interval": "year",
                "name": "BEATCUT STUDIO",
                "desc": "5 profils artistes, watermark personnalisé, 3 utilisateurs, support prioritaire — 499 €/an"}
    if plan == "yearly":
        return {"amount_cents": PRO_PRICE_YEAR_CENTS, "interval": "year",
                "name": "BEATCUT PRO — annuel",
                "desc": "Export sans watermark + .srt + extraction acapella — 99 €/an (2 mois offerts)"}
    if plan == "basic":
        return {"amount_cents": BASIC_PRICE_CENTS, "interval": "month",
                "name": "BEATCUT BASIC",
                "desc": f"Export sans watermark — {BASIC_MONTHLY_EXPORTS} vidéos/mois, sous-titres .srt — sans acapella, sans engagement"}
    return {"amount_cents": PRO_PRICE_CENTS, "interval": "month",
            "name": "BEATCUT PRO",
            "desc": "Export vidéo sans watermark + sous-titres .srt + acapella — sans engagement"}


async def _apply_affiliate_discount(params: dict, plan: str, promo_code: str) -> str:
    """Applique la remise Stripe d'un code affilié (coupon duration=forever). Retourne le code normalisé ou ''."""
    aff_code = _normalize_promo(promo_code or "")
    if not aff_code:
        return ""
    aff = await db.affiliate_codes.find_one({"code": aff_code, "active": True})
    if not aff:
        raise HTTPException(status_code=400, detail="Code affilié invalide ou expiré")
    _covered = set(aff.get("plans") or [])
    if plan not in _covered and LEGACY_PLAN_EQUIV.get(plan) not in _covered:
        raise HTTPException(status_code=400, detail="Ce code affilié ne couvre pas ce plan")
    params["discounts"] = [{"coupon": aff["stripe_coupon_id"]}]
    params["metadata"]["affiliate_code"] = aff_code
    return aff_code


@api_router.post("/payments/checkout")
async def create_checkout(data: CheckoutIn, request: Request, user: dict = Depends(get_current_user)):
    if (user.get("email") or "").lower() in PRO_WHITELIST:
        raise HTTPException(status_code=400, detail="Compte VIP — déjà PRO")
    origin = data.origin_url.rstrip("/")
    sub = user.get("subscription") or {}
    plan = data.plan if data.plan in (*NEW_PLANS, "monthly", "yearly", "basic") else "pro_monthly"
    pricing = _plan_pricing(plan)
    params = dict(
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": PRO_CURRENCY,
                "unit_amount": pricing["amount_cents"],
                "recurring": {"interval": pricing["interval"]},
                "product_data": {"name": pricing["name"], "description": pricing["desc"]},
            },
            "quantity": 1,
        }],
        success_url=f"{origin}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/dashboard",
        metadata={"user_id": user["user_id"], "email": user["email"], "product": f"beatcut_{plan}"},
        subscription_data={"metadata": {"user_id": user["user_id"], "plan": plan}},
    )
    rp = (data.return_path or "").strip()
    if rp.startswith("/") and not rp.startswith("//"):
        sep = "&" if "?" in rp else "?"
        params["success_url"] = f"{origin}{rp}{sep}session_id={{CHECKOUT_SESSION_ID}}"
        params["cancel_url"] = f"{origin}{rp}"
    with_trial = False
    if plan == "pro_monthly" and not sub.get("stripe_subscription_id"):
        # Essai 7 jours : un seul par email ET par carte (empreinte vérifiée après le checkout)
        already = user.get("trial_used") or await db.trial_fingerprints.find_one({"email": user["email"]})
        if not already:
            params["subscription_data"]["trial_period_days"] = TRIAL_DAYS
            with_trial = True
    if sub.get("stripe_customer_id"):
        params["customer"] = sub["stripe_customer_id"]
    else:
        params["customer_email"] = user["email"]
    aff_code = await _apply_affiliate_discount(params, plan, data.promo_code)
    try:
        session = await asyncio.to_thread(lambda: stripe.checkout.Session.create(**params))
    except Exception as e:
        logger.error("Stripe checkout error: %s", e)
        raise HTTPException(status_code=502, detail="Erreur Stripe lors de la création du paiement — réessaie") from e
    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "user_id": user["user_id"],
        "email": user["email"],
        "amount": pricing["amount_cents"] / 100.0,
        "currency": PRO_CURRENCY,
        "product": f"beatcut_{plan}",
        "plan": plan,
        "status": "open",
        "payment_status": "initiated",
        "processed": False,
        "affiliate_code": aff_code or None,
        "with_trial": with_trial,
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
        fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "trial_refused_at": 1, "subscription": 1})
        if fresh and fresh.get("trial_refused_at") and ((fresh.get("subscription") or {}).get("status") == "expired"):
            return {"status": session.status, "payment_status": "trial_refused"}
    return {"status": session.status, "payment_status": session.payment_status}


_WEBHOOK_SECRET_CACHE = None
STRIPE_WEBHOOK_EVENTS = ["checkout.session.completed", "customer.subscription.updated",
                         "customer.subscription.deleted", "customer.subscription.trial_will_end", "invoice.paid"]


async def get_webhook_secret() -> str:
    """Secret webhook : env prioritaire, sinon celui créé automatiquement (db.config)."""
    global _WEBHOOK_SECRET_CACHE
    env_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if env_secret:
        return env_secret
    if _WEBHOOK_SECRET_CACHE is None:
        doc = await db.config.find_one({"_id": "stripe_webhook"})
        _WEBHOOK_SECRET_CACHE = (doc or {}).get("secret") or ""
    return _WEBHOOK_SECRET_CACHE


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    secret = await get_webhook_secret()
    if not secret:
        # Pas de webhook configuré : le filet de sécurité est la réconciliation périodique.
        return {"received": True}
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("Stripe-Signature", ""), secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Webhook invalide")
    etype = event["type"]
    obj = event["data"]["object"]
    if etype == "checkout.session.completed":
        if obj.get("payment_status") == "paid":
            await _claim_and_activate(obj["id"], obj.get("customer"), obj.get("subscription"))
    elif etype == "customer.subscription.trial_will_end":
        sub_id = obj.get("id")
        u = await db.users.find_one({"subscription.stripe_subscription_id": sub_id},
                                    {"_id": 0, "user_id": 1, "email": 1, "subscription": 1})
        if u and not (u.get("subscription") or {}).get("trial_reminder_sent"):
            te = obj.get("trial_end")
            end_iso = iso(datetime.fromtimestamp(te, tz=timezone.utc)) if te else (u.get("subscription") or {}).get("current_period_end")
            await send_email(u["email"], "Ton essai Pro se termine bientôt — BEATCUT", trial_reminder_email_html(end_iso))
            await db.users.update_one({"user_id": u["user_id"]}, {"$set": {"subscription.trial_reminder_sent": True}})
    elif etype in ("customer.subscription.updated", "customer.subscription.deleted", "invoice.paid"):
        sub_id = obj.get("id") if etype.startswith("customer.subscription") else obj.get("subscription")
        if sub_id:
            u = await db.users.find_one({"subscription.stripe_subscription_id": sub_id}, {"_id": 0, "user_id": 1})
            if u:
                try:
                    s = obj if etype.startswith("customer.subscription") else await asyncio.to_thread(stripe.Subscription.retrieve, sub_id)
                    await _apply_stripe_sub_state(u["user_id"], s)
                except Exception:
                    logger.exception("Webhook : sync abonnement %s impossible", sub_id)
    return {"received": True}


# ---------------------------------------------------------------------------
# Réconciliation : filet de sécurité pour les paiements jamais réclamés
# (client parti avant le retour sur le site) + vérification des annulations
# ---------------------------------------------------------------------------
async def reconcile_payments() -> dict:
    cutoff = iso(now_utc() - timedelta(days=30))
    txs = await db.payment_transactions.find(
        {"processed": {"$ne": True}, "created_at": {"$gt": cutoff}},
        {"_id": 0, "session_id": 1, "email": 1},
    ).to_list(500)
    activated, emails = 0, []
    for tx in txs:
        try:
            session = await asyncio.to_thread(stripe.checkout.Session.retrieve, tx["session_id"])
        except Exception as e:
            logger.warning("Réconciliation session %s : %s", tx["session_id"], e)
            continue
        if session.payment_status == "paid":
            await _claim_and_activate(tx["session_id"], session.get("customer"), session.get("subscription"))
            activated += 1
            emails.append(tx.get("email"))
            logger.info("Réconciliation : accès activé rétroactivement pour %s (session %s)", tx.get("email"), tx["session_id"])
        elif session.status == "expired":
            await db.payment_transactions.update_one(
                {"session_id": tx["session_id"]},
                {"$set": {"processed": True, "status": "expired",
                          "payment_status": session.payment_status, "updated_at": iso(now_utc())}},
            )
    return {"checked": len(txs), "activated": activated, "activated_emails": emails}


async def reconcile_subscriptions(force: bool = False) -> dict:
    users = await db.users.find(
        {"subscription.stripe_subscription_id": {"$exists": True, "$nin": [None, ""]}},
        {"_id": 0, "user_id": 1, "email": 1, "subscription": 1},
    ).to_list(1000)
    checked, changes = 0, []
    for u in users:
        sub = u.get("subscription") or {}
        synced = parse_dt(sub.get("synced_at"))
        if not force and synced and (now_utc() - synced) < timedelta(hours=12):
            continue
        checked += 1
        try:
            s = await asyncio.to_thread(stripe.Subscription.retrieve, sub["stripe_subscription_id"])
        except Exception as e:
            logger.warning("Réconciliation abonnement %s : %s", sub.get("stripe_subscription_id"), e)
            continue
        new_status = _stripe_sub_status(s)
        await _apply_stripe_sub_state(u["user_id"], s)
        if new_status != sub.get("status"):
            changes.append({"email": u.get("email"), "avant": sub.get("status"), "apres": new_status})
            logger.info("Réconciliation : %s %s → %s", u.get("email"), sub.get("status"), new_status)
    return {"checked": checked, "status_changed": len(changes), "changes": changes}


async def _payments_watchdog():
    await asyncio.sleep(15)
    while True:
        try:
            r = await reconcile_payments()
            if r["activated"]:
                logger.info("Watchdog paiements : %s", r)
            await reconcile_subscriptions()
        except Exception:
            logger.exception("Watchdog paiements en erreur")
        await asyncio.sleep(600)


@api_router.post("/admin/payments/reconcile")
async def admin_payments_reconcile(user: dict = Depends(get_current_user)):
    await require_admin(user)
    payments = await reconcile_payments()
    subscriptions = await reconcile_subscriptions(force=True)
    return {"payments": payments, "subscriptions": subscriptions}


@api_router.get("/admin/payments/webhook")
async def admin_webhook_status(user: dict = Depends(get_current_user)):
    await require_admin(user)
    if os.environ.get("STRIPE_WEBHOOK_SECRET"):
        return {"configured": True, "source": "env", "url": None}
    doc = await db.config.find_one({"_id": "stripe_webhook"})
    return {"configured": bool(doc and doc.get("secret")), "source": "auto", "url": (doc or {}).get("url")}


@api_router.post("/admin/payments/webhook-setup")
async def admin_webhook_setup(request: Request, user: dict = Depends(get_current_user)):
    """Crée le webhook Stripe automatiquement pour le domaine courant (secret stocké en base)."""
    await require_admin(user)
    global _WEBHOOK_SECRET_CACHE
    host = (request.headers.get("x-forwarded-host") or request.url.hostname or "").split(",")[0].strip()
    if not host:
        raise HTTPException(status_code=400, detail="Hôte introuvable")
    url = f"https://{host}/api/webhook/stripe"
    doc = await db.config.find_one({"_id": "stripe_webhook"})
    if doc and doc.get("url") == url and doc.get("secret"):
        # Met à jour la liste d'événements (ex: trial_will_end ajouté après coup)
        if doc.get("endpoint_id"):
            try:
                await asyncio.to_thread(lambda: stripe.WebhookEndpoint.modify(
                    doc["endpoint_id"], enabled_events=STRIPE_WEBHOOK_EVENTS))
            except Exception:
                logger.warning("Mise à jour des événements webhook impossible")
        return {"configured": True, "url": url, "already": True}
    if doc and doc.get("endpoint_id"):
        try:
            await asyncio.to_thread(stripe.WebhookEndpoint.delete, doc["endpoint_id"])
        except Exception:
            pass
    try:
        ep = await asyncio.to_thread(lambda: stripe.WebhookEndpoint.create(
            url=url,
            enabled_events=STRIPE_WEBHOOK_EVENTS,
            description="BEATCUT — créé automatiquement",
        ))
    except Exception as e:
        logger.error("Création webhook Stripe : %s", e)
        raise HTTPException(status_code=502, detail="Création du webhook Stripe impossible — réessaie") from e
    await db.config.update_one(
        {"_id": "stripe_webhook"},
        {"$set": {"secret": ep["secret"], "url": url, "endpoint_id": ep["id"], "created_at": iso(now_utc())}},
        upsert=True,
    )
    _WEBHOOK_SECRET_CACHE = ep["secret"]
    logger.info("Webhook Stripe créé : %s", url)
    return {"configured": True, "url": url, "already": False}


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
    if info.get("trial"):
        # Annulation PENDANT l'essai : immédiate, aucun débit, accès coupé
        if sub.get("stripe_subscription_id"):
            try:
                await asyncio.to_thread(stripe.Subscription.cancel, sub["stripe_subscription_id"])
            except Exception as e:
                logger.error("Stripe trial cancel error: %s", e)
                raise HTTPException(status_code=502, detail="Erreur Stripe lors de l'annulation — réessaie")
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"subscription.status": "expired", "subscription.canceled_at": iso(now_utc()),
                      "subscription.was_trial": True}},
        )
        await send_email(user["email"], "Essai annulé — BEATCUT", trial_canceled_email_html())
        await _mark_feedback_lost(user["user_id"])
        return {"message": "Essai annulé — rien ne sera débité. Ton montage reste sauvegardé, tu peux te réabonner quand tu veux.",
                "current_period_end": None}
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
    await _mark_feedback_lost(user["user_id"])
    return {
        "message": "Abonnement annulé — aucun prélèvement futur. Tu gardes l'accès PRO jusqu'à la fin de la période en cours.",
        "current_period_end": info["current_period_end"],
    }


# ---------------------------------------------------------------------------
# Formulaire d'annulation + offre de rétention (−50 % sur la prochaine facture)
# ---------------------------------------------------------------------------
CANCEL_REASONS = ("too_expensive", "not_enough_use", "missing_features", "technical_issues", "promo_done", "other")
# Offre de rétention −50 % : plans MENSUELS uniquement (sur une facture annuelle la remise serait énorme)
RETENTION_PLANS = ("monthly", "pro_monthly", "basic", "essentiel")


async def _mark_feedback_lost(user_id: str):
    await db.cancel_feedback.find_one_and_update(
        {"user_id": user_id, "retained": None}, {"$set": {"retained": False}}, sort=[("at", -1)])


async def _retention_coupon_id() -> str:
    doc = await db.config.find_one({"_id": "retention_coupon"})
    if doc and doc.get("coupon_id"):
        return doc["coupon_id"]
    c = await asyncio.to_thread(lambda: stripe.Coupon.create(
        percent_off=50, duration="once", name="On reste ensemble −50 %"))
    await db.config.update_one({"_id": "retention_coupon"}, {"$set": {"coupon_id": c["id"]}}, upsert=True)
    return c["id"]


@api_router.post("/subscription/cancel-feedback")
async def cancel_feedback(payload: dict, user: dict = Depends(get_current_user)):
    """Étape 1 du formulaire d'annulation : enregistre la raison, dit si l'offre −50 % est disponible."""
    user = await sync_stripe_subscription(user)
    info = sub_info(user)
    reason = payload.get("reason")
    if reason not in CANCEL_REASONS:
        raise HTTPException(status_code=400, detail="Raison invalide")
    comment = str(payload.get("comment") or "")[:500].strip()
    sub = user.get("subscription") or {}
    await db.cancel_feedback.insert_one({
        "user_id": user["user_id"], "email": user["email"], "plan": sub.get("plan"),
        "trial": bool(info.get("trial")), "reason": reason, "comment": comment,
        "retained": None, "at": iso(now_utc()),
    })
    offer_available = bool(
        sub.get("stripe_subscription_id") and info["is_pro"]
        and not info["cancel_at_period_end"] and not user.get("retention_offer_used")
        and (sub.get("plan") or "monthly") in RETENTION_PLANS
    )
    return {"ok": True, "offer_available": offer_available}


@api_router.post("/subscription/retention-accept")
async def retention_accept(user: dict = Depends(get_current_user)):
    """Le client accepte l'offre : −50 % sur sa prochaine facture, l'abonnement continue."""
    user = await sync_stripe_subscription(user)
    info = sub_info(user)
    sub = user.get("subscription") or {}
    if not (sub.get("stripe_subscription_id") and info["is_pro"] and not info["cancel_at_period_end"]):
        raise HTTPException(status_code=400, detail="Aucun abonnement actif")
    if (sub.get("plan") or "monthly") not in RETENTION_PLANS:
        raise HTTPException(status_code=400, detail="Offre réservée aux abonnements mensuels")
    if user.get("retention_offer_used"):
        raise HTTPException(status_code=400, detail="Offre déjà utilisée")
    cid = await _retention_coupon_id()
    try:
        await asyncio.to_thread(lambda: stripe.Subscription.modify(
            sub["stripe_subscription_id"], discounts=[{"coupon": cid}]))
    except Exception as e:
        logger.error("Application remise rétention : %s", e)
        raise HTTPException(status_code=502, detail="Erreur Stripe — réessaie") from e
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"retention_offer_used": True}})
    await db.cancel_feedback.find_one_and_update(
        {"user_id": user["user_id"], "retained": None}, {"$set": {"retained": True}}, sort=[("at", -1)])
    return {"message": "C'est noté : −50 % sur ta prochaine facture. Content de continuer avec toi 🖤"}


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
from fastapi.responses import StreamingResponse

SEP_DIR = Path("/tmp/beatcut_sep")
SEP_DIR.mkdir(parents=True, exist_ok=True)
# Jobs stockés dans MongoDB (collection separation_jobs) — l'état en mémoire ne
# fonctionne pas en production où plusieurs workers servent les requêtes.

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
    return vocals_url


async def _run_separation(job_id: str, input_path: str):
    try:
        loop = asyncio.get_running_loop()
        vocals_url = await loop.run_in_executor(None, _separate_with_replicate, input_path)
        await db.separation_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "done", "result_url": vocals_url}},
        )
    except Exception as e:
        msg = str(e)
        logger.error("Séparation %s échouée: %s", job_id, msg)
        if "Insufficient credit" in msg or "402" in msg:
            user_msg = "Service de séparation momentanément indisponible — réessaie plus tard."
        else:
            user_msg = "séparation échouée — réessaie"
        await db.separation_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "error", "error": user_msg}},
        )
    finally:
        try:
            os.remove(input_path)
        except OSError:
            pass
        cutoff = now_utc() - timedelta(hours=2)
        await db.separation_jobs.delete_many({"created_at": {"$lt": iso(cutoff)}})


async def require_pro(user: dict) -> dict:
    """Extraction acapella : réservée aux plans PRO et STUDIO."""
    user = await sync_stripe_subscription(user)
    info = sub_info(user)
    if info["tier"] not in ("pro", "studio"):
        if info["tier"] in ("basic", "essentiel"):
            raise HTTPException(status_code=403, detail="Extraction acapella réservée aux plans PRO et STUDIO — passe en PRO depuis Mon compte")
        raise HTTPException(status_code=403, detail="Fonction réservée aux abonnés PRO")
    return user


def _month_start_iso() -> str:
    return iso(now_utc().replace(day=1, hour=0, minute=0, second=0, microsecond=0))


def _essentiel_period_start(user: dict) -> str:
    """Début de la période mensuelle en cours (reset à la date anniversaire d'abonnement)."""
    end = parse_dt((user.get("subscription") or {}).get("current_period_end"))
    if end:
        return iso(end - relativedelta(months=1))
    return _month_start_iso()


@api_router.post("/export/register")
async def register_export(user: dict = Depends(get_current_user)):
    """Free : aucun export (paywall essai Pro). Essai Pro : plafond 15. Essentiel : 15/mois
    (reset à la date d'abonnement). Basic (legacy) : 10/mois. Pro/Studio/VIP : illimité."""
    user = await sync_stripe_subscription(user)
    info = sub_info(user)
    tier = info["tier"]
    if tier == "free":
        raise HTTPException(status_code=402, detail={
            "code": "paywall",
            "message": "Ta vidéo est prête. Débloque-la avec 7 jours offerts.",
        })
    if info.get("trial"):
        since = (user.get("subscription") or {}).get("started_at") or _month_start_iso()
        used = await db.export_logs.count_documents({"user_id": user["user_id"], "created_at": {"$gte": since}})
        if used >= TRIAL_EXPORT_CAP:
            raise HTTPException(status_code=429, detail={
                "code": "trial_cap",
                "message": f"Tu as atteint la limite de l'essai — ton accès illimité démarre avec ton abonnement le {_fmt_date_fr(info.get('trial_end'))}, ou active-le maintenant.",
                "trial_end": info.get("trial_end"),
            })
        await db.export_logs.insert_one({"user_id": user["user_id"], "tier": "trial", "created_at": iso(now_utc())})
        return {"allowed": True, "used": used + 1, "quota": TRIAL_EXPORT_CAP, "trial": True}
    if tier == "essentiel":
        since = _essentiel_period_start(user)
        used = await db.export_logs.count_documents({"user_id": user["user_id"], "created_at": {"$gte": since}})
        if used >= ESSENTIEL_MONTHLY_EXPORTS:
            raise HTTPException(
                status_code=429,
                detail=f"Quota atteint : {ESSENTIEL_MONTHLY_EXPORTS} exports/mois avec le plan Essentiel. Passe en Pro pour exporter en illimité.",
            )
        await db.export_logs.insert_one({"user_id": user["user_id"], "tier": "essentiel", "created_at": iso(now_utc())})
        return {"allowed": True, "used": used + 1, "quota": ESSENTIEL_MONTHLY_EXPORTS}
    if tier == "basic":
        used = await db.export_logs.count_documents({
            "user_id": user["user_id"], "created_at": {"$gte": _month_start_iso()},
        })
        if used >= BASIC_MONTHLY_EXPORTS:
            raise HTTPException(
                status_code=429,
                detail=f"Quota atteint : {BASIC_MONTHLY_EXPORTS} vidéos/mois avec le plan Basic. Passe en PRO pour exporter en illimité.",
            )
        await db.export_logs.insert_one({
            "user_id": user["user_id"], "tier": "basic", "created_at": iso(now_utc()),
        })
        return {"allowed": True, "used": used + 1, "quota": BASIC_MONTHLY_EXPORTS}
    await db.export_logs.insert_one({
        "user_id": user["user_id"], "tier": info["tier"], "created_at": iso(now_utc()),
    })
    return {"allowed": True, "used": None, "quota": None}


@api_router.get("/export/quota")
async def export_quota(user: dict = Depends(get_current_user)):
    info = sub_info(user)
    tier = info["tier"]
    if tier == "free":
        return {"tier": "free", "used": 0, "quota": 0, "paywall": True}
    if info.get("trial"):
        since = (user.get("subscription") or {}).get("started_at") or _month_start_iso()
        used = await db.export_logs.count_documents({"user_id": user["user_id"], "created_at": {"$gte": since}})
        return {"tier": tier, "used": used, "quota": TRIAL_EXPORT_CAP, "trial": True, "trial_end": info.get("trial_end")}
    if tier == "essentiel":
        used = await db.export_logs.count_documents({
            "user_id": user["user_id"], "created_at": {"$gte": _essentiel_period_start(user)},
        })
        return {"tier": "essentiel", "used": used, "quota": ESSENTIEL_MONTHLY_EXPORTS}
    if tier != "basic":
        return {"tier": tier, "used": None, "quota": None}
    used = await db.export_logs.count_documents({
        "user_id": user["user_id"], "created_at": {"$gte": _month_start_iso()},
    })
    return {"tier": "basic", "used": used, "quota": BASIC_MONTHLY_EXPORTS}


@api_router.post("/payments/activate-now")
async def activate_now(user: dict = Depends(get_current_user)):
    """Fin d'essai anticipée : démarre l'abonnement Pro immédiatement (débit immédiat, exports illimités)."""
    user = await sync_stripe_subscription(user)
    info = sub_info(user)
    sub = user.get("subscription") or {}
    if not (info.get("trial") and sub.get("stripe_subscription_id")):
        raise HTTPException(status_code=400, detail="Aucun essai en cours")
    try:
        s = await asyncio.to_thread(
            lambda: stripe.Subscription.modify(sub["stripe_subscription_id"], trial_end="now"))
    except Exception as e:
        logger.error("Fin d'essai anticipée : %s", e)
        raise HTTPException(status_code=502, detail="Erreur Stripe — réessaie") from e
    await _apply_stripe_sub_state(user["user_id"], s)
    return {"message": "Ton abonnement Pro est actif — exports illimités débloqués 🎉"}


# ---------------------------------------------------------------------------
# Studio (plan 499 €/an) — watermark personnalisé (logo PNG incrusté aux exports)
# ---------------------------------------------------------------------------
@api_router.post("/studio/watermark")
async def upload_watermark(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    info = sub_info(user)
    if info["tier"] != "studio":
        raise HTTPException(status_code=403, detail="Watermark personnalisé réservé au plan Studio")
    content = await file.read()
    if len(content) > 2_000_000:
        raise HTTPException(status_code=413, detail="Logo trop lourd (max 2 Mo)")
    if not content.startswith(b"\x89PNG"):
        raise HTTPException(status_code=400, detail="Le logo doit être un fichier PNG")
    old = user.get("watermark_media_id")
    media_id = await media_fs.upload_from_stream("watermark.png", content, metadata={
        "user_id": user["user_id"], "content_type": "image/png", "kind": "watermark",
        "created_at": iso(now_utc())})
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"watermark_media_id": str(media_id)}})
    if old:
        try:
            await media_fs.delete(ObjectId(old))
        except Exception:
            pass
    return {"ok": True}


@api_router.get("/studio/watermark")
async def get_watermark(user: dict = Depends(get_current_user)):
    mid = user.get("watermark_media_id")
    if not mid or sub_info(user)["tier"] != "studio":
        raise HTTPException(status_code=404, detail="Pas de watermark configuré")
    stream = await media_fs.open_download_stream(ObjectId(mid))
    data = await stream.read()
    return Response(content=data, media_type="image/png")


@api_router.delete("/studio/watermark")
async def delete_watermark(user: dict = Depends(get_current_user)):
    mid = user.get("watermark_media_id")
    if mid:
        try:
            await media_fs.delete(ObjectId(mid))
        except Exception:
            pass
        await db.users.update_one({"user_id": user["user_id"]}, {"$unset": {"watermark_media_id": ""}})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Onboarding (formulaire de bienvenue, 5 écrans)
# ---------------------------------------------------------------------------
ONBOARDING_FIELDS = ("persona", "genre", "release_timing", "current_method", "source")


@api_router.post("/onboarding")
async def save_onboarding(payload: dict, user: dict = Depends(get_current_user)):
    sets = {}
    for f in ONBOARDING_FIELDS:
        v = payload.get(f)
        if isinstance(v, str) and 0 < len(v) <= 40:
            sets[f"onboarding.{f}"] = v
    if payload.get("skipped_at") is not None:
        try:
            sets["onboarding.skipped_at"] = int(payload["skipped_at"])
        except (TypeError, ValueError):
            pass
    if payload.get("done"):
        sets["onboarding_done"] = True
        sets["onboarding.done_at"] = iso(now_utc())
    if sets:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": sets})
    return {"ok": True}


@api_router.post("/telemetry/onboarding")
async def telemetry_onboarding(payload: dict, user: dict = Depends(get_current_user)):
    event = str(payload.get("event") or "")[:40]
    if event:
        await db.onboarding_logs.insert_one({
            "user_id": user["user_id"], "event": event,
            "step": payload.get("step"), "at": iso(now_utc())})
    return {"ok": True}


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
    await db.separation_jobs.insert_one({
        "job_id": job_id, "user_id": user["user_id"],
        "status": "processing", "error": None, "result_url": None,
        "created_at": iso(now_utc()),
    })
    await db.separation_logs.insert_one({
        "user_id": user["user_id"], "job_id": job_id,
        "size": len(content), "created_at": iso(now_utc()),
    })
    asyncio.create_task(_run_separation(job_id, input_path))
    return {"id": job_id, "status": "processing"}


async def _get_job(job_id: str, user: dict) -> dict:
    job = await db.separation_jobs.find_one(
        {"job_id": job_id, "user_id": user["user_id"]}
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return job


@api_router.get("/separate/{job_id}")
async def separation_status(job_id: str, user: dict = Depends(get_current_user)):
    job = await _get_job(job_id, user)
    return {"id": job_id, "status": job["status"], "error": job.get("error")}


@api_router.get("/separate/{job_id}/result")
async def separation_result(job_id: str, user: dict = Depends(get_current_user)):
    job = await _get_job(job_id, user)
    if job["status"] != "done" or not job.get("result_url"):
        raise HTTPException(status_code=404, detail="Résultat indisponible")
    result_url = job["result_url"]

    async def stream_wav():
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as http:
            async with http.stream("GET", result_url) as r:
                r.raise_for_status()
                async for chunk in r.aiter_bytes():
                    yield chunk

    return StreamingResponse(
        stream_wav(),
        media_type="audio/wav",
        headers={"Content-Disposition": 'attachment; filename="acapella.wav"'},
    )


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


# ---------------------------------------------------------------------------
# LOT 4 — PROJETS & MÉDIAS (GridFS) : sauvegarde/reprise complète
# ---------------------------------------------------------------------------
import hashlib
from bson import ObjectId
from fastapi.responses import StreamingResponse as _SR  # alias local

PROJECT_QUOTAS = {"free": 1, "basic": 10, "essentiel": 20, "pro": None, "studio": None}   # None = illimité
STORAGE_QUOTAS = {"free": 200_000_000, "basic": 2_000_000_000, "essentiel": 5_000_000_000,
                  "pro": 10_000_000_000, "studio": 20_000_000_000}
MAX_MEDIA_SIZE = 300_000_000  # 300 Mo par fichier (les vidéos iPhone 4K dépassent vite 80 Mo)

# --- Transcodage vidéo (H.264 1080p, keyframes 0.5s, AAC, faststart) -------
import re as _re
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
TRANSCODE_SEM = asyncio.Semaphore(6)
_VIDEO_EXT_RE = _re.compile(r"\.(mp4|mov|m4v|webm|avi|mkv|3gp|hevc)$", _re.I)


def _is_video(content_type: str, filename: str) -> bool:
    if (content_type or "").lower().startswith("video/"):
        return True
    return bool(_VIDEO_EXT_RE.search(filename or ""))


async def _ffmpeg_transcode(src_bytes: bytes, suffix: str):
    """Retourne les octets MP4 optimisés, ou None si échec."""
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in" + (suffix or ".mp4"))
        dst = os.path.join(td, "out.mp4")
        with open(src, "wb") as f:
            f.write(src_bytes)
        cmd = [FFMPEG_EXE, "-y", "-i", src,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
               "-profile:v", "high", "-pix_fmt", "yuv420p",
               "-vf", "scale=w='min(1920,iw)':h='min(1920,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
               "-force_key_frames", "expr:gte(t,n_forced*0.5)",
               "-c:a", "aac", "-b:a", "128k", "-ac", "2",
               "-movflags", "+faststart", dst]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout=900)
        except asyncio.TimeoutError:
            proc.kill()
            return None
        if proc.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
            logger.warning("FFmpeg échec: %s", (err or b"")[-300:])
            return None
        with open(dst, "rb") as f:
            return f.read()


# --- Mux : transcodage externalisé (encodage "basic" gratuit, asset supprimé après) ---
MUX_TOKEN_ID = os.environ.get('MUX_TOKEN_ID', '')
MUX_TOKEN_SECRET = os.environ.get('MUX_TOKEN_SECRET', '')
MUX_API = "https://api.mux.com/video/v1"


async def _mux_create_upload(cx) -> dict | None:
    """Crée une URL d'upload Mux signée (repli encoding_tier=baseline si video_quality refusé)."""
    settings = {
        "playback_policies": ["public"],
        "video_quality": "basic",
        "max_resolution_tier": "1080p",
        "static_renditions": [{"resolution": "highest"}],
    }
    r = await cx.post(f"{MUX_API}/uploads", json={"cors_origin": "*", "new_asset_settings": settings})
    if r.status_code == 400 and "video_quality" in r.text:
        settings.pop("video_quality")
        settings["encoding_tier"] = "baseline"
        r = await cx.post(f"{MUX_API}/uploads", json={"cors_origin": "*", "new_asset_settings": settings})
    if r.status_code >= 300:
        logger.warning("Mux upload create %s : %s", r.status_code, r.text[:300])
        return None
    return r.json()["data"]


async def _mux_wait_asset_id(cx, upload_id: str) -> str | None:
    for _ in range(60):
        r = await cx.get(f"{MUX_API}/uploads/{upload_id}")
        d = r.json().get("data") or {}
        if d.get("asset_id"):
            return d["asset_id"]
        if d.get("status") in ("errored", "cancelled", "timed_out"):
            logger.warning("Mux upload status : %s", d.get("status"))
            return None
        await asyncio.sleep(2)
    return None


async def _mux_wait_mp4(cx, asset_id: str) -> tuple:
    """Attend asset ready + rendition MP4 prête. Retourne (playback_id, mp4_name) ou (None, None)."""
    for _ in range(200):
        r = await cx.get(f"{MUX_API}/assets/{asset_id}")
        a = r.json().get("data") or {}
        if a.get("status") == "errored":
            logger.warning("Mux asset errored : %s", a.get("errors"))
            return None, None
        if a.get("status") == "ready":
            pids = a.get("playback_ids") or []
            playback_id = pids[0]["id"] if pids else None
            files = ((a.get("static_renditions") or {}).get("files")) or []
            ready = [f for f in files if str(f.get("name", "")).endswith(".mp4")
                     and f.get("status", "ready") in ("ready", "skipped")]
            ready = [f for f in ready if f.get("status", "ready") == "ready"]
            if ready and playback_id:
                return playback_id, ready[0]["name"]
        await asyncio.sleep(3)
    return None, None


async def _mux_transcode(src_bytes: bytes):
    """Upload vers Mux → asset H.264 1080p max → télécharge le MP4 → supprime l'asset.
    Retourne les octets MP4, ou None si échec (repli FFmpeg local)."""
    if not MUX_TOKEN_ID or not MUX_TOKEN_SECRET:
        return None
    asset_id = None
    auth = (MUX_TOKEN_ID, MUX_TOKEN_SECRET)
    try:
        async with httpx.AsyncClient(auth=auth, timeout=120) as cx:
            up = await _mux_create_upload(cx)
            if not up:
                return None
            # Envoi du fichier (client sans auth : l'URL d'upload est déjà signée)
            async with httpx.AsyncClient(timeout=300) as plain:
                pr = await plain.put(up["url"], content=src_bytes,
                                     headers={"Content-Type": "application/octet-stream"})
                if pr.status_code >= 300:
                    logger.warning("Mux upload PUT %s", pr.status_code)
                    return None
            asset_id = await _mux_wait_asset_id(cx, up["id"])
            if not asset_id:
                return None
            playback_id, mp4_name = await _mux_wait_mp4(cx, asset_id)
            if not (mp4_name and playback_id):
                logger.warning("Mux : rendition MP4 non prête (asset %s)", asset_id)
                return None
            async with httpx.AsyncClient(timeout=300, follow_redirects=True) as plain:
                dl = await plain.get(f"https://stream.mux.com/{playback_id}/{mp4_name}")
                if dl.status_code >= 300 or not dl.content:
                    logger.warning("Mux download %s", dl.status_code)
                    return None
                logger.info("Transcodage Mux OK (asset %s) : %d → %d octets", asset_id, len(src_bytes), len(dl.content))
                return dl.content
    except Exception:
        logger.exception("Transcodage Mux échoué")
        return None
    finally:
        if asset_id:
            try:
                async with httpx.AsyncClient(auth=auth, timeout=60) as cx:
                    await cx.delete(f"{MUX_API}/assets/{asset_id}")
            except Exception:
                logger.warning("Suppression asset Mux %s impossible (à nettoyer)", asset_id)


async def _probe_video(src_bytes: bytes, suffix: str):
    """Sonde rapide (ffmpeg -i) : codec vidéo, dimensions, durée. None si illisible."""
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in" + (suffix or ".mp4"))
        with open(src, "wb") as f:
            f.write(src_bytes)
        proc = await asyncio.create_subprocess_exec(
            FFMPEG_EXE, "-hide_banner", "-i", src,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            return None
    out = (err or b"").decode("utf-8", "ignore")
    m_v = _re.search(r"Video:\s*(\w+).*?(\d{2,5})x(\d{2,5})", out)
    m_d = _re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out)
    if not m_v:
        return None
    dur = 0.0
    if m_d:
        dur = int(m_d.group(1)) * 3600 + int(m_d.group(2)) * 60 + float(m_d.group(3))
    return {"codec": m_v.group(1).lower(), "w": int(m_v.group(2)), "h": int(m_v.group(3)), "duration": dur}


async def _transcode_media(oid):
    """Remplace le fichier GridFS par sa version optimisée (même _id conservé).
    Transcodage via Mux (rapide, externalisé) avec repli FFmpeg local."""
    async with TRANSCODE_SEM:
        doc = await db["media.files"].find_one({"_id": oid})
        if not doc:
            return
        meta = doc.get("metadata") or {}
        try:
            grid_out = await media_fs.open_download_stream(oid)
            raw = await grid_out.read()
            suffix = os.path.splitext(doc.get("filename") or "")[1]
            # Déjà propre (H.264 ≤1080p, débit raisonnable) ? → rien à faire : optimisation instantanée
            probe = await _probe_video(raw, suffix)
            if probe and probe["codec"] == "h264" and min(probe["w"], probe["h"]) <= 1080:
                bitrate = (len(raw) * 8 / probe["duration"]) if probe["duration"] > 0 else 0
                if 0 < bitrate <= 12_000_000:
                    await db["media.files"].update_one(
                        {"_id": oid},
                        {"$set": {"metadata.transcoded": True, "metadata.processing": False,
                                  "metadata.transcode_skipped": True}})
                    logger.info("Transcodage sauté %s : déjà H.264 %dx%d @ %.1f Mbps",
                                oid, probe["w"], probe["h"], bitrate / 1e6)
                    return
            out = await _mux_transcode(raw)
            if not out:
                out = await _ffmpeg_transcode(raw, suffix)
            if out:
                fname = os.path.splitext(doc.get("filename") or "media")[0] + ".mp4"
                new_meta = {**meta, "content_type": "video/mp4", "transcoded": True, "processing": False}
                await media_fs.delete(oid)
                await media_fs.upload_from_stream_with_id(oid, fname, out, metadata=new_meta)
                logger.info("Transcodage OK %s : %d → %d octets", oid, len(raw), len(out))
                return
        except Exception:
            logger.exception("Transcodage échoué %s", oid)
        await db["media.files"].update_one(
            {"_id": oid},
            {"$set": {"metadata.processing": False, "metadata.transcode_failed": True}})

async def _storage_used(user_id: str) -> int:
    pipeline = [
        {"$match": {"metadata.user_id": user_id}},
        {"$group": {"_id": None, "total": {"$sum": "$length"}}},
    ]
    rows = await db["media.files"].aggregate(pipeline).to_list(1)
    return rows[0]["total"] if rows else 0


@api_router.get("/media/quota")
async def media_quota(user: dict = Depends(get_current_user)):
    info = sub_info(user)
    used = await _storage_used(user["user_id"])
    return {"tier": info["tier"], "used": used, "quota": STORAGE_QUOTAS[info["tier"]]}


async def _store_media(user: dict, content: bytes, filename: str, content_type: str) -> dict:
    if len(content) > MAX_MEDIA_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop lourd (max 80 Mo)")
    info = sub_info(user)
    sha = hashlib.sha256(content).hexdigest()
    # Dédup : même fichier déjà stocké pour cet utilisateur → on renvoie l'existant
    existing = await db["media.files"].find_one(
        {"metadata.user_id": user["user_id"], "metadata.sha256": sha}
    )
    if existing:
        emeta = existing.get("metadata") or {}
        return {"media_id": str(existing["_id"]), "size": existing["length"], "deduped": True,
                "processing": bool(emeta.get("processing"))}
    used = await _storage_used(user["user_id"])
    if used + len(content) > STORAGE_QUOTAS[info["tier"]]:
        quota_mb = STORAGE_QUOTAS[info["tier"]] // 1_000_000
        raise HTTPException(
            status_code=413,
            detail=f"Stockage plein ({quota_mb} Mo sur ton plan). Supprime un projet ou passe au plan supérieur.",
        )
    is_video = _is_video(content_type, filename)
    if is_video and info["tier"] == "free":
        nvids = await db["media.files"].count_documents({
            "metadata.user_id": user["user_id"],
            "metadata.content_type": {"$regex": "^video"},
        })
        if nvids >= 5:
            raise HTTPException(status_code=403,
                                detail="5 clips maximum sans abonnement — débloque tout avec ton essai Pro (7 jours offerts).")
    media_id = await media_fs.upload_from_stream(
        filename or "media",
        content,
        metadata={
            "user_id": user["user_id"], "sha256": sha,
            "content_type": content_type or "application/octet-stream",
            "created_at": iso(now_utc()),
            "processing": is_video,
        },
    )
    if is_video:
        asyncio.create_task(_transcode_media(media_id))
    return {"media_id": str(media_id), "size": len(content), "deduped": False, "processing": is_video}


@api_router.post("/media/upload")
async def media_upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    content = await file.read()
    return await _store_media(user, content, file.filename or "media", file.content_type or "")


@api_router.post("/media/import-url")
async def media_import_url(payload: dict, user: dict = Depends(get_current_user)):
    """Import serveur d'un clip Pexels : téléchargement + transcodage sans re-upload client."""
    from urllib.parse import urlparse
    url = (payload.get("url") or "").strip()
    name = (payload.get("name") or "").strip() or "clip.mp4"
    host = (urlparse(url).hostname or "") if url else ""
    if not url.startswith("https://") or not (host == "pexels.com" or host.endswith(".pexels.com")):
        raise HTTPException(status_code=400, detail="URL non autorisée")
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as cx:
            r = await cx.get(url)
    except Exception:
        raise HTTPException(status_code=502, detail="Clip indisponible — réessaie")
    if r.status_code != 200 or not r.content:
        raise HTTPException(status_code=502, detail="Clip indisponible — réessaie")
    return await _store_media(user, r.content, name, r.headers.get("content-type") or "video/mp4")


IMPORT_LINK_JOBS: dict = {}


def _link_host_ok(url: str) -> bool:
    from urllib.parse import urlparse
    import ipaddress
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        host = p.hostname.lower()
        if host in ("localhost",) or host.endswith(".local") or host.endswith(".internal"):
            return False
        try:
            if ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback:
                return False
        except ValueError:
            pass
        return True
    except Exception:
        return False


async def _run_import_link(job_id: str, url: str, user: dict):
    job = IMPORT_LINK_JOBS[job_id]
    tmpdir = tempfile.mkdtemp(prefix="bc_link_")
    try:
        job["status"] = "downloading"
        import nodejs_wheel
        import imageio_ffmpeg
        node_bin = os.path.join(os.path.dirname(nodejs_wheel.__file__), "bin", "node")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "yt_dlp",
            "--js-runtimes", f"node:{node_bin}",
            "--ffmpeg-location", imageio_ffmpeg.get_ffmpeg_exe(),
            "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
            "--merge-output-format", "mp4", "--max-filesize", "78M",
            "--no-playlist", "--restrict-filenames", "--no-progress",
            "-o", os.path.join(tmpdir, "%(title).60s.%(ext)s"), url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout=240)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("Téléchargement trop long — vidéo trop lourde ?")
        files = [f for f in os.listdir(tmpdir) if not f.endswith((".part", ".ytdl"))]
        if proc.returncode != 0 or not files:
            msg = (err or b"").decode(errors="ignore")[-500:]
            if "max-filesize" in msg or "File is larger" in msg:
                raise RuntimeError("Vidéo trop lourde (max ~78 Mo) — choisis une vidéo plus courte")
            logger.warning("yt-dlp échec %s : %s", url[:80], msg)
            if "youtube" in url.lower() or "youtu.be" in url.lower():
                raise RuntimeError("YouTube bloque parfois les téléchargements depuis nos serveurs — réessaie, ou utilise un lien TikTok/Vimeo/.mp4 direct, ou télécharge la vidéo puis dépose le fichier")
            raise RuntimeError("Lien non téléchargeable — vérifie qu'il pointe vers une vidéo publique")
        path = os.path.join(tmpdir, files[0])
        with open(path, "rb") as fh:
            content = fh.read()
        job["status"] = "storing"
        stored = await _store_media(user, content, files[0], "video/mp4")
        job.update({"status": "done", "media_id": stored["media_id"], "filename": files[0]})
    except HTTPException as e:
        job.update({"status": "error", "error": e.detail})
    except Exception as e:
        job.update({"status": "error", "error": str(e)[:200]})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@api_router.post("/media/import-link")
async def media_import_link(payload: dict, user: dict = Depends(get_current_user)):
    """Import d'une vidéo par lien (YouTube & co) via yt-dlp, en tâche de fond."""
    url = (payload.get("url") or "").strip()
    if not _link_host_ok(url):
        raise HTTPException(status_code=400, detail="Lien invalide — colle une URL https vers une vidéo")
    if len(IMPORT_LINK_JOBS) > 500:
        IMPORT_LINK_JOBS.clear()
    job_id = uuid.uuid4().hex[:16]
    IMPORT_LINK_JOBS[job_id] = {"status": "queued", "user_id": user["user_id"]}
    asyncio.create_task(_run_import_link(job_id, url, user))
    return {"job_id": job_id}


@api_router.get("/media/import-link/{job_id}")
async def media_import_link_status(job_id: str, user: dict = Depends(get_current_user)):
    job = IMPORT_LINK_JOBS.get(job_id)
    if not job or job.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=404, detail="Import introuvable")
    return {k: v for k, v in job.items() if k != "user_id"}


@api_router.get("/media/mine")
async def media_mine(user: dict = Depends(get_current_user)):
    """Liste des médias de l'utilisateur (récupération de vidéos orphelines dans le studio)."""
    docs = await db["media.files"].find(
        {"metadata.user_id": user["user_id"]},
        {"filename": 1, "length": 1, "uploadDate": 1, "metadata.content_type": 1, "metadata.transcoded": 1},
    ).sort("uploadDate", -1).to_list(1000)
    return {"media": [{
        "media_id": str(d["_id"]), "filename": d.get("filename"),
        "size": d.get("length"),
        "content_type": ((d.get("metadata") or {}).get("content_type")) or "",
        "transcoded": bool(((d.get("metadata") or {}).get("transcoded"))),
    } for d in docs]}


@api_router.get("/media/{media_id}")
async def media_download(media_id: str, user: dict = Depends(get_current_user)):
    try:
        oid = ObjectId(media_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID média invalide")
    doc = await db["media.files"].find_one({"_id": oid, "metadata.user_id": user["user_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Média introuvable")

    async def stream():
        grid_out = await media_fs.open_download_stream(oid)
        while True:
            chunk = await grid_out.readchunk()
            if not chunk:
                break
            yield chunk

    return _SR(
        stream(),
        media_type=doc.get("metadata", {}).get("content_type", "application/octet-stream"),
        headers={"Content-Length": str(doc["length"]),
                 "Content-Disposition": f'inline; filename="{doc.get("filename","media")}"'},
    )


@api_router.get("/media/{media_id}/status")
async def media_status(media_id: str, user: dict = Depends(get_current_user)):
    try:
        oid = ObjectId(media_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID média invalide")
    doc = await db["media.files"].find_one({"_id": oid, "metadata.user_id": user["user_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Média introuvable")
    meta = doc.get("metadata") or {}
    return {"processing": bool(meta.get("processing")), "transcoded": bool(meta.get("transcoded")),
            "skipped": bool(meta.get("transcode_skipped")),
            "failed": bool(meta.get("transcode_failed")), "size": doc["length"]}


# --- Migration : transcode les vidéos GridFS existantes (admin) ------------
MIGRATION_STATE = {"running": False, "total": 0, "done": 0, "failed": 0}


def _migration_query():
    return {
        "$and": [
            {"metadata.transcoded": {"$ne": True}},
            {"metadata.transcode_failed": {"$ne": True}},
            {"$or": [
                {"metadata.content_type": {"$regex": "^video/"}},
                {"filename": {"$regex": r"\.(mp4|mov|m4v|webm|avi|mkv|3gp)$", "$options": "i"}},
            ]},
        ]
    }


async def _run_media_migration(ids):
    for oid in ids:
        try:
            await _transcode_media(oid)
            doc = await db["media.files"].find_one({"_id": oid}, {"metadata.transcoded": 1})
            ok = bool(((doc or {}).get("metadata") or {}).get("transcoded"))
            MIGRATION_STATE["done" if ok else "failed"] += 1
        except Exception:
            MIGRATION_STATE["failed"] += 1
    MIGRATION_STATE["running"] = False
    logger.info("Migration médias terminée : %s", MIGRATION_STATE)


@api_router.post("/admin/media/migrate")
async def admin_media_migrate(user: dict = Depends(get_current_user)):
    await require_admin(user)
    if MIGRATION_STATE["running"]:
        return MIGRATION_STATE
    ids = [d["_id"] async for d in db["media.files"].find(_migration_query(), {"_id": 1})]
    MIGRATION_STATE.update({"running": bool(ids), "total": len(ids), "done": 0, "failed": 0})
    if ids:
        asyncio.create_task(_run_media_migration(ids))
    return MIGRATION_STATE


@api_router.get("/admin/media/migrate")
async def admin_media_migrate_status(user: dict = Depends(get_current_user)):
    await require_admin(user)
    return MIGRATION_STATE


@api_router.post("/export/finalize")
async def export_finalize(video: UploadFile = File(...), audio: UploadFile = File(...),
                          user: dict = Depends(get_current_user)):
    """Assemble le MP4 vidéo (encodé côté client via WebCodecs) avec la piste audio WAV.
    Utilisé par Safari (pas d'AudioEncoder) : -c:v copy → zéro ré-encodage vidéo, très rapide."""
    v = await video.read()
    a = await audio.read()
    if not v or not a:
        raise HTTPException(status_code=400, detail="Fichiers manquants")
    if len(v) > 500_000_000 or len(a) > 100_000_000:
        raise HTTPException(status_code=413, detail="Export trop volumineux")
    with tempfile.TemporaryDirectory() as td:
        vp, ap, op = os.path.join(td, "v.mp4"), os.path.join(td, "a.wav"), os.path.join(td, "out.mp4")
        with open(vp, "wb") as f:
            f.write(v)
        with open(ap, "wb") as f:
            f.write(a)
        cmd = [FFMPEG_EXE, "-y", "-i", vp, "-i", ap,
               "-map", "0:v:0", "-map", "1:a:0",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-shortest", "-movflags", "+faststart", op]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(status_code=504, detail="Assemblage trop long — réessaie")
        if proc.returncode != 0 or not os.path.exists(op):
            logger.warning("export_finalize ffmpeg : %s", (err or b"")[-300:])
            raise HTTPException(status_code=500, detail="Assemblage audio impossible")
        with open(op, "rb") as f:
            out = f.read()
    return Response(content=out, media_type="video/mp4")


def _project_media_ids(state: dict) -> set:
    ids = set()
    audio = (state or {}).get("audio") or {}
    if audio.get("mediaId"):
        ids.add(audio["mediaId"])
    for c in (state or {}).get("clips") or []:
        if c.get("mediaId"):
            ids.add(c["mediaId"])
    return ids


def _refs_count(st) -> int:
    return len([c for c in ((st or {}).get("clipRefs") or []) if c.get("mediaId") or c.get("pexelsUrl")])


async def _backup_project(doc, reason="auto"):
    """Snapshot de l'état courant dans project_backups (15 versions max par projet)."""
    await db.project_backups.insert_one({
        "backup_id": uuid.uuid4().hex[:10], "project_id": doc["project_id"], "user_id": doc["user_id"],
        "title": doc.get("title"), "state": doc.get("state"),
        "state_updated_at": doc.get("updated_at"), "created_at": iso(now_utc()), "reason": reason,
    })
    old = [d["_id"] async for d in db.project_backups.find(
        {"project_id": doc["project_id"]}, {"_id": 1}).sort("created_at", -1).skip(15)]
    if old:
        await db.project_backups.delete_many({"_id": {"$in": old}})


async def _maybe_backup_project(existing, new_state):
    old_n, new_n = _refs_count(existing.get("state")), _refs_count(new_state)
    losing = new_n < old_n
    last = await db.project_backups.find_one(
        {"project_id": existing["project_id"]}, {"created_at": 1}, sort=[("created_at", -1)])
    stale = (not last) or (parse_dt(last["created_at"]) < now_utc() - timedelta(minutes=10))
    if losing or stale:
        await _backup_project(existing, "perte-de-clips" if losing else "auto")


@api_router.get("/projects")
async def list_projects(user: dict = Depends(get_current_user)):
    docs = await db.projects.find(
        {"user_id": user["user_id"]},
        {"_id": 0, "state": 0},
    ).sort("updated_at", -1).to_list(200)
    info = sub_info(user)
    return {"projects": docs, "count": len(docs), "quota": PROJECT_QUOTAS[info["tier"]]}


@api_router.post("/projects")
async def save_project(payload: dict, user: dict = Depends(get_current_user)):
    """Upsert : payload = {project_id?, title, state, thumb?}"""
    state = payload.get("state")
    if not isinstance(state, dict):
        raise HTTPException(status_code=400, detail="État du projet manquant")
    title = (payload.get("title") or "Sans titre")[:120]
    thumb = payload.get("thumb") or None
    if thumb and len(thumb) > 120_000:
        thumb = None  # vignette trop lourde : on l'ignore
    project_id = payload.get("project_id")
    now = iso(now_utc())
    if project_id:
        existing = await db.projects.find_one({"project_id": project_id, "user_id": user["user_id"]})
        if not existing:
            raise HTTPException(status_code=404, detail="Projet introuvable")
        await _maybe_backup_project(existing, state)
        res = await db.projects.update_one(
            {"project_id": project_id, "user_id": user["user_id"]},
            {"$set": {"title": title, "state": state, "updated_at": now,
                      **({"thumb": thumb} if thumb else {})}},
        )
        if not res.matched_count:
            raise HTTPException(status_code=404, detail="Projet introuvable")
        return {"project_id": project_id, "updated_at": now}
    # Création → quota projets
    info = sub_info(user)
    quota = PROJECT_QUOTAS[info["tier"]]
    if quota is not None:
        count = await db.projects.count_documents({"user_id": user["user_id"]})
        if count >= quota:
            raise HTTPException(
                status_code=429,
                detail=f"Limite de {quota} projet{'s' if quota>1 else ''} atteinte sur ton plan. Supprime un projet ou passe au plan supérieur.",
            )
    project_id = uuid.uuid4().hex[:14]
    await db.projects.insert_one({
        "project_id": project_id, "user_id": user["user_id"],
        "title": title, "state": state, "thumb": thumb,
        "created_at": now, "updated_at": now,
    })
    return {"project_id": project_id, "updated_at": now}


@api_router.get("/projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    doc = await db.projects.find_one(
        {"project_id": project_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    return doc


@api_router.get("/projects/{project_id}/backups")
async def list_project_backups(project_id: str, user: dict = Depends(get_current_user)):
    docs = await db.project_backups.find(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"_id": 0, "backup_id": 1, "created_at": 1, "title": 1, "state": 1, "reason": 1},
    ).sort("created_at", -1).to_list(20)
    return {"backups": [{
        "backup_id": d["backup_id"], "created_at": d["created_at"], "title": d.get("title"),
        "reason": d.get("reason"), "clips": _refs_count(d.get("state")),
        "plans": len(((d.get("state") or {}).get("plans")) or []),
    } for d in docs]}


@api_router.post("/projects/{project_id}/backups/{backup_id}/restore")
async def restore_project_backup(project_id: str, backup_id: str, user: dict = Depends(get_current_user)):
    bk = await db.project_backups.find_one(
        {"project_id": project_id, "backup_id": backup_id, "user_id": user["user_id"]})
    if not bk:
        raise HTTPException(status_code=404, detail="Version introuvable")
    cur = await db.projects.find_one({"project_id": project_id, "user_id": user["user_id"]})
    if not cur:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    await _backup_project(cur, "avant-restauration")
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"state": bk["state"], "title": bk.get("title") or cur.get("title"),
                  "updated_at": iso(now_utc())}})
    return {"restored": True}


@api_router.post("/projects/{project_id}/duplicate")
async def duplicate_project(project_id: str, user: dict = Depends(get_current_user)):
    doc = await db.projects.find_one(
        {"project_id": project_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    info = sub_info(user)
    quota = PROJECT_QUOTAS[info["tier"]]
    if quota is not None:
        count = await db.projects.count_documents({"user_id": user["user_id"]})
        if count >= quota:
            raise HTTPException(status_code=429, detail=f"Limite de {quota} projet(s) atteinte — passe au plan supérieur.")
    new_id = uuid.uuid4().hex[:14]
    now = iso(now_utc())
    await db.projects.insert_one({
        **doc, "project_id": new_id,
        "title": (doc["title"] + " (copie)")[:120],
        "created_at": now, "updated_at": now,
    })
    return {"project_id": new_id}


@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    doc = await db.projects.find_one(
        {"project_id": project_id, "user_id": user["user_id"]}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    media_ids = _project_media_ids(doc.get("state") or {})
    await db.projects.delete_one({"project_id": project_id, "user_id": user["user_id"]})
    # Supprime les médias qui ne sont référencés par AUCUN autre projet
    deleted_media = 0
    if media_ids:
        others = await db.projects.find(
            {"user_id": user["user_id"]}, {"_id": 0, "state": 1}
        ).to_list(500)
        still_used = set()
        for o in others:
            still_used |= _project_media_ids(o.get("state") or {})
        for mid in media_ids - still_used:
            try:
                await media_fs.delete(ObjectId(mid))
                deleted_media += 1
            except Exception:
                pass
    return {"message": "Projet supprimé", "media_deleted": deleted_media}


_STRIPE_STATS_CACHE = {"at": None, "data": None}


def _sub_monthly_cents(s) -> float:
    """Montant mensuel (centimes) d'une souscription Stripe, remise coupon incluse."""
    monthly = 0.0
    for it in ((s.get("items") or {}).get("data") or []):
        price = it.get("price") or {}
        amount = float((price.get("unit_amount") or 0) * (it.get("quantity") or 1))
        rec = price.get("recurring") or {}
        interval, cnt = rec.get("interval"), rec.get("interval_count") or 1
        if interval == "year":
            amount /= 12 * cnt
        elif interval == "month":
            amount /= cnt
        elif interval == "week":
            amount = amount * 4.345 / cnt
        elif interval == "day":
            amount = amount * 30.44 / cnt
        monthly += amount
    coupon = ((s.get("discount") or {}).get("coupon") or {})
    if coupon.get("percent_off"):
        monthly *= 1 - coupon["percent_off"] / 100.0
    elif coupon.get("amount_off"):
        monthly = max(0.0, monthly - coupon["amount_off"])
    return monthly


def _stripe_mrr_cents() -> tuple:
    mrr_cents = 0.0
    active_count = 0
    for s in stripe.Subscription.list(status="active", limit=100).auto_paging_iter():
        active_count += 1
        mrr_cents += _sub_monthly_cents(s)
    return mrr_cents, active_count


def _stripe_charge_totals(month_start: int) -> tuple:
    total_cents = month_cents = 0
    n = 0
    for ch in stripe.Charge.list(limit=100).auto_paging_iter():
        n += 1
        if n > 5000:
            break
        if ch.get("status") != "succeeded":
            continue
        net = (ch.get("amount") or 0) - (ch.get("amount_refunded") or 0)
        total_cents += net
        if (ch.get("created") or 0) >= month_start:
            month_cents += net
    return total_cents, month_cents


async def _stripe_revenue_stats() -> dict:
    """MRR réel + encaissements calculés directement depuis Stripe (source de vérité)."""
    now = now_utc()
    if _STRIPE_STATS_CACHE["data"] and (now - _STRIPE_STATS_CACHE["at"]) < timedelta(minutes=10):
        return _STRIPE_STATS_CACHE["data"]

    def compute():
        mrr_cents, active_count = _stripe_mrr_cents()
        trialing_count = 0
        for _ in stripe.Subscription.list(status="trialing", limit=100).auto_paging_iter():
            trialing_count += 1
        month_start = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
        total_cents, month_cents = _stripe_charge_totals(month_start)
        return {
            "stripe_mrr": round(mrr_cents / 100.0, 2),
            "stripe_active_subs": active_count,
            "stripe_trialing_subs": trialing_count,
            "revenue_this_month": round(month_cents / 100.0, 2),
            "revenue_total": round(total_cents / 100.0, 2),
        }

    try:
        data = await asyncio.to_thread(compute)
    except Exception as e:
        logger.warning("Stats Stripe indisponibles : %s", e)
        return {"stripe_mrr": None, "stripe_active_subs": None, "stripe_trialing_subs": None,
                "revenue_this_month": None, "revenue_total": None}
    _STRIPE_STATS_CACHE.update({"at": now, "data": data})
    return data


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
    active_paid = {
        "subscription.status": {"$in": ["active", "canceled"]},
        "subscription.current_period_end": {"$gt": iso(now_utc())},
    }
    # Payants réels : abonnement Stripe actif. Les accès offerts via code promo
    # n'ont pas de stripe_subscription_id → exclus du MRR et du compteur payant.
    real_paid_filter = {**active_paid, "subscription.stripe_subscription_id": {"$nin": [None, ""]}}
    real_paid = await db.users.count_documents(real_paid_filter)
    promo_active = max(0, paid_users - real_paid)  # actifs sans Stripe = promo / offert
    # Répartition par plan (payants réels actifs) — anciens et nouveaux plans séparés
    plans = {}
    for key in ("essentiel", "pro_monthly", "pro_yearly", "studio", "basic", "yearly"):
        plans[key] = await db.users.count_documents({**real_paid_filter, "subscription.plan": key})
    plans["monthly"] = max(0, real_paid - sum(plans.values()))  # legacy PRO mensuel (plan par défaut)
    # Essai gratuit 7 jours : en cours / démarrés / convertis en payant réel
    trial_users = await db.users.count_documents({
        "subscription.status": "trialing",
        "subscription.current_period_end": {"$gt": iso(now_utc())},
    })
    trial_started = await db.users.count_documents({"trial_used": True})
    trial_converted = await db.users.count_documents({**real_paid_filter, "trial_used": True})
    trial_conversion_rate = round(trial_converted / trial_started * 100) if trial_started else None
    # MRR : uniquement les payants réels — annuels comptés au prorata mensuel
    mrr = round(
        plans["monthly"] * PRO_PRICE + plans["basic"] * BASIC_PRICE + plans["yearly"] * (PRO_PRICE_YEAR / 12)
        + plans["essentiel"] * (ESSENTIEL_PRICE_CENTS / 100)
        + plans["pro_monthly"] * (PRO2_PRICE_CENTS / 100)
        + plans["pro_yearly"] * (PRO2_YEAR_CENTS / 100 / 12)
        + plans["studio"] * (STUDIO_YEAR_CENTS / 100 / 12), 2)
    # Séparations du mois
    start_month = iso(now_utc().replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    sep_count = await db.separation_logs.count_documents({"created_at": {"$gt": start_month}})
    est_sep_cost = round(sep_count * 0.015, 2)
    promos = await db.promo_codes.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    # Formulaire d'annulation : répartition des raisons (%) + efficacité de l'offre −50 %
    fb_total = await db.cancel_feedback.count_documents({})
    fb_reasons = {}
    if fb_total:
        async for g in db.cancel_feedback.aggregate([{"$group": {"_id": "$reason", "n": {"$sum": 1}}}]):
            fb_reasons[g["_id"]] = {"count": g["n"], "pct": round(g["n"] / fb_total * 100)}
    fb_retained = await db.cancel_feedback.count_documents({"retained": True})
    fb_lost = await db.cancel_feedback.count_documents({"retained": False})
    fb_recent = await db.cancel_feedback.find(
        {}, {"_id": 0, "email": 1, "reason": 1, "comment": 1, "retained": 1, "at": 1, "plan": 1},
    ).sort("at", -1).to_list(20)
    cancel_fb = {
        "total": fb_total,
        "reasons": fb_reasons,
        "retained": fb_retained,
        "lost": fb_lost,
        "retained_pct": round(fb_retained / fb_total * 100) if fb_total else None,
        "recent": fb_recent,
    }
    stripe_stats = await _stripe_revenue_stats()
    return {
        "total_users": total_users,
        "paid_users": paid_users,
        "real_paid_users": real_paid,
        "promo_active_users": promo_active,
        "canceled": canceled,
        "google_users": google_users,
        "password_users": pwd_users,
        "monthly_subscribers": plans["monthly"],
        "basic_subscribers": plans["basic"],
        "yearly_subscribers": plans["yearly"],
        "plans": plans,
        "trial_users": trial_users,
        "trial_started": trial_started,
        "trial_converted": trial_converted,
        "trial_conversion_rate": trial_conversion_rate,
        "mrr": mrr,
        **stripe_stats,
        "separations_this_month": sep_count,
        "estimated_separation_cost_eur": est_sep_cost,
        "promo_codes": promos,
        "cancel_feedback": cancel_fb,
    }


@api_router.get("/admin/cancellations")
async def admin_cancellations(user: dict = Depends(get_current_user)):
    """Suivi des annulations : qui a annulé, quand, et jusqu'à quand l'accès court."""
    await require_admin(user)
    docs = await db.users.find(
        {"$or": [
            {"subscription.canceled_at": {"$exists": True}},
            {"subscription.status": "canceled"},
        ]},
        {"_id": 0, "email": 1, "name": 1, "subscription": 1},
    ).to_list(5000)
    rows = []
    for u in docs:
        sub = u.get("subscription") or {}
        end = parse_dt(sub.get("current_period_end"))
        still = sub.get("status") == "canceled" and end is not None and end > now_utc()
        rows.append({
            "email": u.get("email"),
            "name": u.get("name"),
            "plan": PLAN_LABELS.get(sub.get("plan"), sub.get("plan") or "—"),
            "was_trial": bool(sub.get("was_trial")),
            "canceled_at": sub.get("canceled_at"),
            "access_until": sub.get("current_period_end"),
            "state": "access_until_end" if still else "ended",
        })
    rows.sort(key=lambda r: r.get("canceled_at") or "", reverse=True)
    return {"count": len(rows), "cancellations": rows}


@api_router.get("/admin/onboarding-stats")
async def admin_onboarding_stats(user: dict = Depends(get_current_user)):
    """Stats onboarding : funnel du tutoriel studio + réponses au questionnaire."""
    await require_admin(user)
    tuto = {}
    for key, ev in (("started", "mobtuto_start"), ("done", "mobtuto_done"), ("skipped", "mobtuto_skipped")):
        tuto[key] = len(await db.onboarding_logs.distinct("user_id", {"event": ev}))
    tuto["completion_pct"] = round(tuto["done"] / tuto["started"] * 100) if tuto["started"] else None
    answers = {}
    for field in ONBOARDING_FIELDS:
        rows_f = await db.users.aggregate([
            {"$match": {f"onboarding.{field}": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": f"$onboarding.{field}", "count": {"$sum": 1}}},
        ]).to_list(50)
        total = sum(r["count"] for r in rows_f)
        answers[field] = {
            "total": total,
            "options": {r["_id"]: {"count": r["count"], "pct": round(r["count"] / total * 100)} for r in rows_f if r["_id"]},
        }
    form_done = await db.users.count_documents({"onboarding.done_at": {"$exists": True}})
    form_skipped = await db.users.count_documents({"onboarding.skipped_at": {"$exists": True}})
    return {"tuto": tuto, "form": {"done": form_done, "skipped": form_skipped}, "answers": answers}


@api_router.get("/admin/users")
async def admin_all_users(user: dict = Depends(get_current_user)):
    """Liste complète de tous les inscrits (email, plan, promo, date)."""
    await require_admin(user)
    docs = await db.users.find(
        {},
        {"_id": 0, "email": 1, "name": 1, "auth_provider": 1, "created_at": 1, "subscription": 1, "role": 1, "onboarding": 1},
    ).sort("created_at", -1).to_list(50000)
    users = []
    for u in docs:
        info = sub_info(u)
        sub = u.get("subscription") or {}
        users.append({
            "email": u.get("email"),
            "name": u.get("name"),
            "provider": u.get("auth_provider"),
            "created_at": u.get("created_at"),
            "tier": info["tier"],
            "plan": info["plan"],
            "promo": sub.get("promo_applied"),
            "paying": bool(sub.get("stripe_subscription_id")) and info["is_pro"],
            "role": u.get("role"),
            "onboarding": u.get("onboarding") or {},
        })
    return {"count": len(users), "users": users}


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


@api_router.delete("/admin/promo/{code}")
async def admin_delete_promo(code: str, user: dict = Depends(get_current_user)):
    await require_admin(user)
    norm = _normalize_promo(code)
    res = await db.promo_codes.delete_one({"code": norm})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Code introuvable")
    # Mémorise la suppression : le seed de démarrage ne recréera plus ce code par défaut
    await db.config.update_one({"_id": "deleted_promo_codes"}, {"$addToSet": {"codes": norm}}, upsert=True)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Codes AFFILIÉS : remise Stripe automatique À VIE + suivi pour les affiliés
# ---------------------------------------------------------------------------
PLAN_PRICES = {"monthly": PRO_PRICE_CENTS, "yearly": PRO_PRICE_YEAR_CENTS, "basic": BASIC_PRICE_CENTS,
               "essentiel": ESSENTIEL_PRICE_CENTS, "pro_monthly": PRO2_PRICE_CENTS,
               "pro_yearly": PRO2_YEAR_CENTS, "studio": STUDIO_YEAR_CENTS}
PLAN_LABELS = {"monthly": "PRO mensuel", "yearly": "PRO annuel", "basic": "BASIC",
               "essentiel": "ESSENTIEL", "pro_monthly": "PRO mensuel", "pro_yearly": "PRO annuel", "studio": "STUDIO"}
# Équivalence nouveaux plans → anciens (codes affiliés créés avant la refonte)
LEGACY_PLAN_EQUIV = {"pro_monthly": "monthly", "pro_yearly": "yearly", "essentiel": "basic"}


def _aff_price_after(aff: dict, plan: str) -> int:
    base = PLAN_PRICES[plan]
    if aff["kind"] == "percent":
        return max(0, round(base * (1 - aff["percent_off"] / 100)))
    return max(0, base - aff["amount_off_cents"])


@api_router.get("/affiliate/check/{code}")
async def affiliate_check(code: str):
    aff = await db.affiliate_codes.find_one({"code": _normalize_promo(code), "active": True}, {"_id": 0})
    if not aff:
        raise HTTPException(status_code=404, detail="Code invalide")
    return {
        "code": aff["code"],
        "kind": aff["kind"],
        "percent_off": aff.get("percent_off"),
        "amount_off_cents": aff.get("amount_off_cents"),
        "plans": aff["plans"],
        "prices": {p: {"base_cents": PLAN_PRICES[p], "after_cents": _aff_price_after(aff, p), "label": PLAN_LABELS[p]}
                   for p in aff["plans"]},
    }


@api_router.post("/admin/affiliate")
async def admin_create_affiliate(payload: dict, user: dict = Depends(get_current_user)):
    await require_admin(user)
    code = _normalize_promo(str(payload.get("code") or ""))
    if len(code) < 3:
        raise HTTPException(status_code=400, detail="Code trop court (3 min)")
    if await db.affiliate_codes.find_one({"code": code}):
        raise HTTPException(status_code=400, detail="Code affilié déjà existant")
    if await db.promo_codes.find_one({"code": code}):
        raise HTTPException(status_code=400, detail="Ce code existe déjà en code « jours offerts »")
    kind = payload.get("kind")
    plans = [p for p in (payload.get("plans") or []) if p in PLAN_PRICES]
    if not plans:
        raise HTTPException(status_code=400, detail="Choisis au moins un plan")
    commission_pct = float(payload.get("commission_pct") or 0)
    if kind == "percent":
        percent_off = float(payload.get("percent_off") or 0)
        if not (0 < percent_off < 100):
            raise HTTPException(status_code=400, detail="Pourcentage entre 1 et 99")
        coupon = stripe.Coupon.create(percent_off=percent_off, duration="forever", name=f"Affilié {code}")
        doc = {"kind": "percent", "percent_off": percent_off, "amount_off_cents": None}
    elif kind == "amount":
        amount_off = int(payload.get("amount_off_cents") or 0)
        if amount_off <= 0 or amount_off >= min(PLAN_PRICES[p] for p in plans):
            raise HTTPException(status_code=400, detail="Remise en € invalide pour les plans choisis")
        coupon = stripe.Coupon.create(amount_off=amount_off, currency="eur", duration="forever", name=f"Affilié {code}")
        doc = {"kind": "amount", "percent_off": None, "amount_off_cents": amount_off}
    else:
        raise HTTPException(status_code=400, detail="Type de remise invalide")
    doc.update({
        "code": code, "plans": plans, "commission_pct": commission_pct,
        "stripe_coupon_id": coupon["id"], "active": True,
        "use_count": 0, "uses": [], "created_at": iso(now_utc()),
    })
    try:
        await db.affiliate_codes.insert_one({**doc})
    except DuplicateKeyError:
        # compensation : évite un coupon Stripe orphelin en cas de double-clic / race
        try:
            stripe.Coupon.delete(coupon["id"])
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="Code affilié déjà existant")
    doc.pop("_id", None)
    return doc


@api_router.get("/admin/affiliate")
async def admin_list_affiliates(user: dict = Depends(get_current_user)):
    await require_admin(user)
    out = []
    async for aff in db.affiliate_codes.find({}, {"_id": 0}).sort("created_at", -1):
        uses = aff.get("uses") or []
        active_count = 0
        monthly_rev = 0.0
        for u in uses:
            udoc = await db.users.find_one({"user_id": u.get("user_id")}, {"subscription": 1})
            sub = (udoc or {}).get("subscription") or {}
            if sub.get("status") in ("active", "trialing", "cancelling"):
                active_count += 1
                after = _aff_price_after(aff, u.get("plan", "monthly"))
                monthly_rev += (after / 12 if u.get("plan") == "yearly" else after) / 100
        aff["active_subscribers"] = active_count
        aff["monthly_revenue"] = round(monthly_rev, 2)
        aff["monthly_commission"] = round(monthly_rev * (aff.get("commission_pct") or 0) / 100, 2)
        aff["prices"] = {p: {"base_cents": PLAN_PRICES[p], "after_cents": _aff_price_after(aff, p), "label": PLAN_LABELS[p]}
                         for p in aff.get("plans", [])}
        out.append(aff)
    return {"codes": out}


@api_router.delete("/admin/affiliate/{code}")
async def admin_delete_affiliate(code: str, user: dict = Depends(get_current_user)):
    await require_admin(user)
    aff = await db.affiliate_codes.find_one({"code": _normalize_promo(code)})
    if not aff:
        raise HTTPException(status_code=404, detail="Code introuvable")
    try:
        stripe.Coupon.delete(aff["stripe_coupon_id"])   # les abonnés existants GARDENT leur remise
    except Exception as e:
        logger.warning("Suppression coupon Stripe %s : %s", aff.get("stripe_coupon_id"), e)
    await db.affiliate_codes.delete_one({"_id": aff["_id"]})
    return {"ok": True}


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
    await db.project_backups.create_index([("project_id", 1), ("created_at", -1)])
    await db.password_reset_tokens.create_index("token")
    await db.affiliate_codes.create_index("code", unique=True)
    await db.promo_codes.create_index("code", unique=True)
    await db.templates.create_index([("user_id", 1), ("created_at", -1)])
    await seed_user(os.environ['ADMIN_EMAIL'], os.environ['ADMIN_PASSWORD'], "Admin", "admin")
    await seed_user("demo@beatcut.fr", "Demo1234!", "Démo", "user")
    # Compte démo : abonnement BASIC toujours actif (période glissante +30 j)
    await db.users.update_one(
        {"email": "demo@beatcut.fr"},
        {"$set": {"subscription": {
            "status": "active",
            "plan": "basic",
            "started_at": iso(now_utc()),
            "current_period_end": iso(now_utc() + timedelta(days=30)),
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "synced_at": iso(now_utc()),
        }}},
    )
    # Codes promo par défaut (jamais recréés s'ils ont été supprimés dans /admin)
    _deleted_doc = await db.config.find_one({"_id": "deleted_promo_codes"}) or {}
    _deleted_codes = set(_deleted_doc.get("codes") or [])
    for code, days in (("BIENVENUE50", 15), ("LAUNCH30", 30), ("BEATCUTSTART", 30)):
        if code in _deleted_codes:
            continue
        existing = await db.promo_codes.find_one({"code": code})
        if not existing:
            await db.promo_codes.insert_one({
                "code": code, "bonus_days": days, "max_uses": None,
                "expires_at": None, "used_count": 0, "used_by": [],
                "created_at": iso(now_utc()),
            })
    asyncio.create_task(_reengage_loop())
    asyncio.create_task(_payments_watchdog())


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
