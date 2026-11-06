"""Per-user event ingress: tokens, adapters, rules, delivery into sessions."""

from __future__ import annotations

from kb_app_api.ingress.schema import ensure_ingress_schema

__all__ = ["ensure_ingress_schema"]
