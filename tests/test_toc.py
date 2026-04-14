import unittest

from pdf2epub.toc import detect_toc_page, parse_toc_entries


class TocTests(unittest.TestCase):
    def test_parse_toc_entries_with_trailing_page_numbers(self) -> None:
        entries = parse_toc_entries("目次\n特集 AIの現在地 .... 12\n量子計算の基礎 24\n")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].title, "特集 AIの現在地")
        self.assertEqual(entries[0].printed_page, 12)

    def test_detect_toc_page_prefers_keyword_and_entries(self) -> None:
        index, text = detect_toc_page(
            [
                "Newton\n2025 4",
                "目次\n特集 AIの現在地 12\n量子計算の基礎 24",
                "本文ページ",
            ]
        )
        self.assertEqual(index, 1)
        self.assertIn("目次", text)
