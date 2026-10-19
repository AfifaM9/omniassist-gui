"""RFC 6238 TOTP tests, including the official Appendix B test vectors."""

import unittest

from core import totp


class TestTotpVectors(unittest.TestCase):
    SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32 of "12345678901234567890"

    def test_rfc6238_sha1_vectors(self):
        for at, expected in [
            (59, "287082"),
            (1111111109, "081804"),
            (1111111111, "050471"),
            (1234567890, "005924"),
            (2000000000, "279037"),
        ]:
            self.assertEqual(totp.now_code(self.SECRET, at=at), expected, at)
            self.assertTrue(totp.verify(self.SECRET, expected, at=at, window=0), at)

    def test_window_tolerates_previous_and_next_step(self):
        code = totp.now_code(self.SECRET, at=1000)
        self.assertTrue(totp.verify(self.SECRET, code, at=1000 + 30))
        self.assertTrue(totp.verify(self.SECRET, code, at=1000 - 30))
        self.assertFalse(totp.verify(self.SECRET, code, at=1000 + 120))

    def test_rejects_malformed_input(self):
        for bad in ("", "12345", "abcdef", "1234567", "   "):
            self.assertFalse(totp.verify(self.SECRET, bad))

    def test_generate_secret_round_trips(self):
        secret = totp.generate_secret()
        self.assertTrue(totp.verify(secret, totp.now_code(secret)))

    def test_invalid_secret_is_not_accepted(self):
        self.assertFalse(totp.verify("not base32 !!!", "123456"))


if __name__ == "__main__":
    unittest.main()
