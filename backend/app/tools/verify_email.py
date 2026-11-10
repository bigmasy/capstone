"""Confirm an account by hand, or print a fresh confirmation link for it.

Usage, from ``backend/``: ``python -m app.tools.verify_email ADDRESS`` confirms the account at
once; ``python -m app.tools.verify_email --link ADDRESS`` prints a new link instead (the same
link the message carries), and ``--reset-link`` prints a password-reset link. It is the
administrator's way round a mail server that is not set up yet, for example on a demo, and the
way the end-to-end tests confirm their throw-away accounts. It needs the database and nothing
else: no mail is sent.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

from app.composition import build_auth_service
from app.conf.config import Settings, get_settings
from app.core.mail import MemoryMailSender
from app.database.db import DatabaseSessionManager

EXIT_NOT_FOUND = 1


def _parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog="python -m app.tools.verify_email", description=__doc__)
    parser.add_argument("email", help="address of the account")
    parser.add_argument(
        "--link",
        action="store_true",
        help="print a fresh confirmation link instead of confirming the account",
    )
    parser.add_argument(
        "--reset-link",
        action="store_true",
        help="print a fresh password-reset link instead of confirming the account",
    )
    return parser


async def confirm(
    settings: Settings, email: str, *, link: bool, reset_link: bool = False
) -> str | None:
    """Confirm an account or issue a link for it.

    :param settings: Application settings.
    :param email: Address of the account.
    :param link: Issue a link instead of confirming.
    :param reset_link: Issue a password-reset link instead.
    :return: The link when ``link`` or ``reset_link`` is set, an empty string after a
        confirmation, or None when there is no such account.
    """
    manager = DatabaseSessionManager(settings)
    try:
        async with manager.session() as session:
            service = build_auth_service(session, settings, MemoryMailSender())
            account = await service.users.get_user_by_email(email)
            if account is None:
                return None
            if reset_link:
                return await service.issue_reset_link(account)
            if link:
                return await service.issue_confirmation_link(account)
            await service.users.mark_email_verified(account.id, datetime.now(UTC))
            return ""
    finally:
        await manager.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line.

    :param argv: Arguments without the program name; defaults to ``sys.argv``.
    :return: Process exit code: 0 on success, 1 when there is no account with that address.
    """
    args = _parser().parse_args(argv)
    outcome = asyncio.run(
        confirm(
            get_settings(),
            args.email.strip().lower(),
            link=args.link,
            reset_link=args.reset_link,
        )
    )
    if outcome is None:
        sys.stderr.write("No account with this address\n")
        return EXIT_NOT_FOUND
    sys.stdout.write(outcome + "\n" if args.link or args.reset_link else "Confirmed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
