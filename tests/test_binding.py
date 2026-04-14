import unittest

from pdf2epub.binding import BindingDirection, resolve_binding


class BindingTests(unittest.TestCase):
    def test_explicit_rtl_wins(self) -> None:
        decision = resolve_binding("rtl", "Some English Book")
        self.assertEqual(decision.direction, BindingDirection.RTL)

    def test_japanese_filename_defaults_to_rtl(self) -> None:
        decision = resolve_binding("auto", "宇宙兄弟 第42巻")
        self.assertEqual(decision.direction, BindingDirection.RTL)

    def test_english_filename_defaults_to_ltr(self) -> None:
        decision = resolve_binding("auto", "Sample English Magazine Issue 12")
        self.assertEqual(decision.direction, BindingDirection.LTR)

    def test_image_only_japanese_scan_defaults_to_rtl(self) -> None:
        decision = resolve_binding(
            "auto",
            "20260315135121",
            [],
            language_hint="ja",
            pdf_creator="PFU ScanSnap Home",
            image_only=True,
        )
        self.assertEqual(decision.direction, BindingDirection.RTL)
