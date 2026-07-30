from app.db.models import User

WILDCARD_PERMISSION_TAG = "*"
ADMIN_ROLE_NAME = "admin"


def compute_user_permission_tags(user: User) -> list[str]:
    """合并用户所有角色的 permission_tags 并去重。"""
    merged: set[str] = set()
    for role in user.roles:
        for tag in role.permission_tags:
            if tag == WILDCARD_PERMISSION_TAG:
                return [WILDCARD_PERMISSION_TAG]
            merged.add(tag)
    return sorted(merged)


def is_admin(user: User) -> bool:
    """是否持有 admin 角色。"""
    return any(role.name == ADMIN_ROLE_NAME for role in user.roles)
