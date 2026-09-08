# Frappe Moyasar Payments

Reusable Moyasar hosted-checkout integration for Frappe Web Forms and custom
Frappe documents.

Version 0.1 focuses on payment collection and verification. It does **not**
create Sales Invoices, Customers, Payment Entries, or General Ledger entries.

Version 0.1.1 also includes a compatibility repair for Frappe v15 sites where
the Payments submit override is active but the core Web Form controller remains
cached.

## Compatibility

- Frappe Framework 15
- ERPNext 15 (optional)
- Payments app 0.0.1
- Frappe Cloud private benches

## What it does

- Registers `Moyasar` as a Frappe Payment Gateway.
- Creates hosted Moyasar invoices from the standard Web Form payment flow.
- Stores every checkout attempt in `Moyasar Payment`.
- Verifies paid status, amount, currency, provider ID, and metadata server-side.
- Handles repeat callbacks idempotently.
- Reuses an active checkout and blocks a second payment after success.
- Optionally updates standard Moyasar summary fields on the referenced document.
- Adds payment summary fields to `CRM Lead` when that DocType is installed.

## Installation on Frappe Cloud

1. Add this GitHub repository to the private bench.
2. Ensure the official `payments` app is on the same bench.
3. Deploy the bench and install `frappe_moyasar_payments` on the site.
4. Open **Moyasar Settings** as System Manager.
5. Enable the gateway, choose Test Mode, and enter a newly generated test
   secret key. Do not paste keys into source files.
6. Optionally create a Moyasar dashboard webhook pointing to the URL displayed
   in Moyasar Settings and use the same shared secret on both sides.

## Web Form setup

In the Web Form's **Payments** tab:

- Enable **Accept Payment**.
- Select **Moyasar**.
- Select the currency.
- Enter a fixed amount, or enable **Amount Based On Field**.

The amount and description are supplied by the calling Web Form/document. They
are not global settings, so the gateway can be reused by multiple forms.

For the course-registration use case, configure the Web Form for `SAR 299.00`.
After a verified payment, these fields on the CRM Lead are updated:

- `custom_moyasar_payment_status`
- `custom_moyasar_invoice_id`
- `custom_moyasar_payment_id`
- `custom_moyasar_paid_amount`
- `custom_moyasar_paid_at`
- `custom_seat_reserved`

## Security model

- The Moyasar secret key is stored in an encrypted Frappe `Password` field.
- Only the backend calls Moyasar with the secret key.
- Callback payloads and browser redirects are never trusted as proof of payment.
- The app fetches the invoice directly from Moyasar before completing it.
- Callback links use a random token; only its SHA-256 digest is stored.
- Authorization headers and secrets are never written to transaction logs.
- Return URLs are restricted to the current Frappe site.

If a test secret has ever been shared in chat, email, or source control,
regenerate it before configuring the site.

## Callback endpoints

Per-checkout paid notification:

`/api/method/frappe_moyasar_payments.api.invoice_callback`

Global Moyasar webhook (optional):

`/api/method/frappe_moyasar_payments.api.webhook`

Browser return endpoint:

`/api/method/frappe_moyasar_payments.api.payment_return`

## Development checks

The pure-Python tests do not require a running bench:

```text
python -m unittest discover -s tests -v
```

Install the app on a Frappe v15 development site for integration testing.
