"""Persistence helpers for ingress (sqlite + postgres)."""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from database.postgresql_db import PostgreSQLDatabase
from database.sqlite_db import SQLiteDatabase
from utils.db_helpers import get_db

from kb_app_api.ingress.schema import ensure_ingress_schema


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(raw: Any, default: Any = None) -> Any:
    if raw is None or raw == "":
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_ingress_token_plaintext() -> str:
    # URL-safe; enough entropy for bearer-in-path use.
    return secrets.token_urlsafe(32)


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return str(value).lower() in ("1", "true", "yes")


def _token_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": int(row["user_id"]),
        "token_prefix": str(row.get("token_prefix") or ""),
        "label": str(row.get("label") or ""),
        "description": str(row.get("description") or ""),
        "channel_id": str(row.get("channel_id") or "default"),
        "adapter_key": row.get("adapter_key"),
        "allowed_sources": _loads(row.get("allowed_sources_json"), None),
        "allow_enqueue_agent": _boolish(row.get("allow_enqueue_agent")),
        "allow_script": _boolish(row.get("allow_script")),
        "agent_runtime": str(row.get("agent_runtime") or "none"),
        "agent_prompt_profile": str(row.get("agent_prompt_profile") or "untrusted_ingress"),
        "created_at": row.get("created_at"),
        "revoked_at": row.get("revoked_at"),
    }


def _adapter_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": int(row["user_id"]),
        "key": str(row["key"]),
        "label": str(row.get("label") or row["key"]),
        "participant_key": str(row.get("participant_key") or row["key"]),
        "avatar_asset_id": row.get("avatar_asset_id"),
        "config": _loads(row.get("config_json"), {}),
        "created_at": row.get("created_at"),
    }


def _rule_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": int(row["user_id"]),
        "priority": int(row.get("priority") or 100),
        "enabled": _boolish(row.get("enabled")),
        "match": _loads(row.get("match_json"), {}),
        "extract": _loads(row.get("extract_json"), {}),
        "action": _loads(row.get("action_json"), {}),
        "label": str(row.get("label") or ""),
        "created_at": row.get("created_at"),
    }


def _event_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": int(row["user_id"]),
        "token_id": row.get("token_id"),
        "channel_id": str(row.get("channel_id") or "default"),
        "adapter_key": row.get("adapter_key"),
        "source": str(row.get("source") or ""),
        "type": str(row.get("event_type") or ""),
        "summary": str(row.get("summary") or ""),
        "dedupe_key": row.get("dedupe_key"),
        "status": str(row.get("status") or "received"),
        "envelope": _loads(row.get("envelope_json"), {}),
        "result": _loads(row.get("result_json"), None),
        "error_message": row.get("error_message"),
        "created_at": row.get("created_at"),
    }


async def create_token(
    *,
    user_id: int,
    label: str = "",
    description: str = "",
    channel_id: str = "default",
    adapter_key: str | None = None,
    allowed_sources: list[str] | None = None,
    allow_enqueue_agent: bool = False,
    allow_script: bool = False,
    agent_runtime: str = "none",
    agent_prompt_profile: str = "untrusted_ingress",
) -> tuple[dict[str, Any], str]:
    await ensure_ingress_schema()
    plaintext = new_ingress_token_plaintext()
    token_id = str(uuid.uuid4())
    prefix = plaintext[:8]
    runtime = agent_runtime if agent_runtime in ("none", "container", "host") else "none"
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO ingress_tokens (
                    id, user_id, token_hash, token_prefix, label, description, channel_id, adapter_key,
                    allowed_sources_json, allow_enqueue_agent, allow_script,
                    agent_runtime, agent_prompt_profile
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    user_id,
                    hash_token(plaintext),
                    prefix,
                    label,
                    description or "",
                    channel_id or "default",
                    adapter_key,
                    _dumps(allowed_sources) if allowed_sources is not None else None,
                    1 if allow_enqueue_agent else 0,
                    1 if allow_script else 0,
                    runtime,
                    agent_prompt_profile or "untrusted_ingress",
                ),
            )
            await conn.commit()
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM ingress_tokens WHERE id = ?", (token_id,))
            row = dict(await cur.fetchone())
    else:
        assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
        async with db.pool.acquire() as conn:
            row = dict(
                await conn.fetchrow(
                    """
                    INSERT INTO ingress_tokens (
                        id, user_id, token_hash, token_prefix, label, description, channel_id, adapter_key,
                        allowed_sources_json, allow_enqueue_agent, allow_script,
                        agent_runtime, agent_prompt_profile
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    RETURNING *
                    """,
                    token_id,
                    user_id,
                    hash_token(plaintext),
                    prefix,
                    label,
                    description or "",
                    channel_id or "default",
                    adapter_key,
                    _dumps(allowed_sources) if allowed_sources is not None else None,
                    allow_enqueue_agent,
                    allow_script,
                    runtime,
                    agent_prompt_profile or "untrusted_ingress",
                )
            )
    return _token_row(row), plaintext


