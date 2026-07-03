from __future__ import annotations


def transcription_user_message(exc: Exception) -> str:
    detail = str(exc).lower()
    if "timeout" in detail or "timed out" in detail:
        return (
            "Таймаут при распознавании речи. Проверьте VPN и интернет на сервере "
            "и повторите отправку с устройства."
        )
    if "connection" in detail or "connect" in detail:
        return (
            "Нет соединения с OpenAI (Whisper). Проверьте VPN/прокси на сервере "
            "и повторите отправку."
        )
    return "Ошибка распознавания речи. Повторите отправку голосового с устройства."
