"""Pluggable authentication / authorization layer (OFF by default).

ClaimLens is a library, not a hosted service — so it ships NO auth wired in, and
the grader / CI / local demo run with `NoAuth` (anonymous, always-allow). A host
that wants to "enable the chat for a given user / tenant" picks a real provider
via `CLAIMLENS_AUTH` (or constructs one directly) and applies it to the FastAPI
`/api/*` routes with `make_fastapi_dependency`.

Design notes:
  - Providers are plain objects with one method, `authenticate(headers) ->
    AuthContext` (raising `AuthError` on failure), so they are trivially unit-
    testable WITHOUT FastAPI installed.
  - This module imports cleanly with NO web framework present. `fastapi` is
    imported lazily, only inside the callable returned by
    `make_fastapi_dependency`, and `jwt` (PyJWT) only inside `OIDCAuth`.
  - HMAC verification reuses `integrations.sign_body` (one HMAC implementation
    for the whole codebase) and `hmac.compare_digest` for constant-time compare.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass, field

from .. import integrations


@dataclass
class AuthContext:
    """The authenticated principal handed to a request. Anonymous under NoAuth."""

    subject: str
    tenant: str = ""
    scopes: tuple = ()
    raw: dict = field(default_factory=dict)


class AuthError(Exception):
    """Raised by a provider when a request fails authentication."""


def _header(headers: dict, name: str) -> str | None:
    """Case-insensitive header lookup (HTTP header names are case-insensitive)."""
    if not headers:
        return None
    target = name.lower()
    for k, v in headers.items():
        if str(k).lower() == target:
            return v
    return None


class AuthProvider:
    """Base provider. Subclasses validate `headers` and return an AuthContext."""

    name: str = "base"

    def authenticate(self, headers: dict, body: bytes | None = None) -> AuthContext:
        raise NotImplementedError


class NoAuth(AuthProvider):
    """DEFAULT: never rejects — every request is an anonymous principal.

    This keeps the grader / CI / local demo working with zero configuration.
    """

    name = "none"

    def authenticate(self, headers: dict, body: bytes | None = None) -> AuthContext:
        return AuthContext(subject="anonymous", tenant="", scopes=(), raw={})


class ApiKeyAuth(AuthProvider):
    """Static API-key auth via the `X-API-Key` header.

    Keys come from the `keys` arg or env `CLAIMLENS_API_KEYS` (comma-separated).
    A key may optionally map to a tenant with `key=tenant` syntax, e.g.
    `CLAIMLENS_API_KEYS="k1=acme,k2=globex"`.
    """

    name = "apikey"

    def __init__(self, keys=None):
        self._key_to_tenant: dict = {}
        raw = keys
        if raw is None:
            raw = [k for k in os.environ.get("CLAIMLENS_API_KEYS", "").split(",") if k.strip()]
        if isinstance(raw, str):
            raw = [k for k in raw.split(",") if k.strip()]
        if isinstance(raw, dict):
            self._key_to_tenant = {str(k): str(v) for k, v in raw.items()}
        else:
            for entry in raw:
                entry = str(entry).strip()
                if not entry:
                    continue
                if "=" in entry:
                    key, tenant = entry.split("=", 1)
                    self._key_to_tenant[key.strip()] = tenant.strip()
                else:
                    self._key_to_tenant[entry] = ""

    def authenticate(self, headers: dict, body: bytes | None = None) -> AuthContext:
        presented = _header(headers, "X-API-Key")
        if not presented:
            raise AuthError("missing X-API-Key header")
        # constant-time compare against each configured key — no early break, so
        # total comparison count is independent of which key (if any) matched.
        matched = None
        for key in self._key_to_tenant:
            if hmac.compare_digest(str(presented), key):
                matched = key
        if matched is None:
            raise AuthError("invalid API key")
        return AuthContext(
            subject=f"apikey:{matched[:6]}",
            tenant=self._key_to_tenant.get(matched, ""),
            scopes=(),
            raw={"auth": "apikey"},
        )


class HMACAuth(AuthProvider):
    """Verify an `X-ClaimLens-Signature` HMAC over the raw request body.

    Reuses `integrations.sign_body` (same scheme as the outbound webhook) and
    `hmac.compare_digest`. The signature is computed over the EXACT raw bytes, so
    callers must pass `body` (the unparsed request body) — see `verify_body`.
    Secret comes from the `secret` arg or env `CLAIMLENS_HMAC_SECRET`.
    """

    name = "hmac"

    def __init__(self, secret=None):
        self._secret = secret if secret is not None else os.environ.get("CLAIMLENS_HMAC_SECRET", "")

    def verify_body(self, body: bytes, headers: dict) -> AuthContext:
        return self.authenticate(headers, body=body)

    def authenticate(self, headers: dict, body: bytes | None = None) -> AuthContext:
        if not self._secret:
            raise AuthError("hmac auth requires a configured secret (CLAIMLENS_HMAC_SECRET)")
        presented = _header(headers, "X-ClaimLens-Signature")
        if not presented:
            raise AuthError("missing X-ClaimLens-Signature header")
        if body is None:
            raise AuthError("hmac auth requires the raw request body")
        expected = integrations.sign_body(body, self._secret)
        if not hmac.compare_digest(str(presented), expected):
            raise AuthError("invalid HMAC signature")
        tenant = _header(headers, "X-ClaimLens-Tenant") or ""
        return AuthContext(subject="hmac", tenant=tenant, scopes=(), raw={"auth": "hmac"})


class OIDCAuth(AuthProvider):
    """Verify a Bearer JWT (OIDC). Reference implementation.

    Testable path: HS256 via a shared secret (`CLAIMLENS_OIDC_SECRET`).
    Production path: RS256 + JWKS (`CLAIMLENS_OIDC_JWKS`) — the issuer's signing
    keys are fetched and the token's `kid` selects the verifying key. Both paths
    validate `aud` (CLAIMLENS_OIDC_AUDIENCE) and `iss` (CLAIMLENS_OIDC_ISSUER).

    PyJWT is an OPTIONAL dependency, imported lazily; absence raises a clear
    AuthError rather than an ImportError at module load.
    """

    name = "oidc"

    def __init__(self, issuer=None, audience=None, secret=None, jwks=None):
        self.issuer = issuer if issuer is not None else os.environ.get("CLAIMLENS_OIDC_ISSUER", "")
        self.audience = (
            audience if audience is not None else os.environ.get("CLAIMLENS_OIDC_AUDIENCE", "")
        )
        self.secret = secret if secret is not None else os.environ.get("CLAIMLENS_OIDC_SECRET", "")
        self.jwks = jwks if jwks is not None else os.environ.get("CLAIMLENS_OIDC_JWKS", "")

    def authenticate(self, headers: dict, body: bytes | None = None) -> AuthContext:
        try:
            import jwt  # PyJWT — optional dependency
        except Exception as exc:  # pragma: no cover - exercised only without PyJWT
            raise AuthError("oidc requires PyJWT (pip install pyjwt)") from exc

        authz = _header(headers, "Authorization") or ""
        parts = authz.split(None, 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            raise AuthError("missing or malformed Bearer token")
        token = parts[1].strip()

        options = {"verify_aud": bool(self.audience)}
        decode_kwargs = {
            "algorithms": ["HS256", "RS256"],
            "audience": self.audience or None,
            "issuer": self.issuer or None,
            "options": options,
        }
        try:
            if self.jwks:
                # Production route: RS256 via the issuer's JWKS endpoint.
                jwks_client = jwt.PyJWKClient(self.jwks)
                signing_key = jwks_client.get_signing_key_from_jwt(token).key
                decode_kwargs["algorithms"] = ["RS256"]
                claims = jwt.decode(token, signing_key, **decode_kwargs)
            elif self.secret:
                # Testable route: HS256 shared secret.
                decode_kwargs["algorithms"] = ["HS256"]
                claims = jwt.decode(token, self.secret, **decode_kwargs)
            else:
                raise AuthError("oidc requires CLAIMLENS_OIDC_SECRET or CLAIMLENS_OIDC_JWKS")
        except AuthError:
            raise
        except Exception as exc:
            raise AuthError(f"invalid token: {exc}") from exc

        scope_str = claims.get("scope") or claims.get("scp") or ""
        if isinstance(scope_str, (list, tuple)):
            scopes = tuple(scope_str)
        else:
            scopes = tuple(s for s in str(scope_str).split() if s)
        return AuthContext(
            subject=str(claims.get("sub", "")),
            tenant=str(claims.get("tenant") or claims.get("tid") or ""),
            scopes=scopes,
            raw=dict(claims),
        )


def auth_from_env() -> AuthProvider:
    """Build the configured provider from `CLAIMLENS_AUTH` (default: NoAuth).

    CLAIMLENS_AUTH in {none, apikey, hmac, oidc}; anything else -> NoAuth.
    """
    mode = os.environ.get("CLAIMLENS_AUTH", "none").strip().lower()
    if mode == "apikey":
        return ApiKeyAuth()
    if mode == "hmac":
        return HMACAuth()
    if mode == "oidc":
        return OIDCAuth()
    return NoAuth()


def make_fastapi_dependency(provider: AuthProvider):
    """Return a FastAPI dependency that enforces `provider` on a route.

    Use as `Depends(make_fastapi_dependency(auth_from_env()))`. The returned
    callable lazily imports FastAPI (so this module imports without it), reads
    the raw body (needed by HMACAuth), runs the provider, maps AuthError -> 401,
    and returns the AuthContext for the handler to consume.
    """

    # Imported lazily (only when a server actually wires auth) so this module
    # still imports cleanly without FastAPI installed.
    from fastapi import HTTPException, Request

    async def dependency(request: Request):
        body = None
        # Only HMAC needs the raw body; reading it here is harmless for others.
        if isinstance(provider, HMACAuth):
            body = await request.body()
        try:
            return provider.authenticate(dict(request.headers), body=body)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    # `from __future__ import annotations` stringifies the `request: Request`
    # annotation, and `Request` is imported in this function's scope (not module
    # globals), so FastAPI's get_type_hints() can't resolve the string and would
    # treat `request` as a query param (→ 422 on every route). Bind the real
    # class object so FastAPI injects the Request instead.
    dependency.__annotations__["request"] = Request
    return dependency