async def list_tokens(user_id: int) -> list[dict[str, Any]]:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """
                SELECT * FROM ingress_tokens
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = [dict(r) for r in await cur.fetchall()]
    else:
        assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
        async with db.pool.acquire() as conn:
            rows = [dict(r) for r in await conn.fetch(
                "SELECT * FROM ingress_tokens WHERE user_id=$1 ORDER BY created_at DESC",
                user_id,
            )]
    return [_token_row(r) for r in rows]


async def revoke_token(*, user_id: int, token_id: str) -> bool:
    await ensure_ingress_schema()
    now = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            cur = await conn.execute(
                """
                UPDATE ingress_tokens SET revoked_at = ?
                WHERE id = ? AND user_id = ? AND revoked_at IS NULL
                """,
                (now, token_id, user_id),
            )
            await conn.commit()
            return cur.rowcount > 0
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE ingress_tokens SET revoked_at = NOW()
            WHERE id = $1 AND user_id = $2 AND revoked_at IS NULL
            """,
            token_id,
            user_id,
        )
        return result != "UPDATE 0"


async def resolve_token(plaintext: str) -> dict[str, Any] | None:
    await ensure_ingress_schema()
    digest = hash_token(plaintext)
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM ingress_tokens WHERE token_hash = ? LIMIT 1",
                (digest,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            data = dict(row)
    else:
        assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM ingress_tokens WHERE token_hash = $1 LIMIT 1",
                digest,
            )
            if not row:
                return None
            data = dict(row)
    if data.get("revoked_at"):
        return None
    return _token_row(data)


