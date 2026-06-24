#!/usr/bin/env python3
"""ClaimLens local server — serves the PWA AND runs the REAL pipeline.

Mirrors the nextmillionai pattern (one localhost server serves the UI + the
endpoints). The chat messenger POSTs a live capture to /api/review, which runs
the genuine tiered harness — Gemini Flash perception on the actual pixels +
Claude judge over scenario packs / history / tool signals — so a photo that
isn't the claimed object comes back as wrong_object / not_enough_information with
a grounded, conversational reply. No mock.

Run:
    pip install fastapi uvicorn        # plus the core requirements + keys in code/.env
    python code/server.py              # http://localhost:8000
"""
# NOTE: no `from __future__ import annotations` — FastAPI/pydantic must see the
# real ReviewIn type at runtime to bind the request body.

import json
import os
import sys
import tempfile
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

from evidence_review import Config, Pipeline, embed, integrations  # noqa: E402
from evidence_review.harness.auth import auth_from_env, make_fastapi_dependency  # noqa: E402
from server_helpers import (  # noqa: E402
    _assistant_message,
    _decode_images,
    _detail,
    _now_iso,
)

PWA_DIR = CODE_DIR / "pwa"

# Build the pipeline once (real models if keys present; mock fallback otherwise).
_cfg = Config()
_pipe = Pipeline(_cfg, use_cache=True, verbose=False)

# Pluggable auth (default NoAuth — open, so the demo/CI run with no config) and
# the connector registry, built once. `CLAIMLENS_AUTH=apikey|hmac|oidc` enables it.
_auth = auth_from_env()
_connectors = integrations.default_connectors()


def create_app():
    from fastapi import Depends, FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel

    app = FastAPI(title="ClaimLens")

    # One auth dependency, applied to the /api/* + inbound routes. Under the
    # default NoAuth it admits everyone as an anonymous principal.
    require_auth = make_fastapi_dependency(_auth)

    class ReviewIn(BaseModel):
        claim_object: str
        user_claim: str = ""
        images: list[str] = []  # data URLs (base64) from the live camera
        user_id: str = ""

    @app.get("/api/health")
    def health():
        return {"ok": True, "config": _cfg.summary(), "auth": _auth.name}

    @app.post("/api/review")
    def review(body: ReviewIn, ctx=Depends(require_auth)):
        with tempfile.TemporaryDirectory() as td:
            paths = _decode_images(body.images, Path(td))
            if not paths:
                return JSONResponse(
                    {
                        "claim_status": "not_enough_information",
                        "assistant_message": "I didn’t receive a usable photo — please capture the item live and try again.",
                        "risk_flags": "manual_review_required",
                        "severity": "unknown",
                    },
                    status_code=200,
                )
            decision, extra = _pipe.review_uploaded(
                body.claim_object, body.user_claim, paths, user_id=body.user_id
            )
            decision = dict(decision)
            decision["assistant_message"] = _assistant_message(decision, body.claim_object.lower())
            esc = extra.get("escalation", {})
            decision["confidence"] = esc.get("confidence")
            decision["detail"] = _detail(extra)  # per-run observability for the UI dashboard
            return decision

    @app.get("/api/connectors")
    def connectors():
        """Connector capability catalog — the single source of truth the UI
        renders its integrations list from (keeps UI ↔ backend in sync)."""
        return {"connectors": _connectors.manifests()}

    @app.post("/api/intake")
    def intake(body: dict, ctx=Depends(require_auth)):
        """Provider-agnostic embed surface: any chat/host posts a {claims,
        evidence, protocols} envelope and gets the same verdict as the batch
        pipeline. The envelope is validated inside `embed.handle_intake`."""
        # Tenancy is owned by the authenticated principal, not the (untrusted)
        # envelope: if auth resolved a tenant, it wins over any client-supplied one.
        if getattr(ctx, "tenant", ""):
            meta = dict(body.get("metadata") or {})
            meta["tenant"] = ctx.tenant
            body = {**body, "metadata": meta}
        try:
            resp = embed.handle_intake(body, _pipe, reviewed_at=_now_iso())
        except ValueError as e:
            return JSONResponse({"error": f"invalid intake envelope: {e}"}, status_code=400)
        if "assistant_message" not in resp:
            claim_object = str((body.get("claims") or {}).get("claim_object") or "").lower()
            resp["assistant_message"] = _assistant_message(resp, claim_object)
        return resp

    @app.post("/integrations/inbound/{connector}")
    async def inbound(connector: str, request: Request):
        """Close the loop: a helpdesk webhook (e.g. Zendesk) posts a ticket; the
        connector parses it into a claim job, ClaimLens reviews it, and the
        normalized verdict comes back.

        NOTE: this route is intentionally NOT behind the app-level `require_auth`
        dependency — inbound webhooks authenticate with the *connector's own*
        signature scheme (here, `X-ClaimLens-Signature` gated by
        `CLAIMLENS_WEBHOOK_SECRET`), not the API auth used by `/api/*`. Putting it
        behind `require_auth` would 401 every helpdesk webhook the moment an
        operator enables api-key/OIDC auth."""
        raw = await request.body()
        conn = _connectors.get(connector)
        if conn is None or not conn.supports_inbound():
            return JSONResponse(
                {"error": f"connector '{connector}' has no inbound support"}, status_code=404
            )
        # Fail closed when a secret is configured: a signed scheme must present a
        # valid signature. With no secret set, inbound is unauthenticated (demo
        # default — documented in SECURITY.md / INTEGRATIONS.md). Real helpdesks
        # (e.g. Zendesk's X-Zendesk-Webhook-Signature) use their own header/scheme,
        # wired per-connector at integration time.
        secret = os.environ.get("CLAIMLENS_WEBHOOK_SECRET", "")
        if secret:
            sig = request.headers.get("X-ClaimLens-Signature", "")
            if not (sig and conn.verify_inbound_signature(raw, sig, secret)):
                return JSONResponse({"error": "missing or invalid signature"}, status_code=401)
        try:
            payload = json.loads(raw or b"{}")
        except ValueError:
            return JSONResponse({"error": "invalid json body"}, status_code=400)
        job = conn.parse_inbound(payload, dict(request.headers))
        try:
            review = embed.handle_intake(embed.intake_from_job(job), _pipe, reviewed_at=_now_iso())
        except ValueError as e:
            # e.g. the ticket didn't carry a recognizable claim_object — surface
            # the parsed job so the caller can enrich it, don't 500.
            return JSONResponse(
                {"connector": connector, "claim_job": job, "error": f"incomplete claim: {e}"},
                status_code=422,
            )
        return {"connector": connector, "claim_job": job, "review": review}

    # serve the PWA (must be mounted last so /api/* routes win)
    app.mount("/", StaticFiles(directory=str(PWA_DIR), html=True), name="static")
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    print(f"[claimlens] {_cfg.summary()}")
    print("[claimlens] serving http://localhost:8000  (UI + /api/review)")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
