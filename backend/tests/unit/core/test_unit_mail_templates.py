"""The two messages: both versions say the same, the link is intact, nothing leaks into HTML."""

import re
from email import message_from_bytes, policy

import pytest

from app.core import mail_templates
from app.core.mail import Mail, SmtpMailSender
from app.core.mail_templates import _duration, confirmation_mail, password_reset_mail
from tests.conftest import make_settings

LINK = "https://porych.life/reset-password#token=AbC_-123456789012345678901234567890123"


@pytest.mark.parametrize(
    ("build", "words"),
    [
        (confirmation_mail, ("Підтвердити пошту", "24 години")),
        (password_reset_mail, ("Задати новий пароль", "1 годину")),
    ],
)
def test_both_versions_carry_the_link_and_the_button_text(build, words):
    ttl = 1440 if build is confirmation_mail else 60

    mail = build("a@example.org", LINK, ttl)

    assert LINK in mail.text
    assert mail.html is not None and LINK in mail.html
    for word in words:
        assert word in mail.text
        assert word in mail.html
    assert mail.to == "a@example.org"


def test_the_html_is_self_contained_and_shows_the_logo_by_content_id():
    mail = password_reset_mail("a@example.org", LINK, 60)

    html = mail.html or ""
    assert 'src="cid:logo"' in html
    assert not re.search(r'(src|href)="http://', html)
    assert "<script" not in html
    # Only the link itself and the site address leave the message
    sources = re.findall(r'src="([^"]+)"', html)
    assert sources == ["cid:logo"]
    assert [image.cid for image in mail.images] == ["logo"]
    assert mail.images[0].data.startswith(b"\x89PNG")


def test_a_hostile_link_cannot_break_out_of_the_html():
    hostile = 'https://x.test/"><script>alert(1)</script>'

    html = confirmation_mail("a@example.org", hostile, 60).html or ""

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_the_message_has_a_dark_mode_block_and_a_preheader():
    html = confirmation_mail("a@example.org", LINK, 60).html or ""

    assert "prefers-color-scheme: dark" in html
    assert 'name="color-scheme"' in html
    assert "display:none" in html


def test_secrets_stay_out_of_the_repr():
    mail = password_reset_mail("a@example.org", LINK, 60)

    assert LINK not in repr(mail)
    assert "a@example.org" not in repr(mail)


@pytest.mark.parametrize(
    ("minutes", "said"),
    [
        (60, "1 годину"),
        (120, "2 години"),
        (1440, "24 години"),
        (300, "5 годин"),
        (11 * 60, "11 годин"),
        (1, "1 хвилину"),
        (15, "15 хвилин"),
        (22, "22 хвилини"),
        (30, "30 хвилин"),
        (11, "11 хвилин"),
    ],
)
def test_lifetimes_are_said_in_correct_ukrainian(minutes: int, said: str):
    assert _duration(minutes) == said


def test_smtp_builds_text_and_html_alternatives_with_the_logo_attached():
    sender = SmtpMailSender(make_settings(MAIL_FROM="Поруч <hello@porych.life>"))
    captured = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, context):
            return None

        def login(self, user, password):
            return None

        def send_message(self, message):
            captured.append(message)

    import smtplib

    original = smtplib.SMTP
    smtplib.SMTP = lambda *a, **k: FakeClient()  # type: ignore[assignment]
    try:
        sender._deliver(password_reset_mail("a@example.org", LINK, 60))  # noqa: SLF001
    finally:
        smtplib.SMTP = original  # type: ignore[assignment]

    parsed = message_from_bytes(captured[0].as_bytes(), policy=policy.default)
    assert parsed["To"] == "a@example.org"
    assert parsed.get_body(("plain",)) is not None
    html = parsed.get_body(("html",))
    assert html is not None and "cid:logo" in html.get_content()
    related = [p for p in parsed.walk() if p.get_content_type() == "image/png"]
    assert len(related) == 1 and related[0]["Content-ID"] == "<logo>"


def test_a_text_only_mail_stays_text_only():
    sender = SmtpMailSender(make_settings())
    captured = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, context):
            return None

        def login(self, user, password):
            return None

        def send_message(self, message):
            captured.append(message)

    import smtplib

    original = smtplib.SMTP
    smtplib.SMTP = lambda *a, **k: FakeClient()  # type: ignore[assignment]
    try:
        sender._deliver(Mail(to="a@example.org", subject="s", text="body"))  # noqa: SLF001
    finally:
        smtplib.SMTP = original  # type: ignore[assignment]

    assert captured[0].get_content_type() == "text/plain"


def test_the_logo_file_ships_with_the_code():
    assert mail_templates._LOGO_FILE.is_file()  # noqa: SLF001
