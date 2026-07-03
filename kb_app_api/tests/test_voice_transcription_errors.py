import unittest

from kb_app_api.voice_errors import transcription_user_message


class TestTranscriptionUserMessage(unittest.TestCase):
    def test_timeout_message(self) -> None:
        msg = transcription_user_message(TimeoutError("Request timed out"))
        self.assertIn("Таймаут", msg)
        self.assertIn("VPN", msg)

    def test_connection_message(self) -> None:
        msg = transcription_user_message(ConnectionError("Connection error"))
        self.assertIn("соединения", msg.lower())

    def test_generic_message(self) -> None:
        msg = transcription_user_message(RuntimeError("boom"))
        self.assertIn("Ошибка распознавания", msg)
