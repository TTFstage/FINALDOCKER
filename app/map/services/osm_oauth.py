"""Porting di src/lib/osm/oauth.ts: flusso OAuth2 + PKCE verso OpenStreetMap."""

import base64
import hashlib
import secrets
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from flask import current_app

TOKEN_COOKIE = "osm_access_token"
STATE_COOKIE = "osm_oauth_state"
VERIFIER_COOKIE = "osm_oauth_verifier"
RETURN_TO_COOKIE = "osm_return_to"

OSM_SCOPES = ["write_api", "read_prefs"]
TEMP_COOKIE_MAX_AGE = 600  # 10 minuti


class OsmConfigError(RuntimeError):
    pass


def get_osm_config():
    client_id = current_app.config.get("OSM_CLIENT_ID")
    client_secret = current_app.config.get("OSM_CLIENT_SECRET")
    app_origin = current_app.config.get("APP_ORIGIN")
    if not client_id or not client_secret or not app_origin:
        raise OsmConfigError(
            "OSM OAuth non configurato: imposta OSM_CLIENT_ID, "
            "OSM_CLIENT_SECRET e APP_ORIGIN"
        )
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "app_origin": app_origin.rstrip("/"),
    }


def osm_server_url() -> str:
    return current_app.config["OSM_SERVER_URL"].rstrip("/")


def get_callback_url() -> str:
    return f"{get_osm_config()['app_origin']}/api/v1/osm/auth/callback"


def sanitize_return_to(return_to: str | None) -> str | None:
    if not return_to or not return_to.startswith("/"):
        return None
    if return_to.startswith("//") or "\\" in return_to:
        return None
    return return_to


def create_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def create_state() -> str:
    return secrets.token_hex(16)


def token_cookie_kwargs() -> dict:
    return {"httponly": True, "samesite": "Lax", "secure": True, "path": "/"}


def oauth_temp_cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "samesite": "Lax",
        "secure": True,
        "max_age": TEMP_COOKIE_MAX_AGE,
        "path": "/api/v1/osm/auth",
    }


def relative_redirect_target(return_to: str, error: str | None) -> str:
    parsed = urlparse(return_to)
    query = parsed.query
    if error:
        extra = urlencode({"osm_auth_error": error})
        query = f"{query}&{extra}" if query else extra
    return urlunparse(("", "", parsed.path or "/", "", query, ""))


def build_authorize_url(redirect_uri: str, state: str, code_challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": get_osm_config()["client_id"],
        "redirect_uri": redirect_uri,
        "scope": " ".join(OSM_SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{osm_server_url()}/oauth2/authorize?{urlencode(params)}"


def exchange_code_for_token(code: str, redirect_uri: str, code_verifier: str) -> str:
    config = get_osm_config()
    response = requests.post(
        f"{osm_server_url()}/oauth2/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code_verifier": code_verifier,
        },
        timeout=10,
    )
    if not response.ok:
        raise RuntimeError(
            f"OSM token exchange failed with status {response.status_code}: {response.text}"
        )
    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError("OSM token endpoint non ha restituito un access_token")
    return access_token


def fetch_osm_user(access_token: str) -> dict:
    response = requests.get(
        f"{osm_server_url()}/api/0.6/user/details.json",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not response.ok:
        raise RuntimeError(f"OSM user details failed with status {response.status_code}")
    user = response.json().get("user")
    if not user or "display_name" not in user:
        raise RuntimeError("Payload utente OSM inatteso")
    return {"id": int(user["id"]), "displayName": user["display_name"]}
