"""Shared SQL fragments / column lists for KB App login users + refresh sessions."""

USER_AUTH_COLUMNS = (
    "login",
    "password_hash",
    "email",
    "role",
    "must_change_password",
    "signup_source",
    "nextcloud_username",
    "vault_root_relative",
    "quota_bytes",
    "cursor_isolation",
)

AUTH_USER_SELECT = """
    id, telegram_id, username, is_allowed, is_admin, created_at,
    login, password_hash, email, role, must_change_password, signup_source,
    nextcloud_username, vault_root_relative, quota_bytes, cursor_isolation,
    health_data_relative
"""
