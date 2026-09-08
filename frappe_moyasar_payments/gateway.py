from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any, NoReturn
from urllib.parse import urlsplit

import frappe
import requests
from frappe import _
from frappe.utils import get_url, now_datetime

from frappe_moyasar_payments.utils import (
    append_query_parameters,
    is_same_origin_url,
    moyasar_error_message,
    normalize_currency,
    to_minor_units,
    token_digest,
)

MOYASAR_API_BASE = "https://api.moyasar.com/v1"
REQUEST_TIMEOUT_SECONDS = 30


class MoyasarAPIError(RuntimeError):
    pass


def create_hosted_invoice(settings: Any, **kwargs: Any) -> str:
    reference_doctype = (kwargs.get("reference_doctype") or "").strip()
    reference_docname = (kwargs.get("reference_docname") or "").strip()
    if not reference_doctype or not reference_docname:
        frappe.throw(_("A reference document is required for Moyasar payment"))

    reference = frappe.get_doc(reference_doctype, reference_docname)
    currency = normalize_currency(kwargs.get("currency"))
    amount_minor = to_minor_units(kwargs.get("amount"), currency)
    if amount_minor < 100:
        frappe.throw(_("Moyasar requires an amount of at least 100 minor units"))
    amount = kwargs.get("amount")

    completed = _latest_payment(reference_doctype, reference_docname, ["Paid"])
    if completed:
        return _return_url(completed, "paid")

    active = _latest_payment(reference_doctype, reference_docname, ["Initiated"])
    if (
        active
        and active.checkout_url
        and active.amount_minor == amount_minor
        and active.currency == currency
    ):
        return active.checkout_url

    payer_name, payer_email = _payer_details(reference, kwargs)
    redirect_to = _safe_return_url(kwargs.get("redirect_to"))
    callback_token = secrets.token_urlsafe(32)
    description = (
        kwargs.get("description")
        or kwargs.get("title")
        or _("Payment for {0} {1}").format(reference_doctype, reference_docname)
    )

    transaction = frappe.get_doc(
        {
            "doctype": "Moyasar Payment",
            "status": "Initiated",
            "environment": "Test" if settings.test_mode else "Live",
            "reference_doctype": reference_doctype,
            "reference_docname": reference_docname,
            "amount": amount,
            "amount_minor": amount_minor,
            "currency": currency,
            "description": description,
            "payer_name": payer_name,
            "payer_email": payer_email,
            "redirect_to": redirect_to,
            "callback_token_hash": token_digest(callback_token),
        }
    ).insert(ignore_permissions=True)

    callback_url = _endpoint_url(
        "invoice_callback", transaction.name, callback_token
    )
    success_url = _endpoint_url("payment_return", transaction.name, callback_token)
    back_url = append_query_parameters(success_url, cancelled="1")

    payload = {
        "amount": amount_minor,
        "currency": currency,
        "description": str(description)[:500],
        "callback_url": callback_url,
        "success_url": success_url,
        "back_url": back_url,
        "metadata": {
            "frappe_reference_doctype": reference_doctype[:500],
            "frappe_reference_docname": reference_docname[:500],
            "frappe_transaction": transaction.name,
        },
    }

    try:
        invoice = _request(settings, "POST", "/invoices", payload)
    except MoyasarAPIError as exc:
        _raise_checkout_api_error(
            exc, transaction, reference_doctype, reference_docname
        )

    invoice_id = invoice.get("id")
    checkout_url = invoice.get("url")
    if not invoice_id or not checkout_url:
        _raise_checkout_api_error(
            MoyasarAPIError("Moyasar returned an incomplete invoice response"),
            transaction,
            reference_doctype,
            reference_docname,
        )

    # Keep local persistence outside the provider-error handler. If this code
    # fails, Frappe must report the real local exception rather than disguising
    # it as a Moyasar API failure.
    transaction.db_set(
        {
            "moyasar_invoice_id": invoice_id,
            "checkout_url": checkout_url,
            "error_message": None,
        },
        update_modified=False,
    )
    transaction.moyasar_invoice_id = invoice_id
    transaction.checkout_url = checkout_url
    _update_reference_summary(settings, transaction, "Initiated")
    return checkout_url


