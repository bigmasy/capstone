# ruff: noqa: E501  (the HTML is written as it is sent, one tag per line)
"""The two messages the service sends, as plain text and as HTML.

The HTML follows what mail clients can render: nested tables, inline styles, a button that is
an ordinary link, a picture shipped inside the message (``cid:``) and no scripts, web fonts or
remote images, so nothing is loaded from outside and nothing can track the reader. The colours
are the product's own; a ``prefers-color-scheme`` block darkens the message in clients that
read it, and the plain-text part carries the same content for those that show no HTML.

Every value that reaches the HTML is escaped.
"""

from dataclasses import dataclass
from functools import cache
from html import escape
from pathlib import Path

from app.core.mail import InlineImage, Mail

_LOGO_CID = "logo"
_LOGO_FILE = Path(__file__).parent / "assets" / "logo.png"
_PRODUCT = "Поруч"
_SITE = "porych.life"
_FONT = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


@dataclass(frozen=True, slots=True)
class _Content:
    """What a message says, independent of how it is drawn."""

    preheader: str
    heading: str
    paragraphs: tuple[str, ...]
    button: str
    link: str
    fallback_hint: str
    notes: tuple[str, ...]


@cache
def _logo() -> InlineImage:
    """Read the logo once; it is a small file shipped with the code."""
    return InlineImage(_LOGO_CID, _LOGO_FILE.read_bytes())


def _plain(content: _Content) -> str:
    """Render the text version."""
    lines = [content.heading, "", *[f"{p}\n" for p in content.paragraphs]]
    lines += [f"{content.button}:", content.link, ""]
    lines += [*[f"{note}\n" for note in content.notes], f"— {_PRODUCT}, {_SITE}"]
    return "\n".join(lines)


def _paragraphs_html(paragraphs: tuple[str, ...]) -> str:
    return "".join(
        f'<p class="text" style="margin:0 0 16px;font-size:16px;line-height:26px;'
        f'color:#14231d;">{escape(p)}</p>'
        for p in paragraphs
    )


def _html(content: _Content) -> str:
    """Render the HTML version: a centred 560 px card on a quiet background."""
    link = escape(content.link, quote=True)
    notes = "".join(
        f'<p class="muted" style="margin:0 0 8px;font-size:14px;line-height:22px;'
        f'color:#44544b;">{escape(note)}</p>'
        for note in content.notes
    )
    return f"""<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{escape(content.heading)}</title>
<style>
  @media (prefers-color-scheme: dark) {{
    .page {{ background-color: #0e1612 !important; }}
    .card {{ background-color: #1a2620 !important; }}
    .text, .brand {{ color: #e8efe9 !important; }}
    .muted {{ color: #a9b8af !important; }}
    .rule {{ border-color: #2c3a32 !important; }}
    .button {{ background-color: #7fcaa5 !important; color: #0e1612 !important; }}
    .linkbox {{ background-color: #0e1612 !important; color: #a4dcc0 !important; }}
    .linkbox a {{ color: #a4dcc0 !important; }}
    .muted a {{ color: #a9b8af !important; }}
  }}
  @media only screen and (max-width: 600px) {{
    .card {{ border-radius: 0 !important; }}
    .pad {{ padding-left: 20px !important; padding-right: 20px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{escape(content.preheader)}</div>
<table role="presentation" class="page" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f6f3ec;">
  <tr>
    <td align="center" style="padding:32px 12px;">
      <table role="presentation" class="card" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;background-color:#ffffff;border-radius:16px;">
        <tr>
          <td class="pad" style="padding:28px 40px 0;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td style="padding-right:12px;"><img src="cid:{_LOGO_CID}" width="44" height="44" alt="" style="display:block;border:0;border-radius:10px;"></td>
                <td class="brand" style="font-family:{_FONT};font-size:24px;font-weight:700;color:#1d6a4f;letter-spacing:-0.2px;">{_PRODUCT}</td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td class="pad" style="padding:28px 40px 8px;font-family:{_FONT};">
            <h1 class="text" style="margin:0 0 16px;font-size:26px;line-height:32px;font-weight:700;color:#14231d;">{escape(content.heading)}</h1>
            {_paragraphs_html(content.paragraphs)}
          </td>
        </tr>
        <tr>
          <td class="pad" style="padding:8px 40px 24px;font-family:{_FONT};">
            <a class="button" href="{link}" style="display:inline-block;background-color:#1d6a4f;color:#ffffff;font-size:16px;font-weight:700;line-height:20px;text-decoration:none;padding:14px 28px;border-radius:10px;">{escape(content.button)}</a>
          </td>
        </tr>
        <tr>
          <td class="pad" style="padding:0 40px 28px;font-family:{_FONT};">
            <p class="muted" style="margin:0 0 8px;font-size:14px;line-height:22px;color:#44544b;">{escape(content.fallback_hint)}</p>
            <p class="linkbox" style="margin:0;padding:12px 14px;border-radius:8px;background-color:#ecefe6;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:13px;line-height:20px;color:#0f3f2e;word-break:break-all;"><a href="{link}" style="color:#0f3f2e;text-decoration:underline;">{link}</a></p>
          </td>
        </tr>
        <tr>
          <td class="pad" style="padding:0 40px 32px;font-family:{_FONT};">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr><td class="rule" style="border-top:1px solid #d9ddd2;padding-top:20px;">{notes}</td></tr>
            </table>
          </td>
        </tr>
      </table>
      <p class="muted" style="margin:20px 0 0;font-family:{_FONT};font-size:12px;line-height:18px;color:#5f6e66;">Цей лист надіслано автоматично, відповідати на нього не потрібно.<br>{_PRODUCT} · <a href="https://{_SITE}" style="color:#5f6e66;">{_SITE}</a></p>
    </td>
  </tr>
</table>
</body>
</html>
"""


