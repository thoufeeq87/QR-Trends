"""Google sign-in, restricted to ALLOWED_EMAILS. See workflows/deploy_railway.md
for how to create the Google OAuth client this depends on.

/api/ingest (its own X-Ingest-Secret auth, called by the cron service — not a human)
and /api/health (infra monitoring) are deliberately exempt from this — gating them
behind a human Google login would break the cron service and health checks.
"""

import logging

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.config import ALLOWED_EMAILS, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, PUBLIC_BASE_URL

logger = logging.getLogger(__name__)

SESSION_KEY = "user_email"

PUBLIC_PATHS = {"/login.html", "/style.css", "/api/health", "/api/ingest"}
PUBLIC_PREFIXES = ("/auth/",)

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

router = APIRouter(prefix="/auth")


def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


@router.get("/login")
async def login(request: Request):
    redirect_uri = f"{PUBLIC_BASE_URL}/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="auth_callback")
async def callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        logger.exception("Google OAuth callback failed")
        return RedirectResponse("/login.html?error=oauth_failed", status_code=302)

    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").strip().lower()

    if not email or not userinfo.get("email_verified") or email not in ALLOWED_EMAILS:
        request.session.pop(SESSION_KEY, None)
        return HTMLResponse(
            "<h1>Access denied</h1>"
            "<p>This dashboard is private. Your Google account isn't on the allowed list.</p>"
            '<p><a href="/login.html">Back to login</a></p>',
            status_code=403,
        )

    request.session[SESSION_KEY] = email
    next_path = request.session.pop("next", None) or "/"
    return RedirectResponse(next_path, status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.pop(SESSION_KEY, None)
    return RedirectResponse("/login.html", status_code=302)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Re-check against the *current* ALLOWED_EMAILS on every request, not just at
        # login — so revoking access (removing an email + redeploy) actually revokes
        # an existing session instead of only blocking future logins.
        session_email = request.session.get(SESSION_KEY)
        if is_public(path) or (session_email and session_email in ALLOWED_EMAILS):
            return await call_next(request)

        if path.startswith("/api/"):
            return JSONResponse({"detail": "authentication required"}, status_code=401)

        request.session["next"] = path
        return RedirectResponse("/login.html", status_code=302)
