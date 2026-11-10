"""Mail senders: SMTP for delivery, the log for development, a list for the tests."""

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from app.conf.config import Settings

logger = logging.getLogger(__name__)

_SMTP_TIMEOUT_SECONDS = 15


class MailDeliveryError(Exception):
    """A message could not be handed over to the mail server.

    The text never contains the address or the body.
    """


@dataclass(frozen=True, slots=True)
class InlineImage:
    """A picture shipped inside the message and referred to from the HTML as ``cid:<cid>``.

    :param cid: Content id used in the HTML.
    :param data: PNG bytes.
    """

    cid: str
    data: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class Mail:
    """One message: plain text, and optionally an HTML version of the same content.

    :param to: Recipient address.
    :param subject: Subject line.
    :param text: Plain-text body; it may hold a one-time link, so it stays out of ``repr``.
    :param html: HTML body, sent as an alternative to the text; None for text only.
    :param images: Pictures the HTML refers to by ``cid:``.
    """

    to: str = field(repr=False)
    subject: str
    text: str = field(repr=False)
    html: str | None = field(default=None, repr=False)
    images: tuple[InlineImage, ...] = field(default=(), repr=False)


class MailSender(Protocol):
    """Delivers a message; implemented by the senders below."""

    async def send(self, mail: Mail) -> None:
        """Hand a message to the mail server.

        :param mail: The message.
        :raises MailDeliveryError: If it could not be delivered.
        """
        ...


class LogMailSender:
    """Writes the subject and the body to the log instead of sending anything.

    For development and for a demo without a mail server: the one-time link in the body is
    printed, so it must never be used where the log is shared. Production uses SMTP.
    """

    async def send(self, mail: Mail) -> None:
        """Log the message.

        :param mail: The message.
        """
        logger.warning(
            "mail not sent (MAIL_BACKEND=log): to=%s subject=%s\n%s",
            mail.to,
            mail.subject,
            mail.text,
        )


class MemoryMailSender:
    """Keeps the sent messages in a list; used by the tests to read the confirmation link."""

    def __init__(self) -> None:
        """Start with an empty outbox."""
        self.sent: list[Mail] = []

    async def send(self, mail: Mail) -> None:
        """Remember the message.

        :param mail: The message.
        """
        self.sent.append(mail)


class SmtpMailSender:
    """Delivers through an SMTP server over TLS.

    ``smtplib`` blocks, so the exchange runs in a worker thread. The certificate of the server
    is verified; the password is read from the settings only when a message is sent.

    :param settings: Application settings with the SMTP section.
    """

    def __init__(self, settings: Settings) -> None:
        """Keep the connection settings."""
        self.settings = settings

    def _deliver(self, mail: Mail) -> None:
        """Send one message synchronously."""
        settings = self.settings
        message = EmailMessage()
        message["From"] = settings.MAIL_FROM
        message["To"] = mail.to
        message["Subject"] = mail.subject
        message.set_content(mail.text)
        if mail.html is not None:
            message.add_alternative(mail.html, subtype="html")
            html_part = message.get_body(preferencelist=("html",))
            if html_part is not None:
                for image in mail.images:
                    html_part.add_related(image.data, "image", "png", cid=f"<{image.cid}>")
        context = ssl.create_default_context()
        if settings.SMTP_IMPLICIT_TLS:
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=_SMTP_TIMEOUT_SECONDS,
                context=context,
            )
        else:
            client = smtplib.SMTP(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=_SMTP_TIMEOUT_SECONDS
            )
        with client:
            if settings.SMTP_STARTTLS and not settings.SMTP_IMPLICIT_TLS:
                client.starttls(context=context)
            if settings.SMTP_USERNAME:
                client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD.get_secret_value())
            client.send_message(message)

    async def send(self, mail: Mail) -> None:
        """Send the message in a worker thread.

        :param mail: The message.
        :raises MailDeliveryError: If the server refused it or could not be reached; only the
            class of the problem is kept, never an address.
        """
        try:
            await asyncio.to_thread(self._deliver, mail)
        except (OSError, smtplib.SMTPException) as error:
            raise MailDeliveryError(type(error).__name__) from None


def build_mail_sender(settings: Settings) -> MailSender:
    """Choose the sender named by ``MAIL_BACKEND``.

    :param settings: Application settings.
    :return: The sender; one instance serves the whole process.
    """
    if settings.MAIL_BACKEND == "smtp":
        return SmtpMailSender(settings)
    if settings.MAIL_BACKEND == "memory":
        return MemoryMailSender()
    return LogMailSender()
