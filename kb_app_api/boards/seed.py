"""Board seed for fresh installs.

Open-source installs ship with an **empty** catalog. Domain boards (fuel, workouts,
demos) are created via MCP / ``PUT /api/boards/{id}`` — never hardcoded here.
Test fixtures live under ``kb_app_api/tests/fixtures/``.
"""
from __future__ import annotations

from typing import Any

DEFAULT_BOARDS: list[dict[str, Any]] = []
