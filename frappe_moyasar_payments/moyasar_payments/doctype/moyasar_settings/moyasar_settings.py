from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url
from payments.utils import create_payment_gateway

from frappe_moyasar_payments.gateway import _request, create_hosted_invoice
from frappe_moyasar_payments.utils import normalize_currency

if TYPE_CHECKING:
    from typing import Any


class MoyasarSettings(Document):
    def validate(self) -> None:
        create_payment_gateway("Moyasar")
        self.webhook_url = get_url(
            "/api/method/frappe_moyasar_payments.api.webhook"
        )

        currencies = []
        for value in (self.allowed_currencies or "").splitlines():
            value = value.strip()
            if value:
                try:
                    currencies.append(normalize_currency(value))
                except ValueError as exc:
                    frappe.throw(str(exc))
        self.allowed_currencies = "\n".join(dict.fromkeys(currencies))

        if self.enabled:
            secret = self.get_secret_key()
            expected_prefix = "sk_test_" if self.test_mode else "sk_live_"
            if not secret.startswith(expected_prefix):
                frappe.throw(
                    _("Secret Key must start with {0} for the selected mode").format(
                        expected_prefix
                    )
                )

    def get_secret_key(self) -> str:
        secret = self.get_password("secret_key", raise_exception=False) or ""
        if not secret:
            frappe.throw(_("Moyasar Secret Key is not configured"))
        return secret

    def validate_transaction_currency(self, currency: str) -> None:
        try:
            currency = normalize_currency(currency)
        except ValueError as exc:
            frappe.throw(str(exc))

        allowed = {
            line.strip().upper()
            for line in (self.allowed_currencies or "").splitlines()
            if line.strip()
        }
        if allowed and currency not in allowed:
            frappe.throw(
                _("Moyasar is not enabled for currency {0}").format(currency)
            )

    def get_payment_url(self, **kwargs: Any) -> str:
        if not self.enabled:
            frappe.throw(_("Moyasar payment gateway is disabled"))
        self.validate_transaction_currency(kwargs.get("currency"))
        return create_hosted_invoice(self, **kwargs)

    @frappe.whitelist()
    def test_connection(self) -> str:
        """Verify API reachability and credentials without creating an invoice."""
        frappe.only_for("System Manager")
        if not self.enabled:
            frappe.throw(_("Moyasar payment gateway is disabled"))
        _request(self, "GET", "/invoices?page=1")
        return _("Moyasar API connection is working")
