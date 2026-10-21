# from __future__ import annotations

# import frappe
# from frappe.website.doctype.web_form.web_form import WebForm
# from payments.overrides.payment_webform import PaymentWebForm
# from payments.overrides.payment_webform import accept as payments_accept


# def ensure_payment_webform_method() -> None:

#     if not hasattr(WebForm, "get_payment_gateway_url"):
#         setattr(
#             WebForm,
#             "get_payment_gateway_url",
#             PaymentWebForm.get_payment_gateway_url,
#         )
from frappe.website.doctype.web_form.web_form import WebForm
from payments.overrides.payment_webform import PaymentWebForm


def ensure_payment_webform_method() -> None:
    """Ensure WebForm has the payment gateway URL method."""

    if not hasattr(WebForm, "get_payment_gateway_url"):
        setattr(
            WebForm,
            "get_payment_gateway_url",
            PaymentWebForm.get_payment_gateway_url,
        )
# @frappe.whitelist(allow_guest=True, methods=["POST"])
# def accept(
#     web_form: str,
#     data: str,
#     docname: str | None = None,
#     for_payment: bool | str = False,
# ):

#     ensure_payment_webform_method()
#     return payments_accept(
#         web_form=web_form,
#         data=data,
#         docname=docname,
#         for_payment=for_payment,
#     )