async def upsert_adapter(
    *,
    user_id: int,
    key: str,
    label: str,
    participant_key: str | None = None,
    avatar_asset_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await ensure_ingress_schema()
    key = key.strip()
    if not key:
        raise ValueError("adapter key required")
    participant = (participant_key or key).strip()
    adapter_id = str(uuid.uuid4())
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            existing = await (
                await conn.execute(
                    "SELECT id FROM ingress_adapters WHERE user_id=? AND key=?",
                    (user_id, key),
                )
            ).fetchone()
            if existing:
                await conn.execute(
                    """
                    UPDATE ingress_adapters
                    SET label=?, participant_key=?, avatar_asset_id=?, config_json=?
                    WHERE user_id=? AND key=?
                    """,
                    (
                        label or key,
                        participant,
                        avatar_asset_id,
                        _dumps(config or {}),
                        user_id,
                        key,
                    ),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO ingress_adapters (
                        id, user_id, key, label, participant_key, avatar_asset_id, config_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        adapter_id,
                        user_id,
                        key,
                        label or key,
                        participant,
                        avatar_asset_id,
                        _dumps(config or {}),
                    ),
                )
            await conn.commit()
            cur = await conn.execute(
                "SELECT * FROM ingress_adapters WHERE user_id=? AND key=?",
                (user_id, key),
            )
            return _adapter_row(dict(await cur.fetchone()))
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ingress_adapters (
                id, user_id, key, label, participant_key, avatar_asset_id, config_json
            ) VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (user_id, key) DO UPDATE SET
                label = EXCLUDED.label,
                participant_key = EXCLUDED.participant_key,
                avatar_asset_id = COALESCE(EXCLUDED.avatar_asset_id, ingress_adapters.avatar_asset_id),
                config_json = EXCLUDED.config_json
            RETURNING *
            """,
            adapter_id,
            user_id,
            key,
            label or key,
            participant,
            avatar_asset_id,
            _dumps(config or {}),
        )
        return _adapter_row(dict(row))


async def list_adapters(user_id: int) -> list[dict[str, Any]]:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM ingress_adapters WHERE user_id=? ORDER BY key",
                (user_id,),
            )
            return [_adapter_row(dict(r)) for r in await cur.fetchall()]
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM ingress_adapters WHERE user_id=$1 ORDER BY key",
            user_id,
        )
        return [_adapter_row(dict(r)) for r in rows]


async def get_adapter(user_id: int, key: str) -> dict[str, Any] | None:
    for item in await list_adapters(user_id):
        if item["key"] == key:
            return item
    return None


async def delete_adapter(*, user_id: int, key: str) -> bool:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            cur = await conn.execute(
                "DELETE FROM ingress_adapters WHERE user_id=? AND key=?",
                (user_id, key),
            )
            await conn.commit()
            return cur.rowcount > 0
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM ingress_adapters WHERE user_id=$1 AND key=$2",
            user_id,
            key,
        )
        return result != "DELETE 0"


async def upsert_binding(*, user_id: int, binding_key: str, session_id: int) -> None:
    await ensure_ingress_schema()
    key = binding_key.strip()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO ingress_session_bindings (user_id, binding_key, session_id)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, binding_key) DO UPDATE SET
                    session_id=excluded.session_id,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (user_id, key, session_id),
            )
            await conn.commit()
        return
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ingress_session_bindings (user_id, binding_key, session_id)
            VALUES ($1,$2,$3)
            ON CONFLICT (user_id, binding_key) DO UPDATE SET
                session_id = EXCLUDED.session_id,
                updated_at = NOW()
            """,
            user_id,
            key,
            session_id,
        )


async def list_bindings(user_id: int) -> list[dict[str, Any]]:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM ingress_session_bindings WHERE user_id=? ORDER BY binding_key",
                (user_id,),
            )
            return [
                {
                    "binding_key": str(r["binding_key"]),
                    "session_id": int(r["session_id"]),
                    "updated_at": r["updated_at"],
                }
                for r in await cur.fetchall()
            ]
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM ingress_session_bindings WHERE user_id=$1 ORDER BY binding_key",
            user_id,
        )
        return [
            {
                "binding_key": str(r["binding_key"]),
                "session_id": int(r["session_id"]),
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]


async def resolve_binding(user_id: int, binding_key: str) -> int | None:
    for item in await list_bindings(user_id):
        if item["binding_key"] == binding_key:
            return int(item["session_id"])
    return None


async def create_rule(
    *,
    user_id: int,
    match: dict[str, Any],
    action: dict[str, Any],
    extract: dict[str, Any] | None = None,
    priority: int = 100,
    label: str = "",
    enabled: bool = True,
) -> dict[str, Any]:
    await ensure_ingress_schema()
    rule_id = str(uuid.uuid4())
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO ingress_rules (
                    id, user_id, priority, enabled, match_json, extract_json, action_json, label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule_id,
                    user_id,
                    priority,
                    1 if enabled else 0,
                    _dumps(match or {}),
                    _dumps(extract or {}),
                    _dumps(action or {}),
                    label,
                ),
            )
            await conn.commit()
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM ingress_rules WHERE id=?", (rule_id,))
            return _rule_row(dict(await cur.fetchone()))
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ingress_rules (
                id, user_id, priority, enabled, match_json, extract_json, action_json, label
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            RETURNING *
            """,
            rule_id,
            user_id,
            priority,
            enabled,
            _dumps(match or {}),
            _dumps(extract or {}),
            _dumps(action or {}),
            label,
        )
        return _rule_row(dict(row))


async def list_rules(user_id: int) -> list[dict[str, Any]]:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """
                SELECT * FROM ingress_rules
                WHERE user_id=?
                ORDER BY priority ASC, created_at ASC
                """,
                (user_id,),
            )
            return [_rule_row(dict(r)) for r in await cur.fetchall()]
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM ingress_rules
            WHERE user_id=$1
            ORDER BY priority ASC, created_at ASC
            """,
            user_id,
        )
        return [_rule_row(dict(r)) for r in rows]


