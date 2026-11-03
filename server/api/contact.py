"""Stateless contact API. Cloudflare Turnstile is mandatory in production."""
from __future__ import annotations
import hashlib
import ipaddress
import json
import logging
import os
import time
from uuid import UUID
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from server.core.guard import RateLimited, IdempotencyConflict

router = APIRouter(prefix="/api")
log = logging.getLogger("portfolio.contact")


class ContactPayload(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr = Field(max_length=254)
    subject: str = Field(min_length=3, max_length=140)
    message: str = Field(min_length=10, max_length=5000)
    consent: bool
    website: str = Field(default="", max_length=200)  # honeypot
    started_at: float = Field(ge=0, allow_inf_nan=False)
    turnstile_token: str = Field(default="", max_length=2048)

    @field_validator("name", "subject", mode="before")
    @classmethod
    def clean_header(cls, value):
        if isinstance(value, str):
            if any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError("Control characters are not permitted.")
            return value.strip()
        return value

    @field_validator("message", mode="before")
    @classmethod
    def clean_body(cls, value):
        if isinstance(value, str):
            if "\x00" in value:
                raise ValueError("Invalid message character.")
            return value.strip()
        return value


def ip_for(request: Request) -> str:
    settings = request.app.state.settings
    ip = request.client.host if request.client else "unknown"
    if settings.trust_proxy:
        # Only enable behind a proxy that strips attacker-supplied forwarding headers.
        key = "x-vercel-forwarded-for" if os.environ.get("VERCEL") == "1" else "x-forwarded-for"
        ip = request.headers.get(key, ip).split(",")[0].strip()
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return "unknown"


def outcome(state: str, request_id: str):
    cases = {
        "accepted": (200, "Your message was accepted for delivery. Thank you for reaching out."),
        "pending": (409, "This message may already be processing. Please do not resend yet."),
        "uncertain": (409, "Delivery could not be confirmed. Please keep this reference and do not immediately resend."),
        "failed": (503, "Email delivery is unavailable. Your message was not confirmed as sent."),
    }
    status, message = cases[state]
    return JSONResponse({"status": state, "message": message, "reference": request_id}, status_code=status)


@router.get("/contact/status")
def contact_status(request: Request):
    settings = request.app.state.settings
    return {"ready": settings.contact_ready,
            "captcha_required": settings.captcha_required,
            "message": "Ready to receive your message." if settings.contact_ready else "Email delivery is not connected yet."}


def verify_turnstile(token: str, request_id: str, ip: str, settings) -> None:
    if not settings.captcha_required:
        return
    if not token:
        raise HTTPException(400, "Please complete the security check.")
    try:
        response = httpx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                              data={"secret": settings.turnstile_secret, "response": token,
                                    "remoteip": ip if ip != "unknown" else "",
                                    "idempotency_key": request_id}, timeout=6)
        response.raise_for_status()
        verification = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Security check unavailable. Please try again later.")
    if not verification.get("success") or verification.get("action") != "contact":
        raise HTTPException(400, "The security check expired. Please complete it again.")
    if settings.turnstile_hostnames and verification.get("hostname") not in settings.turnstile_hostnames:
        raise HTTPException(400, "The security check did not match this website.")


@router.post("/contact")
def submit(payload: ContactPayload, request: Request):
    settings = request.app.state.settings
    if not settings.contact_ready:
        raise HTTPException(503, "Email delivery is not connected yet. Please use another contact method.")
    origin = request.headers.get("origin")
    if origin and origin not in settings.allowed_origins:
        raise HTTPException(403, "This website is not allowed to submit messages.")
    if not payload.consent:
        raise HTTPException(422, "Please agree to the privacy notice before sending.")
    if payload.website or not (2 <= time.time() - payload.started_at <= 86400):
        raise HTTPException(400, "Please review the form and try again.")
    try:
        request_id = str(UUID(request.headers.get("idempotency-key", "")))
    except (ValueError, AttributeError):
        raise HTTPException(400, "A valid request reference is required.")

    content = payload.model_dump(include={"name", "email", "subject", "message"})
    fingerprint = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    guard = request.app.state.guard
    # Instance-local duplicate check before Turnstile, so a warm instance can
    # answer a repeat without consuming a second one-time Turnstile token.
    try:
        previous = guard.lookup(request_id, fingerprint)
    except IdempotencyConflict:
        raise HTTPException(409, "This reference belongs to a different message.")
    if previous is not None:
        return outcome(previous, request_id)

    ip = ip_for(request)
    verify_turnstile(payload.turnstile_token, request_id, ip, settings)
    try:
        state = guard.claim(request_id, fingerprint, ip)
    except RateLimited as exc:
        return JSONResponse({"status": "rate_limited", "message": "Too many enquiries. Try again later."},
                            status_code=429, headers={"Retry-After": str(exc.retry_after)})
    except IdempotencyConflict:
        raise HTTPException(409, "This reference belongs to a different message.")
    if state != "new":
        return outcome(state, request_id)
    try:
        state = request.app.state.mailer.send(content, request_id).status
        if state not in {"accepted", "failed", "uncertain"}:
            raise ValueError("Unexpected delivery outcome")
    except Exception:
        state = "uncertain"  # Unexpected failure is not proof the SMTP DATA was rejected.
        log.error("Unexpected SMTP failure reference=%s", request_id)
    guard.finish(request_id, state)
    return outcome(state, request_id)
