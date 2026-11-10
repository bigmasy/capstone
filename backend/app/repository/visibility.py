"""Who can be found: the one definition shared by the feed, public profiles and invitations."""

from sqlalchemy import ColumnElement, and_, select

from app.database.models import Profile, User


def discoverable() -> ColumnElement[bool]:
    """Condition for a profile that other people may see and invite.

    The owner has to want it (``is_visible``) and to have confirmed the e-mail address. A
    profile of an unconfirmed account is treated exactly like a hidden one, so nothing tells
    the two apart.

    :return: SQL condition over ``profiles``.
    """
    confirmed_owners = select(User.id).where(User.email_verified_at.is_not(None))
    return and_(Profile.is_visible.is_(True), Profile.user_id.in_(confirmed_owners))
