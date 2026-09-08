import unittest
from decimal import Decimal

from frappe_moyasar_payments.utils import (
    append_query_parameters,
    constant_time_token_matches,
    from_minor_units,
    is_same_origin_url,
    normalize_currency,
    to_minor_units,
    token_digest,
)


class MinorUnitTests(unittest.TestCase):
    def test_sar_uses_two_decimals(self):
        self.assertEqual(to_minor_units("299.00", "sar"), 29900)
        self.assertEqual(from_minor_units(29900, "SAR"), Decimal("299"))

    def test_kwd_uses_three_decimals(self):
        self.assertEqual(to_minor_units("1.250", "KWD"), 1250)

    def test_jpy_uses_no_decimals(self):
        self.assertEqual(to_minor_units("299", "JPY"), 299)

    def test_rejects_invalid_amounts(self):
        for value in ("0", "-1", "NaN", "Infinity", "not-a-number"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                to_minor_units(value, "SAR")

    def test_rejects_too_many_decimal_places(self):
        with self.assertRaises(ValueError):
            to_minor_units("1.001", "SAR")

    def test_currency_is_normalized(self):
        self.assertEqual(normalize_currency(" sar "), "SAR")
        with self.assertRaises(ValueError):
            normalize_currency("Saudi Riyal")


class CallbackAndRedirectSecurityTests(unittest.TestCase):
    def test_token_digest_comparison(self):
        digest = token_digest("random-token")
        self.assertTrue(constant_time_token_matches("random-token", digest))
        self.assertFalse(constant_time_token_matches("wrong", digest))

    def test_only_same_origin_redirects_are_allowed(self):
        site = "https://erp.example.com"
        self.assertTrue(is_same_origin_url("/register/success", site))
        self.assertTrue(is_same_origin_url("https://erp.example.com/register/success", site))
        self.assertFalse(is_same_origin_url("https://evil.example/register/success", site))
        self.assertFalse(is_same_origin_url("//evil.example/register/success", site))

    def test_query_parameters_preserve_existing_values(self):
        result = append_query_parameters("https://erp.example.com/done?lang=en", status="paid")
        self.assertIn("lang=en", result)
        self.assertIn("status=paid", result)


if __name__ == "__main__":
    unittest.main()
