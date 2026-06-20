import unittest

from utils.sync_path_filter import (
    filter_trackable_changes,
    is_excluded_sync_path,
    sanitize_text_for_db,
)


class SyncPathFilterTests(unittest.TestCase):
    def test_excludes_fastlane_test_output(self) -> None:
        path = "knowledge-base-app-ios/fastlane/test_output/report.junit"
        self.assertTrue(is_excluded_sync_path(path))

    def test_excludes_xcresult_blob(self) -> None:
        path = (
            "knowledge-base-app-ios/fastlane/test_output/"
            "KnowledgeBaseApp.xcresult/Data/data.0~abc"
        )
        self.assertTrue(is_excluded_sync_path(path))

    def test_excludes_vendor_bundle(self) -> None:
        path = "knowledge-base-app-ios/vendor/bundle/ruby/3.3.0/gems/fastlane-2.233.1/README"
        self.assertTrue(is_excluded_sync_path(path))

    def test_allows_source_swift(self) -> None:
        path = "knowledge-base-app-ios/KnowledgeBaseApp/Views/Files/FileDiffView.swift"
        self.assertFalse(is_excluded_sync_path(path))

    def test_sanitize_strips_null_bytes(self) -> None:
        self.assertEqual(sanitize_text_for_db("hello\x00world"), "helloworld")

    def test_filter_trackable_changes_drops_artifacts(self) -> None:
        changes = [
            {"path": "knowledge-base-app-ios/KnowledgeBaseApp/Models/KBMessage.swift", "type": "modified"},
            {"path": "knowledge-base-app-ios/fastlane/build_logs/foo.log", "type": "modified"},
        ]
        filtered = filter_trackable_changes(changes)
        self.assertEqual(len(filtered), 1)
        self.assertIn("KBMessage.swift", filtered[0]["path"])


if __name__ == "__main__":
    unittest.main()
