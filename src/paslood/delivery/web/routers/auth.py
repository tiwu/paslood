"""Authentication and Social OAuth APIRouter for Paslood."""

from __future__ import annotations

import secrets
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from paslood.adapters.settings import AppSettings
from paslood.delivery.web.auth import AuthManager
from paslood.delivery.web.dependencies import get_app_settings, get_auth_manager

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "has_google": settings.has_google_oauth,
            "has_github": settings.has_github_oauth,
            "has_meta": settings.has_meta_oauth,
            "has_oauth": settings.has_oauth,
            "has_password": settings.has_password,
            "error": request.query_params.get("error"),
            "message": request.query_params.get("message"),
        },
    )


@router.post("/auth/login")
async def local_password_login(
    request: Request,
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    form = await request.form()
    password = str(form.get("password") or "").strip()
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not auth_manager.check_rate_limit(client_ip):
        return RedirectResponse(
            url="/login?error=Too+many+failed+attempts.+Please+wait+5+minutes.",
            status_code=303,
        )
    tenant = auth_manager.authenticate_local_password(password)
    if not tenant:
        return RedirectResponse(url="/login?error=Invalid+passphrase", status_code=303)

    token = auth_manager.create_session(user_id=tenant.user_id, tenant_id=tenant.tenant_id)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(
        "wp_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,
        secure=(request.url.scheme == "https"),
    )
    return resp


@router.get("/auth/logout")
async def logout(
    request: Request,
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    cookie = request.cookies.get("wp_session")
    if cookie:
        auth_manager.delete_session(cookie)
    resp = RedirectResponse(url="/login?message=Signed+out+successfully", status_code=303)
    resp.delete_cookie("wp_session")
    return resp


@router.get("/auth/google/login")
async def google_login(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    if not settings.has_google_oauth:
        return RedirectResponse(url="/login?error=Google+OAuth+not+configured", status_code=303)
    state_token = secrets.token_urlsafe(16)
    auth_manager.save_oauth_state(state_token, {"provider": "google"})
    redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/google/callback"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state_token,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url, status_code=303)


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    code = request.query_params.get("code")
    state_token = request.query_params.get("state")
    oauth_state = auth_manager.pop_oauth_state(state_token or "")
    if not state_token or not oauth_state:
        return RedirectResponse(url="/login?error=Invalid+or+expired+login+state", status_code=303)

    redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/google/callback"
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        t_resp = await client.post("https://oauth2.googleapis.com/token", data=data)
        if t_resp.is_error:
            return RedirectResponse(
                url="/login?error=Failed+to+exchange+Google+token", status_code=303
            )
        tokens = t_resp.json()
        access_tok = tokens.get("access_token")
        u_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        if u_resp.is_error:
            return RedirectResponse(
                url="/login?error=Failed+to+fetch+Google+profile", status_code=303
            )
        u_info = u_resp.json()

    email = u_info.get("email", "")
    if not email or not auth_manager.is_owner_email(email):
        return RedirectResponse(
            url="/login?error=Configure+exactly+one+allowed+owner+email", status_code=303
        )

    sub = str(u_info.get("sub") or email)
    name = u_info.get("name") or email.split("@")[0]
    avatar = u_info.get("picture")
    user, tenant_id = auth_manager.get_or_create_user("google", sub, email, name, avatar)
    token = auth_manager.create_session(user.id, tenant_id)
    resp = RedirectResponse(url="/#dashboard", status_code=303)
    resp.set_cookie(
        "wp_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,
        secure=(request.url.scheme == "https"),
    )
    return resp


@router.get("/auth/github/login")
async def github_login(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    if not settings.has_github_oauth:
        return RedirectResponse(url="/login?error=GitHub+OAuth+not+configured", status_code=303)
    state_token = secrets.token_urlsafe(16)
    auth_manager.save_oauth_state(state_token, {"provider": "github"})
    redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/github/callback"
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email",
        "state": state_token,
    }
    url = "https://github.com/login/oauth/authorize?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url, status_code=303)


@router.get("/auth/github/callback")
async def github_callback(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    code = request.query_params.get("code")
    state_token = request.query_params.get("state")
    oauth_state = auth_manager.pop_oauth_state(state_token or "")
    if not state_token or not oauth_state:
        return RedirectResponse(url="/login?error=Invalid+or+expired+login+state", status_code=303)

    redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/github/callback"
    data = {
        "code": code,
        "client_id": settings.github_client_id,
        "client_secret": settings.github_client_secret,
        "redirect_uri": redirect_uri,
    }
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        t_resp = await client.post(
            "https://github.com/login/oauth/access_token", data=data, headers=headers
        )
        if t_resp.is_error:
            return RedirectResponse(
                url="/login?error=Failed+to+exchange+GitHub+token", status_code=303
            )
        tokens = t_resp.json()
        access_tok = tokens.get("access_token")
        u_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_tok}", "User-Agent": "Paslood"},
        )
        if u_resp.is_error:
            return RedirectResponse(
                url="/login?error=Failed+to+fetch+GitHub+profile", status_code=303
            )
        u_info = u_resp.json()

        email = u_info.get("email")
        if not email:
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_tok}", "User-Agent": "Paslood"},
            )
            if emails_resp.status_code == 200:
                for em in emails_resp.json():
                    if em.get("primary") and em.get("verified"):
                        email = em.get("email")
                        break
                    elif em.get("verified") and not email:
                        email = em.get("email")

    if not email:
        email = f"{u_info.get('login', 'github-user')}@users.noreply.github.com"

    if not auth_manager.is_owner_email(email):
        return RedirectResponse(
            url="/login?error=Configure+exactly+one+allowed+owner+email", status_code=303
        )

    sub = str(u_info.get("id"))
    name = u_info.get("name") or u_info.get("login") or email.split("@")[0]
    avatar = u_info.get("avatar_url")
    user, tenant_id = auth_manager.get_or_create_user("github", sub, email, name, avatar)
    token = auth_manager.create_session(user.id, tenant_id)
    resp = RedirectResponse(url="/#dashboard", status_code=303)
    resp.set_cookie(
        "wp_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,
        secure=(request.url.scheme == "https"),
    )
    return resp