async def set_rule_enabled(*, user_id: int, rule_id: str, enabled: bool) -> bool:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            cur = await conn.execute(
                "UPDATE ingress_rules SET enabled=? WHERE id=? AND user_id=?",
                (1 if enabled else 0, rule_id, user_id),
            )
            await conn.commit()
            return cur.rowcount > 0
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE ingress_rules SET enabled=$1 WHERE id=$2 AND user_id=$3",
            enabled,
            rule_id,
            user_id,
        )
        return result != "UPDATE 0"


async def delete_rule(*, user_id: int, rule_id: str) -> bool:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            cur = await conn.execute(
                "DELETE FROM ingress_rules WHERE id=? AND user_id=?",
                (rule_id, user_id),
            )
            await conn.commit()
            return cur.rowcount > 0
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM ingress_rules WHERE id=$1 AND user_id=$2",
            rule_id,
            user_id,
        )
        return result != "DELETE 0"


async def insert_event(
    *,
    user_id: int,
    token_id: str | None,
    channel_id: str,
    adapter_key: str | None,
    source: str,
    event_type: str,
    summary: str,
    dedupe_key: str | None,
    envelope: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Returns (event, created). created=False when dedupe hit."""
    await ensure_ingress_schema()
    event_id = str(uuid.uuid4())
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if dedupe_key:
                existing = await (
                    await conn.execute(
                        "SELECT * FROM ingress_events WHERE user_id=? AND dedupe_key=?",
                        (user_id, dedupe_key),
                    )
                ).fetchone()
                if existing:
                    return _event_row(dict(existing)), False
            try:
                await conn.execute(
                    """
                    INSERT INTO ingress_events (
                        id, user_id, token_id, channel_id, adapter_key,
                        source, event_type, summary, dedupe_key, status, envelope_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'received', ?)
                    """,
                    (
                        event_id,
                        user_id,
                        token_id,
                        channel_id,
                        adapter_key,
                        source,
                        event_type,
                        summary,
                        dedupe_key,
                        _dumps(envelope),
                    ),
                )
                await conn.commit()
            except Exception:
                if dedupe_key:
                    existing = await (
                        await conn.execute(
                            "SELECT * FROM ingress_events WHERE user_id=? AND dedupe_key=?",
                            (user_id, dedupe_key),
                        )
                    ).fetchone()
                    if existing:
                        return _event_row(dict(existing)), False
                raise
            cur = await conn.execute("SELECT * FROM ingress_events WHERE id=?", (event_id,))
            return _event_row(dict(await cur.fetchone())), True
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        if dedupe_key:
            existing = await conn.fetchrow(
                "SELECT * FROM ingress_events WHERE user_id=$1 AND dedupe_key=$2",
                user_id,
                dedupe_key,
            )
            if existing:
                return _event_row(dict(existing)), False
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO ingress_events (
                    id, user_id, token_id, channel_id, adapter_key,
                    source, event_type, summary, dedupe_key, status, envelope_json
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'received',$10)
                RETURNING *
                """,
                event_id,
                user_id,
                token_id,
                channel_id,
                adapter_key,
                source,
                event_type,
                summary,
                dedupe_key,
                _dumps(envelope),
            )
            return _event_row(dict(row)), True
        except Exception:
            if dedupe_key:
                existing = await conn.fetchrow(
                    "SELECT * FROM ingress_events WHERE user_id=$1 AND dedupe_key=$2",
                    user_id,
                    dedupe_key,
                )
                if existing:
                    return _event_row(dict(existing)), False
            raise