def fetch_invoice(settings: Any, invoice_id: str) -> dict[str, Any]:
    if not invoice_id:
        raise MoyasarAPIError("Moyasar invoice ID is missing")
    return _request(settings, "GET", f"/invoices/{invoice_id}")


def verify_and_update(
    settings: Any, transaction: Any, invoice: dict[str, Any]
) -> str:
    invoice_id = str(invoice.get("id") or "")
    if not invoice_id or invoice_id != transaction.moyasar_invoice_id:
        raise MoyasarAPIError("Moyasar invoice ID does not match the transaction")

    currency = normalize_currency(invoice.get("currency"))
    if currency != transaction.currency:
        raise MoyasarAPIError("Moyasar invoice currency does not match")

    try:
        remote_amount = int(invoice.get("amount"))
    except (TypeError, ValueError) as exc:
        raise MoyasarAPIError("Moyasar invoice amount is invalid") from exc
    if remote_amount != transaction.amount_minor:
        raise MoyasarAPIError("Moyasar invoice amount does not match")

    metadata = invoice.get("metadata") or {}
    if metadata.get("frappe_transaction") not in (None, "", transaction.name):
        raise MoyasarAPIError("Moyasar invoice metadata does not match")

    status = _map_invoice_status(invoice.get("status"))
    values: dict[str, Any] = {"status": status, "error_message": None}

    payment = _successful_payment(invoice.get("payments") or [])
    if payment:
        values["moyasar_payment_id"] = payment.get("id")

    if status == "Paid" and transaction.status != "Paid":
        values["paid_at"] = _parse_datetime(
            (payment or {}).get("updated_at") or invoice.get("updated_at")
        ) or now_datetime()

    transaction.db_set(values, update_modified=False)
    for fieldname, value in values.items():
        setattr(transaction, fieldname, value)

    _update_reference_summary(settings, transaction, status)
    return status