@router.get("/auth/meta/login")
async def meta_login(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    if not settings.has_meta_oauth:
        return RedirectResponse(url="/login?error=Meta+OAuth+not+configured", status_code=303)
    state_token = secrets.token_urlsafe(16)
    auth_manager.save_oauth_state(state_token, {"provider": "meta"})
    redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/meta/callback"
    params = {
        "client_id": settings.meta_client_id,
        "redirect_uri": redirect_uri,
        "scope": "email,public_profile",
        "state": state_token,
    }
    url = "https://www.facebook.com/v19.0/dialog/oauth?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url, status_code=303)


@router.get("/auth/meta/callback")
async def meta_callback(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    code = request.query_params.get("code")
    state_token = request.query_params.get("state")
    oauth_state = auth_manager.pop_oauth_state(state_token or "")
    if not state_token or not oauth_state:
        return RedirectResponse(url="/login?error=Invalid+or+expired+login+state", status_code=303)

    redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/meta/callback"
    params = {
        "client_id": settings.meta_client_id,
        "client_secret": settings.meta_client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        t_resp = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token", params=params
        )
        if t_resp.is_error:
            return RedirectResponse(
                url="/login?error=Failed+to+exchange+Meta+token", status_code=303
            )
        tokens = t_resp.json()
        access_tok = tokens.get("access_token")
        u_resp = await client.get(
            "https://graph.facebook.com/me?fields=id,name,email",
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        if u_resp.is_error:
            return RedirectResponse(
                url="/login?error=Failed+to+fetch+Meta+profile", status_code=303
            )
        u_info = u_resp.json()

    email = u_info.get("email") or f"{u_info.get('id')}@facebook.com"
    if not auth_manager.is_owner_email(email):
        return RedirectResponse(
            url="/login?error=Configure+exactly+one+allowed+owner+email", status_code=303
        )

    sub = str(u_info.get("id"))
    name = u_info.get("name") or "Meta User"
    user, tenant_id = auth_manager.get_or_create_user("meta", sub, email, name, None)
    token = auth_manager.create_session(user.id, tenant_id)
    resp = RedirectResponse(url="/#dashboard", status_code=303)
    resp.set_cookie(
        "wp_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,
        secure=(request.url.scheme == "https"),
    )
    return resp