async def get_event(event_id: str) -> dict[str, Any] | None:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM ingress_events WHERE id=? LIMIT 1",
                (event_id,),
            )
            row = await cur.fetchone()
            return _event_row(dict(row)) if row else None
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM ingress_events WHERE id=$1 LIMIT 1",
            event_id,
        )
        return _event_row(dict(row)) if row else None


async def update_event_status(
    event_id: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                """
                UPDATE ingress_events
                SET status=?, result_json=?, error_message=?
                WHERE id=?
                """,
                (
                    status,
                    _dumps(result) if result is not None else None,
                    error_message,
                    event_id,
                ),
            )
            await conn.commit()
        return
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE ingress_events
            SET status=$1, result_json=$2, error_message=$3
            WHERE id=$4
            """,
            status,
            _dumps(result) if result is not None else None,
            error_message,
            event_id,
        )


async def list_events(user_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
    await ensure_ingress_schema()
    limit = max(1, min(limit, 200))
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """
                SELECT * FROM ingress_events
                WHERE user_id=?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            return [_event_row(dict(r)) for r in await cur.fetchall()]
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM ingress_events
            WHERE user_id=$1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
        return [_event_row(dict(r)) for r in rows]


async def upsert_script(
    *,
    user_id: int,
    key: str,
    label: str = "",
    command: dict[str, Any] | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    await ensure_ingress_schema()
    key = key.strip()
    script_id = str(uuid.uuid4())
    db = await get_db()
    payload = {
        "id": script_id,
        "user_id": user_id,
        "key": key,
        "label": label or key,
        "command": command or {},
        "enabled": enabled,
    }
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO ingress_scripts (id, user_id, key, label, command_json, enabled)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET
                    label=excluded.label,
                    command_json=excluded.command_json,
                    enabled=excluded.enabled
                """,
                (
                    script_id,
                    user_id,
                    key,
                    label or key,
                    _dumps(command or {}),
                    1 if enabled else 0,
                ),
            )
            await conn.commit()
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM ingress_scripts WHERE user_id=? AND key=?",
                (user_id, key),
            )
            row = dict(await cur.fetchone())
            return {
                "id": str(row["id"]),
                "key": str(row["key"]),
                "label": str(row["label"] or ""),
                "command": _loads(row["command_json"], {}),
                "enabled": _boolish(row["enabled"]),
            }
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ingress_scripts (id, user_id, key, label, command_json, enabled)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT (user_id, key) DO UPDATE SET
                label = EXCLUDED.label,
                command_json = EXCLUDED.command_json,
                enabled = EXCLUDED.enabled
            RETURNING *
            """,
            script_id,
            user_id,
            key,
            label or key,
            _dumps(command or {}),
            enabled,
        )
        return {
            "id": str(row["id"]),
            "key": str(row["key"]),
            "label": str(row["label"] or ""),
            "command": _loads(row["command_json"], {}),
            "enabled": _boolish(row["enabled"]),
        }


async def get_script(user_id: int, key: str) -> dict[str, Any] | None:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM ingress_scripts WHERE user_id=? AND key=?",
                (user_id, key),
            )
            row = await cur.fetchone()
            if not row:
                return None
            data = dict(row)
    else:
        assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM ingress_scripts WHERE user_id=$1 AND key=$2",
                user_id,
                key,
            )
            if not row:
                return None
            data = dict(row)
    return {
        "id": str(data["id"]),
        "key": str(data["key"]),
        "label": str(data.get("label") or ""),
        "command": _loads(data.get("command_json"), {}),
        "enabled": _boolish(data.get("enabled")),
    }


