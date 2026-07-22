import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notify import format_subject, notify_all, send_email, send_macos_notification  # noqa: E402
from state import Alert  # noqa: E402


class FormatSubjectTests(unittest.TestCase):
    def test_down_alert_gets_red_icon(self):
        subject = format_subject(Alert("Google Ads", "down", "..."))
        self.assertIn("\U0001f534", subject)
        self.assertIn("Google Ads", subject)
        self.assertIn("connection down", subject)

    def test_recovered_alert_gets_green_check(self):
        subject = format_subject(Alert("Google Ads", "recovered", "..."))
        self.assertIn("✅", subject)
        self.assertIn("back up", subject)

    def test_heartbeat_alert_labeled_all_green(self):
        subject = format_subject(Alert("*all*", "heartbeat", "..."))
        self.assertIn("all green", subject)


class SendEmailTests(unittest.TestCase):
    def test_missing_smtp_env_returns_false_not_raise(self):
        alert = Alert("A", "down", "A is down")
        with patch.dict(os.environ, {}, clear=True):
            ok = send_email(alert, "someone@example.com")
        self.assertFalse(ok)

    def test_missing_recipient_returns_false(self):
        alert = Alert("A", "down", "A is down")
        env = {
            "SENTINEL_SMTP_HOST": "smtp.example.com",
            "SENTINEL_SMTP_USER": "u",
            "SENTINEL_SMTP_PASS": "p",
        }
        with patch.dict(os.environ, env, clear=True):
            ok = send_email(alert, "")
        self.assertFalse(ok)


class SendMacosNotificationTests(unittest.TestCase):
    @patch("notify.platform.system", return_value="Linux")
    def test_noop_on_non_mac(self, _mock_system):
        alert = Alert("A", "down", "A is down")
        ok = send_macos_notification(alert)
        self.assertFalse(ok)

    @patch("notify.subprocess.run")
    @patch("notify.platform.system", return_value="Darwin")
    def test_calls_osascript_on_mac(self, _mock_system, mock_run):
        alert = Alert("A", "down", "A is down")
        ok = send_macos_notification(alert)
        self.assertTrue(ok)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "osascript")

    @patch("notify.subprocess.run", side_effect=RuntimeError("boom"))
    @patch("notify.platform.system", return_value="Darwin")
    def test_subprocess_failure_returns_false_not_raise(self, _mock_system, _mock_run):
        alert = Alert("A", "down", "A is down")
        ok = send_macos_notification(alert)
        self.assertFalse(ok)


class NotifyAllTests(unittest.TestCase):
    class _FakeNotifyCfg:
        email_enabled = False
        email_to = ""
        macos_enabled = False

    def test_falls_back_to_console_print_when_all_channels_off(self):
        alert = Alert("A", "down", "A is down")
        # must not raise even with nothing configured
        notify_all(alert, self._FakeNotifyCfg())

    @patch("notify.send_macos_notification", return_value=True)
    def test_calls_macos_when_enabled(self, mock_macos):
        class Cfg:
            email_enabled = False
            email_to = ""
            macos_enabled = True
        notify_all(Alert("A", "down", "..."), Cfg())
        mock_macos.assert_called_once()

    @patch("notify.send_email", return_value=True)
    def test_calls_email_when_enabled_with_recipient(self, mock_email):
        class Cfg:
            email_enabled = True
            email_to = "me@example.com"
            macos_enabled = False
        notify_all(Alert("A", "down", "..."), Cfg())
        mock_email.assert_called_once()


if __name__ == "__main__":
    unittest.main()
