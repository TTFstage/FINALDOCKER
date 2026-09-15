import time
from hashlib import sha256
from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, redirect, request

from app.map.services import osm_api
from app.map.services import osm_oauth as oauth

osm_bp = Blueprint("osm", __name__, url_prefix="/api/v1/osm")

# Rate limit in-memory per il submit dei POI: { hash(token): {count, window_start} }
_submission_counts: dict[str, dict] = {}


def _is_rate_limited(access_token: str) -> bool:
    key = sha256(access_token.encode()).hexdigest()
    now = time.time()
    entry = _submission_counts.get(key)
    limit = current_app.config["POI_RATE_LIMIT"]
    window = current_app.config["POI_RATE_WINDOW_SECONDS"]
    if not entry or now - entry["window_start"] >= window:
        _submission_counts[key] = {"count": 1, "window_start": now}
        return False
    entry["count"] += 1
    return entry["count"] > limit


@osm_bp.get("/auth/start")
def auth_start():
    try:
        app_origin = oauth.get_osm_config()["app_origin"]
    except oauth.OsmConfigError as error:
        current_app.logger.error(error)
        return redirect(oauth.relative_redirect_target("/", "not_configured"))

    if request.args.get("osm_src") != "canonical" and urlparse(
        request.url_root
    ).netloc != urlparse(app_origin).netloc:
        # Rimanda alla origin canonica configurata, preservando i query params
        target = f"{app_origin}{request.path}?{request.query_string.decode()}"
        sep = "&" if "?" in target else "?"
        return redirect(f"{target}{sep}osm_src=canonical")

    return_to = oauth.sanitize_return_to(request.args.get("returnTo")) or "/"

    state = oauth.create_state()
    verifier, challenge = oauth.create_pkce_pair()

    authorize_url = oauth.build_authorize_url(
        redirect_uri=oauth.get_callback_url(),
        state=state,
        code_challenge=challenge,
    )

    response = redirect(authorize_url)
    cookie_kwargs = oauth.oauth_temp_cookie_kwargs()
    response.set_cookie(oauth.STATE_COOKIE, state, **cookie_kwargs)
    response.set_cookie(oauth.VERIFIER_COOKIE, verifier, **cookie_kwargs)
    response.set_cookie(oauth.RETURN_TO_COOKIE, return_to, **cookie_kwargs)
    return response


@osm_bp.get("/auth/callback")
def auth_callback():
    return_to = (
        oauth.sanitize_return_to(request.cookies.get(oauth.RETURN_TO_COOKIE)) or "/"
    )

    def redirect_back(error):
        response = redirect(oauth.relative_redirect_target(return_to, error), code=307)
        _clear_temp_cookies(response)
        return response

    code = request.args.get("code")
    state = request.args.get("state")
    expected_state = request.cookies.get(oauth.STATE_COOKIE)
    code_verifier = request.cookies.get(oauth.VERIFIER_COOKIE)

    if not code or not state or not expected_state or state != expected_state or not code_verifier:
        return redirect_back("invalid_state")

    if request.args.get("error"):
        return redirect_back("access_denied")

    try:
        access_token = oauth.exchange_code_for_token(
            code=code,
            redirect_uri=oauth.get_callback_url(),
            code_verifier=code_verifier,
        )
        response = redirect_back(None)
        response.set_cookie(oauth.TOKEN_COOKIE, access_token, **oauth.token_cookie_kwargs())
        return response
    except Exception:
        current_app.logger.exception("OSM token exchange failed")
        return redirect_back("token_exchange")


def _clear_temp_cookies(response):
    for cookie_name in (oauth.STATE_COOKIE, oauth.VERIFIER_COOKIE, oauth.RETURN_TO_COOKIE):
        response.delete_cookie(cookie_name, path="/api/v1/osm/auth")


@osm_bp.get("/me")
def me():
    access_token = request.cookies.get(oauth.TOKEN_COOKIE)
    if not access_token:
        return jsonify({"error": "Not authenticated"}), 401
    try:
        user = oauth.fetch_osm_user(access_token)
        return jsonify(user)
    except Exception:
        current_app.logger.exception("Failed to fetch OSM user")
        return jsonify({"error": "Invalid session"}), 401


@osm_bp.post("/logout")
def logout():
    response = jsonify({"ok": True})
    response.set_cookie(oauth.TOKEN_COOKIE, "", max_age=0, path="/", secure=True, httponly=True, samesite="Lax")
    return response


@osm_bp.post("/poi")
def submit_poi():
    access_token = request.cookies.get(oauth.TOKEN_COOKIE)
    if not access_token:
        return jsonify({"error": "Not authenticated"}), 401

    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"error": "Invalid JSON body"}), 400

    lat = body.get("lat")
    lng = body.get("lng")
    poi_type = body.get("type")

    valid_coords = (
        isinstance(lat, (int, float))
        and isinstance(lng, (int, float))
        and -90 <= lat <= 90
        and -180 <= lng <= 180
    )
    if not valid_coords:
        return jsonify({"error": "Invalid coordinates"}), 400

    if not osm_api.is_poi_type(poi_type):
        return jsonify({"error": "Invalid POI type"}), 400

    try:
        oauth.fetch_osm_user(access_token)
    except Exception:
        return jsonify({"error": "Invalid session"}), 401

    if _is_rate_limited(access_token):
        return jsonify({"error": "Too many requests"}), 429

    try:
        changeset_id = osm_api.create_changeset(access_token, poi_type)
        try:
            node_id = osm_api.create_node(access_token, changeset_id, lat, lng, poi_type)
            return jsonify(
                {
                    "nodeId": node_id,
                    "changesetId": changeset_id,
                    "osmUrl": f"{oauth.osm_server_url()}/node/{node_id}",
                }
            )
        finally:
            try:
                osm_api.close_changeset(access_token, changeset_id)
            except Exception:
                current_app.logger.exception(
                    "Failed to close changeset %s", changeset_id
                )
    except Exception:
        current_app.logger.exception("Failed to create POI on OpenStreetMap")
        return jsonify({"error": "Failed to create POI on OpenStreetMap"}), 502
