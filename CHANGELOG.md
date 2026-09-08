# Changelog

## 0.1.1

- Work around stale or conflicting Frappe Web Form controller overrides.
- Restore payment checkout when the Payments submit handler receives the core
  `WebForm` class.

## 0.1.0

- Initial reusable Moyasar hosted-invoice gateway.
- Standard Frappe Web Form payment integration.
- Server-side invoice verification and idempotent callbacks.
- Generic transaction history linked to any reference document.
- Optional CRM Lead paid/reserved summary fields.
- No accounting document creation.
