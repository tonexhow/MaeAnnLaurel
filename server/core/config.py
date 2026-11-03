"""Environment configuration for the stateless contact-only API."""
from __future__ import annotations
import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import dotenv_values
from email_validator import validate_email, EmailNotValidError

SERVER = Path(__file__).resolve().parents[1]


def split_csv(value: str) -> list[str]:
    if not str(value).strip():
        return []
    return [part.strip() for part in next(csv.reader([value], skipinitialspace=True))]


def boolean(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SMTPAccount:
    host: str
    port: int
    security: str
    user: str
    password: str = field(repr=False)


@dataclass
class Settings:
    environment: str = "development"
    allowed_origins: list[str] = field(default_factory=lambda: ["http://127.0.0.1:3000", "http://localhost:3000"])
    contact_to: str = ""
    sender_name: str = "Mae Ann Laurel - Portfolio"
    accounts: list[SMTPAccount] = field(default_factory=list, repr=False)
    smtp_timeout: float = 5.0
    smtp_budget: float = 24.0
    # Best effort only: memory is NOT shared across serverless instances.
    rate_limit: int = 5
    rate_window: int = 900
    global_daily_limit: int = 60
    trust_proxy: bool = False
    turnstile_secret: str = field(default="", repr=False)
    turnstile_hostnames: list[str] = field(default_factory=list)
    turnstile_required: bool = False
    configuration_error: str = ""

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @property
    def captcha_required(self) -> bool:
        return self.production or self.turnstile_required or bool(self.turnstile_secret)

    @property
    def readiness_error(self) -> str:
        if self.configuration_error:
            return self.configuration_error
        if not self.accounts or not self.contact_to:
            return "SMTP accounts and recipient email are not configured."
        if self.captcha_required and not self.turnstile_secret:
            return "Turnstile secret is required before contact can accept messages."
        if self.production and not self.turnstile_hostnames:
            return "Production requires TURNSTILE_ALLOWED_HOSTNAMES."
        if self.production and (not self.allowed_origins or any(not origin.startswith("https://") for origin in self.allowed_origins)):
            return "Production requires exact HTTPS ALLOWED_ORIGINS."
        return ""

    @property
    def contact_ready(self) -> bool:
        return not self.readiness_error


def _accounts(values: dict[str, str]) -> list[SMTPAccount]:
    raw = values.get("SMTP_ACCOUNTS_JSON", "").strip()
    if raw:
        rows = json.loads(raw)
        if not isinstance(rows, list):
            raise ValueError("SMTP_ACCOUNTS_JSON must be an array.")
        result = [SMTPAccount(host=str(x["host"]), port=int(x.get("port", 587)),
                              security=str(x.get("security", "starttls")).lower(),
                              user=str(x["user"]), password=str(x["password"])) for x in rows]
    else:
        users, passwords = split_csv(values.get("SMTP_USER", "")), split_csv(values.get("SMTP_PASS", ""))
        if not users and not passwords:
            return []
        if len(users) != len(passwords):
            raise ValueError("SMTP_USER and SMTP_PASS must have matching counts.")
        count = len(users)
        def column(name: str, default: str) -> list[str]:
            items = split_csv(values.get(name, default))
            if len(items) == 1:
                return items * count
            if len(items) != count:
                raise ValueError(f"{name} needs one value or {count} matching values.")
            return items
        result = [SMTPAccount(h, int(p), s.lower(), u, password)
                  for h, p, s, u, password in zip(column("SMTP_HOST", "smtp.gmail.com"),
                                                  column("SMTP_PORT", "587"),
                                                  column("SMTP_SECURITY", "starttls"), users, passwords)]
    if not 1 <= len(result) <= 5:
        raise ValueError("Configure 1 to 5 SMTP accounts.")
    for account in result:
        validate_email(account.user, check_deliverability=False)
        if not account.password or not account.host or any(c.isspace() for c in account.host):
            raise ValueError("SMTP host and credentials are required.")
        if account.port not in {465, 587, 2525} or account.security not in {"tls", "starttls"}:
            raise ValueError("Use secure SMTP port 465, 587 or 2525.")
    return result


def load_settings() -> Settings:
    # Hosting environment overrides the local nonsecret development templates.
    raw = {**dotenv_values(SERVER.parent / ".env"), **dotenv_values(SERVER / ".env"), **os.environ}
    values = {key: str(value or "") for key, value in raw.items()}
    env = values.get("APP_ENV", "development").strip().lower()
    if values.get("VERCEL") == "1" or values.get("RENDER") == "true":
        env = "production"
    errors = []
    if env not in {"production", "development"}:
        errors.append("APP_ENV must be production or development.")
    allowed = split_csv(values.get("ALLOWED_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000"))
    for origin in allowed:
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc or
            parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password or
            "*" in origin):
            errors.append("ALLOWED_ORIGINS must contain only exact HTTP(S) origins.")
    allowed = [origin.rstrip("/") for origin in allowed]
    try:
        accounts = _accounts(values)
    except (ValueError, KeyError, TypeError, EmailNotValidError, json.JSONDecodeError):
        accounts = []
        errors.append("SMTP settings are invalid; check account pairs, hosts and ports.")
    contact_to = values.get("CONTACT_TO", "").strip()
    if contact_to:
        try:
            contact_to = validate_email(contact_to, check_deliverability=False).normalized
        except EmailNotValidError:
            errors.append("CONTACT_TO must be one valid email address.")
    def number(key: str, default: float, lo: float, hi: float) -> float:
        try:
            result = float(values.get(key, str(default)))
            if not lo <= result <= hi:
                raise ValueError("out of range")
            return result
        except (TypeError, ValueError):
            errors.append(f"{key} must be within {lo} and {hi}.")
            return default
    sender_name = values.get("CONTACT_SENDER_NAME", "Mae Ann Laurel - Portfolio")
    if "\r" in sender_name or "\n" in sender_name:
        errors.append("Sender name must not contain line breaks.")
    return Settings(
        environment=env, allowed_origins=allowed, contact_to=contact_to,
        sender_name=sender_name, accounts=accounts,
        smtp_timeout=number("SMTP_TIMEOUT_SECONDS", 5, 1, 10),
        smtp_budget=number("SMTP_TOTAL_BUDGET_SECONDS", 24, 5, 55),
        rate_limit=int(number("CONTACT_RATE_LIMIT", 5, 1, 30)),
        rate_window=int(number("CONTACT_RATE_WINDOW_SECONDS", 900, 60, 86400)),
        global_daily_limit=int(number("CONTACT_GLOBAL_DAILY_LIMIT", 60, 1, 1000)),
        trust_proxy=boolean(values.get("TRUST_PROXY_HEADERS", "false")),
        turnstile_secret=values.get("TURNSTILE_SECRET_KEY", ""),
        turnstile_hostnames=split_csv(values.get("TURNSTILE_ALLOWED_HOSTNAMES", "")),
        turnstile_required=boolean(values.get("TURNSTILE_REQUIRED", "false")),
        configuration_error=" ".join(errors),
    )
