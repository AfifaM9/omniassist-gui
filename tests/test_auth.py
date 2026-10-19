"""Auth-mode tests for the three-port system (:8000 open, :8001 totp, :8002 token)."""

import unittest

from core.auth import AuthManager, AuthMode
from core.totp import generate_secret, now_code


class TestAuthModes(unittest.TestCase):
    def test_default_ports(self):
        self.assertEqual(AuthMode.OPEN.default_port, 8000)
        self.assertEqual(AuthMode.TOTP.default_port, 8001)
        self.assertEqual(AuthMode.TOKEN.default_port, 8002)

    def test_from_env_is_lenient(self):
        self.assertEqual(AuthMode.from_env("TOTP"), AuthMode.TOTP)
        self.assertEqual(AuthMode.from_env(" token "), AuthMode.TOKEN)
        self.assertEqual(AuthMode.from_env("bogus"), AuthMode.OPEN)
        self.assertEqual(AuthMode.from_env(None), AuthMode.OPEN)

    def test_open_mode_needs_no_credential(self):
        self.assertFalse(AuthManager(mode=AuthMode.OPEN).requires_credential)


class TestTotpLocking(unittest.TestCase):
    """The rule from the design: no secret means locked, never open."""

    def test_totp_mode_without_secret_stays_locked(self):
        mgr = AuthManager(mode=AuthMode.TOTP, totp_secret=None)
        self.assertTrue(mgr.requires_credential)
        self.assertFalse(mgr.totp_configured)
        for code in ("000000", "123456", now_code(generate_secret())):
            self.assertFalse(mgr.check_totp(code))

    def test_totp_mode_with_secret_verifies(self):
        secret = generate_secret()
        mgr = AuthManager(mode=AuthMode.TOTP, totp_secret=secret)
        self.assertTrue(mgr.requires_credential)
        self.assertTrue(mgr.totp_configured)
        self.assertTrue(mgr.check_totp(now_code(secret)))
        self.assertFalse(mgr.check_totp("000000"))


class TestTokenMode(unittest.TestCase):
    def test_token_mode_without_token_falls_back_to_open(self):
        self.assertFalse(AuthManager(mode=AuthMode.TOKEN, api_token=None).requires_credential)

    def test_token_mode_with_token_requires_it(self):
        mgr = AuthManager(mode=AuthMode.TOKEN, api_token="abc")
        self.assertTrue(mgr.requires_credential)
        self.assertTrue(mgr.check_token("abc"))
        self.assertFalse(mgr.check_token("nope"))
        self.assertFalse(mgr.check_token(None))


class TestSessions(unittest.TestCase):
    def test_issue_and_validate(self):
        mgr = AuthManager(mode=AuthMode.TOKEN, api_token="abc")
        session = mgr.issue_session()
        self.assertTrue(mgr.is_valid_session(session))
        self.assertFalse(mgr.is_valid_session("not-a-session"))
        self.assertFalse(mgr.is_valid_session(None))

    def test_expired_session_is_rejected(self):
        mgr = AuthManager(mode=AuthMode.TOKEN, api_token="abc", ttl=-1)
        self.assertFalse(mgr.is_valid_session(mgr.issue_session()))

    def test_revoke(self):
        mgr = AuthManager(mode=AuthMode.TOKEN, api_token="abc")
        session = mgr.issue_session()
        mgr.revoke(session)
        self.assertFalse(mgr.is_valid_session(session))


class TestThrottle(unittest.TestCase):
    def test_lockout_after_max_attempts(self):
        mgr = AuthManager(mode=AuthMode.TOTP, totp_secret=generate_secret(), max_attempts=3, lockout=60)
        self.assertFalse(mgr.is_locked_out("1.2.3.4"))
        for _ in range(3):
            mgr._record_failure("1.2.3.4")
        self.assertTrue(mgr.is_locked_out("1.2.3.4"))
        self.assertFalse(mgr.is_locked_out("5.6.7.8"))


if __name__ == "__main__":
    unittest.main()
