"""Fill an empty database with demo accounts built from the synthetic generator.

Usage, from ``backend/``: ``SEED_PASSWORD=... python -m app.tools.seed [--count N] [--seed S]``.

Every generated profile gets an account with an obviously fake e-mail on the reserved
``example.invalid`` domain and one shared demo password. Accounts and profiles are created
through the same services the API uses, so the consent rule and the location coarsening apply
exactly as they do for a real user. The run is idempotent: an existing e-mail is skipped, so a
second run adds nothing. The tool refuses to run when ``ENV=prod`` unless ``--force-demo`` is
given, because demo accounts with a known password must not appear in a real deployment.
"""

import argparse
import asyncio
import dataclasses
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from app.composition import build_auth_service, build_profile_service
from app.conf.config import Settings, get_settings
from app.core.mail import LogMailSender
from app.database.db import DatabaseSessionManager
from app.domain.account import ProfileDraft, password_meets_policy
from app.domain.errors import ConflictError
from app.domain.profile import ProfileView
from app.synthetic import GeneratorParams, generate_profiles

DEFAULT_COUNT = 200
DEFAULT_SEED = 42
PASSWORD_ENV = "SEED_PASSWORD"  # noqa: S105 - name of the variable, not a secret
# Reserved by RFC 2606: mail to it can never reach a real person.
EMAIL_DOMAIN = "example.invalid"
EXIT_REFUSED = 2


@dataclass(frozen=True, slots=True)
class SeedResult:
    """Outcome of one seeding run.

    :param created: Accounts created by this run.
    :param skipped: Accounts that already existed and were left untouched.
    """

    created: int
    skipped: int


def demo_email(index: int) -> str:
    """Return the fake e-mail address of the demo account at a position.

    :param index: Zero-based position of the profile in the generated population.
    :return: Address such as ``demo-0001@example.invalid``.
    """
    return f"demo-{index + 1:04d}@{EMAIL_DOMAIN}"


def profile_to_draft(profile: ProfileView, index: int) -> ProfileDraft:
    """Turn a generated profile into the submission a user would make.

    The generator already holds grid-cell centres, which the service coarsens to the same
    cell again, so no exact point exists anywhere in this path. Capabilities are submitted
    with consent, and consent is given only when the profile has capabilities to store.

    :param profile: Synthetic profile.
    :param index: Zero-based position, used for the display name.
    :return: Draft ready for ``ProfileService.put_profile``.
    """
    capabilities = tuple(
        sorted(profile.functional.capabilities, key=lambda entry: entry.category.value)
    )
    return ProfileDraft(
        display_name=f"Demo participant {index + 1:04d}",
        district=profile.district,
        intensity=profile.intensity,
        is_visible=profile.is_visible,
        latitude=profile.cell.latitude,
        longitude=profile.cell.longitude,
        sports=tuple(sorted(profile.sports, key=lambda entry: entry.sport.value)),
        capabilities=capabilities,
        functional_data_consent=bool(capabilities),
        contact=None,
    )


async def seed_demo(
    manager: DatabaseSessionManager,
    settings: Settings,
    *,
    count: int,
    seed: int,
    password: str,
) -> SeedResult:
    """Create the demo accounts and profiles that do not exist yet.

    One session and one transaction per account keeps a failure local: a run that is
    interrupted can simply be started again. An account that exists without a profile (an
    earlier run stopped half-way) gets its profile now.

    :param manager: Session manager of the target database; the schema must exist.
    :param settings: Application settings, used for the password hashing cost.
    :param count: Number of demo accounts.
    :param seed: Seed of the generator; the same seed gives the same population.
    :param password: Shared demo password.
    :return: How many accounts were created and how many were skipped.
    """
    params = dataclasses.replace(GeneratorParams(), count=count)
    created = skipped = 0
    for index, profile in enumerate(generate_profiles(params, seed)):
        email = demo_email(index)
        async with manager.session() as session:
            auth = build_auth_service(session, settings, LogMailSender())
            profiles = build_profile_service(session)
            account = await auth.users.get_user_by_email(email)
            if account is not None:
                skipped += 1
            else:
                try:
                    account = await auth.register_confirmed(email, password)
                except ConflictError:
                    # A concurrent run created it between the lookup and the insert.
                    skipped += 1
                    continue
                created += 1
            if await profiles.profiles.get_profile_by_user_id(account.id) is None:
                await profiles.put_profile(account.id, profile_to_draft(profile, index))
    return SeedResult(created=created, skipped=skipped)


def _positive(value: str) -> int:
    """Parse a positive integer for argparse."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog="python -m app.tools.seed", description=__doc__)
    parser.add_argument("--count", type=_positive, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--password",
        default=os.environ.get(PASSWORD_ENV),
        help=f"shared demo password; defaults to ${PASSWORD_ENV} (prefer the variable, "
        "a command line argument is visible to other users of the machine)",
    )
    parser.add_argument(
        "--force-demo",
        action="store_true",
        help="allow running when ENV=prod (demo accounts with a shared password)",
    )
    return parser


async def _run(settings: Settings, count: int, seed: int, password: str) -> SeedResult:
    """Open the database, seed it and close the connection pool."""
    manager = DatabaseSessionManager(settings)
    try:
        return await seed_demo(manager, settings, count=count, seed=seed, password=password)
    finally:
        await manager.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line.

    :param argv: Arguments without the program name; defaults to ``sys.argv``.
    :return: Process exit code: 0 on success, 2 when the run was refused or the password
        is missing or too weak for the policy.
    """
    args = _parser().parse_args(argv)
    settings = get_settings()
    if settings.ENV == "prod" and not args.force_demo:
        sys.stderr.write(
            "Refusing to seed demo data when ENV=prod; pass --force-demo to override\n"
        )
        return EXIT_REFUSED
    if not args.password:
        sys.stderr.write(f"A demo password is required: set {PASSWORD_ENV} or pass --password\n")
        return EXIT_REFUSED
    if not password_meets_policy(args.password):
        sys.stderr.write("The demo password does not meet the password policy\n")
        return EXIT_REFUSED
    result = asyncio.run(_run(settings, args.count, args.seed, args.password))
    sys.stdout.write(f"Demo accounts: {result.created} created, {result.skipped} skipped\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
