from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from payments.utils import create_payment_gateway


CRM_LEAD_FIELDS = [
    "custom_moyasar_payment_section",
    "custom_moyasar_payment_status",
    "custom_moyasar_invoice_id",
    "custom_moyasar_payment_id",
    "custom_moyasar_paid_amount",
    "custom_moyasar_paid_at",
    "custom_seat_reserved",
]


def after_install() -> None:
    ensure_setup()


def after_migrate() -> None:
    ensure_setup()


def ensure_setup() -> None:
    create_payment_gateway("Moyasar")
    _create_crm_lead_fields()

    settings = frappe.get_single("Moyasar Settings")
    if not settings.webhook_url:
        from frappe.utils import get_url

        settings.db_set(
            "webhook_url",
            get_url("/api/method/frappe_moyasar_payments.api.webhook"),
            update_modified=False,
        )


def before_uninstall() -> None:
    if frappe.db.exists("Payment Gateway", "Moyasar"):
        frappe.delete_doc("Payment Gateway", "Moyasar", ignore_permissions=True)

    for doctype in ("CRM Lead",):
        if not frappe.db.exists("DocType", doctype):
            continue
        frappe.db.delete(
            "Custom Field",
            {"dt": doctype, "fieldname": ["in", CRM_LEAD_FIELDS]},
        )
        frappe.clear_cache(doctype=doctype)


def _create_crm_lead_fields() -> None:
    if not frappe.db.exists("DocType", "CRM Lead"):
        return

    create_custom_fields(
        {
            "CRM Lead": [
                {
                    "fieldname": "custom_moyasar_payment_section",
                    "fieldtype": "Section Break",
                    "label": "Moyasar Payment",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_moyasar_payment_status",
                    "fieldtype": "Select",
                    "label": "Course Payment Status",
                    "options": "Not Started\nInitiated\nPaid\nFailed\nExpired\nCanceled\nRefunded\nError",
                    "default": "Not Started",
                    "read_only": 1,
                    "in_list_view": 1,
                },
                {
                    "fieldname": "custom_moyasar_invoice_id",
                    "fieldtype": "Data",
                    "label": "Moyasar Invoice ID",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_moyasar_payment_id",
                    "fieldtype": "Data",
                    "label": "Moyasar Payment ID",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_moyasar_paid_amount",
                    "fieldtype": "Currency",
                    "label": "Paid Amount",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_moyasar_paid_at",
                    "fieldtype": "Datetime",
                    "label": "Paid At",
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_seat_reserved",
                    "fieldtype": "Check",
                    "label": "Seat Reserved",
                    "default": "0",
                    "read_only": 1,
                    "in_list_view": 1,
                },
            ]
        },
        update=True,
    )