def _request(
    settings: Any, method: str, path: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    secret_key = settings.get_secret_key()
    try:
        response = requests.request(
            method,
            f"{MOYASAR_API_BASE}{path}",
            auth=(secret_key, ""),
            headers={"Accept": "application/json"},
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise MoyasarAPIError("Unable to reach Moyasar") from exc

    if response.status_code < 200 or response.status_code >= 300:
        message = "Moyasar rejected the request"
        try:
            body = response.json()
            message = moyasar_error_message(body) or message
        except (ValueError, TypeError):
            pass
        raise MoyasarAPIError(f"{message} (HTTP {response.status_code})")

    try:
        body = response.json()
    except ValueError as exc:
        raise MoyasarAPIError("Moyasar returned an invalid JSON response") from exc
    if not isinstance(body, dict):
        raise MoyasarAPIError("Moyasar returned an unexpected response")
    return body


def _latest_payment(
    reference_doctype: str, reference_docname: str, statuses: list[str]
) -> Any | None:
    rows = frappe.get_all(
        "Moyasar Payment",
        filters={
            "reference_doctype": reference_doctype,
            "reference_docname": reference_docname,
            "status": ["in", statuses],
        },
        fields=[
            "name",
            "status",
            "checkout_url",
            "amount_minor",
            "currency",
            "redirect_to",
        ],
        order_by="creation desc",
        limit=1,
    )
    return frappe._dict(rows[0]) if rows else None


def _payer_details(reference: Any, kwargs: dict[str, Any]) -> tuple[str, str]:
    payer_name = kwargs.get("payer_name")
    payer_email = kwargs.get("payer_email")
    if not payer_name or str(payer_name).lower() == "guest":
        payer_name = _first_value(
            reference, "full_name", "lead_name", "first_name", "customer_name"
        ) or reference.name
    if not payer_email or str(payer_email).lower() == "guest":
        payer_email = _first_value(
            reference, "email", "email_id", "contact_email", "email_address"
        )
    return str(payer_name or ""), str(payer_email or "")


def _first_value(doc: Any, *fieldnames: str) -> Any | None:
    for fieldname in fieldnames:
        value = doc.get(fieldname)
        if value:
            return value
    return None


def _endpoint_url(method: str, transaction: str, token: str) -> str:
    base = get_url(f"/api/method/frappe_moyasar_payments.api.{method}")
    return append_query_parameters(base, transaction=transaction, token=token)


def _safe_return_url(candidate: str | None) -> str:
    site_url = get_url()
    if candidate and is_same_origin_url(candidate, site_url):
        if not urlsplit(candidate).scheme:
            return f"{site_url.rstrip('/')}/{candidate.lstrip('/')}"
        return candidate
    return site_url


def _return_url(transaction: Any, status: str) -> str:
    return append_query_parameters(
        _safe_return_url(transaction.redirect_to),
        moyasar_status=status.lower(),
        moyasar_transaction=transaction.name,
    )


def _map_invoice_status(status: str | None) -> str:
    mapping = {
        "paid": "Paid",
        "refunded": "Refunded",
        "expired": "Expired",
        "canceled": "Canceled",
        "voided": "Canceled",
        "failed": "Failed",
    }
    return mapping.get(str(status or "").lower(), "Initiated")


def _successful_payment(payments: list[dict[str, Any]]) -> dict[str, Any] | None:
    for payment in reversed(payments):
        if str(payment.get("status") or "").lower() in {
            "paid",
            "captured",
            "authorized",
        }:
            return payment
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _update_reference_summary(settings: Any, transaction: Any, status: str) -> None:
    if not settings.update_reference_fields:
        return
    if not frappe.db.exists(transaction.reference_doctype, transaction.reference_docname):
        return

    meta = frappe.get_meta(transaction.reference_doctype)
    candidates = {
        "custom_moyasar_payment_status": status,
        "custom_moyasar_invoice_id": transaction.moyasar_invoice_id,
        "custom_moyasar_payment_id": transaction.moyasar_payment_id,
        "custom_moyasar_paid_amount": transaction.amount if status == "Paid" else None,
        "custom_moyasar_paid_at": transaction.paid_at if status == "Paid" else None,
        "custom_seat_reserved": 1 if status == "Paid" else 0,
    }
    values = {
        fieldname: value
        for fieldname, value in candidates.items()
        if meta.has_field(fieldname)
    }
    if values:
        frappe.db.set_value(
            transaction.reference_doctype,
            transaction.reference_docname,
            values,
            update_modified=False,
        )


def _safe_error_message(exc: Exception) -> str:
    # Never include request headers, keys, or raw payloads in the transaction log.
    return f"{type(exc).__name__}: {str(exc)[:400]}"


def _raise_checkout_api_error(
    exc: MoyasarAPIError,
    transaction: Any,
    reference_doctype: str,
    reference_docname: str,
) -> NoReturn:
    safe_error = _safe_error_message(exc)
    transaction.db_set(
        {"status": "Error", "error_message": safe_error},
        update_modified=False,
    )
    # Frappe's deferred insert is independent of the Web Form rollback. This is
    # best-effort diagnostics; the public error also contains the safe reason.
    frappe.log_error(
        title="Moyasar checkout creation failed",
        message=(
            f"Reference: {reference_doctype} {reference_docname}\n"
            f"Transaction: {transaction.name}\n"
            f"Error: {safe_error}"
        ),
        reference_doctype=reference_doctype,
        reference_name=reference_docname,
        defer_insert=True,
    )
    frappe.throw(
        _("Moyasar could not create the checkout: {0}").format(
            _public_error_message(exc)
        ),
        title=_("Payment Gateway Error"),
    )


def _public_error_message(exc: Exception) -> str:
    """Return a credential-free reason suitable for the public Web Form."""
    if isinstance(exc, MoyasarAPIError):
        return str(exc)[:400]
    return _("Unexpected gateway error. Please contact the site administrator.")
