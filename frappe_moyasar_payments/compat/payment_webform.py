from __future__ import annotations

import frappe
from frappe.website.doctype.web_form.web_form import WebForm
from payments.overrides.payment_webform import PaymentWebForm
from payments.overrides.payment_webform import accept as payments_accept


def ensure_payment_webform_method() -> None:
    """Install the Payments mixin method when Frappe cached the core class.

    Some v15 deployments can resolve the Payments whitelisted submit override
    while still returning the core WebForm controller. The upstream submit
    handler then calls a method which is only present on PaymentWebForm. Adding
    that method to the core base also covers other WebForm subclasses without
    replacing their controller.
    """

    if not hasattr(WebForm, "get_payment_gateway_url"):
        setattr(
            WebForm,
            "get_payment_gateway_url",
            PaymentWebForm.get_payment_gateway_url,
        )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def accept(
    web_form: str,
    data: str,
    docname: str | None = None,
    for_payment: bool | str = False,
):
    """Delegate to Payments after repairing its expected WebForm method."""

    ensure_payment_webform_method()
    return payments_accept(
        web_form=web_form,
        data=data,
        docname=docname,
        for_payment=for_payment,
    )
