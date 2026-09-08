from __future__ import annotations

import hmac
from typing import Any

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from frappe_moyasar_payments.gateway import _return_url, fetch_invoice, verify_and_update
from frappe_moyasar_payments.utils import constant_time_token_matches


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="moyasar_invoice_callback", limit=120, seconds=60, methods=["POST"])
def invoice_callback(
    transaction: str | None = None, token: str | None = None
) -> dict[str, Any]:
    """Receive the per-invoice notification and verify it with Moyasar.

    The posted invoice object is treated only as a hint. Completion always uses
    a fresh backend fetch authenticated with the Moyasar secret key.
    """

    payment = _get_transaction(transaction, token)
    payload = _request_payload()
    posted_invoice_id = str(payload.get("id") or "")
    if posted_invoice_id and posted_invoice_id != payment.moyasar_invoice_id:
        frappe.throw(_("Invalid Moyasar invoice"), exc=frappe.PermissionError)

    settings = frappe.get_single("Moyasar Settings")
    invoice = fetch_invoice(settings, payment.moyasar_invoice_id)
    status = verify_and_update(settings, payment, invoice)
    return {"received": True, "status": status.lower()}


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(key="moyasar_payment_return", limit=120, seconds=60, methods=["GET"])
def payment_return(
    transaction: str | None = None,
    token: str | None = None,
    cancelled: str | int | None = None,
) -> None:
    """Verify the browser return, then redirect to the original Frappe URL."""

    payment = _get_transaction(transaction, token)
    status = "cancelled" if frappe.parse_json(cancelled or 0) else "pending"

    if payment.moyasar_invoice_id:
        try:
            settings = frappe.get_single("Moyasar Settings")
            invoice = fetch_invoice(settings, payment.moyasar_invoice_id)
            status = verify_and_update(settings, payment, invoice).lower()
            # Frappe rolls back writes made during a GET unless this flag is set.
            frappe.local.flags.commit = True
        except Exception:
            # A delayed callback can still complete the record. The customer is
            # redirected with a pending state rather than shown an internal error.
            status = "pending"

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = _return_url(payment, status)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="moyasar_webhook", limit=240, seconds=60, methods=["POST"])
def webhook() -> dict[str, Any]:
    """Handle optional global Moyasar payment webhooks.

    Moyasar includes the configured shared secret in `secret_token`. We validate
    it, locate the hosted invoice, and still fetch the invoice from Moyasar
    before changing local state.
    """

    payload = _request_payload()
    settings = frappe.get_single("Moyasar Settings")
    expected = settings.get_password("webhook_secret", raise_exception=False) or ""
    supplied = str(payload.get("secret_token") or "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        frappe.throw(_("Invalid webhook secret"), exc=frappe.PermissionError)

    event_type = str(payload.get("type") or "")
    event_data = payload.get("data") or {}
    if not isinstance(event_data, dict):
        frappe.throw(_("Invalid webhook payload"))

    invoice_id = str(event_data.get("invoice_id") or "")
    if not invoice_id:
        return {"received": True, "ignored": True, "event": event_type}

    transaction_name = frappe.db.get_value(
        "Moyasar Payment", {"moyasar_invoice_id": invoice_id}, "name"
    )
    if not transaction_name:
        return {"received": True, "ignored": True, "event": event_type}

    payment = frappe.get_doc("Moyasar Payment", transaction_name)
    invoice = fetch_invoice(settings, invoice_id)
    status = verify_and_update(settings, payment, invoice)
    return {"received": True, "status": status.lower(), "event": event_type}


def _get_transaction(transaction: str | None, token: str | None) -> Any:
    if not transaction or not token:
        frappe.throw(_("Missing payment callback token"), exc=frappe.PermissionError)
    payment = frappe.get_doc("Moyasar Payment", transaction)
    if not constant_time_token_matches(token, payment.callback_token_hash):
        frappe.throw(_("Invalid payment callback token"), exc=frappe.PermissionError)
    return payment


def _request_payload() -> dict[str, Any]:
    request = getattr(frappe.local, "request", None)
    if request:
        try:
            data = request.get_json(silent=True)
            if isinstance(data, dict):
                return data
        except (TypeError, ValueError):
            pass
    return dict(frappe.form_dict or {})
