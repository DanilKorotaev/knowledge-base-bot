"""Default board rows seeded into the app DB.

Open-source installs ship with an **empty** catalog. Domain-specific boards are
created per instance via MCP / ``PUT /api/boards/{id}`` — never hardcoded here.
Test examples live under ``kb_app_api/tests/fixtures/``.
"""
from __future__ import annotations

from typing import Any

DEFAULT_BOARDS: list[dict[str, Any]] = []