def _mail(to: str, subject: str, content: _Content) -> Mail:
    return Mail(
        to=to,
        subject=subject,
        text=_plain(content),
        html=_html(content),
        images=(_logo(),),
    )


def _duration(minutes: int) -> str:
    """Name a lifetime the way a person would say it: "1 годину", "24 години", "30 хвилин"."""
    if minutes % 60 == 0:
        hours = minutes // 60
        tens, units = hours % 100, hours % 10
        if units == 1 and tens != 11:
            return f"{hours} годину"
        if 2 <= units <= 4 and not 12 <= tens <= 14:
            return f"{hours} години"
        return f"{hours} годин"
    tens, units = minutes % 100, minutes % 10
    if units == 1 and tens != 11:
        return f"{minutes} хвилину"
    if 2 <= units <= 4 and not 12 <= tens <= 14:
        return f"{minutes} хвилини"
    return f"{minutes} хвилин"


def confirmation_mail(to: str, link: str, ttl_minutes: int) -> Mail:
    """Build the message that asks a new user to confirm the address.

    :param to: Recipient address.
    :param link: The one-time link.
    :param ttl_minutes: How long the link works, in minutes.
    :return: The message, text and HTML.
    """
    return _mail(
        to,
        "Підтвердіть пошту на «Поруч»",
        _Content(
            preheader="Одне натискання, і ви зможете запрошувати партнерів і з’являтися в стрічці.",
            heading="Підтвердіть електронну пошту",
            paragraphs=(
                "Вітаємо в «Поруч»! Підтвердіть, що ця адреса належить вам. Тоді ви зможете "
                "надсилати й приймати запрошення, а інші побачать вас у стрічці.",
            ),
            button="Підтвердити пошту",
            link=link,
            fallback_hint="Якщо кнопка не відкривається, скопіюйте це посилання в браузер:",
            notes=(
                f"Посилання діє {_duration(ttl_minutes)} і спрацьовує один раз.",
                "Якщо ви не реєструвалися, просто проігноруйте цей лист: без підтвердження "
                "обліковий запис нічого не зможе.",
            ),
        ),
    )


def password_reset_mail(to: str, link: str, ttl_minutes: int) -> Mail:
    """Build the message with the link that sets a new password.

    :param to: Recipient address.
    :param link: The one-time link.
    :param ttl_minutes: How long the link works, in minutes.
    :return: The message, text and HTML.
    """
    return _mail(
        to,
        "Відновлення пароля на «Поруч»",
        _Content(
            preheader=f"Посилання діє {_duration(ttl_minutes)}. Якщо це були не ви, нічого не робіть.",
            heading="Відновлення пароля",
            paragraphs=(
                "Хтось попросив задати новий пароль для вашого облікового запису в «Поруч». "
                "Натисніть кнопку нижче й придумайте новий пароль.",
            ),
            button="Задати новий пароль",
            link=link,
            fallback_hint="Якщо кнопка не відкривається, скопіюйте це посилання в браузер:",
            notes=(
                f"Посилання діє {_duration(ttl_minutes)} і спрацьовує один раз. Нікому його "
                "не пересилайте.",
                "Якщо ви не просили змінити пароль, нічого не робіть: поточний пароль "
                "залишиться чинним.",
            ),
        ),
    )
