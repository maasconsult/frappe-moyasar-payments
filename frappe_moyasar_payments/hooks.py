app_name = "frappe_moyasar_payments"
app_title = "Frappe Moyasar Payments"
app_publisher = "Maas Consult Middle East"
app_description = "Reusable Moyasar hosted payment gateway for Frappe"
app_email = ""
app_license = "Proprietary"
app_version = "0.1.1"

required_apps = ["payments"]

after_install = "frappe_moyasar_payments.install.after_install"
after_migrate = "frappe_moyasar_payments.install.after_migrate"
before_uninstall = "frappe_moyasar_payments.install.before_uninstall"

override_whitelisted_methods = {
    "frappe.website.doctype.web_form.web_form.accept": (
        "frappe_moyasar_payments.compat.payment_webform.accept"
    )
}
