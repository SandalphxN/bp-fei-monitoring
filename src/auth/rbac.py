from __future__ import annotations
from typing import Dict, Any, Set

ROLE_TEACHER = "teacher"
ROLE_ADMIN = "admin"

ALL_ROLES = {ROLE_TEACHER, ROLE_ADMIN}


def resolve_role(username: str, settings: Dict[str, Any]) -> str:
    auth = settings.get("auth", {}) if isinstance(settings, dict) else {}

    admins: Set[str] = set(auth.get("admin_users", []) or [])
    teachers: Set[str] = set(auth.get("teacher_users", []) or [])

    if username in admins:
        return ROLE_ADMIN
    if username in teachers:
        return ROLE_TEACHER

    local_users = auth.get("local_users", {}) if isinstance(auth, dict) else {}
    if isinstance(local_users, dict) and username in local_users:
        role = (local_users.get(username) or {}).get("role", ROLE_TEACHER)
        if role in ALL_ROLES:
            return role

    return ROLE_TEACHER


def can_upload(role: str) -> bool:
    return role == ROLE_ADMIN


def can_manage_datasets(role: str) -> bool:
    return role == ROLE_ADMIN


def can_full_filters(role: str) -> bool:
    return role in (ROLE_TEACHER, ROLE_ADMIN)


def can_export(role: str) -> bool:
    return role in (ROLE_TEACHER, ROLE_ADMIN)