def avatar_storage_dir() -> "Path":
    """Directory for avatar blobs next to the DB file (no vault paths)."""
    from pathlib import Path

    from config import config

    if config.DB_FILE:
        base = Path(config.DB_FILE).expanduser().resolve().parent
    else:
        import os

        base = Path(os.environ.get("KB_APP_DATA_DIR") or "/var/tmp/kb-app-data").resolve()
    path = base / "ingress_avatars"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def upsert_avatar_asset(
    *,
    user_id: int,
    participant_key: str,
    content_type: str,
    file_name: str,
    data: bytes,
) -> dict[str, Any]:
    await ensure_ingress_schema()
    if not data:
        raise ValueError("empty avatar")
    if len(data) > 512_000:
        raise ValueError("avatar too large (max 512KB)")
    key = participant_key.strip() or "default"
    ct = (content_type or "image/png").split(";")[0].strip().lower() or "image/png"
    if not ct.startswith("image/"):
        raise ValueError("avatar must be an image/* content type")
    asset_id = str(uuid.uuid4())
    dest = avatar_storage_dir() / asset_id
    dest.write_bytes(data)

    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT id FROM ingress_avatar_assets WHERE user_id=? AND participant_key=?",
                (user_id, key),
            )
            existing = await cur.fetchone()
            if existing:
                old_id = str(existing["id"])
                old_path = avatar_storage_dir() / old_id
                if old_path.is_file() and old_id != asset_id:
                    try:
                        old_path.unlink()
                    except OSError:
                        pass
                await conn.execute(
                    """
                    UPDATE ingress_avatar_assets
                    SET id=?, content_type=?, file_name=?
                    WHERE user_id=? AND participant_key=?
                    """,
                    (asset_id, ct, file_name or f"{key}.bin", user_id, key),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO ingress_avatar_assets
                        (id, user_id, participant_key, content_type, file_name)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (asset_id, user_id, key, ct, file_name or f"{key}.bin"),
                )
            await conn.commit()
            cur = await conn.execute(
                "SELECT * FROM ingress_avatar_assets WHERE id=?",
                (asset_id,),
            )
            row = dict(await cur.fetchone())
    else:
        assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
        async with db.pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM ingress_avatar_assets WHERE user_id=$1 AND participant_key=$2",
                user_id,
                key,
            )
            if existing:
                old_id = str(existing["id"])
                old_path = avatar_storage_dir() / old_id
                if old_path.is_file() and old_id != asset_id:
                    try:
                        old_path.unlink()
                    except OSError:
                        pass
                await conn.execute(
                    """
                    UPDATE ingress_avatar_assets
                    SET id=$1, content_type=$2, file_name=$3
                    WHERE user_id=$4 AND participant_key=$5
                    """,
                    asset_id,
                    ct,
                    file_name or f"{key}.bin",
                    user_id,
                    key,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO ingress_avatar_assets
                        (id, user_id, participant_key, content_type, file_name)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    asset_id,
                    user_id,
                    key,
                    ct,
                    file_name or f"{key}.bin",
                )
            row = dict(
                await conn.fetchrow(
                    "SELECT * FROM ingress_avatar_assets WHERE id=$1",
                    asset_id,
                )
            )
    return {
        "id": str(row["id"]),
        "participant_key": str(row["participant_key"]),
        "content_type": str(row["content_type"]),
        "file_name": str(row["file_name"]),
        "avatar_path": f"/api/ingress/avatars/{row['id']}",
    }


async def get_avatar_asset(asset_id: str) -> dict[str, Any] | None:
    await ensure_ingress_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM ingress_avatar_assets WHERE id=?",
                (asset_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            data = dict(row)
    else:
        assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM ingress_avatar_assets WHERE id=$1",
                asset_id,
            )
            if not row:
                return None
            data = dict(row)
    path = avatar_storage_dir() / str(data["id"])
    if not path.is_file():
        return None
    return {
        "id": str(data["id"]),
        "user_id": int(data["user_id"]),
        "participant_key": str(data["participant_key"]),
        "content_type": str(data["content_type"]),
        "file_name": str(data["file_name"]),
        "path": path,
    }
