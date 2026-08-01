"""Role-based access control helpers."""

from functools import wraps
from typing import Callable, Iterable

from fastapi import Depends, HTTPException, status

from app.auth import UserContext, get_current_user
from config import ROLE_ALIASES, ROLES


def normalize_role(role: str | None) -> str:
    if not role:
        return "engineer"
    r = role.lower().strip()
    return ROLE_ALIASES.get(r, r)


def role_level(role: str | None) -> int:
    r = normalize_role(role)
    try:
        return ROLES.index(r)
    except ValueError:
        return ROLES.index("engineer")


def has_role(user: UserContext, minimum: str) -> bool:
    return role_level(user.role) >= role_level(minimum)


def can_access_team(user: UserContext, team: str | None) -> bool:
    """Admin and team_lead can access any team; others only their own."""
    if not team:
        return True
    if has_role(user, "team_lead"):
        return True
    return (user.team or "").lower() == team.lower()


def require_roles(*allowed: str):
    """Dependency factory: user must have one of the allowed roles (or higher if admin)."""

    def dependency(user: UserContext = Depends(get_current_user)) -> UserContext:
        if has_role(user, "admin"):
            return user
        normalized_allowed = {normalize_role(r) for r in allowed}
        if normalize_role(user.role) not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed)}",
            )
        return user

    return dependency


def require_team_access(team_param: str = "team"):
    """Use as a decorator helper — validates team query param access."""

    def check(user: UserContext, team: str | None) -> None:
        if team and not can_access_team(user, team):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this team's data",
            )

    return check
