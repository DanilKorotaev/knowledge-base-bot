from __future__ import annotations


def transcription_user_message(exc: Exception) -> str:
    """Neutral English fallback for API ``message`` (client should prefer L10n by code)."""
    detail = str(exc).lower()
    if "timeout" in detail or "timed out" in detail:
        return "Speech recognition timed out. Please try again."
    if "connection" in detail or "connect" in detail:
        return "Could not reach the speech recognition service. Please try again."
    return "Speech recognition failed. Please try again."
