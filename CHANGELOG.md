# Changelog

## 0.1.3

- Restrict friendly checkout handling to Moyasar API errors.
- Allow unexpected local Frappe persistence errors to retain their real traceback.
- Keep the hook-reported app version synchronized with the package version.

## 0.1.2

- Show credential-free Moyasar API validation details when checkout creation fails.
- Preserve failed checkout diagnostics in Frappe Error Log after request rollback.
- Add a non-mutating **Test API Connection** action to Moyasar Settings.

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
