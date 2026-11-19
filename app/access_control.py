"""Central route access policy and operator-session enforcement."""

from __future__ import annotations

from enum import Enum
import logging
from typing import Sequence
from urllib.parse import parse_qs, urlencode

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Match, Mount

from app.auth import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    authenticate_operator_session,
    csrf_token_matches,
    safe_login_redirect,
)
from app.database import get_connection


logger = logging.getLogger(__name__)


class AccessCategory(str, Enum):
    PUBLIC = "PUBLIC"
    OPERATOR_ONLY = "OPERATOR_ONLY"
    AUTH_EXCEPTION = "AUTH_EXCEPTION"
    TECHNICAL = "TECHNICAL"


PUBLIC_ROUTES = {
    ("GET", "/api/availability"),
    ("POST", "/api/inquiries"),
}
AUTH_EXCEPTION_ROUTES = {
    ("GET", "/login"),
    ("POST", "/login"),
    ("POST", "/logout"),
}
TECHNICAL_ROUTES = {
    ("GET", "/"),
    ("HEAD", "/"),
    ("GET", "/health"),
    ("HEAD", "/health"),
    ("GET", "/docs"),
    ("HEAD", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("HEAD", "/docs/oauth2-redirect"),
    ("GET", "/redoc"),
    ("HEAD", "/redoc"),
    ("GET", "/openapi.json"),
    ("HEAD", "/openapi.json"),
}
PRESERVED_NOT_FOUND_ROUTES = {
    ("GET", "/ui/reservations/historical"),
    ("POST", "/ui/reservations/historical"),
}


def api_docs_enabled(app_env: str | None) -> bool:
    """Keep interactive API docs available outside production."""
    return (app_env or "").strip().lower() != "production"


def classify_access(path: str, method: str) -> AccessCategory:
    """Classify a registered route; unknown routes are filtered by the router first."""
    method = method.upper()
    if (method, path) in PUBLIC_ROUTES:
        return AccessCategory.PUBLIC
    if (method, path) in AUTH_EXCEPTION_ROUTES:
        return AccessCategory.AUTH_EXCEPTION
    if (method, path) in TECHNICAL_ROUTES:
        return AccessCategory.TECHNICAL
    if (path == "/static" or path.startswith("/static/")) and method in {
        "GET",
        "HEAD",
    }:
        return AccessCategory.TECHNICAL
    return AccessCategory.OPERATOR_ONLY


def _route_match(scope: dict, routes: Sequence) -> tuple[object | None, bool]:
    partial_match = False
    for route in routes:
        match, _ = route.matches(scope)
        if match is Match.FULL:
            return route, False
        if match is Match.PARTIAL:
            partial_match = True
    return None, partial_match


def _database_error_code(error: Exception) -> int | None:
    args = getattr(error, "args", ())
    if args and isinstance(args[0], int):
        return args[0]
    return None


class OperatorAccessMiddleware:
    """Protect registered operational routes using the existing DB sessions."""

    def __init__(self, app, *, routes: Sequence):
        self.app = app
        # FastAPI mutates this list as routes are registered after middleware setup.
        self.routes = routes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        route, partial_match = _route_match(scope, self.routes)
        if route is None:
            # Preserve Starlette's native 404 and 405 handling.
            await self.app(scope, receive, send)
            return
        if partial_match and getattr(route, "methods", None) is not None:
            # A path exists but the requested method does not; let Starlette return 405.
            await self.app(scope, receive, send)
            return

        method = scope["method"].upper()
        path = scope["path"]
        if (method, path) in PRESERVED_NOT_FOUND_ROUTES:
            # These retired routes intentionally keep their existing 404 response.
            await self.app(scope, receive, send)
            return
        if isinstance(route, Mount) and path.startswith("/static") and method not in {
            "GET",
            "HEAD",
        }:
            # StaticFiles has its own method response (405).
            await self.app(scope, receive, send)
            return

        category = classify_access(path, method)
        is_logout = method == "POST" and path == "/logout"
        if category is not AccessCategory.OPERATOR_ONLY and not is_logout:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            await self._unauthorized(scope, receive, send)
            return

        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        try:
            session = await run_in_threadpool(
                self._verify_session,
                token,
            )
        except Exception:
            if path.startswith("/api/"):
                response = JSONResponse(
                    {"detail": "Authentication service is unavailable."},
                    status_code=503,
                    headers={"Cache-Control": "no-store"},
                )
            else:
                response = PlainTextResponse(
                    "Authentication service is unavailable.",
                    status_code=503,
                    headers={"Cache-Control": "no-store"},
                )
            await response(scope, receive, send)
            return

        if session is None or not session.get("csrf_token_hash"):
            # Sessions created before the CSRF migration cannot authenticate
            # state-changing requests; require a fresh login to initialize one.
            await self._unauthorized(scope, receive, send)
            return

        csrf_token = (
            csrf_cookie
            if csrf_token_matches(csrf_cookie, session.get("csrf_token_hash"))
            else None
        )
        replay_receive = receive
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            if path.startswith("/api/"):
                supplied_csrf_token = request.headers.get("x-csrf-token")
            else:
                supplied_csrf_token, replay_receive = await self._form_csrf_token(
                    scope,
                    receive,
                )
            if not csrf_token_matches(
                supplied_csrf_token,
                session.get("csrf_token_hash"),
            ):
                response = JSONResponse(
                    {"detail": "CSRF token is missing or invalid."},
                    status_code=403,
                    headers={"Cache-Control": "no-store"},
                ) if path.startswith("/api/") else PlainTextResponse(
                    "CSRF token is missing or invalid.",
                    status_code=403,
                    headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
                return

        scope.setdefault("state", {})["operator"] = {
            "operator_id": session["operator_id"],
        }
        scope.setdefault("state", {})["csrf_token"] = csrf_token or ""

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if not any(name.lower() == b"cache-control" for name, _ in headers):
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, replay_receive, send_with_security_headers)

    @staticmethod
    async def _form_csrf_token(scope, receive):
        request = Request(scope, receive=receive)
        try:
            body = await request.body()
            form_values = parse_qs(body.decode("utf-8"), keep_blank_values=True)
            values = form_values.get("csrf_token", [])
            csrf_token = values[0] if len(values) == 1 else None
        except (UnicodeDecodeError, ValueError):
            body = b""
            csrf_token = None

        replayed = False

        async def replay_receive():
            nonlocal replayed
            if replayed:
                return {"type": "http.disconnect"}
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        return csrf_token, replay_receive

    @staticmethod
    def _verify_session(token: str):
        connection = None
        try:
            connection = get_connection()
            session = authenticate_operator_session(connection, token)
            connection.commit()
            return session
        except Exception as error:
            if connection is not None:
                try:
                    connection.rollback()
                except Exception as rollback_error:
                    logger.error(
                        "Operator access rollback failed (error_type=%s, error_code=%s)",
                        type(rollback_error).__name__,
                        _database_error_code(rollback_error),
                    )
            logger.error(
                "Operator access session verification failed (error_type=%s, error_code=%s)",
                type(error).__name__,
                _database_error_code(error),
            )
            raise
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception as close_error:
                    logger.error(
                        "Operator access connection close failed (error_type=%s, error_code=%s)",
                        type(close_error).__name__,
                        _database_error_code(close_error),
                    )

    @staticmethod
    async def _unauthorized(scope, receive, send):
        path = scope["path"]
        if path.startswith("/api/"):
            response = JSONResponse(
                {"detail": "Authentication required."},
                status_code=401,
                headers={"Cache-Control": "no-store"},
            )
        else:
            destination = path
            query_string = scope.get("query_string", b"").decode("latin-1")
            if query_string:
                destination = f"{destination}?{query_string}"
            next_path = safe_login_redirect(destination)
            root_path = scope.get("root_path", "").rstrip("/")
            login_path = "/login"
            if root_path and not (
                login_path == root_path or login_path.startswith(f"{root_path}/")
            ):
                login_path = f"{root_path}{login_path}"
            response = RedirectResponse(
                url=f"{login_path}?{urlencode({'next': next_path})}",
                status_code=303,
                headers={"Cache-Control": "no-store"},
            )
        await response(scope, receive, send)
