from __future__ import annotations

import hashlib
import hmac
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


# ISO 4217 currencies whose minor-unit exponent differs from the common value 2.
ZERO_DECIMAL_CURRENCIES = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "ISK",
    "JPY",
    "KMF",
    "KRW",
    "PYG",
    "RWF",
    "UGX",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}

THREE_DECIMAL_CURRENCIES = {
    "BHD",
    "IQD",
    "JOD",
    "KWD",
    "LYD",
    "OMR",
    "TND",
}


def normalize_currency(currency: str) -> str:
    value = (currency or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise ValueError("Currency must be a three-letter ISO 4217 code")
    return value


def minor_unit_exponent(currency: str) -> int:
    currency = normalize_currency(currency)
    if currency in ZERO_DECIMAL_CURRENCIES:
        return 0
    if currency in THREE_DECIMAL_CURRENCIES:
        return 3
    return 2


def to_minor_units(amount: object, currency: str) -> int:
    """Convert a major-unit amount to the integer expected by Moyasar.

    The conversion is strict: a value with more fractional digits than the
    currency supports is rejected instead of being silently rounded.
    """

    try:
        major = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Amount must be a valid number") from exc

    if not major.is_finite() or major <= 0:
        raise ValueError("Amount must be greater than zero")

    exponent = minor_unit_exponent(currency)
    factor = Decimal(10) ** exponent
    minor = major * factor
    if minor != minor.to_integral_value():
        raise ValueError(f"Amount has too many decimal places for {normalize_currency(currency)}")
    return int(minor)


def from_minor_units(amount: object, currency: str) -> Decimal:
    try:
        minor = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Minor-unit amount must be a valid number") from exc
    if not minor.is_finite() or minor != minor.to_integral_value():
        raise ValueError("Minor-unit amount must be an integer")
    return minor / (Decimal(10) ** minor_unit_exponent(currency))


def token_digest(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def constant_time_token_matches(token: str, expected_digest: str) -> bool:
    if not token or not expected_digest:
        return False
    return hmac.compare_digest(token_digest(token), expected_digest)


def append_query_parameters(url: str, **parameters: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({key: value for key, value in parameters.items() if value is not None})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def is_same_origin_url(candidate: str, site_url: str) -> bool:
    """Allow relative URLs or absolute URLs on the configured Frappe origin."""

    if not candidate:
        return False
    candidate_parts = urlsplit(candidate)
    if not candidate_parts.scheme and not candidate_parts.netloc:
        return candidate.startswith("/") and not candidate.startswith("//")

    site_parts = urlsplit(site_url)
    return (
        candidate_parts.scheme.lower() == site_parts.scheme.lower()
        and candidate_parts.netloc.lower() == site_parts.netloc.lower()
    )


def moyasar_error_message(body: Any) -> str:
    """Flatten Moyasar's message and field errors into a safe short string."""
    if not isinstance(body, dict):
        return ""

    parts: list[str] = []
    message = body.get("message")
    error_type = body.get("type")
    if message:
        parts.append(str(message))
    elif error_type:
        parts.append(str(error_type).replace("_", " "))

    errors = body.get("errors")
    if isinstance(errors, dict):
        for fieldname, field_errors in errors.items():
            if isinstance(field_errors, (list, tuple)):
                detail = ", ".join(str(value) for value in field_errors if value)
            else:
                detail = str(field_errors or "")
            if detail:
                parts.append(f"{fieldname}: {detail}")

    return "; ".join(parts)[:350]
