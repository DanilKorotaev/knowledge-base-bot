from __future__ import annotations

from pathlib import Path

DEFAULT_HEALTH_DATA_RELATIVE = "HealthData"


def normalize_relative_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def validate_health_data_relative(value: str) -> str:
    normalized = normalize_relative_path(value)
    if not normalized:
        raise ValueError("health_data_relative must not be empty")
    parts = normalized.split("/")
    if ".." in parts:
        raise ValueError("path traversal is not allowed")
    if normalized.startswith("/") or ":" in normalized:
        raise ValueError("absolute paths are not allowed")
    return normalized


def validate_health_file_path(value: str) -> str:
    normalized = normalize_relative_path(value)
    if not normalized:
        raise ValueError("file path must not be empty")
    parts = normalized.split("/")
    if ".." in parts:
        raise ValueError("path traversal is not allowed")
    if normalized.startswith("/") or ":" in normalized:
        raise ValueError("absolute paths are not allowed")
    return normalized


def resolve_health_file(local_kb: Path, health_root_relative: str, file_relative: str) -> Path:
    root_rel = validate_health_data_relative(health_root_relative)
    file_rel = validate_health_file_path(file_relative)
    kb_root = local_kb.resolve()
    health_root = (kb_root / root_rel).resolve()
    if health_root != kb_root and kb_root not in health_root.parents:
        raise ValueError("invalid health root")
    if not str(health_root).startswith(str(kb_root)):
        raise ValueError("path traversal is not allowed")
    target = (health_root / file_rel).resolve()
    if target != health_root and health_root not in target.parents:
        raise ValueError("path traversal is not allowed")
    return target


def vault_relative_path(health_root_relative: str, file_relative: str) -> str:
    root_rel = validate_health_data_relative(health_root_relative)
    file_rel = validate_health_file_path(file_relative)
    return f"{root_rel}/{file_rel}"
